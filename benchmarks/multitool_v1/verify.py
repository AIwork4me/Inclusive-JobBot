"""Check the frozen corpus and replay reference calls through synthetic tools."""

from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks.tool_calling_v2.evaluator import Call, _resolve

from .dataset import CATEGORIES, DEPTHS, LANGUAGES, ROOT, SEEDS, canonical, load_freeze
from .runtime import Scenario, score


def replay_reference(case, directory):
    """Fixture-only positive control, never a source of model benchmark traces."""
    workflow = case.workflow()
    path = directory / f"{case.case_id}.sqlite3" if workflow.state is not None else None
    scenario = Scenario(case, path)
    calls, results, turns, delivered = [], {}, {}, []
    for node in workflow.nodes:
        turns[node.node_id] = max((turns[dep] + 1 for dep in node.depends_on), default=0)
    before = scenario.snapshot()
    # Independent nodes share a turn. Sorting by dependency layer keeps legal
    # parallel calls in one batch while preserving the authored order within it.
    for node in sorted(workflow.nodes, key=lambda node: turns[node.node_id]):
        args = _resolve(node.arguments, results)
        raw = canonical(args).decode("utf-8").rstrip("\n")
        call_id, turn = node.node_id, turns[node.node_id]
        results[call_id] = scenario.call(call_id, node.tool, raw)
        calls.append(Call(turn, call_id, node.tool, raw, results[call_id]))
        delivered.extend((turn, event_id) for event_id, _ in scenario.take_events())
    final_text = canonical(case.oracle["answer"]).decode("utf-8").rstrip("\n")
    after = scenario.snapshot()
    evaluated = score(case, calls, final_text, before=before, after=after, delivered_events=delivered)
    return evaluated, calls, final_text, before, after, delivered


def require(predicate, detail):
    if not predicate:
        raise ValueError(f"invalid MULTITOOL-V1 freeze: {detail}")


def verify_freeze(freeze, directory):
    cases = freeze.active
    require(freeze.manifest["version"] == "MULTITOOL-V1", "dataset version")
    require(freeze.manifest["holdout_count"] == len(cases) == 600, "holdout count")
    require(freeze.manifest["diagnostic_count"] == len(freeze.controls) == 6, "diagnostic count")
    depth_distribution, language_distribution, coverage, outcomes = Counter(), Counter(), Counter(), Counter()
    for case in cases.values():
        data = case.oracle
        steps = data["required_steps"]
        category, depth, language = (data[key] for key in ("category", "depth_bin", "language"))
        require(case.case_id.startswith(f"{category}-"), f"{case.case_id} category")
        require(steps == len(data["nodes"]) and any(low <= steps <= high and depth == f"{low}-{high}"
                                                    for low, high in DEPTHS), f"{case.case_id} step count")
        depth_distribution[category, depth] += 1
        language_distribution[category, depth, language] += 1
        coverage.update(data["coverage"])
        outcomes[data["outcome"]] += 1
    expected_depths = {f"{low}-{high}" for low, high in DEPTHS}
    require(depth_distribution == {(category, depth): 15 for category in CATEGORIES for depth in expected_depths},
            "depth strata")
    require(language_distribution == {(category, depth, lang): 5 for category in CATEGORIES
                                       for depth in expected_depths for lang in LANGUAGES}, "language strata")
    require(len({case.prompt["text"] for case in cases.values()}) == 600, "duplicate prompt")
    for case in freeze.controls.values():
        require(case.oracle["required_steps"] == 0 and not case.oracle["nodes"], f"{case.case_id} diagnostic")
        coverage.update(case.oracle["coverage"])
    require({"homonyms", "similar_ids", "null_field", "source_conflict", "not_found", "stale_record",
             "superseding_business_state", "permission_denied", "timeout", "http_429", "http_500",
             "temporary_unavailable", "permanent_unavailable", "no_tool", "missing_field", "multi_tool_conflict_resolution",
             "clarification_required", "multi_turn", "constraint_change", "missing_site"}.issubset(coverage),
            "required scenario coverage")
    is_panel = freeze.panel["case_ids"]
    require(len(is_panel) == len(set(is_panel)) == 100 and set(is_panel) <= cases.keys(), "repeat panel identities")
    require(tuple(freeze.panel["seeds"]) == SEEDS and len(set(SEEDS)) == 3, "repeat panel seeds")
    repeated = Counter((cases[key].oracle["category"], cases[key].oracle["depth_bin"]) for key in is_panel)
    require(repeated.keys() == depth_distribution.keys() and set(repeated.values()) == {2, 3}, "repeat panel strata")
    repeat_language = Counter(cases[key].oracle["language"] for key in is_panel)
    require(len(repeat_language) == 3 and sorted(repeat_language.values()) == [33, 33, 34], "repeat panel languages")
    repeat_depth = Counter(cases[key].oracle["depth_bin"] for key in is_panel)
    require(set(repeat_depth.values()) == {20}, "repeat panel depth balance")
    for case in (*cases.values(), *freeze.controls.values()):
        result, *_ = replay_reference(case, directory)
        require(result["status"] == "PASS", f"{case.case_id} replay: {result['findings']}")
    return {"fixture_status": "PASS", "model_status": "NOT_RUN", "case_count": len(cases),
            "control_count": len(freeze.controls), "verified": len(cases) + len(freeze.controls),
            "repeat_languages": dict(repeat_language), "coverage": dict(coverage), "holdout_outcomes": dict(outcomes),
            "depth_distribution": {f"{category}/{depth}": n for (category, depth), n in depth_distribution.items()},
            "freeze_sha256": freeze.manifest["freeze_sha256"]}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT)
    with TemporaryDirectory(prefix="multitool-fixtures-") as directory:
        result = verify_freeze(load_freeze(parser.parse_args().data), Path(directory))
    print(canonical(result).decode("utf-8"), end="")
