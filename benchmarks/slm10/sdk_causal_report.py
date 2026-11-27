"""Bind offline SDK diagnostics to sealed trials and replay the published study."""

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
from statistics import median

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import ROOT, canonical

from .sdk_causal_metrics import VERSION, analyze, summary
from .tc_dashboard import load_seal, objects, percentile
from .tc_v3 import HERE

OUTPUT = ROOT / "evidence/IJSLM/sdk-causal"
METRICS = OUTPUT / "offline_metrics.jsonl.gz"
MATRIX = HERE.parent / "sdk-causal-matrices.json"
PASSPORTS = HERE.parent / "sdk-causal-passports.json"
FORMAL = ROOT / "evidence/IJSLM/tc-v3"
MODELS = {"A": "MiniCPM5-2B", "B": "LFM3-1.7B", "D": "Qwen3.5-2B"}
STAGES = ("first_tool_choice", "required_tool_coverage", "exact_tool_sequence", "argument_accuracy_per_call",
          "result_delivery", "result_comprehension", "final_answer", "stop_decision", "business_correctness",
          "strict_end_to_end")
TELEMETRY = ("system_bytes", "model_requests", "input_tokens", "output_tokens", "provider_inference_ms")
DECODERS = ("native_visible_match", "adapter_same_bytes")


def inventory(directory, private_root=None):
    specs = {r["trial_id"]: r for r in objects(HERE / "roster.jsonl")}
    oracles = {r["case_id"]: r for r in objects(HERE / "holdout-oracle.jsonl")}
    seen = set()
    for path in sorted(directory.glob("*/manifest.json")):
        manifest, rows, memory = load_seal(path)
        candidate = manifest["identity"]["candidate"]
        for row in rows:
            key = row["trial_id"]
            spec = specs[key]
            if candidate != spec["candidate"] or key in seen:
                raise ValueError("invalid offline trial provenance")
            seen.add(key)
            trace = row.get("trace")
            if trace is None or row["physical_execution"] != "PASS":
                continue
            if private_root:
                original = private_root / path.parent.name / (key + ".json")
                if digest(original) != row["private_capture_sha256"]:
                    raise ValueError("private trial differs from the formal seal")
            original_assessment = row["component_assessment"] | {"strict_end_to_end": row["status"]}
            basis = analyze(trace, oracles[spec["case_id"]], candidate, original_assessment, memory)
            if private_root:
                exact = analyze(json.loads(original.read_bytes()), oracles[spec["case_id"]], candidate,
                                original_assessment, memory)
                # System prompt size may change during privacy redaction. Recheck
                # all other reproducible fields using the original capture.
                for observed, unredacted in zip(basis["turns"], exact["turns"], strict=True):
                    observed.pop("system_bytes", None)
                    unredacted.pop("system_bytes", None)
                if basis != exact:
                    raise ValueError(f"portable causal assessment differs from private capture on {key}")
            else:
                for turn in basis["turns"]:
                    turn.pop("system_bytes", None)
            yield basis | {"physical_run_id": path.parent.name, "private_capture_sha256": row["private_capture_sha256"],
                           "portable_seal_sha256": manifest["artifacts"]["trials.jsonl.gz"]}


def pair_statistics(rows):
    by_case = defaultdict(dict)
    for row in rows:
        if row["track"] in ("direct_first", "sdk_first", "sdk_streaming"):
            by_case[row["candidate"], row["case_id"]][row["track"]] = row
    paired = {}
    for model in MODELS:
        cells = [arms for (candidate, _), arms in by_case.items() if model == candidate]
        comparisons = {}
        for first, second in (("direct_first", "sdk_first"), ("sdk_first", "sdk_streaming")):
            cases = [(cell[first], cell[second]) for cell in cells if first in cell and second in cell]
            values = {metric: [b[metric] - a[metric] for a, b in cases if metric in a and metric in b]
                      for metric in TELEMETRY if metric != "system_bytes"}
            outcomes = {metric: Counter((a["metrics"][metric], b["metrics"][metric]) for a, b in cases)
                        for metric in STAGES}
            comparisons[f"{first}_vs_{second}"] = {
                "paired_attempts": len(cases),
                "metric_transitions": {metric: {f"{a}/{b}": n for (a, b), n in sorted(count.items())}
                                       for metric, count in outcomes.items()},
                "paired_delta_second_minus_first": {
                    metric: percentile(items) | {"median": median(items) if items else None}
                    for metric, items in values.items()},
            }
        paired[model] = comparisons
    return paired


def cohort_case_ids():
    return {obj["case_id"] for obj in objects(HERE / "holdout-public.jsonl") if obj["family"] == "single"}


