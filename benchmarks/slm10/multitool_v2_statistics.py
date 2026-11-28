"""Summarize exact-roster MULTITOOL-V2 candidate development seals offline."""

import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re

from benchmarks.ij06_sdk.wire_boundary import assemble_reply
from benchmarks.root_cause.generation_capture import protocol_reply
from benchmarks.tool_calling_v2.oracle import decode_object, equal
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.gpu_handoff import HANDOFF
from evaluation.aeve.runtime import ROOT, canonical, fingerprint

from .multitool_v2_balanced import trial_roster
from .multitool_v2_candidate import BANDS, COUNTS, MODELS, REPEAT_SEEDS
from .multitool_v2_revised import FOLDER, VERSION, candidate, evaluate
from .tc_dashboard import load_seal, percentile, proportion


REPORT_VERSION = "IJ-SLM-MULTITOOL-V2-STATISTICS/1.0"
TRACE_DIMENSIONS = ("actual_tool_calls", "model_requests", "user_turns")
DIMENSIONS = ("authored_actions", "authored_dag_critical_path", *TRACE_DIMENSIONS)
SCORED = ("PASS", "FAIL")
STRATA = {"bands": "band", "categories": "category", "risks": "risk"}
SCOPE = "candidate-development"
RISK = "synthetic-read-only"


def registered_roster():
    manifest_path, roster_path = (FOLDER / name for name in ("manifest.json", "roster.json"))
    manifest = json.loads(manifest_path.read_bytes())
    if (manifest["version"] != VERSION or manifest["formal_roster_freeze"] != "NOT_RUN"
            or manifest["formal_dispatch"] != "BLOCKED" or manifest["attributed_physical_trials"] != 0
            or manifest["panel"] != list(MODELS) or manifest["counts_per_model"] != COUNTS
            or digest(roster_path) != manifest["files"]["roster.json"]):
        raise ValueError("MULTITOOL-V2 candidate roster or development state differs from the pinned manifest")
    for name, expected in manifest["source_sha256"].items():
        if Path(name).name != name or digest(Path(__file__).with_name(name)) != expected:
            raise ValueError("MULTITOOL-V2 candidate source differs from its pinned replay")
    published = json.loads(roster_path.read_bytes())
    rows, repeats = candidate()
    cases = {row[0]["case_id"]: row for row in rows}
    specs = {}
    for model in MODELS:
        trials = trial_roster(model, rows, repeats)
        for trial in trials:
            trial["suite"] = VERSION
            trial["trial_id"] = fingerprint({key: value for key, value in trial.items() if key != "trial_id"})
        if fingerprint(trials) != published["per_model_candidate_roster_sha256"][model]:
            raise ValueError("registered model trial identities differ from the sealed roster")
        for trial in trials:
            public, _, oracle = cases[trial["case_id"]]
            actions = public["required_actions"]
            band = next(f"{low}-{high}" for low, high in BANDS if low <= actions <= high)
            specs[trial["trial_id"]] = trial | {"band": band, "category": public["category"], "risk": RISK,
                                                "authored_actions": actions,
                                                "authored_dag_critical_path": oracle["critical_path"]}
    if len(specs) != manifest["planned_trials"] or len(specs) != 7500:
        raise ValueError("registered trial total differs from the frozen candidate allocation")
    return digest(manifest_path), specs, cases


def capture_dimensions(trace):
    calls = trace.get("calls")
    call_count = len(calls) if isinstance(calls, list) and all(isinstance(row, dict) for row in calls) else None

    def count_ids(field, id_key, *, allow_undispatched=False):
        events = trace.get(field)
        if not isinstance(events, list) or any(not isinstance(row, dict) for row in events):
            return None
        ids = [row.get(id_key) for row in events]
        if allow_undispatched:
            ids = [key for key in ids if key is not None]
        if any(not isinstance(key, str) or not key for key in ids):
            return None
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate captured {id_key}")
        return len(ids)

    return {"actual_tool_calls": call_count,
            "model_requests": count_ids("wire", "provider_request_id", allow_undispatched=True),
            "user_turns": count_ids("user_turns", "user_turn_id")}


