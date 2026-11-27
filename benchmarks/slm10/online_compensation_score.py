"""Score sealed P0-B output captures offline against separately authored answers."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from math import ceil, isfinite
from pathlib import Path

from audit import write_evidence
from benchmarks.root_cause.generation_capture import correlate, protocol_reply
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import canonical, fingerprint
from model_gateway import GatewayError
from model_gateway.strict_json import strict_object

from . import online_compensation as run


EXPECTED = {
    "P0B-O01": ("BX-81", 17), "P0B-O02": ("CS-24", 6), "P0B-O03": ("VT-00", 0),
    "P0B-O04": ("AH-23", 12), "P0B-O05": ("SL-05", 40), "P0B-O06": ("ZK-16", 45),
    "P0B-O07": (None, None), "P0B-O08": (None, None), "P0B-O09": (None, None),
    "P0B-O10": ("MX-20", 8), "P0B-O11": (None, None), "P0B-O12": ("BC-83", 72),
}
METRICS = ("schema", "facts", "uncertainty", "usable", "terminal", "no_tool_proposal", "no_extra_fields")
OUTCOMES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")


def verdict(value):
    return "PASS" if value else "FAIL"


def assess(trial, expected):
    attempts = trial["attempts"]
    events = [event for attempt in attempts for event in attempt["wire"]]
    providers = [event for event in events if event.get("provider_request_id")]
    if (not providers or any(event.get("response_capture_complete") is not True for event in providers)
            or any(event.get("http_status") == 200 and event.get("native_evidence", {}).get("status") != "PASS"
                   for event in providers)):
        return dict.fromkeys(METRICS, "BLOCKED")
    if len(providers) != len(attempts) or len(providers) != len(events):
        return dict.fromkeys(METRICS, "FAIL")
    answer = trial["delivered"]
    valid_terminal = run.terminal(attempts[-1]) and answer is not None
    shape = valid_terminal and run.contract(answer)
    try:
        value = strict_object(run.extract_object(answer, terminal_allowed=True) or answer) if valid_terminal else {}
    except GatewayError:
        value = {}
    facts = all(key in value and type(value[key]) is type(want) and value[key] == want
                for key, want in expected.items())
    uncertainty = value.get("state") == expected["state"] and (
        expected["state"] == "found" or all(key in value and value[key] is None for key in ("reference", "units")))
    tool_attestations = [event.get("parsed_response") for event in providers]
    no_calls = "BLOCKED" if any(not choices for choices in tool_attestations) else verdict(
        all(not choice.get("message", {}).get("tool_calls")
            for choices in tool_attestations for choice in choices))
    no_extras = bool(value) and not (value.keys() - expected.keys())
    return {"schema": verdict(shape), "facts": verdict(facts), "uncertainty": verdict(uncertainty),
            "usable": verdict(shape and facts and no_calls == "PASS"), "terminal": verdict(valid_terminal),
            "no_tool_proposal": no_calls, "no_extra_fields": verdict(no_extras)}


def total(values):
    return (sum(values) if values and all(type(v) in (int, float) and isfinite(v) and v >= 0 for v in values)
            else None)


def resources(trial):
    attempts = trial["attempts"]
    providers = [event for attempt in attempts for event in attempt["wire"] if "provider_request_id" in event]

    def metric(section, key):
        return total([(event.get(section) or {}).get(key) for event in providers])

    return {"provider_requests": len(providers), "sdk_sessions": len(attempts),
            "sdk_wall_ms": total([attempt.get("sdk_wall_ms") for attempt in attempts]),
            "trial_wall_ms": trial.get("trial_wall_ms"), "host_normalization_ms": trial.get("host_normalization_ms"),
            "provider_boundary_wall_ms": total([event.get("wall_ms") for event in providers]),
            "prompt_tokens": metric("usage", "prompt_tokens"), "completion_tokens": metric("usage", "completion_tokens"),
            "native_prompt_ms": metric("timings", "prompt_ms"), "native_decode_ms": metric("timings", "predicted_ms")}


def quantiles(values):
    known = sorted(value for value in values if value is not None)
    return {"observed": len(known), "missing": len(values) - len(known),
            "p50": known[ceil(len(known) * 0.50) - 1] if known else None,
            "p95": known[ceil(len(known) * 0.95) - 1] if known else None}


def replay(metadata, captures, reserved=()):
    if metadata.get("plan") != run.plan() or metadata.get("candidate") not in run.CANDIDATES:
        raise ValueError("capture preregistration differs from the registered plan")
    if set(EXPECTED) != run.PUBLIC.keys():
        raise ValueError("offline references do not cover the registered public cohort")
    by_id = {row["trial_id"]: row for row in captures}
    if len(by_id) != len(captures):
        raise ValueError("capture includes duplicate trial identities")
    rows, matched = [], {}
    for spec in run.schedule():
        case = spec["case_id"]
        trial_id = fingerprint([metadata["run_id"], spec])
        trial = by_id.pop(trial_id, None)
        row = spec | {"trial_id": trial_id, "resources": {}}
        reference, units = EXPECTED[case]
        expected = {"reference": reference, "units": units, "state": "unknown" if reference is None else "found"}
        if trial is None:
            row["metrics"] = dict.fromkeys(METRICS, "BLOCKED" if trial_id in reserved else "NOT_RUN")
        elif metadata["gpu_execution"] != "PASS":
            row["metrics"] = dict.fromkeys(METRICS, "BLOCKED")
            row["resources"] = resources(trial)
        else:
            row["metrics"] = assess(trial, expected)
            row["resources"] = resources(trial)
        rows.append(row)
        matched[case, spec["seed"], spec["arm"]] = row
    if by_id:
        raise ValueError("capture includes unregistered trial identities")

    summaries, paired = {}, {}
    for arm in run.ARMS:
        selection = [row for row in rows if row["arm"] == arm]
        keys = sorted({key for row in selection for key in row["resources"]})
        summaries[arm] = {
            key: {outcome: sum(row["metrics"][key] == outcome for row in selection) for outcome in OUTCOMES}
            for key in METRICS
        } | {"resources": {key: quantiles([row["resources"].get(key) for row in selection]) for key in keys}}
        if arm == "MODEL_NATIVE":
            continue
        comparisons = [(matched[row["case_id"], row["seed"], "MODEL_NATIVE"], row) for row in selection]
        discordance = {key: Counter(f'{base["metrics"][key]}->{test["metrics"][key]}' for base, test in comparisons)
                       for key in METRICS}
        deltas = {}
        for key in keys:
            values = [(base["resources"].get(key), test["resources"].get(key)) for base, test in comparisons]
            deltas[key] = quantiles([test - base if base is not None and test is not None else None
                                     for base, test in values])
        paired[arm] = {"transitions": discordance, "resource_deltas": deltas}
    coverage = [row["metrics"]["usable"] for row in rows]
    physical = ("NOT_RUN" if set(coverage) == {"NOT_RUN"} else metadata["gpu_execution"]
                if metadata["gpu_execution"] == "FAIL" else
                "BLOCKED" if any(outcome in {"NOT_RUN", "BLOCKED"} for outcome in coverage) else "PASS")
    return {"version": run.VERSION, "candidate": metadata["candidate"], "run_id": metadata["run_id"],
            "public_sha256": metadata["plan"]["public_sha256"], "oracle_sha256": fingerprint(EXPECTED),
            "physical": physical, "formal_trial_attribution": 0, "arms": summaries, "paired_against_original": paired,
            "rows": rows}


def verified_attempt(attempt, trial_id, spec, profile, candidate, native_records=None):
    if attempt["profile"] != profile:
        raise ValueError("attempt used a different treatment")
    alias = "ijslm-candidate-" + candidate.lower()
    for event in attempt["wire"]:
        if event["trial_id"] != trial_id:
            raise ValueError("SDK boundary lost its trial identity")
        if not event.get("provider_request_id"):
            continue
        request = event["provider_request"].encode()
        prompt = run.PUBLIC[spec["case_id"]][1]
        if (sha256(request).hexdigest() != event["provider_request_sha256"]
                or request != canonical(run.request_body(json.loads(event["request"]), alias, spec["seed"], profile, prompt))):
            raise ValueError("provider request differs from the registered treatment")
        if event.get("response_capture_complete") is True:
            response = (bytes.fromhex(event["private_response_hex"]) if "private_response_hex" in event
                        else event["response"].encode())
            if sha256(response).hexdigest() != event["response_sha256"] or len(response) != event["response_bytes"]:
                raise ValueError("raw provider response differs from its checksum")
            if event.get("parsed_response"):
                reply = protocol_reply(response, True)
                expected = {"completion_id": reply["id"], "parsed_response": reply["choices"],
                            "provider_stop_reason": reply["choices"][0]["finish_reason"],
                            "usage": reply.get("usage"), "timings": reply.get("timings")}
                if any(event.get(key) != value for key, value in expected.items()):
                    raise ValueError("wire projection differs from the raw provider response")
                if native_records is not None and event.get("native_evidence", {}).get("status") == "PASS":
                    source = correlate(native_records.get(reply["id"], []), reply, True)
                    if source != event.get("source_generation"):
                        raise ValueError("native generation differs from its raw observer record")


def read_capture(folder):
    from scripts.tools.verify_ij06_evidence import verify_gpu

    metadata = json.loads((folder / "run.json").read_bytes())
    if metadata.get("plan") != run.plan() or metadata.get("candidate") not in run.CANDIDATES:
        raise ValueError("capture preregistration differs from the registered plan")
    if metadata.get("source_sha256") != run.source_hashes():
        raise ValueError("replay requires the captured execution sources")
    sealed = metadata.get("trial_sha256")
    native_records = None
    if sealed is not None:
        launch_file = folder / "launch.json"
        launch = json.loads(launch_file.read_bytes())
        counters = folder / launch["counter_file"]
        trace = folder / launch["trace_file"]
        artifacts = {path.name: digest(path) for path in (launch_file, counters, trace)}
        if artifacts != metadata["artifacts"] or verdict(verify_gpu(
                {"gpu_launch": launch_file, "gpu_counters": counters}, "vulkan")) != metadata["gpu_execution"]:
            raise ValueError("GPU or native evidence differs from the final capture")
        if launch["gpu_lease"]["runtime_session"] != metadata["run_id"] or launch["build"] != metadata["engine_build"]:
            raise ValueError("GPU launch differs from the capture identity")
        native_records = {}
        with trace.open("rb") as file:
            for line in file:
                source = json.loads(line)
                native_records.setdefault(source["completion_id"], []).append(source)
    elif metadata["gpu_execution"] != "NOT_RUN":
        raise ValueError("GPU evidence requires a finalized capture")
    captures, reserved, observed = [], set(), {}
    for spec in run.schedule():
        trial_id = fingerprint([metadata["run_id"], spec])
        target = folder / trial_id
        if not target.is_dir():
            continue
        reserved.add(trial_id)
        trial_path = target / "trial.json"
        if not trial_path.is_file():
            continue
        observed[trial_id] = digest(trial_path)
        trial = json.loads(trial_path.read_bytes())
        if trial["trial_id"] != trial_id or any(trial[key] != value for key, value in spec.items()):
            raise ValueError("trial is outside its registered block")
        attempts = []

        def invoke(profile, number):
            path = target / f"attempt-{number}" / "capture.json"
            if number >= len(trial["attempt_sha256"]) or digest(path) != trial["attempt_sha256"][number]:
                raise ValueError("attempt capture changed or is missing")
            attempt = json.loads(path.read_bytes())
            verified_attempt(attempt, f"{trial_id}-{number}", spec, profile, metadata["candidate"], native_records)
            attempts.append(attempt)
            return attempt

        outcome = run.apply_arm(spec["arm"], invoke)
        if (len(attempts) != len(trial["attempt_sha256"]) or any(trial[key] != outcome[key]
                for key in ("delivered", "retry_reason", "host_normalized"))):
            raise ValueError("offline intervention replay differs from the captured dispatch")
        captures.append(trial | {"attempts": attempts})
    if sealed is not None and observed != sealed:
        raise ValueError("trial captures differ from the finalized trial index")
    return metadata, captures, reserved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.capture is None:
        print(json.dumps({"oracle_sha256": fingerprint(EXPECTED), "physical": "NOT_RUN"}))
        return 0
    if args.output is None or args.output.exists():
        parser.error("scoring requires a fresh output file")
    result = replay(*read_capture(args.capture)) | {
        "capture_manifest_sha256": digest(args.capture / "run.json"), "scorer_sha256": digest(Path(__file__))}
    check_text(canonical(result))
    write_evidence(args.output, result)
    return 0 if result["physical"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
