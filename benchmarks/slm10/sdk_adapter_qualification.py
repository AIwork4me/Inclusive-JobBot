"""Replay single-factor request controls over existing portable Radeon pilot evidence."""

from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path

from model_gateway.strict_json import strict_object

from .sdk_adapters import (
    CallbackReceipt, MAX_REQUEST_BYTES, REGISTRY, RequestContext, Scope, STYLE_LINE, adapt_request,
    load_profiles,
)
from .tc_verification import delivered_result


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJSLM/sdk-causal"
OUTPUT = ROOT / "evidence/IJSLM/sdk-adapters/archived-request-controls.json"
COMPONENTS = ("prompt_compiler", "compact_result_codec", "action_state")
VERSION = "IJ-SLM-SDK-ADAPTER-ARCHIVE-REPLAY/1.0"


def _callbacks(capture, before, scope):
    for call in capture["calls"]:
        if call["trial_id"] != capture["trial_id"]:
            raise ValueError("archived callback does not belong to the captured trial")
        if call["turn"] >= before or call["decision"] != "EXECUTED" or "error" in call["result"]:
            continue
        event = capture["wire"][call["turn"]]
        if (event["provider_request_id"] != call["provider_request_id"] or event["completion_id"] != call["completion_id"]
                or call["call_id"] not in event["parsed_tool_call_ids"]):
            raise ValueError("archived callback lacks its provider source")
        yield CallbackReceipt(scope, call["provider_request_id"], call["completion_id"], call["call_id"],
                              call["tool"], call["arguments_raw"].encode(), json.dumps(call["result"]).encode(),
                              call["decision"])


def _independent_check(component, raw, output, indices):
    """Compare whole parsed requests after accounting for exactly the expected single change."""
    before = strict_object(raw, max_bytes=MAX_REQUEST_BYTES, max_depth=48)
    after = strict_object(output, max_bytes=MAX_REQUEST_BYTES, max_depth=48)
    if component in ("prompt_compiler", "action_state") and len(indices) != 1:
        return False
    for index in indices:
        old, new = before["messages"][index], after["messages"][index]
        if component == "prompt_compiler":
            if old["role"] != "system" or new["content"] != old["content"].replace(STYLE_LINE, "", 1):
                return False
        if component == "action_state":
            if old["role"] != "system" or not new["content"].startswith(old["content"] + "\nObserved completed actions"):
                return False
        if component == "compact_result_codec":
            if old["role"] != "tool" or delivered_result(old, {"tool": old["name"]}, "sdk_first") != strict_object(
                    new["content"], max_bytes=MAX_REQUEST_BYTES):
                return False
        old["content"] = new["content"]
    return bool(indices) and before == after


def archived_request_controls(evidence=EVIDENCE, *, include_timings=False):
    evidence = Path(evidence)
    manifest = json.loads((evidence / "manifest.json").read_bytes())
    profiles = load_profiles()
    comparisons, sources = [], {}
    for candidate in ("A", "B", "D"):
        path = f"pilot-{candidate}/report.json"
        report_bytes = (evidence / path).read_bytes()
        report_hash = sha256(report_bytes).hexdigest()
        if report_hash != manifest["files"][path]:
            raise ValueError("portable pilot report digest differs from its evidence seal")
        report = json.loads(report_bytes)
        if report["candidate"] != candidate or report["formal_trials"] != 0:
            raise ValueError("source is outside the registered development pilot")
        sources[candidate] = {
            "file": path,
            "portable_report_sha256": report_hash,
            "private_report_sha256": report["private_report_sha256"],
            "git_sha": report["git_sha"],
            "engine_sha256": report["engine_sha256"],
            "backend": report["gpu"]["backend"],
            "engine_build": report["gpu"]["build"],
            "gpu": report["gpu"]["gpu"],
            "dataset_manifest_sha256": report["dataset_manifest_sha256"],
            "model_revision": report["model"]["runtime_revision"],
            "model_sha256": report["model"]["model_sha256"],
            "sdk": report["sdk"],
            "run_id": report["run_id"],
        }
        for case in report["results"]:
            capture = next(arm["capture"] for arm in case["arms"] if arm["arm"] == "SDK_CONTROL")
            wire = [(event, event["provider_request"].encode()) for event in capture["wire"]]
            before = next((index for index, (_, raw) in enumerate(wire)
                           if any(message["role"] == "tool" for message in json.loads(raw)["messages"])), 0)
            event, raw = wire[before]
            messages = json.loads(raw)["messages"]
            system = [message["content"] for message in messages if message["role"] == "system"]
            if len(system) != 1 or event["trial_id"] != capture["trial_id"]:
                raise ValueError("SDK capture lacks unique source context")
            scope = Scope(capture["trial_id"], capture["trial_id"], "synthetic-pilot", case["case_id"], "executive")
            context = RequestContext(scope, event["provider_request_id"], sha256(system[0].encode()).hexdigest(),
                                     tuple(_callbacks(capture, before, scope)))
            reference, baseline = adapt_request(profiles["reference"], raw, context)
            for component in COMPONENTS:
                treatment, audit = adapt_request(profiles[component], raw, context)
                status = "NOT_RUN"
                if audit.message_indices:
                    passed = reference == raw and _independent_check(component, raw, treatment, audit.message_indices)
                    status = "PASS" if passed else "FAIL"
                record = {
                    "candidate": candidate, "case_id": case["case_id"], "component": component,
                    "version": audit.profile.version, "status": status,
                    "provider_request_id": audit.provider_request_id,
                    "original_private_source_sha256": event["provider_request_sha256"],
                    "portable_source_sha256": audit.before_sha256,
                    "reference_request_sha256": baseline.after_sha256,
                    "treatment_request_sha256": audit.after_sha256,
                    "reference_bytes": audit.before_bytes, "treatment_bytes": audit.after_bytes,
                    "message_indices": audit.message_indices, "callback_sources": audit.callback_sources,
                }
                if include_timings:
                    record["reference_elapsed_ns"] = baseline.elapsed_ns
                    record["treatment_elapsed_ns"] = audit.elapsed_ns
                comparisons.append(record)
    covered = {(row["candidate"], row["component"]) for row in comparisons if row["status"] == "PASS"}
    status = "FAIL" if any(row["status"] == "FAIL" for row in comparisons) else "PASS" if len(covered) == 9 else "BLOCKED"
    return {
        "version": VERSION,
        "status": status,
        "scope": "software transformation replay over sealed portable SDK development requests",
        "physical_dispatch": "NOT_RUN",
        "formal_trial_attribution": 0,
        "profiles_sha256": sha256(REGISTRY.read_bytes()).hexdigest(),
        "implementation_sha256": sha256(Path(__file__).with_name("sdk_adapters.py").read_bytes()).hexdigest(),
        "replay_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "sources": sources,
        "comparisons": comparisons,
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--timings", action="store_true", help="include host processing observations")
    parser.add_argument("--check", action="store_true", help="verify the versioned artifact")
    args = parser.parse_args()
    if args.check and args.timings:
        parser.error("timing observations are outside the deterministic archive")
    result = archived_request_controls(include_timings=args.timings)
    if args.check:
        current = json.loads(OUTPUT.read_bytes())
        expected = json.loads(json.dumps(result))
        if current != expected:
            raise ValueError("adapter controls differ from archived source replay")
        print(result["status"], len(result["comparisons"]), "archived adapter comparisons")
    else:
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
