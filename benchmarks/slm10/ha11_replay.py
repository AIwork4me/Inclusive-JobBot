"""Recheck private diagnostic seals and produce redaction-safe capability evidence."""

import argparse
from collections import Counter
from itertools import product
import gzip
import json
from pathlib import Path
import re
from statistics import median

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


def verified_cache(folder):
    from .ha11_cache import FACTORS, WEIGHTS, cache_flags, classify_unknown, equivalent

    source = folder / "report.json"
    report = json.loads(source.read_bytes())
    expected = {f"{factor}-{weight}" for factor, weight in product(FACTORS, WEIGHTS)}
    if set(report["cells"]) != expected or report["core_trial_attribution"] != 0:
        raise ValueError("Cache factorial roster differs")
    summary = {}
    for name, cell in report["cells"].items():
        path = folder / name
        gpu = path / "gpu.jsonl"
        launch = path / "launch.json"
        log = path / "server.log"
        if (cell["flags"] != list(cache_flags(*FACTORS[cell["factor"]])) or cell["gpu_execution"] != "PASS"
                or digest(launch) != cell["launch_sha256"] or digest(gpu) != cell["gpu_counters_sha256"]
                or digest(log) != cell["server_log_sha256"]
                or not verify_gpu({"gpu_launch": launch, "gpu_counters": gpu}, "vulkan")):
            raise ValueError(f"Cache factorial physical evidence differs in {name}")
        info = {key: val for key, val in cell.items() if key != "profiles"}
        text = log.read_text(encoding="utf-8", errors="replace")
        info["prompt_cache_updates"] = text.count("updating prompt cache")
        info["recorded_cache_entry_peak_mib"] = max(map(float, re.findall(
            r"\d+ tokens, checkpoints:\s+\d+,\s+([\d.]+) MiB", text)), default=None)
        info["profiles"] = {}
        for mode, profile in cell["profiles"].items():
            data = profile["probes"]
            a, b = ("initial", "repeat") if cell["weight"] == "Original" else ("scale1", "scale1_repeat")
            if (profile["checks"]["same_prefix_repeat"] == "PASS") != equivalent(data[a], data[b]):
                raise ValueError("Cache recurrence verdict differs from raw numerics")
            if "unknown_id" in data and all(entry["http_status"] == 200 for entry in data["unknown_id"]):
                if profile["checks"]["native_unknown_id_effect"] != classify_unknown(
                        data["unknown_id"], data["restore0"], data["scale1"]):
                    raise ValueError("Unknown adapter fingerprint differs from raw numerics")
            info["profiles"][mode] = {"checks": profile["checks"], "stages": {
                stage: {"responses": len(rows), "token_counts": [len(row["tokens"]) for row in rows],
                        "median_prefill_ms": median(row["timings"]["prompt_ms"] for row in rows),
                        "median_decode_ms": median(row["timings"]["predicted_ms"] for row in rows),
                        "median_tokens_cached": median(row["tokens_cached"] for row in rows)}
                for stage, rows in data.items() if all(row["http_status"] == 200 for row in rows)
            }, "token_sequence_repeat": sum(x["tokens"] == y["tokens"] for x, y in zip(data[a], data[b], strict=True))}
        summary[name] = info
    evidence = report | {"cells": summary, "replay": "PASS", "private_report_sha256": digest(source)}
    return evidence, report


def verified_legacy_budget(folder):
    sources = []
    limits = {}
    for path in sorted(folder.glob("batch-*/seal.json")):
        source = json.loads(path.read_bytes())
        host = path.parent
        if (source["gpu_execution"] != "PASS" or source.get("provider_contract") is not None
                or any(digest(host / name) != value for name, value in source["artifacts"].items())
                or not verify_gpu({"gpu_launch": host / "launch.json", "gpu_counters": host / "gpu.jsonl"}, "vulkan")):
            raise ValueError("Historical budget diagnostic evidence differs")
        for row in source["results"]:
            capture_file = host / (row["slot_id"] + ".json")
            if digest(capture_file) != row["capture_sha256"]:
                raise ValueError("Historical budget diagnostic trace differs")
            capture = json.loads(capture_file.read_bytes())
            counts = limits.setdefault(row["profile"], Counter())
            for event in capture["wire"]:
                if "provider_request" in event:
                    cap = json.loads(event["provider_request"]).get("max_completion_tokens")
                    counts[str(cap)] += 1
        sources.append({key: source[key] for key in
                        ("run_id", "git_sha", "runtime", "base", "weights", "roster_sha256", "batch_sha256",
                         "dataset_manifest_sha256", "handoff_sha256", "gpu_execution", "artifacts")}
                       | {"seal_sha256": digest(path), "captured_trials": len(source["results"])})
    count = sum(row["captured_trials"] for row in sources)
    if count != 270 or "65535" not in limits.get("ORIGINAL_SDK", {}) or set(limits.get("DIRECT", {})) != {"768"}:
        raise ValueError("Historical budget diagnostic did not reproduce the mismatch")
    return {"replay": "PASS", "matched_provider_contract": "FAIL", "trials": count,
            "registered_transfer_trials": 0, "formal_core_trials": 0,
            "effective_max_completion_tokens": dict(limits), "seals": sources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--preflight", type=Path)
    inputs.add_argument("--extension", type=Path)
    inputs.add_argument("--cache", type=Path)
    inputs.add_argument("--legacy-budget", type=Path)
    inputs.add_argument("--compatibility-admission", type=Path)
    parser.add_argument("--scripted", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.cache:
        evidence, raw = verified_cache(args.cache)
        data = canonical(raw)
        check_text(data)
        target = args.output.with_suffix(".json.gz")
        target.write_bytes(gzip.compress(data, mtime=0))
        evidence["portable_numeric_archive_sha256"] = digest(target)
    elif args.legacy_budget:
        evidence = verified_legacy_budget(args.legacy_budget)
    elif args.compatibility_admission:
        from .ha11_compatibility_admission import verify

        evidence = verify(args.compatibility_admission)
    else:
        evidence = (verified_preflight(args.preflight) if args.preflight
                    else verified_extension(args.extension, scripted=args.scripted))
    check_text(canonical(evidence))
    write_json(args.output, evidence)
    print(evidence["replay"], len(evidence.get("cells", evidence.get("results", evidence.get("seals", [])))))


if __name__ == "__main__":
    main()