def verify_capture_provenance(trace, status):
    proposals, completions = {}, set()
    native = 0
    last = None
    for turn, event in enumerate(trace["wire"]):
        if event["trial_id"] != trace["trial_id"]:
            raise ValueError("wire event belongs to a different physical trial")
        last = None
        if event.get("http_status") != 200:
            continue
        raw = event["response"].encode()
        if sha256(raw).hexdigest() != event["response_sha256"]:
            raise ValueError("provider response digest differs from its captured bytes")
        completion = event["completion_id"]
        body = json.loads(event["provider_request"])
        if completion in completions or protocol_reply(raw, body["stream"])["id"] != completion:
            raise ValueError("provider completion identity differs from the capture")
        completions.add(completion)
        if event.get("native_evidence", {}).get("status") == "PASS":
            if not event.get("provider_request_id") or event.get("source_generation", {}).get("completion_id") != completion:
                raise ValueError("native completion lacks its linked provider request")
            native += 1
        last = assemble_reply(event["content_type"], raw, max_stream_bytes=1 << 20)
        for call in last.calls:
            if call.call_id in proposals:
                raise ValueError("duplicate provider proposal identity")
            proposals[call.call_id] = turn, completion, call.name, call.arguments_raw
    if not native:
        raise ValueError("physical trial lacks a linked native completion")
    for call in trace.get("calls", ()):
        expected = tuple(call[key] for key in ("turn", "completion_id", "tool", "arguments_raw"))
        if proposals.get(call["call_id"]) != expected:
            raise ValueError("captured tool call differs from its provider proposal")
    if status == "PASS":
        if last is None or last.finish_reason != "stop" or last.calls:
            raise ValueError("passing workflow lacks a terminal provider answer")
        if not equal(decode_object(last.content), trace["answer"]):
            raise ValueError("terminal provider answer differs from the scored answer")


def observer_identity():
    archive = ROOT / "evidence/IJSLM/sdk-causal"
    pilot = "pilot-B/report.json"
    manifest = json.loads((archive / "manifest.json").read_bytes())
    if digest(archive / pilot) != manifest["files"][pilot]:
        raise ValueError("pinned observer identity differs from the sealed reference capture")
    capture = json.loads((archive / pilot).read_bytes())
    return capture["engine_sha256"], capture["sdk"], capture["harness_sha256"]


def _read_physical_seal(path, roster_sha256, specs, cases, observations):
    raw = path.read_bytes()
    check_text(raw)
    identity = json.loads(raw)["identity"]
    if (identity.get("suite") != VERSION or identity.get("candidate_manifest_sha256") != roster_sha256
            or identity.get("scope") != SCOPE or identity.get("formal_trial_attribution") != 0):
        raise ValueError("physical seal lies outside the registered candidate scope and version")
    manifest, rows, _ = load_seal(path)
    launch = manifest["launch"]
    model = identity["candidate"]
    if model not in MODELS or not re.fullmatch("[a-f0-9]{40}", str(identity.get("git_sha", ""))):
        raise ValueError("physical seal lacks a registered candidate and exact Git revision")
    from benchmarks.competitive_slm.tc_v2_candidate import VULKAN_DEVICE, verify_launch

    registry = json.loads((FOLDER.parent / "model_registry.json").read_bytes())["models"][model]
    asset = registry["asset"]
    runtime = json.loads((ROOT / "evidence/IJ07/model_identity/admission_strict" / model / "report.json").read_bytes())
    old_gpu = runtime["gpu"]
    engine, sdk_version, harness_sha256 = observer_identity()
    handoff = json.loads((ROOT / HANDOFF).read_bytes())
    lease = launch["gpu_lease"]
    if (identity["model"]["model_sha256"] != asset["expected_sha256"]
            or identity["model"]["runtime_revision"] != asset["revision"] or identity["model"]["runtime_repo"] != asset["repo"]
            or identity["engine"] != {"build": old_gpu["build"], "sha256": engine} or identity["backend"] != "vulkan"
            or identity["handoff_sha256"] != digest(ROOT / HANDOFF) or handoff["status"] != "PASS"
            or lease["runtime_session"] != identity["run_id"] or lease["mission_id"] != "IJ-SLM-1.0"
            or any(lease[key] != handoff["lease"][key] for key in ("host_sha256", "gpu_physical_sha256"))):
        raise ValueError("physical seal differs from the pinned model, engine or approved Radeon lease")
    verify_launch(launch, {"gpu": VULKAN_DEVICE, "engine": {"build": old_gpu["build"], "layers": old_gpu["layers_total"]},
                           "template": {"sha256": old_gpu["template_sha256"]}})
    for row in rows:
        key = row["trial_id"]
        if key not in specs or key in observations or specs[key]["candidate"] != model:
            raise ValueError("physical trial is outside the registered roster or duplicates a prior trial")
        spec = specs[key]
        if spec["track"].startswith("sdk_") and (identity.get("sdk_version") != sdk_version
                or identity.get("harness_sha256") != harness_sha256):
            raise ValueError("physical SDK trial lacks the pinned SDK and harness identity")
        physically_observed = row["physical_execution"] == "PASS"
        if not physically_observed:
            if row["physical_execution"] != "BLOCKED" or row["status"] != "BLOCKED":
                raise ValueError("unverified capture requires a BLOCKED status")
            observations[key] = {"status": "BLOCKED", "physical_observed": False}
            continue
        trace = row["trace"]
        expected = ("trial_id", "suite", "candidate", "case_id", "track", "seed")
        if (manifest["gpu_execution"] != "PASS" or any(trace.get(field) != spec[field] for field in expected)
                or re.fullmatch("[a-f0-9]{64}", str(row.get("private_capture_sha256", ""))) is None):
            raise ValueError("physical trial lacks matching native and trace provenance")
        status = evaluate(*cases[spec["case_id"]], trace)["status"]
        if status not in (*SCORED, "BLOCKED") or status != row["status"]:
            raise ValueError("sealed trial outcome differs from scoped workflow replay")
        verify_capture_provenance(trace, status)
        observations[key] = {"status": status, "physical_observed": True, **capture_dimensions(trace)}
    return digest(path)


