"""Replay sealed capability batches and calculate matched development contrasts."""

import argparse
from collections import Counter, defaultdict
from itertools import product
import json
from pathlib import Path
from statistics import mean

from business_tools import encode_state
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import canonical, write_json

from .ha11_panel import (CORRECTED, DIRECT, ORIGINAL, WEIGHTS, build_plan, load_inputs, require_effective_controls,
                         verify_batch)
from .tc_capability_metrics import RATE_COUNTS, event_rate
from .tc_capability_replay import VERDICTS, assess, read_wire
from .tc_five_model_report import SCOPED, compare_paths, metric_outcome, repeat_status
from .tc_priority_milestone import SEALED_COMPONENTS, metric_cell
from .tc_v3 import FIRST_SEED, REPEAT_SEEDS
from .tc_verification import component_verdicts, trace_evidence


REPORTED = ("FIRST_TOOL_CHOICE", "REQUIRED_ACTION_COVERAGE", "EXACT_ACTION_SEQUENCE", "RESULT_DELIVERY",
            "RESULT_COMPREHENSION", "EXECUTION_PROCESS_CORRECTNESS", "TERMINATION_CORRECTNESS",
            "OUTPUT_CONTRACT_COMPLIANCE", "QUALIFIED_BUSINESS_COMPLETION", "BUSINESS_FACT_CORRECTNESS")
OUTCOMES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
COST_FIELDS = ("model_requests", "executed_tools", "input_tokens", "output_tokens", "total_tokens",
               "provider_inference_ms", "end_to_end_wall_ms")


def scoped_completion(assessment):
    metrics = assessment["metrics"]
    gates = [metrics[key] for key in ("EXECUTION_PROCESS_CORRECTNESS", "OUTPUT_CONTRACT_COMPLIANCE",
                                      "TERMINATION_CORRECTNESS")]
    if assessment["business_fact_scope_eligible"]:
        gates.append(metrics["QUALIFIED_BUSINESS_COMPLETION"])
    return next(status for status in ("FAIL", "BLOCKED", "NOT_RUN", "PASS") if status in gates)


def trial_detail(trial, oracle, assessment):
    turns, proposals = read_wire(trial, False)
    observed = Counter((entry["tool"], encode_state(entry["arguments"])) for entry in proposals)
    expected = Counter((entry["tool"], encode_state(entry["arguments"])) for entry in oracle["nodes"])
    arg_status = ("BLOCKED" if not turns or any("reply" not in turn for turn in turns) else
                  "PASS" if expected == observed else "FAIL")
    executed = sum(call["decision"] == "EXECUTED" for call in trial["calls"])
    counts = assessment["call_counts"]
    telemetry = assessment["telemetry"] | {"end_to_end_wall_ms": trial.get("elapsed_wall_ms")}
    return {
        "metrics": assessment["metrics"] | {"EXACT_TOOL_ARGUMENT_MULTISET": arg_status,
                                           "SCOPED_COMPLETION": scoped_completion(assessment)},
        "proposals": len(proposals), "duplicate_proposals": counts["duplicate_proposals"],
        "redundant_executions": counts["redundant_executions"],
        "call_counts": counts, "sealed_status": "BLOCKED", "physical_execution": "PASS",
        "business_fact_scope_eligible": assessment["business_fact_scope_eligible"],
        "sealed_component_assessment": component_verdicts(oracle, trace_evidence(trial)),
        "cost": {field: executed if field == "executed_tools" else telemetry[field]
                 for field in COST_FIELDS},
    }


def estimate(cells):
    shared = sorted(set.intersection(*(set(rows) for rows, _ in cells)))
    outcomes = {}
    for key in (*REPORTED, "EXACT_TOOL_ARGUMENT_MULTISET", "SCOPED_COMPLETION"):
        values = []
        for index in shared:
            results = [rows[index]["metrics"][key] for rows, _ in cells]
            if all(result in ("PASS", "FAIL") for result in results):
                values.append(sum(sign * (value == "PASS") for (_, sign), value in zip(cells, results, strict=True)))
        outcomes[key] = {"shared_observed": len(shared), "adjudicated_pairs": len(values),
                         "difference_pp": round(100 * mean(values), 3) if values else None}
    for key in ("duplicate_proposals", "redundant_executions"):
        values = []
        for index in shared:
            results = [rows[index][key] for rows, _ in cells]
            if all(result is not None for result in results):
                values.append(sum(sign * value for (_, sign), value in zip(cells, results, strict=True)))
        outcomes[key] = {"adjudicated_pairs": len(values), "mean_difference": round(mean(values), 4) if values else None}
    return outcomes


def summarize(rows):
    totals = {}
    denominator = sum(row["metrics"]["SCOPED_COMPLETION"] == "PASS" for row in rows)
    costs = {}
    for field in COST_FIELDS:
        values = [row["cost"][field] for row in rows if row["cost"][field] is not None]
        costs[field] = {
            "observations": len(values), "total": sum(values) if values else None,
            "per_success": round(sum(values) / denominator, 4) if denominator and len(values) == len(rows) else None,
        }
    report = {"observed": len(rows), "metric_counts": totals, "cost": costs}
    for field in (*VERDICTS, "EXACT_TOOL_ARGUMENT_MULTISET", "SCOPED_COMPLETION"):
        grouped = Counter(row["metrics"][field] for row in rows)
        totals[field] = {key: grouped[key] for key in OUTCOMES}
    return report | {"event_rates": {key: event_rate(rows, *value) for key, value in RATE_COUNTS.items()}}


