"""Replay sealed capability batches and calculate matched development contrasts."""

import argparse
from collections import Counter, defaultdict
import gzip
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
from .tc_dashboard import percentile
from .tc_five_model_report import compare_paths, repeat_status, summarize_stratum
from .tc_priority_milestone import metric_cell
from .tc_v3 import FIRST_SEED, REPEAT_SEEDS
from .tc_verification import component_verdicts, trace_evidence


REPORTED = ("FIRST_TOOL_CHOICE", "REQUIRED_ACTION_COVERAGE", "EXACT_ACTION_SEQUENCE", "RESULT_DELIVERY",
            "RESULT_COMPREHENSION", "EXECUTION_PROCESS_CORRECTNESS", "TERMINATION_CORRECTNESS",
            "OUTPUT_CONTRACT_COMPLIANCE", "QUALIFIED_BUSINESS_COMPLETION", "BUSINESS_FACT_CORRECTNESS")
OUTCOMES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
ADDED_METRICS = ("EXACT_TOOL_ARGUMENT_MULTISET", "SCOPED_COMPLETION", "TYPED_CALLBACK_BINDING")
COST_FIELDS = ("model_requests", "executed_tools", "input_tokens", "output_tokens", "total_tokens",
               "provider_inference_ms", "end_to_end_wall_ms")


def scoped_completion(assessment):
    metrics = assessment["metrics"]
    gates = [metrics[key] for key in ("EXECUTION_PROCESS_CORRECTNESS", "OUTPUT_CONTRACT_COMPLIANCE",
                                      "TERMINATION_CORRECTNESS")]
    if assessment["business_fact_scope_eligible"]:
        gates.append(metrics["QUALIFIED_BUSINESS_COMPLETION"])
    return next(status for status in ("FAIL", "BLOCKED", "NOT_RUN", "PASS") if status in gates)


def failure_signature(trial, assessment):
    metrics = assessment["metrics"]
    for event in trial["wire"]:
        body = json.loads(event.get("provider_request", "{}"))
        limit = body.get("max_completion_tokens")
        if (type(limit) is int and limit > 0 and event.get("native_evidence", {}).get("status") == "PASS"
                and event.get("provider_stop_reason") == "length"
                and (event.get("usage") or {}).get("completion_tokens") == limit):
            return "MODEL_OUTPUT_LIMIT"
        if (body.get("tool_choice") == "none" and body.get("tools")
                and "<tool_call>" in json.dumps(event.get("parsed_response", []))):
            return "RUNTIME_TOOL_CHOICE_NONE"
    if any(callback["status"] == "FAIL" for callback in trial.get("callbacks", ())):
        return "CALLBACK_BINDING"
    if any(call["decision"] == "DENIED" for call in trial["calls"]):
        return "EXECUTION_DENIAL"
    if (trial.get("failure") or {}).get("type") == "BudgetExceeded":
        return "MODEL_REQUEST_LIMIT"
    if trial.get("failure") or any(event.get("status") == "FAIL" for event in trial["wire"]):
        return "PARSER_OR_TRANSPORT_UNRESOLVED"
    if assessment["call_counts"].get("duplicate_proposals"):
        return "MODEL_REPEAT_PROPOSAL"
    if metrics["EXACT_ACTION_SEQUENCE"] == "FAIL":
        return "MODEL_ACTION_PATH"
    if metrics["TERMINATION_CORRECTNESS"] == "FAIL" or metrics["OUTPUT_CONTRACT_COMPLIANCE"] == "FAIL":
        return "TERMINAL_CONTRACT"
    return {"PASS": "NO_CLASSIFIED_FAILURE", "FAIL": "SCOPED_CONTRACT",
            "BLOCKED": "EVALUATION_UNCERTAINTY", "NOT_RUN": "EVALUATION_UNCERTAINTY"}[scoped_completion(assessment)]


def typed_binding_evidence(turns, proposals, callbacks):
    expected = {proposal["call_id"] for proposal in proposals}
    received = {callback["call_id"] for callback in callbacks}
    rejected = sum(callback["status"] == "FAIL" for callback in callbacks)
    complete_wire = bool(turns) and all("reply" in turn for turn in turns)
    counts = {"wire_proposals": len(expected), "callback_pass": len(callbacks) - rejected,
              "callback_fail": rejected, "integer_conversions": sum(
                  len(callback.get("binding", {}).get("integer_conversions", [])) for callback in callbacks),
              "missing_callbacks": len(expected - received)}
    if rejected or len(received) != len(callbacks) or (complete_wire and received - expected):
        return "FAIL", counts
    if not complete_wire or expected - received:
        return "BLOCKED", counts
    return ("PASS" if expected else "NOT_RUN"), counts