def _stratified(specs, summary):
    result = {"overall": summary(specs)}
    for label, key in STRATA.items():
        groups = defaultdict(list)
        for spec in specs:
            groups[spec[key]].append(spec)
        result[label] = {group: summary(members) for group, members in sorted(groups.items())}
    return result


def repeat_summary(specs, observations):
    def summarize(members):
        groups = defaultdict(list)
        for spec in members:
            groups[spec["case_id"]].append(observations.get(spec["trial_id"], {}))
        all_three, fully_observed, fully_scored, observed_seeds = [], 0, 0, 0
        for group in groups.values():
            if len(group) != len(REPEAT_SEEDS):
                raise ValueError("repeat case does not have three registered seed slots")
            states = {row.get("status", "NOT_RUN") for row in group}
            all_three.append("FAIL" if "FAIL" in states else "PASS" if states == {"PASS"} else
                             "BLOCKED" if "BLOCKED" in states else "NOT_RUN")
            observed = sum(row.get("physical_observed", False) for row in group)
            observed_seeds += observed
            fully_observed += observed == len(REPEAT_SEEDS)
            fully_scored += states <= set(SCORED)
        return {"planned_cases": len(groups), "planned_seeds": len(members), "seeds_physically_observed": observed_seeds,
                "fully_observed_cases": fully_observed, "fully_scored_cases": fully_scored,
                "all_three": proportion(all_three)}

    return _stratified(specs, summarize)


def statistics(seals=()):
    roster_sha, specs, cases = registered_roster()
    observations = {}
    sources = [_read_physical_seal(path, roster_sha, specs, cases, observations) for path in seals]

    def summarize(members):
        observed = [observations.get(spec["trial_id"], {}) for spec in members]
        statuses = [row.get("status", "NOT_RUN") for row in observed]
        dimensions = {}
        for key in DIMENSIONS:
            values = [row[key] for row in (observed if key in TRACE_DIMENSIONS else members) if row.get(key) is not None]
            dimensions[key] = percentile(values)
        return {"planned_trials": len(members), "physical_trials": sum(row.get("physical_observed", False) for row in observed),
                "outcomes": proportion(statuses), "dimensions": dimensions}

    models = {}
    for model in MODELS:
        tracks = {track: [spec for spec in specs.values() if spec["candidate"] == model and spec["track"] == track]
                  for track in COUNTS}
        models[model] = {"tracks": {track: _stratified(members, summarize) for track, members in tracks.items()},
                         "repeat": repeat_summary(tracks["sdk_repeat"], observations)}
    measured = sum(row["physical_observed"] for row in observations.values())
    return {"version": REPORT_VERSION, "suite": VERSION, "scope": SCOPE, "candidate_manifest_sha256": roster_sha,
            "planned_trials": len(specs), "physical_trials": measured, "formal_trial_attribution": 0,
            "physical_execution": "PASS" if measured else "BLOCKED" if observations else "NOT_RUN",
            "physical_seal_sha256": sorted(sources), "models": models,
            "attempt_denominator": "Wilson intervals are descriptive and use PASS + FAIL only. Repeat intervals use the case as the unit.",
            "maximum_verified_depth": {"status": "BLOCKED", "value": None,
                                        "reason": "No accepted depth policy authorizes interpreting the observed repeat stability."}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seal", action="append", default=[], type=Path,
                        help="Candidate physical session manifest with adjacent GPU and trial archives")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = canonical(statistics(args.seal)) + b"\n"
    if args.output:
        args.output.write_bytes(data)
    else:
        print(data.decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
