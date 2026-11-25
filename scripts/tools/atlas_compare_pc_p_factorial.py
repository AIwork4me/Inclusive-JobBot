"""Compare the first complete matched PC-P factorial blocks."""

from argparse import ArgumentParser
from collections import Counter
from itertools import combinations
import json

from benchmarks.agentic_planning_v1.freeze import FROZEN
from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.atlas_validity.evaluation import planning_layered_scores
from scripts.tools.atlas_audit_pc_p_schema import EVIDENCE, audit
from scripts.tools.atlas_compare_pc_p_pilot import selected_archive
from scripts.tools.atlas_pc_p import frozen_panel


OUTPUT = EVIDENCE / "pc-p-h-factorial-first-five.json"
MATRIX = EVIDENCE / "pc-p-factorial-first-five-four-models.json"
MODELS = {
    "A": ("MiniCPM5-2B", "OpenBMB/MiniCPM5-2B-GGUF"),
    "B": ("LFM3-1.7B", "LiquidAI/LFM3-1.7B"),
    "G": ("Gemma-4-E2B", "google/gemma-4-E2B-it"),
    "H": ("Qwen3-8B", "Qwen/Qwen3-8B"),
}
ENDPOINTS = ("initial_plan_protocol", "goal_understanding", "plan_executability", "semantic_correctness",
             "final_output_protocol", "safety", "business_outcome", "strict_end_to_end")
FACTORS = ("example", "schema", "compact")


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


def build(candidate="H"):
    label, model_id = MODELS[candidate]
    panel = frozen_panel()
    arms = panel["arm_factors"]
    selected = set(sorted(panel["case_ids"])[:5])
    cases = {row["case_id"]: row for row in load_jsonl(FROZEN / "datasets/holdout.jsonl")}
    graphs = {row["case_id"]: row for row in load_jsonl(FROZEN / "task_graphs/holdout.jsonl")}
    scores = {key: {} for key in sorted(selected)}
    run_ids, grammar, counts = {}, {}, {}
    source = tasks = config = None
    for arm, factors in arms.items():
        archive = EVIDENCE / f"pc-p-{candidate.lower()}-clean-{arm}-005"
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
    return {
        "scope": f"first five {label} matched cases; four L0 cases and one L1 case",
        "interpretation": "Descriptive factorial contrasts use each arm's PASS count per five physical trials, "
                          "including unobserved downstream endpoints in the denominator. The sample offers one case "
                          "with a public tool schema.",
        "source_git": source, "run_ids": run_ids, "native_grammar_evidence": grammar,
        "counts": counts, "contrast_by_endpoint": contrasts(arms, counts, len(selected)),
        "cases": [{"case_id": key, "level": cases[key]["level"], "language": cases[key]["language"], "arms": value}
                  for key, value in scores.items()],
    }


def matrix():
    results = {MODELS[candidate][0]: build(candidate) for candidate in frozen_panel()["candidate_profiles"]}
    identities = {row["source_git"]["commit"] for row in results.values()}
    if len(identities) != 1:
        raise ValueError("four-model blocks use different experimental source commits")
    strict = Counter()
    for row in results.values():
        for arm in row["counts"].values():
            strict.update(arm["strict_end_to_end"])
    return {"scope": "All nine treatments across four models on the first five registered cases",
            "trials": sum(len(row["cases"]) * len(row["counts"]) for row in results.values()),
            "strict_outcomes": {status: strict[status] for status in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")},
            "models": results}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--matrix", action="store_true")
    args = parser.parse_args()
    result = matrix() if args.matrix else build()
    output = MATRIX if args.matrix else OUTPUT
    raw = (json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    if args.check:
        if output.read_bytes() != raw:
            parser.error("matched factorial evidence differs")
    else:
        with output.open("xb") as stream:
            stream.write(raw)
    models = result["models"] if args.matrix else {"Qwen3-8B": result}
    for model, row in models.items():
        print(model, {arm: (counts["initial_plan_protocol"].get("PASS", 0), counts["strict_end_to_end"].get("PASS", 0))
                      for arm, counts in row["counts"].items()})


if __name__ == "__main__":
    main()
