"""Report all five frozen TC-V3 model cohorts, including missing coverage."""

import argparse
from collections import defaultdict
import gzip
from hashlib import sha256
import json

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import canonical

from .tc_atlas_views import ROWS, SOURCE
from .tc_capability_metrics import RATE_COUNTS, event_rate
from .tc_capability_replay import VERDICTS
from .tc_dashboard import STATUS, objects
from .tc_priority_milestone import SEALED_COMPONENTS, metric_cell, outcome
from .tc_v3 import HERE

OUT = HERE.parent / "tc-five-model-report.json"
SCOPED = ("CLARIFICATION_CORRECTNESS", "FAILURE_RECOVERY")
OBSERVED = {"PASS", "FAIL"}
STREAM_METRICS = ("FIRST_TOOL_CHOICE", "EXACT_ACTION_SEQUENCE", "EXECUTION_PROCESS_CORRECTNESS",
                  "OUTPUT_CONTRACT_COMPLIANCE", "TERMINATION_CORRECTNESS")


def index():
    matrix = json.loads(SOURCE.read_bytes())
    raw = gzip.decompress(ROWS.read_bytes())
    if sha256(raw).hexdigest() != matrix["derived_rows_sha256"]:
        raise ValueError("five-model input differs from the verified seal replay")
    rows = [json.loads(line) for line in raw.splitlines()]
    seen = {row["trial_id"]: row for row in rows}
    roster = {row["trial_id"]: row for row in objects(HERE / "roster.jsonl")}
    if len(rows) != len(seen) or len(rows) != matrix["totals"]["sealed"] or seen.keys() - roster.keys():
        raise ValueError("five-model input includes duplicate or unregistered trials")
    for key, row in seen.items():
        if any(row[field] != roster[key][field] for field in ("candidate", "case_id", "track", "seed")):
            raise ValueError("assessment identity differs from its scheduled trial")
    return matrix, roster, seen


def metric_outcome(row, metric, public, oracle):
    if metric in SCOPED:
        target = "clarification" if metric == SCOPED[0] else "recovery"
        applicable = public["family"] == target
        name = "TERMINATION_CORRECTNESS" if metric == SCOPED[0] else "QUALIFIED_BUSINESS_COMPLETION"
        return applicable, row["metrics"][name] if row else "NOT_RUN"
    if row is None:
        row = {"business_fact_scope_eligible": oracle["risk_scope"] == "synthetic-read-only" and bool(oracle["nodes"]),
               "sealed_component_assessment": dict.fromkeys(SEALED_COMPONENTS, "NOT_RUN"),
               "sealed_status": "NOT_RUN", "metrics": dict.fromkeys(VERDICTS, "NOT_RUN")}
    if row.get("physical_execution") not in (None, "PASS") and not row.get("sealed_component_assessment"):
        row = row | {"sealed_component_assessment": dict.fromkeys(SEALED_COMPONENTS, "BLOCKED")}
    return outcome(row, metric, oracle)


def trials_status(statuses):
    if "NOT_RUN" in statuses:
        return "NOT_RUN"
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if not set(statuses) <= OBSERVED:
        raise ValueError("invalid TC-V3 status in a paired case")
    return None


def compare_paths(first, second):
    if not first or not second:
        return "NOT_RUN"
    left = [first["metrics"][metric] for metric in STREAM_METRICS]
    right = [second["metrics"][metric] for metric in STREAM_METRICS]
    unresolved = trials_status(left + right)
    return unresolved or ("PASS" if left == right else "FAIL")


def repeat_status(rows):
    if not all(rows):
        return "NOT_RUN"
    statuses = [row["metrics"]["QUALIFIED_BUSINESS_COMPLETION"] for row in rows]
    return trials_status(statuses) or ("PASS" if all(value == "PASS" for value in statuses) else "FAIL")


