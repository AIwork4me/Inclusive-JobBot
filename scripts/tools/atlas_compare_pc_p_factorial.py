"""Compare the first complete matched PC-P factorial blocks."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
from itertools import combinations
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.freeze import FROZEN
from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.agentic_planning_v1.runner import PLAN_FIELDS
from benchmarks.atlas_validity.evaluation import FENCE, parsed, planning_layered_scores
from benchmarks.competitive_slm.tc_v2_batch import legacy
from scripts.tools.atlas_audit_pc_p_schema import EVIDENCE, audit
from scripts.tools.atlas_compare_pc_p_pilot import selected_archive
from scripts.tools.atlas_pc_p import frozen_panel
from scripts.tools.atlas_progress import jsonl


OUTPUT = EVIDENCE / "pc-p-h-factorial-first-five.json"
MATRIX = EVIDENCE / "pc-p-factorial-first-five-four-models.json"
FULL_H = EVIDENCE / "pc-p-h-factorial-full.json"
FULL_MATRIX = EVIDENCE / "pc-p-factorial-full-four-models.json"
PROGRESS = EVIDENCE / "pc-p-factorial-progress.json"
MODELS = {
    "A": ("MiniCPM5-2B", "OpenBMB/MiniCPM5-2B-GGUF"),
    "B": ("LFM3-1.7B", "LiquidAI/LFM3-1.7B"),
    "G": ("Gemma-4-E2B", "google/gemma-4-E2B-it"),
    "H": ("Qwen3-8B", "Qwen/Qwen3-8B"),
}
ENDPOINTS = ("initial_plan_protocol", "goal_understanding", "plan_executability", "semantic_correctness",
             "final_output_protocol", "safety", "business_outcome", "strict_end_to_end")
FACTORS = ("example", "schema", "compact")
PRIMARY = ("initial_plan_protocol", "business_outcome", "strict_end_to_end")


def first_response(event):
    if event is None:
        return {"shape": "no_capture", "finish_reason": None, "completion_id": None}
    wire = event["wire"]
    result = {"shape": "unavailable_response", "finish_reason": None,
              "completion_id": wire["source_generation"].get("completion_id")}
    if wire["http_status"] != 200:
        return result
    try:
        choice = json.loads(wire["raw_response"])["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError, ValueError):
        return result
    content = message.get("content") or ""
    fenced = FENCE.fullmatch(content) if isinstance(content, str) else None
    value = parsed(fenced["body"] if fenced else content)
    if message.get("tool_calls"):
        shape = "native_tool_calls"
    elif value is None:
        shape = "non_object" if content else "empty_content"
    elif value.keys() == PLAN_FIELDS:
        shape = "plan_object"
    elif value.keys() == {"disposition", "facts"}:
        shape = "final_object"
    else:
        shape = "other_object"
    return {**result, "shape": f"fenced_{shape}" if fenced and value and not message.get("tool_calls") else shape,
            "finish_reason": choice.get("finish_reason")}


def initial_captures(archive):
    captures = {}
    for part in sorted(archive.glob("planning-part-*.jsonl.gz")):
        for entry in jsonl(part):
            if not entry["name"].startswith("attempts/"):
                continue
            trial = Path(entry["name"]).name.split(".", 1)[0]
            if trial in captures:
                raise ValueError(f"multiple first-response journals for {trial}")
            capture = next((event for event in map(json.loads, entry["raw_text"].splitlines())
                            if event["kind"] == "capture" and event["turn"] == 0), None)
            captures[trial] = first_response(capture)
    return captures


def full_diagnostics(candidate, results, *, separate_plan_checks=False):
    cases = {row["case_id"]: row for row in results["cases"]}
    by_stratum = defaultdict(lambda: defaultdict(lambda: defaultdict(Counter)))
    stops, paired, detail = {}, {}, {}
    for arm in results["run_ids"]:
        archive = EVIDENCE / f"pc-p-{candidate.lower()}-clean-{arm}-032"
        run, scored = selected_archive(archive, set(cases))
        if run["run_id"] != results["run_ids"][arm]:
            raise ValueError(f"first-response audit used the wrong {arm} archive")
        captures = initial_captures(archive)
        if captures.keys() != {row["trial"]["trial_id"] for row in scored.values()}:
            raise ValueError(f"first-response captures differ from {arm} scored trials")
        origins = {name: Counter() for name in ("shape", "finish_reason", "first_runner_finding")}
        changes = {name: Counter() for name in PRIMARY}
        snapshots = {}
        for case_id, case in cases.items():
            trial = scored[case_id]
            snapshot = captures[trial["trial"]["trial_id"]]
            findings = trial["findings"]
            snapshot["first_runner_finding"] = findings[0]["code"] if findings else None
            snapshot["plan_oracle_errors"] = trial["plan"]["errors"] if trial["plan"] is not None else []
            if separate_plan_checks:
                plan = trial["plan"]
                observed = plan is not None and trial["plan_before_tools"] is True
                snapshot["frozen_plan_goal_match"] = "NOT_RUN" if not observed else (
                    "PASS" if plan["goal_understood"] else "FAIL")
                snapshot["frozen_plan_execution_requirements"] = "NOT_RUN" if not observed else (
                    "PASS" if plan["executable"] else "FAIL")
            snapshots[case_id] = snapshot
            for name, counts in origins.items():
                counts[snapshot[name] or "none"] += 1
            for name in PRIMARY:
                score = case["arms"][arm][name]
                by_stratum[f"{case['level']}/{case['language']}"][arm][name][score] += 1
                baseline = case["arms"]["p0"][name]
                changes[name][f"{baseline}->{score}"] += 1
        stops[arm], detail[arm], paired[arm] = origins, snapshots, changes
    return {"stratum_outcomes": by_stratum, "paired_transitions_from_p0": paired,
            "first_response_counts": stops, "first_response_by_case": detail}


def contrasts(arm_factors, counts, size):
    contrasts = {}
    for endpoint in ENDPOINTS:
        passes = {arm: scores[endpoint].get("PASS", 0) for arm, scores in counts.items()}
        effects = {"stage_separation": (passes["p1"] - passes["p0"]) / size}
        for order in range(1, len(FACTORS) + 1):
            for subset in combinations(FACTORS, order):
                joint = frozenset(subset)
                numerator = sum((-1) ** (order - len(joint.intersection(factors))) * passes[arm]
                                for arm, factors in arm_factors.items() if arm != "p0")
                effects[" × ".join(subset)] = numerator / (size * 2 ** (len(FACTORS) - order))
        contrasts[endpoint] = effects
    return contrasts


def build(candidate="H", *, full=False):
    label, model_id = MODELS[candidate]
    panel = frozen_panel()
    arms = panel["arm_factors"]
    selected = set(panel["case_ids"] if full else sorted(panel["case_ids"])[:5])
    archive_suffix = f"{len(selected):03d}"
    cases = {row["case_id"]: row for row in load_jsonl(FROZEN / "datasets/holdout.jsonl")}
    graphs = {row["case_id"]: row for row in load_jsonl(FROZEN / "task_graphs/holdout.jsonl")}
    scores = {key: {} for key in sorted(selected)}
    run_ids, grammar, counts = {}, {}, {}
    source = tasks = config = None
    for arm, factors in arms.items():
        archive = EVIDENCE / f"pc-p-{candidate.lower()}-clean-{arm}-{archive_suffix}"
        run, rows = selected_archive(archive, selected)
        configuration = run["configuration"]
        model = configuration["model"]
        settings = dict(configuration["settings"])
        if (settings.pop("prompt_contract", "p0") != arm or configuration["git"]["dirty"]
                or model.get("official_model_id", model["repo_id"]) != model_id):
            raise ValueError(f"{arm} has an incorrect or modified source treatment")
        identity = {**configuration, "settings": settings}
        trial_ids = {key: row["trial"] for key, row in rows.items()}
        if config is None:
            config, source, tasks = identity, configuration["git"], trial_ids
        elif identity != config or trial_ids != tasks:
            raise ValueError(f"an input other than staged prompt treatment changed for {arm}")
        if "schema" in factors:
            schema = audit(archive)
            if schema["factorial_eligibility"] != "PASS":
                raise ValueError(f"{arm} did not verify native grammar or capture identity")
            grammar[arm] = {"sampler_grammar_verified": len(schema["trials"]),
                            "strict_schema_shape_pass": sum(
                                row["native_plan_shape"] == "PASS" for row in schema["trials"])}
        run_ids[arm] = run["run_id"]
        outcomes = {name: Counter() for name in ENDPOINTS}
        for key, row in sorted(rows.items()):
            layers = planning_layered_scores(cases[key], graphs[key], row)
            scores[key][arm] = layers
            for name in ENDPOINTS:
                outcomes[name][layers[name]] += 1
        counts[arm] = outcomes
    scope = (f"all 32 {label} matched cases across L0-L7 and both languages" if full
             else f"first five {label} matched cases; four L0 cases and one L1 case")
    interpretation = (
        "Descriptive factorial contrasts use each arm's PASS count per 32 physical trials, including "
        "unobserved downstream endpoints in the denominator. Results describe the fixed diagnostic cases in English and Chinese."
        if full else "Descriptive factorial contrasts use each arm's PASS count per five physical trials, "
        "including unobserved downstream endpoints in the denominator. The sample offers one case "
        "with a public tool schema."
    )
    return {
        "scope": scope,
        "interpretation": interpretation,
        "source_git": source, "run_ids": run_ids, "native_grammar_evidence": grammar,
        "counts": counts, "contrast_by_endpoint": contrasts(arms, counts, len(selected)),
        "cases": [{"case_id": key, "level": cases[key]["level"], "language": cases[key]["language"], "arms": value}
                  for key, value in scores.items()],
    }


def matrix(*, full=False):
    results = {MODELS[candidate][0]: build(candidate, full=full)
               for candidate in frozen_panel()["candidate_profiles"]}
    if full:
        for candidate in frozen_panel()["candidate_profiles"]:
            row = results[MODELS[candidate][0]]
            row["source_diagnostics"] = full_diagnostics(candidate, row, separate_plan_checks=True)
    identities = {row["source_git"]["commit"] for row in results.values()}
    if len(identities) != 1:
        raise ValueError("four-model blocks use different experimental source commits")
    strict = Counter()
    for row in results.values():
        for arm in row["counts"].values():
            strict.update(arm["strict_end_to_end"])
    scope = ("All nine treatments across four models on the complete registered cases"
             if full else "All nine treatments across four models on the first five registered cases")
    return {"scope": scope,
            "trials": sum(len(row["cases"]) * len(row["counts"]) for row in results.values()),
            "strict_outcomes": {status: strict[status] for status in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")},
            "models": results}


def checkpoint():
    panel = frozen_panel()
    counts, models = Counter(), {}
    for candidate in panel["candidate_profiles"]:
        stem = f"pc-p-{candidate.lower()}-clean"
        complete = all((EVIDENCE / f"{stem}-{arm}-032/bundle.json").is_file() for arm in panel["arm_factors"])
        result = build(candidate, full=complete)
        bins = Counter()
        for row in result["counts"].values():
            bins.update(row["strict_end_to_end"])
        counts.update(bins)
        models[MODELS[candidate][0]] = {"sealed": sum(bins.values()), "cases_per_treatment": len(result["cases"]),
                                       "counts": dict(bins), "run_ids": result["run_ids"]}
    sealed = sum(counts.values())
    if sealed > panel["planned_trials"]:
        raise ValueError("sealed source blocks exceed the registered trial count")
    counts["NOT_RUN"] += panel["planned_trials"] - sealed
    return {"planned": panel["planned_trials"], "sealed": sealed,
            "counts": {name: counts[name] for name in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")},
            "models": models}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--matrix", action="store_true")
    mode.add_argument("--full-h", action="store_true")
    mode.add_argument("--full-matrix", action="store_true")
    mode.add_argument("--wire", choices=MODELS)
    mode.add_argument("--progress", action="store_true")
    args = parser.parse_args()
    if args.full_matrix:
        result, output = matrix(full=True), FULL_MATRIX
    elif args.matrix:
        result, output = matrix(), MATRIX
    elif args.wire:
        model = build(args.wire, full=True)
        result = {"source_git": model["source_git"], "run_ids": model["run_ids"],
                  **full_diagnostics(args.wire, model)}
        output = EVIDENCE / f"pc-p-{args.wire.lower()}-factorial-wire.json"
    elif args.progress:
        result, output = checkpoint(), PROGRESS
    else:
        result, output = build(full=args.full_h), FULL_H if args.full_h else OUTPUT
    raw = (json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    if args.check:
        if output.read_bytes() != raw:
            parser.error("matched factorial evidence differs")
    elif args.progress:
        legacy.write_json(output, json.loads(raw))
    else:
        with output.open("xb") as stream:
            stream.write(raw)
    if args.progress:
        print(f"{result['sealed']}/{result['planned']} sealed", result["counts"])
        return
    if args.wire:
        for arm, stats in result["first_response_counts"].items():
            print(arm, dict(stats["shape"]), dict(stats["finish_reason"]), dict(stats["first_runner_finding"]))
        return
    models = result["models"] if args.matrix or args.full_matrix else {"Qwen3-8B": result}
    for model, row in models.items():
        print(model, {arm: (counts["initial_plan_protocol"].get("PASS", 0), counts["strict_end_to_end"].get("PASS", 0))
                      for arm, counts in row["counts"].items()})


if __name__ == "__main__":
    main()