def trial_detail(trial, oracle, assessment, *, typed_callback):
    turns, proposals = read_wire(trial, False)
    observed = Counter((entry["tool"], encode_state(entry["arguments"])) for entry in proposals)
    expected = Counter((entry["tool"], encode_state(entry["arguments"])) for entry in oracle["nodes"])
    arg_status = ("BLOCKED" if not turns or any("reply" not in turn for turn in turns) else
                  "PASS" if expected == observed else "FAIL")
    binding_status, binding_counts = ("NOT_RUN", {}) if not typed_callback else typed_binding_evidence(
        turns, proposals, trial["callbacks"])
    executed = sum(call["decision"] == "EXECUTED" for call in trial["calls"])
    counts = assessment["call_counts"]
    telemetry = assessment["telemetry"] | {"end_to_end_wall_ms": trial.get("elapsed_wall_ms")}
    for field, key in (("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens"),
                       ("total_tokens", "total_tokens")):
        native = [(event.get("usage") or {}).get(key) if event.get("native_evidence", {}).get("status") == "PASS"
                  else None for event in trial["wire"]]
        if native and all(type(value) is int and value >= 0 for value in native):
            telemetry[field] = sum(native)
    return {
        "metrics": assessment["metrics"] | {"EXACT_TOOL_ARGUMENT_MULTISET": arg_status,
                                           "SCOPED_COMPLETION": scoped_completion(assessment),
                                           "TYPED_CALLBACK_BINDING": binding_status},
        "typed_callback_counts": binding_counts,
        "proposals": len(proposals), "duplicate_proposals": counts["duplicate_proposals"],
        "redundant_executions": counts["redundant_executions"],
        "call_counts": counts, "sealed_status": "BLOCKED", "physical_execution": "PASS",
        "business_fact_scope_eligible": assessment["business_fact_scope_eligible"],
        "sealed_component_assessment": component_verdicts(oracle, trace_evidence(trial)),
        "failure_signature": failure_signature(trial, assessment),
        "cost": {field: executed if field == "executed_tools" else telemetry[field]
                 for field in COST_FIELDS},
    }


def estimate(cells):
    shared = sorted(set.intersection(*(set(rows) for rows, _ in cells)))
    outcomes = {}
    for key in (*REPORTED, *ADDED_METRICS):
        values = []
        for index in shared:
            results = [rows[index]["metrics"][key] for rows, _ in cells]
            if all(result in ("PASS", "FAIL") for result in results):
                values.append(sum(sign * (value == "PASS") for (_, sign), value in zip(cells, results, strict=True)))
        outcomes[key] = {"shared_observed": len(shared), "adjudicated_pairs": len(values),
                         "difference_pp": round(100 * mean(values), 3) if values else None}
        if len(cells) == 2:
            outcomes[key].update(pass_gain_pairs=values.count(1), pass_loss_pairs=values.count(-1),
                                 unchanged_pairs=values.count(0))
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
        successes = [row["cost"][field] for row in rows if row["metrics"]["SCOPED_COMPLETION"] == "PASS"
                     and row["cost"][field] is not None]
        costs[field] = {
            "observations": len(values), "total": sum(values) if values else None,
            "per_success": round(sum(values) / denominator, 4) if denominator and len(values) == len(rows) else None,
            "attempt_percentiles": percentile(values),
            "successful_trajectory_percentiles": percentile(successes),
        }
    report = {"observed": len(rows), "metric_counts": totals, "cost": costs}
    for field in (*VERDICTS, *ADDED_METRICS):
        grouped = Counter(row["metrics"][field] for row in rows)
        totals[field] = {key: grouped[key] for key in OUTCOMES}
    binding_counts = Counter()
    for row in rows:
        binding_counts.update(row["typed_callback_counts"])
    return report | {"event_rates": {key: event_rate(rows, *value) for key, value in RATE_COUNTS.items()},
                     "typed_callback_counts": dict(binding_counts),
                     "failure_signatures": dict(Counter(row["failure_signature"] for row in rows))}


