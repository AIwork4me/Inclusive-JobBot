"""Recheck private diagnostic seals and produce redaction-safe capability evidence."""

import argparse
from collections import Counter
from itertools import product
import json
from pathlib import Path

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import canonical, fingerprint, write_json
from scripts.tools.verify_ij06_evidence import verify_gpu

from .ha11_preflight import PROFILES
from .ha11_sdk import CORRECTED
from .tc_capability_replay import assess, read_wire
from .tc_v3 import LANGUAGES, PROMPTS, case_data


def verified_preflight(folder):
    source = folder / "report.json"
    report = json.loads(source.read_bytes())
    cases = [case_data(family, LANGUAGES[i % len(LANGUAGES)], "HA-SCOPE-V1", 0)
             for i, family in enumerate(PROMPTS)]
    oracles = {public["case_id"]: oracle for public, _, oracle in cases}
    if ({(row["case_id"], row["profile"]) for row in report["results"]} != set(product(oracles, PROFILES))
            or len(report["results"]) != len(PROFILES) * len(oracles)
            or report["dataset_sha256"] != fingerprint(cases)
            or report["gpu_execution"] != "PASS"
            or report["formal_core_trials"] != 0
            or any(digest(folder / name) != value for name, value in report["private_sha256"].items())
            or not verify_gpu({"gpu_launch": folder / "launch.json", "gpu_counters": folder / "gpu.jsonl"}, "vulkan")):
        raise ValueError("Preflight identities, roster or GPU proof differ")

    rows = []
    for row in report["results"]:
        trial_id = fingerprint([report["run_id"], row["case_id"], row["profile"]])
        trial_path = folder / f"{trial_id}.json"
        trial = json.loads(trial_path.read_bytes())
        assessment = assess(trial, oracles[row["case_id"]], "BLOCKED")
        turns, proposals = read_wire(trial, False)
        native = sum(event.get("native_evidence", {}).get("status") == "PASS" for event in trial["wire"])
        if (trial_id != row["trial_id"] or trial_id != trial["trial_id"] or digest(trial_path) != row["capture_sha256"]
                or assessment != row["assessment"] or row["executed_calls"] != len(trial["calls"])
                or native != row["native_requests"] or len(turns) != native
                or any("reply" not in turn for turn in turns)):
            raise ValueError("Preflight trace, native binding or assessment differs")
        callback_ok = {entry["call_id"] for entry in trial.get("callbacks", []) if entry["status"] == "PASS"}
        if row["profile"] == CORRECTED and (callback_ok != {entry["call_id"] for entry in proposals}
                                            or len(callback_ok) != len(trial["calls"])):
            raise ValueError("Phase-aware callback evidence differs from provider proposals")
        requests = []
        for event in trial["wire"]:
            original = json.loads(event.get("request", event["provider_request"]))
            effective = json.loads(event["provider_request"])
            requests.append({"provider_request_sha256": event["provider_request_sha256"],
                             "provider_response_sha256": event["response_sha256"],
                             "original_tool_choice": original.get("tool_choice"),
                             "effective_tool_choice": effective.get("tool_choice"),
                             "changed_fields": sorted(k for k in original.keys() | effective.keys()
                                                      if original.get(k) != effective.get(k)),
                             "phase": event.get("tool_phase"),
                             "native_capture": event["native_evidence"]["status"],
                             "finish_reason": event["provider_stop_reason"]})
        rows.append(row | {"wire_stages": requests})
    counts = {profile: dict(Counter(row["assessment"]["metrics"]["EXECUTION_PROCESS_CORRECTNESS"]
                                    for row in rows if row["profile"] == profile)) for profile in PROFILES}
    return report | {"results": rows, "private_report_sha256": digest(source),
                     "replay": "PASS", "exact_execution": counts,
                     "direct_executor_scope": "PASS", "corrected_sdk_executor_scope": "PASS"}


def verified_extension(folder, *, scripted):
    from .ha11_extension import CASES
    from .sdk_extension_execution import _frozen_partitions, score

    source = folder / "report.json"
    report = json.loads(source.read_bytes())
    partitions, _ = _frozen_partitions()
    graphs = {public["case_id"]: graph for public, graph in partitions["holdout"]}
    rows = report["results"]
    if [(row["candidate"], row["case_id"]) for row in rows] != [
        (candidate, case_id) for candidate, cohort in CASES.items() for case_id in cohort
    ] or report["core_trial_attribution"] != 0:
        raise ValueError("Extension replay roster differs")
    for row in rows:
        candidate = row["candidate"]
        path = folder / candidate / (row["trial_id"] + ".json")
        trial = json.loads(path.read_bytes())
        bound = [callback["binding"] for callback in trial["callbacks"] if callback["status"] == "PASS"]
        if (digest(path) != row["capture_sha256"] or len(bound) != row["bound"]
                or len(trial["calls"]) != row["executions"] or not bound
                or [entry["integer_conversions"] for entry in bound] != row["conversions"]):
            raise ValueError("Extension callback or capture evidence differs")
        if scripted:
            if (row["historic_first_response_sha256"] != trial["wire"][0]["response_sha256"]
                    or row["score"]["status"] != "NOT_RUN" or candidate in report["models"]):
                raise ValueError("Scripted Extension replay did not play the archived bytes")
        else:
            if row["score"] != score(graphs[row["case_id"]], trial):
                raise ValueError("Extension scorer replay differs")
            info = report["models"][candidate]
            root = folder / candidate
            counters = root / "vulkan-gpu.jsonl"
            if (info["gpu_execution"] != "PASS" or digest(counters) != info["gpu_counters_sha256"]
                    or digest(root / "vulkan-generation.jsonl") != info["trace_sha256"]
                    or not verify_gpu({"gpu_launch": root / "launch.json", "gpu_counters": counters}, "vulkan")):
                raise ValueError("Extension physical evidence differs")
    return report | {"replay": "PASS", "private_report_sha256": digest(source)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--preflight", type=Path)
    inputs.add_argument("--extension", type=Path)
    parser.add_argument("--scripted", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    evidence = (verified_preflight(args.preflight) if args.preflight
                else verified_extension(args.extension, scripted=args.scripted))
    check_text(canonical(evidence))
    write_json(args.output, evidence)
    print(evidence["replay"], len(evidence["results"]))


if __name__ == "__main__":
    main()