def compile_report():
    matrix, roster, rows = index()
    public = {case["case_id"]: case for case in objects(HERE / "holdout-public.jsonl")}
    oracles = {case["case_id"]: case for case in objects(HERE / "holdout-oracle.jsonl")}
    strata, paired, repeats = defaultdict(list), defaultdict(dict), defaultdict(list)
    for trial_id, spec in roster.items():
        model, case_id, track = (spec[k] for k in ("candidate", "case_id", "track"))
        task, oracle, row = public[case_id], oracles[case_id], rows.get(trial_id)
        segments = (("all", "all"), ("family", task["family"]), ("language", task["language"]),
                    ("risk_scope", oracle["risk_scope"]))
        for group in segments:
            strata[model, track, *group].append((row, task, oracle))
        case_key = model, case_id
        if track in ("sdk_first", "sdk_streaming"):
            paired[case_key][track] = row
        if track == "sdk_repeat":
            repeats[case_key].append(row)
    cells, pair_cells = {}, defaultdict(list)
    for key, items in sorted(strata.items()):
        cells["/".join(key)] = {
            "planned": len(items), "sealed": sum(row is not None for row, _, _ in items),
            "executed": sum(bool(row and row["physical_execution"] == "PASS") for row, _, _ in items),
            "metrics": {metric: metric_cell(metric_outcome(row, metric, task, oracle) for row, task, oracle in items)
                        for metric in (*VERDICTS, *SEALED_COMPONENTS, *SCOPED)},
            "event_rates": {metric: event_rate([row for row, _, _ in items if row], *fields)
                            for metric, fields in RATE_COUNTS.items()},
        }
    if any(len(cohort) != 3 for cohort in repeats.values()):
        raise ValueError("the frozen repeat panel requires three seeds per case")
    for (model, case_id), group in paired.items():
        task, oracle = public[case_id], oracles[case_id]
        both_seen = all(group.values())
        status = compare_paths(group["sdk_first"], group["sdk_streaming"])
        repeat_rows = repeats.get((model, case_id))
        for stratum, value in (("all", "all"), ("family", task["family"]), ("language", task["language"]),
                                ("risk_scope", oracle["risk_scope"])):
            pair_cells[model, "STREAMING_CONSISTENCY", stratum, value].append(
                (True, status, both_seen))
            if repeat_rows:
                applicable = oracle["risk_scope"] == "synthetic-read-only" and bool(oracle["nodes"])
                pair_cells[model, "REPEAT_RELIABILITY", stratum, value].append(
                    (applicable, repeat_status(repeat_rows), all(repeat_rows)))
    pair_results = {"/".join(key): {
        **metric_cell((applicable, status) for applicable, status, _ in cohort),
        "planned_case_pairs": len(cohort), "complete_seal_groups": sum(sealed for _, _, sealed in cohort),
    } for key, cohort in sorted(pair_cells.items())}
    return {
        "version": "TC-V3-FIVE-MODEL-CAPABILITY/1.0", "priority_status": ("PASS" if all(matrix["models"][model]["executed"] == 1650
                                           for model in ("A", "B", "D")) else "BLOCKED"),
        "physical_coverage_status": "PASS" if matrix["totals"]["executed"] == 8250 else "BLOCKED",
        "strict_d25": "BLOCKED", "dataset_manifest_sha256": matrix["dataset_manifest_sha256"],
        "assessment_sha256": matrix["derived_rows_sha256"], "seal_summary_sha256": digest(SOURCE),
        "core_denominator": 36550, "tc_v3_denominator": 8250,
        "models": matrix["models"], "cells": cells, "paired_cases": pair_results,
        "definitions": matrix["definitions"] | {
            "CLARIFICATION_CORRECTNESS": "Correct no-tool termination with the exact fixture clarification.",
            "FAILURE_RECOVERY": "Qualified business completion on the frozen recovery family.",
            "STREAMING_CONSISTENCY": "Agreement between SDK first and streaming on the five observed mechanical verdicts. "
                                     "Matching failures count as agreement. See path success columns for quality.",
            "REPEAT_RELIABILITY": "All three seeds achieve scoped read-only completion on an applicable case.",
            "authorization": "Frozen synthetic authorization component. Scope is the TC-V3 denial family.",
            "required_arguments": "Frozen required arguments component with tool cases as the applicable cohort.",
            "entity_binding": "Frozen entity binding component with tool cases as the applicable cohort.",
        },
        "interval_scope": "Wilson intervals use observed binary case outcomes. Duplicate and redundant event counts "
                          "share trial contexts and are published as counts without independent-event intervals.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = compile_report()
    payload = canonical(report) + b"\n"
    check_text(payload)
    if args.write:
        OUT.write_bytes(payload)
    elif OUT.read_bytes() != payload:
        raise ValueError("five-model report differs from the verified TC-V3 assessment ledger")
    print(f"Five-model report verified over {report['tc_v3_denominator']} frozen slots. "
          f"Physical coverage is {report['physical_coverage_status']}.")


if __name__ == "__main__":
    main()