def atlas_views(cells, slots, cases):
    strata = defaultdict(list)
    for slot in slots:
        case_id, weight, track, seed = (slot[key] for key in ("case_id", "weight", "track", "seed"))
        public, _, oracle = cases[case_id]
        row = cells[weight, track].get((case_id, seed))
        for key, value in (("all", "all"), ("family", public["family"]), ("language", public["language"]),
                           ("risk_scope", oracle["risk_scope"])):
            strata[weight, track, key, value].append((row, public, oracle))
    dimensions = {"/".join(key): summarize_stratum(rows, key[1]) for key, rows in strata.items()}

    pairs = defaultdict(list)
    repeat_ids = {slot["case_id"] for slot in slots if slot["track"] == "sdk_repeat"}
    for weight, case_id in product(WEIGHTS, cases):
        case_key = (case_id, FIRST_SEED)
        first, stream = (cells[weight, track].get(case_key) for track in ("sdk_first", "sdk_streaming"))
        public, _, oracle = cases[case_id]
        repeats = [cells[weight, "sdk_repeat"].get((case_id, seed)) for seed in REPEAT_SEEDS]
        for key, value in (("all", "all"), ("family", public["family"]), ("language", public["language"]),
                           ("risk_scope", oracle["risk_scope"])):
            pairs[weight, "STREAMING_CONSISTENCY", key, value].append(
                (True, compare_paths(first, stream), bool(first and stream)))
            if case_id in repeat_ids:
                applicable = oracle["risk_scope"] == "synthetic-read-only" and bool(oracle["nodes"])
                pairs[weight, "REPEAT_RELIABILITY", key, value].append(
                    (applicable, repeat_status(repeats) if applicable else "NOT_RUN", all(repeats)))
    return {"dimensions": dimensions, "paired_cases": {"/".join(key): {
        **metric_cell((applicable, status) for applicable, status, _ in rows),
        "planned_case_pairs": len(rows), "complete_seal_groups": sum(sealed for _, _, sealed in rows),
    } for key, rows in pairs.items()}}


def replay(suite, folder, *, paired_rows=None, through_batches=None):
    cases, input_sha = load_inputs(suite)
    batches, freeze = build_plan(suite, cases, input_sha)
    if through_batches is not None and not 1 <= through_batches <= len(batches):
        raise ValueError("Requested checkpoint is outside the frozen batch roster")
    cells = defaultdict(dict)
    seals = []
    done = 0
    for number, batch in enumerate(batches[:through_batches]):
        path = folder / f"batch-{number:03d}"
        if not (path / "seal.json").exists():
            continue
        seal = verify_batch(path, batch, freeze)
        seals.append({"run_id": seal["run_id"], "seal_sha256": digest(path / "seal.json"),
                      "git_sha": seal["git_sha"], "batch_sha256": seal["batch_sha256"],
                      "weight": seal["weights"],
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
            detail = trial_detail(trial, oracle, assessment, typed_callback=row["profile"] == CORRECTED)
            cells[row["weight"], factor][row["case_id"], row["seed"]] = detail
            if paired_rows is not None:
                paired_rows.append({key: row[key] for key in
                                    ("slot_id", "trial_id", "case_id", "weight", "profile", "track", "seed",
                                     "capture_sha256")}
                                   | {"run_id": seal["run_id"], "git_sha": seal["git_sha"],
                                      "seal_sha256": seals[-1]["seal_sha256"]}
                                   | detail)
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
    resources = {weight: percentile([seal["peak_gpu_committed_bytes"] for seal in seals
                                     if seal["weight"] == weight and seal["peak_gpu_committed_bytes"] is not None])
                 for weight in WEIGHTS}
    base_peak = resources["Original"]["p50"]
    for resource in resources.values():
        peak = resource["p50"]
        resource["median_peak_bytes_delta_vs_original"] = peak - base_peak if None not in (peak, base_peak) else None
    return freeze | {"executed": done, "unexecuted": freeze["planned"] - done,
                     "coverage": "PASS" if done == freeze["planned"] else "BLOCKED",
                     "batch_seals": seals, "arms": arms, "weight_gains": weight_gains,
                     "runtime_gains": runtime_gains, "interactions": interactions, "compatibility_atlas": atlas,
                     "peak_gpu_committed_bytes": resources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=("transfer", "tc-extension"))
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paired-output", type=Path, help="Write a privacy-safe matched JSONL gzip archive")
    parser.add_argument("--through-batches", type=int, help="Replay the frozen roster prefix at a checkpoint")
    args = parser.parse_args()
    paired = [] if args.paired_output else None
    report = replay(args.suite, args.captures, paired_rows=paired, through_batches=args.through_batches)
    if args.paired_output:
        raw = b"".join(canonical(row) + b"\n" for row in paired)
        check_text(raw)
        args.paired_output.write_bytes(gzip.compress(raw, mtime=0))
        report["paired_archive"] = {"filename": args.paired_output.name, "rows": len(paired),
                                    "sha256": digest(args.paired_output)}
    check_text(canonical(report))
    write_json(args.output, report)
    print(report["coverage"], report["executed"], report["planned"])


if __name__ == "__main__":
    main()
