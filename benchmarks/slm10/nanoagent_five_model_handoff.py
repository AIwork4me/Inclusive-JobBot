"""Verify and publish the five-model NanoAgent consumer exchange."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import median

from jsonschema import Draft202012Validator

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import ROOT, canonical

from .nanoagent_handoff import OUT as PRIORITY_HANDOFF
from .tc_five_model_milestone import OUT as MILESTONE
from .tc_five_model_report import index

OUT = PRIORITY_HANDOFF / "v1.1.0"
ATLAS = PRIORITY_HANDOFF.parent
PREVIOUS_SHA = "821a8ae34a113c4fe6d3f4972430e7b5eba5a3e8"
NAMES = ("A", "B", "D", "F", "G")
COST_FIELDS = ("input_tokens", "output_tokens", "total_tokens", "provider_inference_ms",
               "model_requests", "end_to_end_wall_ms")


def read(path):
    return json.loads(path.read_bytes())


def reference(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)}


def measured_deltas(rows):
    pairs = defaultdict(dict)
    for r in rows.values():
        if r["track"] in {"direct_first", "sdk_first"} and r["physical_execution"] == "PASS":
            pairs[r["candidate"], r["case_id"], r["seed"]][r["track"]] = r["telemetry"]
    data = {}
    for model in NAMES:
        joined = [p for (candidate, _, _), p in pairs.items() if candidate == model and len(p) == 2]
        if len(joined) != 500:
            raise ValueError("resource comparison requires all matched first-attempt slots")
        data[model] = {}
        for metric in COST_FIELDS:
            deltas = [p["sdk_first"][metric] - p["direct_first"][metric] for p in joined
                      if all(v[metric] is not None for v in p.values())]
            data[model][metric] = {
                "matched": len(joined), "observed": len(deltas),
                "median_sdk_minus_direct": median(deltas) if deltas else None,
                "status": "PASS" if len(deltas) == len(joined) else "BLOCKED" if deltas else "NOT_RUN",
            }
    return data


def report():
    score, _, rows = index()
    manifest_path = MILESTONE / "EVIDENCE_MANIFEST.json"
    evidence = read(manifest_path)
    matrix_path = MILESTONE / "CAPABILITY_MATRIX.json"
    matrix = read(matrix_path)
    pairs_path = MILESTONE / "PAIRED_RESULTS.json"
    pairs = read(pairs_path)
    if (tuple(matrix["models"]) != NAMES or matrix["executed"] != 8250 or matrix["sealed"] != 8250
            or evidence["derived_all_rows_sha256"] != score["derived_rows_sha256"]
            or pairs["assessment_sha256"] != score["derived_rows_sha256"]):
        raise ValueError("consumer baseline does not match the five-model seal replay")
    old_manifest_path = PRIORITY_HANDOFF / "HANDOFF_MANIFEST.json"
    old_manifest = read(old_manifest_path)
    for filename, expected in old_manifest["data"]["files"].items():
        if Path(filename).name != filename or digest(PRIORITY_HANDOFF / filename) != expected:
            raise ValueError("previous three-model exchange was changed")
    old_contract = PRIORITY_HANDOFF / "MATCHED_BENCHMARK_CONTRACT.json"
    old_mapping = PRIORITY_HANDOFF / "CAPABILITY_COMPONENT_MAPPING.json"
    normalization_path = ATLAS / "tc-output-normalization-replay.json"
    normalization = read(normalization_path)
    if (len(normalization["normalization_candidates"]) != 1596 or normalization["physical_intervention"] != "NOT_RUN"
            or normalization["source_assessments_sha256"] != score["derived_rows_sha256"]):
        raise ValueError("offline normalization evidence differs from the verified five-model baseline")
    lfm_path = ROOT / "evidence/IJSLM/physical-followup/lfm3-paired-analysis.json"
    lfm = read(lfm_path)
    if lfm["physical_execution"] != "PASS" or lfm["measured_trajectories"] != 24 or lfm["measured_pairs"] != 12:
        raise ValueError("LFM3 evidence does not cover all preregistered physical pairs")
    return {
        "version": "1.1.0",
        "scope": "TC-V3/1.0 five-model physical baseline and separately attributed compensation evidence",
        "physical_coverage": {"planned": 8250, "sealed": 8250, "status": "PASS", "strict_d25": "BLOCKED"},
        "previous_version": {"version": "1.0.0", "git_sha": PREVIOUS_SHA, "manifest": reference(old_manifest_path)},
        "models": {model: {"model_asset_sha256": matrix["models"][model]["configurations"][0]["model"]["model_sha256"],
                           "physical_trials": score["models"][model]["executed"],
                           "runtime_configurations": matrix["models"][model]["configurations"],
                           "failure_trace_examples": matrix["models"][model]["failure_examples"]}
                   for model in NAMES},
        "paired_resource_costs": measured_deltas(rows),
        "evidence": {
            "matrix": reference(matrix_path), "matched_quality_repeat_streaming": reference(pairs_path),
            "raw_trial_seal_inventory": reference(manifest_path),
            "paired_resource_pareto": reference(ATLAS / "tc-quality-resource-pareto.json"),
            "r0_r7_contract": reference(old_contract), "three_model_component_mappings": reference(old_mapping),
            "mini_cpm5_repeats_and_termination": reference(ROOT / "reports/SLM10_SDK_CAPABILITY_LOSS_ROOT_CAUSE.md"),
            "lfm3_compact_result_physical": reference(lfm_path),
            "offline_normalization": reference(normalization_path),
        },
        "compensation": {
            "MiniCPM5": {"candidate": "A", "target": "repeated proposals and incomplete stopping",
                         "qualification": "HYPOTHESIS"},
            "LFM3": {"candidate": "B", "target": "compact tool-result encoding",
                     "physical_trials": 24, "outcome": lfm["scoped_effect"]["finding"], "qualification": "HYPOTHESIS"},
            "Qwen3.5_and_Ministral": {"candidates": ["D", "F"], "target": "structured terminal JSON",
                                      "offline_replay_count": 1596, "physical_intervention": "NOT_RUN",
                                      "attribution": "HOST_NORMALIZED", "qualification": "HYPOTHESIS"},
        },
        "formal_trial_attribution": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = report()
    schema_path = OUT / "CAPABILITY_EXCHANGE.schema.json"
    schema = read(schema_path)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(result)
    raw = canonical(result) + b"\n"
    check_text(raw)
    path = OUT / "CAPABILITY_EXCHANGE.json"
    if args.write:
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("five-model exchange differs from the verified evidence")
    print("Verified five-model exchange, 8,250 frozen trials and the linked compensation evidence")


if __name__ == "__main__":
    main()
