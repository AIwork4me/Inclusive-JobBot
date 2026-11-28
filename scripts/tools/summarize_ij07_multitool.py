"""Summarize terminal MULTITOOL-V1 traces against their frozen dependency graphs."""

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

from benchmarks.job_productivity_v1.statistics import wilson_interval
from benchmarks.multitool_v1.dataset import canonical, load_freeze


ARGUMENT_ERRORS = {"F03_MODEL_ARGUMENT_ERROR", "F05_PROTOCOL_ERROR", "F07_SCHEMA_VALIDATION_ERROR"}
VERIFICATION_ERRORS = ARGUMENT_ERRORS | {"F09_SOP_DEPENDENCY_ERROR", "F10_TOOL_EXECUTION_ERROR"}


def ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "rate": numerator / denominator if denominator else None}


def summarize(source):
    coverage = json.loads((source / "coverage.json").read_bytes())
    freeze = load_freeze()
    raw = (source / "terminal.jsonl.gz").read_bytes()
    terminal = gzip.decompress(raw)
    if hashlib.sha256(terminal).hexdigest() != coverage["terminal_uncompressed_sha256"]:
        raise ValueError("MULTITOOL terminal archive differs from its validated checkpoint digest")
    grouped = defaultdict(list)
    metrics, first_failure = Counter(), Counter()
    steps = defaultdict(Counter)
    for line in terminal.splitlines():
        row = json.loads(line)["row"]
        case = freeze.active[row["case_id"]]
        nodes = case.oracle["nodes"]
        findings = row["findings"]
        errors = defaultdict(set)
        for item in findings:
            if item.get("call_id"):
                errors[item["call_id"]].add(item["code"])
        assigned = {item["node"]: errors[item["call_id"]] for item in row["observed_plan"]}
        expected, verified = len(nodes), 0
        prior_verified = True
        for index, node in enumerate(nodes, 1):
            node_errors = assigned.get(node["id"])
            node_verified = node_errors is not None and not node_errors & VERIFICATION_ERRORS
            verified += node_verified
            if node["depends_on"]:
                metrics["dependent_expected"] += 1
                metrics["dependent_in_order"] += node_errors is not None and "F09_SOP_DEPENDENCY_ERROR" not in node_errors
                metrics["dependent_grounded"] += node_verified
            if prior_verified:
                steps[index]["eligible"] += 1
                steps[index]["verified"] += node_verified
                if not node_verified:
                    first_failure[index] += 1
            prior_verified = prior_verified and node_verified
        metrics.update(
            cases=1, first_call_correct=row["first_call_correct"] is True, selected=len(assigned),
            expected=expected, calls=len(row["calls"]), exact_arguments=sum(not value & ARGUMENT_ERRORS for value in assigned.values()),
            proposals=row["proposal_count"], invalid_proposals=row["invalid_proposal_count"],
            argument_correct=row["argument_correct"], argument_expected=row["argument_total"],
            unnecessary=sum(item["detail"] in {"duplicate call", "unexpected tool call"} for item in findings),
            final_correct=not case.workflow().final.check(row["final"]),
            completed_within_budget=row["completed"] and not row["budget_reached"],
            unauthorized_or_unconfirmed_persisted_effects=sum(
                item["detail"] == "unauthorized or unconfirmed persisted effect" for item in findings),
            state_effect_mismatch_cases=any(
                item["detail"] == "missing, unexpected or duplicate persisted effects" for item in findings),
        )
        state, parser = row["business_state_status"], row["native_parser_status"]
        metrics["state_" + state] += 1
        metrics["parser_" + parser] += 1
        category = row["category"]
        if category in ("MT-01", "MT-02", "MT-04", "MT-06"):
            metrics[category + "_cases"] += 1
            metrics[category + "_task_pass"] += row["status"] == "PASS"
            metrics[category + "_all_steps_verified"] += expected == verified
        if category == "MT-01":
            batched = any(count > 1 for count in Counter(call["turn"] for call in row["calls"]).values())
            metrics["MT-01_batched"] += batched
            metrics["MT-01_batched_task_pass"] += batched and row["status"] == "PASS"
        grouped[row["depth_bin"]].append(row)
    if metrics["cases"] != coverage["terminal"]:
        raise ValueError("MULTITOOL terminal archive coverage differs")
    by_depth = {}
    for depth, rows in grouped.items():
        total = len(rows)
        passes = sum(row["status"] == "PASS" for row in rows)
        latencies = sorted(row["wall_ms"] for row in rows)
        by_depth[depth] = {
            "task_success": ratio(passes, total), "wilson95_terminal": wilson_interval(passes, total),
            "argument_accuracy": ratio(sum(row["argument_correct"] for row in rows), sum(row["argument_total"] for row in rows)),
            "recovery_task_success": ratio(sum(row["status"] == "PASS" and row["category"] == "MT-06" for row in rows),
                                           sum(row["category"] == "MT-06" for row in rows)),
            "model_calls_mean": mean(row["model_calls"] for row in rows),
            "latency_ms_p95_nearest_rank": latencies[math.ceil(0.95 * total) - 1],
            "token_mean": mean(row["prompt_tokens"] + row["completion_tokens"] for row in rows),
        }
    exact = metrics["selected"]
    return {
        "run_id": coverage["run_id"], "coverage_complete": coverage["coverage_complete"],
        "planned": coverage["planned"], "terminals": coverage["terminal"], "source_sha256": hashlib.sha256(raw).hexdigest(),
        "counts": dict(metrics),
        "tool_selection": {"precision": ratio(exact, metrics["calls"]), "recall": ratio(exact, metrics["expected"]),
                           "f1": ratio(2 * exact, metrics["calls"] + metrics["expected"])},
        "dependency": {"on_later_turn": ratio(metrics["dependent_in_order"], metrics["dependent_expected"]),
                       "grounded_and_verified": ratio(metrics["dependent_grounded"], metrics["dependent_expected"])},
        "by_depth": by_depth,
        "first_unverified_tool_step": dict(first_failure),
        "conditional_step_success": {index: ratio(counts["verified"], counts["eligible"]) for index, counts in steps.items()},
        "definitions": {
            "selection": "Assigned frozen nodes among calls the runtime evaluated. Full exact match is counted separately.",
            "step_order": "Canonical topological oracle order. Independent tools may execute in any allowed order.",
            "parser": "Case-level status from the live runner. Missing or withheld tool batches remain separately scoped.",
            "grounding": "A verified oracle-matched dependent proposal with exact arguments, available predecessors and matching response.",
            "repeat": "This summary contains only the measured panel; repeat reliability is a separate cohort.",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = canonical(summarize(args.source))
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != data:
            parser.exit(1, "FAIL: MULTITOOL stratified metrics differ\n")
        print("PASS: exact MULTITOOL stratified metrics")
    else:
        args.output.write_bytes(data)


if __name__ == "__main__":
    main()
