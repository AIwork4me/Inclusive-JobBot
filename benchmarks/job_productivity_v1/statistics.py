"""Validate paired JOB-V1 trial evidence and compute reproducible contrasts."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import re


ARMS = tuple("ABCDEF")
CONTRASTS = (("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("D", "F"))
SAFETY_FIELDS = ("unauthorized_effects", "unconfirmed_commits", "duplicate_commits", "false_approvals")
COUNT_FIELDS = (
    "model_calls", "prompt_tokens", "completion_tokens", "argument_correct", "argument_total",
    "invalid_calls", "tool_calls", "correct_escalations", *SAFETY_FIELDS,
)


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True).encode("ascii")).hexdigest()


def _case_identity(row: dict) -> tuple[str, str, str]:
    if not isinstance(row, dict):
        raise ValueError("each trial or plan row must be an object")
    case_id, category, pairing = (row.get(field) for field in ("case_id", "category", "pairing_sha256"))
    if not all(isinstance(value, str) and value.strip() for value in (case_id, category, pairing)):
        raise ValueError("case identity requires case_id, category and pairing_sha256")
    if re.fullmatch("[0-9a-f]{64}", pairing) is None:
        raise ValueError(f"invalid pairing SHA-256 for {case_id}")
    return case_id, category, pairing


def _validate_row(row: dict, arm: str) -> tuple[str, str, str]:
    identity = _case_identity(row)
    if row.get("status") not in {"PASS", "FAIL"}:
        raise ValueError("paired contrasts require a completed PASS/FAIL verdict for every case")
    if any(type(row.get(field)) is not bool for field in ("routine", "first_pass_success", "completed")):
        raise ValueError("routine, first_pass_success and completed require boolean values")
    if row["status"] == "FAIL" and (row["first_pass_success"] or row["completed"]):
        raise ValueError("failed cases cannot count as first-pass successes or correct business completions")
    if any(type(row.get(field)) is not int or row[field] < 0 for field in COUNT_FIELDS):
        raise ValueError("cost, argument and safety counters must be explicit nonnegative integers")
    if row["argument_correct"] > row["argument_total"] or row["invalid_calls"] > row["tool_calls"]:
        raise ValueError("correct argument or invalid call count exceeds its denominator")
    if "business_writes" in row or "correct_business_writes" in row:
        writes, correct = (row.get(field) for field in ("business_writes", "correct_business_writes"))
        if any(type(value) is not int for value in (writes, correct)) or not 0 <= correct <= writes:
            raise ValueError("business_writes and correct_business_writes must be measured together")
    if row["correct_escalations"] not in (0, 1) or (
        row["correct_escalations"] and (row["completed"] or row["status"] != "PASS")
    ):
        raise ValueError("correct escalation requires a passing escalation outcome without completion")
    duration = row.get("machine_ms")
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
        raise ValueError("machine_ms must be a finite nonnegative number")
    if arm == "F" and any(row[field] for field in ("model_calls", "prompt_tokens", "completion_tokens")):
        raise ValueError("No-LLM Arm F cannot report model calls or tokens")
    return identity


def wilson_interval(successes: int, trials: int) -> list[float] | None:
    """Two-sided 95% Wilson score interval for a case-level proportion."""
    if not 0 <= successes <= trials:
        raise ValueError("success count must lie within the trial count")
    if not trials:
        return None
    z = 1.959963984540054
    p = successes / trials
    square = z**2
    center = (p + square / (2 * trials)) / (1 + square / trials)
    radius = z * math.sqrt(p * (1 - p) / trials + square / (4 * trials**2)) / (1 + square / trials)
    return [max(0.0, center - radius), min(1.0, center + radius)]


def zero_event_upper_95(trials: int) -> float | None:
    """One-sided 95% exact binomial upper bound from zero observed cases."""
    if trials < 0:
        raise ValueError("trial count cannot be negative")
    return -math.expm1(math.log(0.05) / trials) if trials else None


def exact_mcnemar(old_only: int, new_only: int) -> float:
    """Two-sided exact McNemar p from the binomial tail on discordant pairs."""
    if min(old_only, new_only) < 0:
        raise ValueError("pair counts cannot be negative")
    discordant = old_only + new_only
    if not discordant:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(old_only, new_only) + 1))
    return min(1.0, (2 * tail) / 2**discordant)


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def _proportion(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator, "denominator": denominator, "rate": _ratio(numerator, denominator),
        "wilson_ci95": wilson_interval(numerator, denominator),
    }


def _percentile(sorted_values: list, q: float) -> float | None:
    if not sorted_values:
        return None
    rank = (len(sorted_values) - 1) * q
    low = math.floor(rank)
    high = math.ceil(rank)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (rank - low)


def _summarize_arm(rows: list[dict]) -> dict:
    n = len(rows)
    routine = [row for row in rows if row["routine"]]
    completed = sum(row["completed"] for row in rows)
    calls = sum(row["model_calls"] for row in rows)
    prompt, completion = (sum(row[field] for row in rows) for field in ("prompt_tokens", "completion_tokens"))
    argument_correct = sum(row["argument_correct"] for row in rows)
    argument_total = sum(row["argument_total"] for row in rows)
    tool_calls = sum(row["tool_calls"] for row in rows)
    invalid_calls = sum(row["invalid_calls"] for row in rows)
    observed_writes = all("business_writes" in row for row in rows)
    writes = sum(row["business_writes"] for row in rows) if observed_writes else None
    correct_writes = sum(row["correct_business_writes"] for row in rows) if observed_writes else None
    durations = sorted(row["machine_ms"] for row in routine)
    safety = {}
    for field in SAFETY_FIELDS:
        event_count = sum(row[field] for row in rows)
        affected = sum(row[field] > 0 for row in rows)
        safety[field] = {
            "events": event_count,
            "affected_cases": affected,
            "cases_observed": n,
            "zero_event_one_sided_upper_95": zero_event_upper_95(n) if affected == 0 else None,
        }
    return {
        "task_success": _proportion(sum(row["status"] == "PASS" for row in rows), n),
        "first_pass_accuracy": _proportion(sum(row["first_pass_success"] for row in rows), n),
        "routine_completion": _proportion(sum(row["completed"] for row in routine), len(routine)),
        "completed_business_tasks": completed,
        "correct_escalations": sum(row["correct_escalations"] for row in rows),
        # Multiple parameters within a single task are statistically clustered.
        "all_step_argument_accuracy": {
            "numerator": argument_correct, "denominator": argument_total,
            "rate": _ratio(argument_correct, argument_total),
        },
        "invalid_call_rate": {"numerator": invalid_calls, "denominator": tool_calls,
                              "rate": _ratio(invalid_calls, tool_calls)},
        "business_writes_correct": (
            {"numerator": correct_writes, "denominator": writes, "rate": _ratio(correct_writes, writes)}
            if observed_writes else None
        ),
        "model_calls": calls, "prompt_tokens": prompt, "completion_tokens": completion,
        "model_calls_per_task": _ratio(calls, n),
        "model_calls_per_successful_task": _ratio(calls, completed),
        "tokens_per_successful_task": _ratio(prompt + completion, completed),
        "routine_machine_ms": {
            "sample_count": len(durations), "p50": _percentile(durations, 0.50),
            "p95": _percentile(durations, 0.95), "p99": _percentile(durations, 0.99),
        },
        "safety": safety,
    }


def _paired_contrast(old: dict[str, dict], new: dict[str, dict], *,
                     bootstrap_samples: int, seed: int) -> dict:
    diffs_by_category = defaultdict(list)
    differences = []
    pair_counts = Counter()
    for case_id in sorted(old):
        start, end = old[case_id], new[case_id]
        before, after = start["status"] == "PASS", end["status"] == "PASS"
        delta = int(after) - int(before)
        pair_counts[before, after] += 1
        diffs_by_category[start["category"]].append(delta)
        differences.append({"case_id": case_id, "old_success": before, "new_success": after,
                            "difference": delta})
    n = len(old)
    old_only = pair_counts[True, False]
    new_only = pair_counts[False, True]
    delta = new_only - old_only
    grouped = [diffs_by_category[category] for category in sorted(diffs_by_category)]
    rng = random.Random(seed)
    resampled = sorted(
        100 * sum(sum(rng.choices(items, k=len(items))) for items in grouped) / n
        for _ in range(bootstrap_samples)
    )
    return {
        "paired_cases": n,
        "both_successful": pair_counts[True, True],
        "both_unsuccessful": pair_counts[False, False],
        "old_only": old_only, "new_only": new_only,
        "absolute_gain_percentage_points": 100 * delta / n,
        "relative_improvement": _ratio(delta, old_only + pair_counts[True, True]),
        "exact_mcnemar_p": exact_mcnemar(old_only, new_only),
        "paired_bootstrap_ci95_percentage_points": [
            _percentile(resampled, 0.025), _percentile(resampled, 0.975),
        ],
        "case_level_differences": differences,
    }


def analyze(arms: dict[str, list[dict]], *, bootstrap_samples: int = 10000, seed: int,
            planned_cases: list[dict] | None = None) -> dict:
    """Compute primary per-arm and paired statistics from all six complete arms."""
    if (not isinstance(arms, dict) or set(arms) != set(ARMS)
            or type(bootstrap_samples) is not int or bootstrap_samples < 100):
        raise ValueError("require exactly arms A–F and at least 100 bootstrap samples")
    if type(seed) is not int:
        raise ValueError("bootstrap seed must be an integer")
    index, reference, routine = {}, None, None
    for arm in ARMS:
        by_id, identities, routine_flags = {}, {}, {}
        if not isinstance(arms[arm], list):
            raise ValueError(f"arm {arm} must contain a list of rows")
        for row in arms[arm]:
            case_id, category, pairing = _validate_row(row, arm)
            if case_id in by_id:
                raise ValueError(f"duplicate case {case_id} in arm {arm}")
            by_id[case_id] = row
            identities[case_id] = (category, pairing)
            routine_flags[case_id] = row["routine"]
        if not by_id:
            raise ValueError(f"arm {arm} contains no cases")
        if reference is not None and (reference != identities or routine != routine_flags):
            raise ValueError(f"arm {arm} has different paired case identities or routine flags")
        reference, routine = identities, routine_flags
        index[arm] = by_id
    if planned_cases is not None:
        if not isinstance(planned_cases, list):
            raise ValueError("planned roster must be a list")
        planned = {}
        for row in planned_cases:
            case_id, category, pairing = _case_identity(row)
            if case_id in planned:
                raise ValueError(f"duplicate case {case_id} in planned roster")
            planned[case_id] = (category, pairing)
        if reference != planned:
            raise ValueError("measured case coverage differs from planned roster")
    summaries = {arm: _summarize_arm(arms[arm]) for arm in ARMS}
    small = summaries["D"]["task_success"]["numerator"]
    large = summaries["E"]["task_success"]["numerator"]
    general_calls = summaries["A"]["model_calls_per_successful_task"]
    purpose_calls = summaries["D"]["model_calls_per_successful_task"]
    general_tokens = summaries["A"]["tokens_per_successful_task"]
    purpose_tokens = summaries["D"]["tokens_per_successful_task"]
    return {
        "paired_cases": len(reference),
        "planned_roster_checked": planned_cases is not None,
        "case_counts_by_category": dict(Counter(category for category, _ in reference.values())),
        "pairing_manifest_sha256": _digest(reference),
        "bootstrap": {"method": "percentile stratified paired case resampling", "samples": bootstrap_samples,
                      "seed": seed},
        "arms": summaries,
        "comparisons": {
            f"{old}-{new}": _paired_contrast(index[old], index[new], bootstrap_samples=bootstrap_samples,
                                             seed=seed)
            for old, new in CONTRASTS
        },
        "d_to_e_task_success_ratio": _ratio(small, large),
        "d_to_a_model_calls_per_successful_task_ratio": (
            _ratio(purpose_calls, general_calls) if purpose_calls is not None and general_calls is not None else None
        ),
        "d_to_a_tokens_per_successful_task_ratio": (
            _ratio(purpose_tokens, general_tokens) if purpose_tokens is not None and general_tokens is not None else None
        ),
    }


def _selection_hash(plan: dict) -> str:
    return _digest({key: value for key, value in plan.items() if key != "selection_sha256"})


def _valid_trial_seeds(value) -> bool:
    return (isinstance(value, (list, tuple)) and len(value) == 3
            and all(type(seed) is int for seed in value) and len(set(value)) == 3)


def select_repeats(cases: list[dict], *, n: int = 50, seed: int,
                   trial_seeds: tuple[int, ...] | None = None) -> dict:
    """Choose a proportional stratified subset from the pre-result case plan."""
    if (not isinstance(cases, list) or type(n) is not int or type(seed) is not int
            or n < 50 or n > len(cases)):
        raise ValueError("repeat selection requires an integer seed and at least 50 available cases")
    if trial_seeds is None:
        trial_seeds = tuple(int(_digest([seed, "repeat", index])[:7], 16) for index in range(3))
    if not _valid_trial_seeds(trial_seeds):
        raise ValueError("repeat selection requires exactly three distinct integer trial seeds")
    groups = defaultdict(list)
    seen = set()
    for row in cases:
        case_id, category, pairing = _case_identity(row)
        if case_id in seen:
            raise ValueError(f"duplicate repeat plan case {case_id}")
        seen.add(case_id)
        groups[category].append({"case_id": case_id, "category": category, "pairing_sha256": pairing})
    if n < len(groups):
        raise ValueError("repeat subset must include at least one case per category")
    quotas = {category: n * len(group) for category, group in groups.items()}
    sizes = {category: max(1, quota // len(cases)) for category, quota in quotas.items()}

    def deficit(category):
        return quotas[category] - sizes[category] * len(cases)

    while sum(sizes.values()) < n:
        category = max((name for name, group in groups.items() if sizes[name] < len(group)),
                       key=lambda name: (deficit(name), name))
        sizes[category] += 1
    while sum(sizes.values()) > n:
        category = min((name for name, count in sizes.items() if count > 1),
                       key=lambda name: (deficit(name), name))
        sizes[category] -= 1

    selected = []
    for category in sorted(groups):
        ranked = sorted(groups[category], key=lambda row: (_digest([seed, row["case_id"]]), row["case_id"]))
        selected.extend(ranked[:sizes[category]])
    plan = {
        "selection_method": "proportional stratified allocation and seeded SHA-256 ranking",
        "seed": seed,
        "trial_seeds": list(trial_seeds),
        "source_plan_sha256": _digest(sorted(
            (row for group in groups.values() for row in group), key=lambda row: row["case_id"]
        )),
        "cases": sorted(selected, key=lambda row: row["case_id"]),
    }
    return {**plan, "selection_sha256": _selection_hash(plan)}


def repeat_summary(selection: dict, arms: dict[str, list[dict]]) -> dict:
    """Require the same 3 scheduled trials per selected case per arm."""
    if not isinstance(selection, dict) or selection.get("selection_sha256") != _selection_hash(selection):
        raise ValueError("repeat selection digest mismatch")
    trial_seeds = selection.get("trial_seeds")
    if not _valid_trial_seeds(trial_seeds) or not isinstance(arms, dict) or set(arms) != set(ARMS):
        raise ValueError("require exactly arms A–F and three distinct integer trial seeds")
    identities = {}
    for item in selection["cases"]:
        case_id, category, pairing = _case_identity(item)
        if case_id in identities:
            raise ValueError(f"duplicate repeat selection case {case_id}")
        identities[case_id] = (category, pairing)
    if len(identities) < 50:
        raise ValueError("repeat schedule has fewer than 50 cases")
    expected = {(case_id, seed) for case_id in identities for seed in trial_seeds}
    summaries = {}
    for arm in ARMS:
        trials = {}
        if not isinstance(arms[arm], list):
            raise ValueError(f"arm {arm} must contain a list of repeated trials")
        for row in arms[arm]:
            case_id, category, pairing = _validate_row(row, arm)
            key = (case_id, row.get("trial_seed"))
            if (type(key[1]) is not int or key not in expected or key in trials
                    or identities.get(case_id) != (category, pairing)):
                raise ValueError(f"invalid or duplicate repeated trial for {case_id}, arm {arm}")
            trials[key] = row["status"] == "PASS"
        if trials.keys() != expected:
            raise ValueError(f"incomplete repeated trials for arm {arm}")
        per_case = {
            case_id: sum(trials[case_id, seed] for seed in trial_seeds) for case_id in sorted(identities)
        }
        summaries[arm] = {
            "all_three_successful": _proportion(sum(count == 3 for count in per_case.values()), len(per_case)),
            "successes_per_case": per_case,
        }
    return {"selection_sha256": selection["selection_sha256"], "trial_seeds": list(trial_seeds), "arms": summaries}


def _read_document(path: Path):
    def unique_object(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError("duplicate JSON key in analysis input")
            obj[key] = value
        return obj

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    first = sub.add_parser("analyze")
    first.add_argument("--input", type=Path, required=True, help="JSON object mapping arm to measured trial rows")
    first.add_argument("--plan", type=Path, required=True, help="JSON array of pre-result case identities")
    first.add_argument("--seed", type=int, required=True)
    first.add_argument("--bootstrap-samples", type=int, default=10000)
    plan = sub.add_parser("select-repeats")
    plan.add_argument("--input", type=Path, required=True, help="JSON array of pre-result case identities")
    plan.add_argument("--seed", type=int, required=True)
    plan.add_argument("--count", type=int, default=50)
    plan.add_argument("--trial-seeds", type=int, nargs=3)
    repeats = sub.add_parser("summarize-repeats")
    repeats.add_argument("--input", type=Path, required=True, help="JSON object mapping arm to repeated trial rows")
    repeats.add_argument("--selection", type=Path, required=True)
    for command in (first, plan, repeats):
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        body = _read_document(args.input)
        if args.command == "analyze":
            result = analyze(body, bootstrap_samples=args.bootstrap_samples, seed=args.seed,
                             planned_cases=_read_document(args.plan))
        elif args.command == "select-repeats":
            result = select_repeats(body, seed=args.seed, n=args.count, trial_seeds=args.trial_seeds)
        else:
            result = repeat_summary(_read_document(args.selection), body)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(result, output, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            output.write("\n")
    except (OSError, ValueError) as error:
        parser.exit(2, f"FAIL: {error}\n")
    print("PASS: wrote deterministic JOB-V1 analysis artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
