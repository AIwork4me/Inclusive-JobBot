"""Analyze prespecified first-attempt and repeat results from paired IJ-0.7 arms."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import re

from benchmarks.job_productivity_v1.statistics import exact_mcnemar, wilson_interval


ROOT = Path(__file__).resolve().parents[1]
SUITES = {"TC-V2": (500, 50), "MULTITOOL-V1": (600, 100), "AGENTIC-PLAN-V1": (800, 160)}
STATUSES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
MEASURED = frozenset(STATUSES[:2])
STRATA = ("task_type", "complexity", "language")
ARM_FIELDS = ("model", "backend", "device", "track", "quantization", "thinking", "protocol", "controls_sha256")
VARY = {"model", "backend", "thinking", "quantization", "protocol"}


def digest(value) -> str:
    """Canonical SHA-256 of a JSON value, independent of formatting and key order."""
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")).hexdigest()


def _check(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _sha(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def _seed(value):
    return type(value) is int and 0 <= value < 2**32 - 1


def _object(value, fields, description):
    _check(isinstance(value, dict) and set(fields) <= value.keys(), f"incomplete {description}")


def _checked_bytes(path, expected):
    raw = path.read_bytes()
    _check(sha256(raw).hexdigest() == expected, f"frozen artifact differs: {path.name}")
    return raw


def _json_rows(raw, key):
    result = {}
    for line in raw.splitlines():
        row = json.loads(line)
        _check(row[key] not in result, f"duplicate frozen case: {row[key]}")
        result[row[key]] = row
    return result


def _case(case_id, payload, task_type, complexity, language):
    return {"case_id": case_id, "pairing_sha256": digest(payload), "task_type": task_type,
            "complexity": str(complexity), "language": language}


def frozen_suite(suite):
    """Build the roster and panel directly from the three archived suite freezes."""
    profile = {"suite": suite}
    if suite == "TC-V2":
        root = ROOT / "tool_calling_v2/holdout"
        manifest = json.loads((root / "manifest.json").read_bytes())
        entry = manifest["split"]["holdout"]
        panel = manifest["repeat"]
        rows = _json_rows(_checked_bytes(root / entry["path"], entry["sha256"]), "id")
        cases = [_case(key, row, row["category"], len(row["oracle"]["steps"]), row["language"])
                 for key, row in rows.items()]
        profile.update(dataset_sha256=entry["sha256"], first_seed=manifest["first_pass_seed"])
        repeat = {"case_ids": panel["cases"], "seeds": panel["seeds"]}
    elif suite == "MULTITOOL-V1":
        root = ROOT / "multitool_v1/frozen"
        manifest = json.loads((root / "manifest.json").read_bytes())
        files = {name: _checked_bytes(root / name, expected) for name, expected in manifest["sha256"].items()}
        canonical_hashes = json.dumps(manifest["sha256"], sort_keys=True, ensure_ascii=False,
                                      separators=(",", ":")).encode("utf-8") + b"\n"
        _check(sha256(canonical_hashes).hexdigest() == manifest["freeze_sha256"], "MULTITOOL-V1 freeze differs")
        panel = json.loads(files["repeat_panel.json"])
        prompts, worlds, oracles = (_json_rows(files[f"{name}.jsonl"], "case_id")
                                   for name in ("prompts", "worlds", "oracles"))
        _check(prompts.keys() == worlds.keys() == oracles.keys(), "MULTITOOL-V1 partitions differ")
        cases = [_case(key, [prompt, worlds[key], oracles[key]], oracles[key]["category"], oracles[key]["depth_bin"],
                       oracles[key]["language"]) for key, prompt in prompts.items() if prompt["split"] == "holdout"]
        profile["dataset_sha256"] = manifest["freeze_sha256"]
        repeat = {key: panel[key] for key in ("case_ids", "seeds")}
    elif suite == "AGENTIC-PLAN-V1":
        root = ROOT / "agentic_planning_v1"
        manifest = json.loads((root / "datasets/manifest.json").read_bytes())
        files = {name: _checked_bytes(root / name, expected)
                 for name, expected in manifest["artifact_sha256"].items()}
        prompts, graphs = (_json_rows(files[f"{name}/holdout.jsonl"], "case_id")
                           for name in ("datasets", "task_graphs"))
        _check(prompts.keys() == graphs.keys(), "AGENTIC-PLAN-V1 partitions differ")
        panel = json.loads(files["datasets/repeat_panel.json"])
        cases = [_case(key, [prompt, graphs[key]], prompt["domain"], prompt["level"], prompt["language"])
                 for key, prompt in prompts.items()]
        _check(Counter(prompts[row["case_id"]]["level"] for row in panel["cases"]) == {
            f"L{level}": 20 for level in range(8)
        }, "AGENTIC-PLAN-V1 repeat levels differ")
        profile["dataset_sha256"] = manifest["artifact_sha256"]["datasets/holdout.jsonl"]
        repeat = {"case_ids": [row["case_id"] for row in panel["cases"]], "seeds": panel["seeds"]}
    else:
        raise ValueError(f"unknown canonical suite: {suite}")
    _check((len(cases), len(set(repeat["case_ids"]))) == SUITES[suite], "frozen case or panel coverage differs")
    return {**profile, "cases": sorted(cases, key=lambda row: row["case_id"]), "repeat": repeat}


def _case_index(rows):
    _check(isinstance(rows, list) and rows, "a nonempty case roster is required")
    by_id = {}
    for row in rows:
        _object(row, ("case_id", "pairing_sha256", *STRATA), "case identity")
        key = row["case_id"]
        _check(all(_text(row[field]) for field in ("case_id", *STRATA)) and _sha(row["pairing_sha256"]),
               "case ID, pairing digest and strata are required")
        _check(key not in by_id, f"duplicate planned case: {key}")
        by_id[key] = row
    return dict(sorted(by_id.items()))


def _validate_comparisons(comparisons, arms):
    _check(isinstance(comparisons, list) and comparisons, "prespecified comparisons are required")
    seen_ids, seen_pairs = set(), set()
    for row in comparisons:
        _object(row, ("id", "left", "right", "vary"), "comparison")
        key, left, right, vary = (row[field] for field in ("id", "left", "right", "vary"))
        _check(all(_text(item) for item in (key, left, right, vary))
               and left in arms and right in arms and left != right and vary in VARY,
               "comparison arms or varying factor are invalid")
        pair = frozenset((left, right))
        _check(key not in seen_ids and pair not in seen_pairs, "duplicate comparison or arm pair")
        seen_ids.add(key)
        seen_pairs.add(pair)
        different = {field for field in ARM_FIELDS if arms[left][field] != arms[right][field]}
        _check(different == {vary}, f"comparison {key} requires matched controls except {vary}")
        minimum = row.get("business_minimum_gain_pp")
        _check(minimum is None or (type(minimum) in (int, float) and 0 <= minimum <= 100),
               "business minimum gain must be within 0 to 100 percentage points")


def _validate_plan(plan, expected_plan_sha256):
    _object(plan, ("schema_version", "suite", "dataset_sha256", "cases", "arms", "repeat",
                   "first_seed", "bootstrap", "comparisons"), "statistics plan")
    _check(_sha(expected_plan_sha256) and digest(plan) == expected_plan_sha256, "plan digest differs from its freeze")
    _check(type(plan["schema_version"]) is int and plan["schema_version"] == 1
           and _text(plan["suite"]) and _sha(plan["dataset_sha256"]) and _seed(plan["first_seed"]),
           "invalid plan version, suite, dataset identity or initial seed")
    cases = _case_index(plan["cases"])
    panel, bootstrap = plan["repeat"], plan["bootstrap"]
    _object(panel, ("case_ids", "seeds"), "repeat panel")
    _object(bootstrap, ("seed", "samples"), "bootstrap plan")
    _check(isinstance(panel["case_ids"], list) and panel["case_ids"] and all(map(_text, panel["case_ids"]))
           and len(set(panel["case_ids"])) == len(panel["case_ids"]) and set(panel["case_ids"]) <= cases.keys(),
           "repeat panel must give unique prespecified cases from the holdout")
    _check(isinstance(panel["seeds"], list) and len(panel["seeds"]) == 3 and all(map(_seed, panel["seeds"]))
           and len(set(panel["seeds"])) == 3, "repeat panel requires three distinct ordered seeds")
    _check(_seed(bootstrap["seed"]) and type(bootstrap["samples"]) is int and bootstrap["samples"] >= 100,
           "bootstrap requires an integer seed and at least 100 draws")
    if plan["suite"] in SUITES:
        source = frozen_suite(plan["suite"])
        _check(cases == _case_index(source["cases"]) and panel == source["repeat"]
               and plan["dataset_sha256"] == source["dataset_sha256"]
               and plan["first_seed"] == source.get("first_seed", plan["first_seed"]),
               "statistics plan differs from canonical frozen holdout or repeat panel")
    arms = plan["arms"]
    _check(isinstance(arms, dict) and len(arms) >= 2, "at least two planned arms are required")
    seen = set()
    for arm, identity in arms.items():
        _object(identity, (*ARM_FIELDS, "configuration_sha256"), f"configuration for arm {arm}")
        _check(_text(arm) and all(_text(identity[key]) for key in ("model", "backend", "device", "quantization", "protocol"))
               and identity["track"] in ("controlled", "best_practice") and type(identity["thinking"]) is bool
               and _sha(identity["controls_sha256"]) and _sha(identity["configuration_sha256"]),
               f"invalid arm identity: {arm}")
        _check(identity["configuration_sha256"] not in seen, "arm configurations must be distinct")
        seen.add(identity["configuration_sha256"])
    _validate_comparisons(plan["comparisons"], arms)
    return cases


def _index_results(bundle, plan, cases):
    _object(bundle, ("schema_version", "evidence_class", "runs", "rows"), "normalized evidence bundle")
    _check(type(bundle["schema_version"]) is int and bundle["schema_version"] == 1
           and bundle["evidence_class"] in ("local_model", "synthetic_software_test")
           and isinstance(bundle["runs"], dict) and isinstance(bundle["rows"], list), "invalid evidence bundle")
    if bundle["evidence_class"] == "local_model":
        _check(plan["suite"] in SUITES, "local-model evidence requires a canonical suite")

    run_phases = set()
    for run_id, run in bundle["runs"].items():
        _object(run, ("arm", "configuration_sha256", "run_configuration_sha256", "dataset_sha256", "phases"),
                "run identity")
        arm = run["arm"]
        _check(_text(run_id) and _text(arm) and arm in plan["arms"]
               and run["configuration_sha256"] == plan["arms"][arm]["configuration_sha256"]
               and _sha(run["run_configuration_sha256"])
               and run["dataset_sha256"] == plan["dataset_sha256"]
               and isinstance(run["phases"], list) and run["phases"]
               and all(phase in ("first", "repeat") for phase in run["phases"])
               and len(set(run["phases"])) == len(run["phases"]), "run differs from frozen configuration")
        for phase in run["phases"]:
            _check((arm, phase) not in run_phases, f"multiple {phase} runs for arm {arm}")
            run_phases.add((arm, phase))

    rows = {arm: {} for arm in plan["arms"]}
    panel_ids = set(plan["repeat"]["case_ids"])
    seeds = plan["repeat"]["seeds"]
    for trial in bundle["rows"]:
        _object(trial, ("arm", "case_id", "pairing_sha256", "phase", "repeat_index", "attempt", "seed",
                        "status", "run_id", "configuration_sha256", "run_configuration_sha256",
                        "evidence_sha256", "failure_class"), "trial row")
        arm, case_id, phase, run_id = (trial[key] for key in ("arm", "case_id", "phase", "run_id"))
        _check(all(map(_text, (arm, case_id, phase, run_id))) and arm in rows and case_id in cases
               and run_id in bundle["runs"], "trial outside the frozen arm, case or run identity")
        run = bundle["runs"][run_id]
        _check(arm == run["arm"] and phase in run["phases"] and trial["configuration_sha256"] == run["configuration_sha256"]
               and trial["run_configuration_sha256"] == run["run_configuration_sha256"]
               and trial["pairing_sha256"] == cases[case_id]["pairing_sha256"]
               and _sha(trial["evidence_sha256"]) and type(trial["attempt"]) is int and trial["attempt"] == 1
               and _seed(trial["seed"]), "trial run, first attempt or pairing identity differs")
        index = trial["repeat_index"]
        if phase == "first":
            _check(index is None and trial["seed"] == plan["first_seed"], "primary first-attempt seed or index differs")
        else:
            _check(case_id in panel_ids and type(index) is int and 1 <= index <= 3
                   and trial["seed"] == seeds[index - 1], "trial is outside the prespecified repeat panel or seeds")
        status, failure = trial["status"], trial["failure_class"]
        _check(status in STATUSES and (_text(failure) if status == "FAIL" else failure is None or _text(failure)),
               "invalid trial status or missing failure class")
        _check(status != "PASS" or failure is None, "passing trial has a failure class")
        key = (case_id, phase, index)
        _check(key not in rows[arm], f"duplicate trial: {arm} {key}")
        rows[arm][key] = trial
    return rows


def _scope(case):
    return tuple(case[field] for field in STRATA)


def _groups(cases):
    groups = {"overall": list(cases)}
    for case_id, case in cases.items():
        for field in STRATA:
            groups.setdefault(f"{field}:{case[field]}", []).append(case_id)
    return dict(sorted(groups.items()))


def _coverage(outcomes):
    return "PASS" if all(outcome in MEASURED for outcome in outcomes) else (
        "NOT_RUN" if all(outcome == "NOT_RUN" for outcome in outcomes) else "BLOCKED"
    )


def _proportion(outcomes):
    counts = {status: outcomes.count(status) for status in STATUSES}
    n = len(outcomes)
    success = counts["PASS"]
    complete = _coverage(outcomes)
    return {"status": complete, "status_counts": counts, "denominator": n,
            "rate": success / n if complete == "PASS" else None,
            "rate_bounds": [success / n, (n - counts["FAIL"]) / n],
            "wilson_ci95": wilson_interval(success, n) if complete == "PASS" else None}


def _status(rows, case_id, phase, index=None):
    return rows.get((case_id, phase, index), {}).get("status", "NOT_RUN")


def _repeat_metric(trials, all_required):
    """Classify known success, known failure or still unresolved for each case."""
    if all_required and "FAIL" in trials:
        return "FAIL"
    if not all_required and "PASS" in trials:
        return "PASS"
    if all(value in MEASURED for value in trials):
        return "PASS" if all_required else "FAIL"
    return "BLOCKED" if "BLOCKED" in trials or any(value in MEASURED for value in trials) else "NOT_RUN"


def _transition_matrix(counts, labels):
    return {left: {right: counts[left, right] for right in labels} for left in labels}


def _repeat_summary(rows, ids, seeds):
    observed = [[_status(rows, case_id, "repeat", index) for index in range(1, 4)] for case_id in ids]
    first, second, third = zip(*observed)
    per_seed = {str(seed): _proportion(values) for seed, values in zip(seeds, (first, second, third))}
    rates = [item["rate"] for item in per_seed.values()]
    variance = None
    if all(rate is not None for rate in rates):
        mean = sum(rates) / len(rates)
        variance = sum((rate - mean) ** 2 for rate in rates) / len(rates)

    transitions, failure_transitions = {}, {}
    for offset, (left, right) in enumerate(zip(seeds, seeds[1:]), 1):
        key = f"{left}->{right}"
        transitions[key] = _transition_matrix(Counter((trials[offset - 1], trials[offset]) for trials in observed), STATUSES)
        labels = []
        for case_id, statuses in zip(ids, observed):
            pair = []
            for index in (offset, offset + 1):
                status = statuses[index - 1]
                trial = rows.get((case_id, "repeat", index), {})
                failure = trial.get("failure_class")
                pair.append(f"{status}:{failure}" if failure else status)
            labels.append(tuple(pair))
        failure_transitions[key] = _transition_matrix(Counter(labels), sorted({label for pair in labels for label in pair}))

    return {
        "status": _coverage([status for trials in observed for status in trials]), "panel_cases": len(ids),
        "repeat_first_pass": per_seed[str(seeds[0])],
        "pass_at_3": _proportion([_repeat_metric(trials, False) for trials in observed]),
        "pass_all_3": _proportion([_repeat_metric(trials, True) for trials in observed]),
        "by_seed": per_seed, "seed_pass_rate_variance": variance,
        "transitions": transitions, "failure_class_transitions": failure_transitions,
    }


def _percentile(ordered, quantile):
    lo, hi = math.floor(quantile), math.ceil(quantile)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (quantile - lo)


def _bootstrap(groups, samples, seed):
    rng = random.Random(seed)
    strata = [(sum(group.values()), group[1], group[-1]) for _, group in sorted(groups.items())]
    n = sum(size for size, _, _ in strata)
    draws = []
    for _ in range(samples):
        delta = 0
        for size, positive, negative in strata:
            if positive + negative == 0:
                continue
            # Two binomial draws are the multinomial distribution of case
            # deltas under paired sampling with replacement in this stratum.
            gains = rng.binomialvariate(size, positive / size)
            losses = rng.binomialvariate(size - gains, negative / (size - positive)) if negative else 0
            delta += gains - losses
        draws.append(100 * delta / n)
    draws.sort()
    last = len(draws) - 1
    return [_percentile(draws, last * q) for q in (0.025, 0.975)]


def _contrast(left, right, ids, cases, bootstrap, minimum):
    pairs = [(_status(left, id_, "first"), _status(right, id_, "first")) for id_ in ids]
    status = _coverage([outcome for pair in pairs for outcome in pair])
    pair_counts = Counter(pairs)
    result = {
        "status": status, "planned_pairs": len(ids),
        "paired_cases": sum(count for pair, count in pair_counts.items() if set(pair) <= MEASURED),
        "status_matrix": _transition_matrix(pair_counts, STATUSES),
        "counts": None, "gain_percentage_points": None, "mcnemar_p": None, "holm_adjusted_p": None,
        "paired_bootstrap_ci95_pp": None, "bootstrap_strata": None, "statistically_significant": None,
        "business_minimum_gain_pp": minimum, "point_estimate_meets_business_minimum": None,
    }
    if status != "PASS":
        return result
    left_only, right_only = pair_counts["PASS", "FAIL"], pair_counts["FAIL", "PASS"]
    gains = 100 * (right_only - left_only) / len(ids)
    strata = defaultdict(Counter)
    for id_, (a, b) in zip(ids, pairs):
        strata[_scope(cases[id_])][int(b == "PASS") - int(a == "PASS")] += 1
    return {**result, "gain_percentage_points": gains,
            "counts": {"both_pass": pair_counts["PASS", "PASS"], "both_fail": pair_counts["FAIL", "FAIL"],
                       "left_only": left_only, "right_only": right_only},
            "mcnemar_p": exact_mcnemar(left_only, right_only),
            "paired_bootstrap_ci95_pp": _bootstrap(strata, bootstrap["samples"], bootstrap["seed"]),
            "bootstrap_strata": {"cells": len(strata),
                                 "singleton_cells": sum(sum(group.values()) == 1 for group in strata.values())},
            "point_estimate_meets_business_minimum": gains >= minimum if minimum is not None else None}


def holm(p_values):
    """Holm familywise-adjusted p-values with planned unobserved tests counted."""
    observed = sorted(((p, key) for key, p in p_values.items() if p is not None), key=lambda item: item[0])
    adjusted = dict.fromkeys(p_values)
    running = 0.0
    for index, (p, key) in enumerate(observed):
        running = max(running, min(1.0, (len(p_values) - index) * p))
        adjusted[key] = running
    return adjusted


def analyze(plan, bundle, *, expected_plan_sha256):
    """Compute statistics using the full frozen denominators and exact first attempts."""
    cases = _validate_plan(plan, expected_plan_sha256)
    indexed = _index_results(bundle, plan, cases)
    groups = _groups(cases)
    seeds = plan["repeat"]["seeds"]
    panel = {key: cases[key] for key in plan["repeat"]["case_ids"]}
    repeat_groups = _groups(panel)
    arms = {
        arm: {"identity": plan["arms"][arm],
              "first": {key: _proportion([_status(rows, case, "first") for case in ids]) for key, ids in groups.items()},
              "repeat": {key: _repeat_summary(rows, ids, seeds) for key, ids in repeat_groups.items()}}
        for arm, rows in sorted(indexed.items())
    }
    contrasts = {}
    for row in plan["comparisons"]:
        left, right = row["left"], row["right"]
        scopes = {group: _contrast(indexed[left], indexed[right], ids, cases, plan["bootstrap"],
                                  row.get("business_minimum_gain_pp")) for group, ids in groups.items()}
        contrasts[row["id"]] = {**row, "scopes": scopes}
    p_values = {(row, group): results["mcnemar_p"]
                for row, contrast in contrasts.items() for group, results in contrast["scopes"].items()}
    for (row, group), value in holm(p_values).items():
        scope = contrasts[row]["scopes"][group]
        scope["holm_adjusted_p"] = value
        scope["statistically_significant"] = value <= 0.05 if value is not None else None
    return {
        "plan_sha256": expected_plan_sha256, "evidence_bundle_sha256": digest(bundle),
        "evidence_class": bundle["evidence_class"], "suite": plan["suite"], "dataset_sha256": plan["dataset_sha256"],
        "runs": bundle["runs"],
        "first_seed": plan["first_seed"], "repeat_seeds": seeds, "case_count": len(cases), "repeat_count": len(panel),
        "bootstrap": {**plan["bootstrap"], "strata": list(STRATA), "method": "percentile paired case resampling"},
        "comparison_family": {"method": "Holm", "alpha": 0.05, "tests": len(p_values),
                              "computed": sum(value is not None for value in p_values.values())},
        "arms": arms, "comparisons": contrasts,
    }


def _read_json(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            _check(key not in value, f"duplicate JSON key {key!r}")
            value[key] = item
        return value

    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    profile = commands.add_parser("suite-profile")
    profile.add_argument("suite", choices=SUITES)
    checksum = commands.add_parser("plan-digest")
    checksum.add_argument("plan", type=Path)
    compute = commands.add_parser("analyze")
    compute.add_argument("--plan", type=Path, required=True)
    compute.add_argument("--plan-sha256", required=True)
    compute.add_argument("--evidence", type=Path, required=True)
    compute.add_argument("--output", type=Path)
    args = cli.parse_args()
    try:
        if args.command == "plan-digest":
            print(digest(_read_json(args.plan)))
            return 0
        if args.command == "suite-profile":
            report = frozen_suite(args.suite)
        else:
            report = analyze(_read_json(args.plan), _read_json(args.evidence), expected_plan_sha256=args.plan_sha256)
        rendered = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
        output = getattr(args, "output", None)
        if output:
            with output.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(rendered)
        else:
            print(rendered, end="")
    except (ValueError, OSError, KeyError) as error:
        cli.exit(2, f"BLOCKED: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
