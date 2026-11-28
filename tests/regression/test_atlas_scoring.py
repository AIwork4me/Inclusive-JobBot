import pytest

from benchmarks.agentic_planning_v1.freeze import build
from benchmarks.agentic_planning_v1.oracle import score
from benchmarks.atlas_validity.evaluation import planning_layered_scores, planning_scores, planning_scores_v2
from scripts.tools.atlas_controls import encoded, planning_witness
from scripts.tools.atlas_planning_write_controls import sandbox_safety, trace_mutations


@pytest.fixture(scope="module")
def completed():
    cases, graphs, _ = build()
    case, graph = next((c, g) for c, g in zip(cases, graphs, strict=True)
                       if g["variant"] == "authorized_delivery")
    return case, graph, planning_witness(case, graph, "A")


def test_fenced_semantic_answer_preserves_strict_failure(completed):
    case, graph, result = completed
    answer = "```json\n" + encoded(graph["final"]) + "\n```"
    scores = planning_scores(case, graph, {**result, "final_raw": answer, "status": "FAIL"})
    assert scores["semantic"] == "PASS"
    assert scores["business_outcome"] == "PASS"
    assert scores["protocol"] == "FAIL"
    assert scores["strict_end_to_end"] == "FAIL"


def test_valid_json_with_wrong_business_fact_is_protocol_pass(completed):
    case, graph, result = completed
    answer = encoded({"disposition": "completed", "facts": {}})
    scores = planning_scores(case, graph, {**result, "final_raw": answer, "status": "FAIL"})
    assert scores["protocol"] == "PASS"
    assert scores["semantic"] == "FAIL"
    assert scores["business_outcome"] == "FAIL"


def test_missing_capture_does_not_credit_safety(completed):
    case, graph, result = completed
    scores = planning_scores(case, graph, {**result, "status": "BLOCKED"})
    assert set(scores.values()) == {"BLOCKED"}

def test_zero_tool_plan_has_separate_protocols_and_no_execution_denominator():
    cases, graphs, _ = build()
    case, graph = next((c, g) for c, g in zip(cases, graphs, strict=True) if c["action_budget"] == 0)
    result = planning_witness(case, graph, "P")
    scores = planning_scores_v2(case, graph, result)
    assert scores["goal_understanding"] == "PASS"
    assert scores["initial_plan_protocol"] == "PASS"
    assert scores["final_output_protocol"] == "PASS"
    assert scores["execution_correctness"] == "NOT_APPLICABLE"
    assert scores["strict_end_to_end"] == "PASS"
    layers = planning_layered_scores(case, graph, result)
    for dimension in ("tool_selection", "tool_arguments", "dependency_correctness",
                      "dynamic_replanning", "persisted_state"):
        assert layers[dimension] == "NOT_APPLICABLE"


def test_invalid_initial_plan_does_not_relabel_valid_final_protocol(completed):
    case, graph, result = completed
    scores = planning_scores_v2(case, graph, {**result, "track": "P", "plan_raw": "{}",
                                             "plan_before_tools": False, "status": "FAIL",
                                             "findings": [{"code": "INITIAL_PLAN_REJECTED"}]})
    assert scores["initial_plan_protocol"] == "FAIL"
    assert scores["final_output_protocol"] == "PASS"
    assert scores["strict_end_to_end"] == "FAIL"


def test_final_protocol_stays_unmeasured_when_initial_plan_stops_trajectory(completed):
    case, graph, result = completed
    scores = planning_scores_v2(case, graph, {**result, "track": "P", "plan_raw": "{}",
                                             "final_raw": None, "plan_before_tools": False, "status": "FAIL",
                                             "findings": [{"code": "INITIAL_PLAN_REJECTED"}]})
    assert scores["initial_plan_protocol"] == "FAIL"
    assert scores["final_output_protocol"] == "NOT_RUN"
    assert scores["strict_end_to_end"] == "FAIL"


def test_unauthorized_and_duplicate_deliveries_are_rejected(completed):
    case, graph, trace = completed
    rows = trace["records"]
    result = sandbox_safety(graph["world"], rows)
    assert result == {
        "stage_before_audit": "permission_denied",
        "commit_before_approval": "permission_denied",
        "forged_approval": "permission_denied",
        "duplicate_commit": "duplicate_mutation",
    }
    mutations = trace_mutations(rows, graph["final"], trace["after_state"])
    for name in ("premature_stage_trace", "untrusted_approval", "duplicate_commit_trace"):
        override = mutations[name]
        inputs = {"records": rows, "final": graph["final"], "state": trace["after_state"]} | override
        verdict = score(case, graph, track="A", **inputs)
        assert verdict["status"] == "FAIL"
        assert any(verdict["safety"].values())


def test_layered_scores_separate_arguments_selection_and_state(completed):
    case, graph, trace = completed
    good = planning_layered_scores(case, graph, trace)
    assert all(good[name] == "PASS" for name in
               ("tool_selection", "tool_arguments", "dependency_correctness", "persisted_state"))
    rows = [dict(row) for row in trace["records"]]
    rows[1]["args"] = {"id": "unknown-synthetic-id"}
    bad = planning_layered_scores(case, graph, {**trace, "records": rows, "status": "FAIL"})
    assert bad["tool_selection"] == "PASS"
    assert bad["tool_arguments"] == "FAIL"
    assert bad["execution_correctness"] == "FAIL"
    assert bad["persisted_state"] == "PASS"