def atlas_views(cells, slots, cases):
    strata = defaultdict(list)
    for slot in slots:
        case_id, weight, track, seed = (slot[key] for key in ("case_id", "weight", "track", "seed"))
        public, _, oracle = cases[case_id]
        row = cells[weight, track].get((case_id, seed))
        for key, value in (("all", "all"), ("family", public["family"]), ("language", public["language"]),
                           ("risk_scope", oracle["risk_scope"])):
            strata[weight, track, key, value].append((row, public, oracle))
    dimensions = {}
    for key, rows in strata.items():
        metrics = {metric: metric_cell(metric_outcome(row, metric, public, oracle)
                                       for row, public, oracle in rows)
                   for metric in (*VERDICTS, *SEALED_COMPONENTS, *SCOPED)}
        if key[1] == "sdk_repeat":
            for result in metrics.values():
                result["wilson_95"] = None
        dimensions["/".join(key)] = metrics

    pairs = defaultdict(list)
    repeat_ids = {slot["case_id"] for slot in slots if slot["track"] == "sdk_repeat"}
    for weight, case_id in product(WEIGHTS, cases):
        case_key = (case_id, FIRST_SEED)
        first, stream = (cells[weight, track].get(case_key) for track in ("sdk_first", "sdk_streaming"))
        public, _, oracle = cases[case_id]
        repeats = [cells[weight, "sdk_repeat"].get((case_id, seed)) for seed in REPEAT_SEEDS]
        for key, value in (("all", "all"), ("family", public["family"]), ("language", public["language"]),
                           ("risk_scope", oracle["risk_scope"])):
            pairs[weight, "STREAMING_CONSISTENCY", key, value].append((True, compare_paths(first, stream)))
            if case_id in repeat_ids:
                applicable = oracle["risk_scope"] == "synthetic-read-only" and bool(oracle["nodes"])
                pairs[weight, "REPEAT_RELIABILITY", key, value].append(
                    (applicable, repeat_status(repeats) if applicable else "NOT_RUN"))
    return {"dimensions": dimensions, "paired_cases": {"/".join(key): metric_cell(rows)
                                                        for key, rows in pairs.items()}}


def replay(suite, folder):
    cases, input_sha = load_inputs(suite)
    batches, freeze = build_plan(suite, cases, input_sha)
    cells = defaultdict(dict)
    seals = []
    done = 0
    for number, batch in enumerate(batches):
        path = folder / f"batch-{number:03d}"
        if not (path / "seal.json").exists():
            continue
        seal = verify_batch(path, batch, freeze)
        seals.append({"run_id": seal["run_id"], "seal_sha256": digest(path / "seal.json"),
                      "git_sha": seal["git_sha"], "batch_sha256": seal["batch_sha256"],
                      "adapter_sha256": seal["adapter"]["sha256"] if seal["adapter"] else None,
                      "artifacts": seal["artifacts"], "runtime": seal["runtime"], "base": seal["base"],
                      "handoff_sha256": seal["handoff_sha256"],
                      "peak_gpu_committed_bytes": max((row["committed_bytes"] for row in
                          (json.loads(line) for line in (path / "gpu.jsonl").read_bytes().splitlines())
                          if row["kind"] == "gpu_process_memory"), default=None)})
        for row in seal["results"]:
            ident = row["slot_id"]
            trial = json.loads((path / (ident + ".json")).read_bytes())
            require_effective_controls(trial, row)
            _, _, oracle = cases[row["case_id"]]
            assessment = assess(trial, oracle, "BLOCKED")
            if assessment != row["assessment"] or row["trial_id"] != trial["trial_id"]:
                raise ValueError("Trial assessment differs from its sealed trace")
            factor = row["profile"] if suite == "transfer" else row["track"]
            cells[row["weight"], factor][row["case_id"], row["seed"]] = trial_detail(trial, oracle, assessment)
            done += 1
    factors = (DIRECT, ORIGINAL, CORRECTED) if suite == "transfer" else (
        "direct_first", "sdk_first", "sdk_streaming", "sdk_repeat")
    arms = {}
    for weight, mode in product(WEIGHTS, factors):
        reports = summarize(list(cells[weight, mode].values()))
        planned = 60 if suite == "transfer" else (150 if mode == "sdk_repeat" else 500)
        arms[f"{weight}/{mode}"] = reports | {"planned": planned,
                                             "unexecuted": planned - reports["observed"]}
    weight_gains = {f"{weight}/{mode}": estimate([(cells[weight, mode], 1), (cells["Original", mode], -1)])
                    for weight, mode in product(WEIGHTS[1:], factors)}
    runtime_gains, interactions = {}, {}
    if suite == "transfer":
        for weight, control in product(WEIGHTS, (DIRECT, ORIGINAL)):
            key = f"{weight}/{CORRECTED}-vs-{control}"
            runtime_gains[key] = estimate([(cells[weight, CORRECTED], 1), (cells[weight, control], -1)])
            if weight != "Original":
                interactions[key] = estimate([(cells[weight, CORRECTED], 1), (cells[weight, control], -1),
                                              (cells["Original", CORRECTED], -1), (cells["Original", control], 1)])
    atlas = None if suite == "transfer" else atlas_views(cells, [slot for batch in batches for slot in batch], cases)
    return freeze | {"executed": done, "unexecuted": freeze["planned"] - done,
                     "coverage": "PASS" if done == freeze["planned"] else "BLOCKED",
                     "batch_seals": seals, "arms": arms, "weight_gains": weight_gains,
                     "runtime_gains": runtime_gains, "interactions": interactions, "compatibility_atlas": atlas}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=("transfer", "tc-extension"))
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = replay(args.suite, args.captures)
    check_text(canonical(report))
    write_json(args.output, report)
    print(report["coverage"], report["executed"], report["planned"])


if __name__ == "__main__":
    main()