def matrices(rows):
    cells = summary(rows)
    single_ids = cohort_case_ids()
    single = [r for r in rows if r["case_id"] in single_ids and r["track"] == "sdk_first"]
    failure_decomposition = {}
    for model in MODELS:
        selected = [r for r in single if r["candidate"] == model]
        entry = {
            "sdk_first_single_count": len(selected),
            "duplicate_proposal_trials": sum(r["duplicate_proposals"] > 0 for r in selected),
            "redundant_execution_trials": sum(r["redundant_executions"] > 0 for r in selected),
            "strict_json_format_failure_with_correct_value_and_delivery": sum(
                r["metrics"]["answer_kind"] == "fenced_json" and r["metrics"]["result_comprehension"] == "PASS"
                and r["metrics"]["result_delivery"] == "PASS" for r in selected),
            "tool_result_old_FAIL": sum(r["old_assessment"].get("tool_result") == "FAIL" for r in selected),
            "stop_decision": dict(Counter(r["metrics"]["stop_decision"] for r in selected)),
            "visible_native_comparison": dict(Counter(turn.get("native_visible_match", "BLOCKED")
                                                      for r in selected for turn in r["turns"])),
            "same_byte_adapter_comparison": dict(Counter(turn.get("adapter_same_bytes", "BLOCKED")
                                                        for r in selected for turn in r["turns"])),
        }
        failure_decomposition[model] = entry
    tp = {}
    for cell in cells:
        model, track = cell.split("/")
        arm = [row for row in rows if row["candidate"] == model and row["track"] == track]
        tp[cell] = {field: percentile([row[field] for row in arm if field in row and row[field] is not None])
                    for field in ("input_tokens", "output_tokens", "model_requests", "provider_inference_ms",
                                  "sdk_boundary_wall_ms_sum", "session_peak_gpu_committed_bytes")}
        latency = [row["provider_inference_ms"] for row in arm if "provider_inference_ms" in row]
        denominator = cells[cell]["requests_per_scoped_success"]["denominator"]
        tp[cell]["provider_ms_per_scoped_success"] = (
            {"denominator": denominator, "value": sum(latency) / denominator if denominator else None}
            if len(latency) == len(arm) else {"status": "BLOCKED"})
    return {"version": VERSION, "attempts": len(rows), "capability": cells, "sdk_delta": pair_statistics(rows),
            "single_tool_stage_findings": failure_decomposition, "cost_and_latency": tp,
            "metric_scope": {
                "business": "Exact final value and delivered required read results; authorization and unverified state remain BLOCKED.",
                "call_occurrence": "Action instance, canonical arguments and dependency ordering from the frozen graph.",
                "native_visible_match": "Recognized text grammar and matching completion, with unrecognized native syntax BLOCKED.",
                "ttft": "NOT_RUN in baseline; buffered SDK observations carry no token-level latency claim.",
                "whole_task_wall_clock": "NOT_RUN in baseline; summed provider time excludes SDK and tool overhead.",
                "necessary_condition_failure": "Named proven violations, independent of the frozen strict verdict.",
            }}


def passports(report):
    cells = report["capability"]
    return {"version": VERSION, "publication_scope": "partial frozen priority cohort",
            "passports": {model: {
                "model": name, "direct_first": cells.get(model + "/direct_first"),
                "sdk_first": cells.get(model + "/sdk_first"), "sdk_streaming": cells.get(model + "/sdk_streaming"),
                "offline_authorization": "BLOCKED", "production": "BLOCKED",
            } for model, name in MODELS.items()}}


def publish(source=None, private_root=None):
    rows = list(inventory(source or FORMAL, private_root))
    payload = b"".join(canonical(row) + b"\n" for row in rows)
    values = matrices(rows)
    if source is not None:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        check_text(payload)
        METRICS.write_bytes(gzip.compress(payload, mtime=0))
        MATRIX.write_bytes(canonical(values) + b"\n")
        PASSPORTS.write_bytes(canonical(passports(values)) + b"\n")
    else:
        if (gzip.decompress(METRICS.read_bytes()) != payload or MATRIX.read_bytes() != canonical(values) + b"\n"
                or PASSPORTS.read_bytes() != canonical(passports(values)) + b"\n"):
            raise ValueError("published SDK metrics differ from the source-seal replay")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--private-sessions", type=Path)
    args = parser.parse_args()
    report = publish(FORMAL if args.write else None, args.private_sessions)
    print("Versioned offline reassessments:", report["attempts"])
    print(json.dumps(report["single_tool_stage_findings"], ensure_ascii=False))


if __name__ == "__main__":
    main()
