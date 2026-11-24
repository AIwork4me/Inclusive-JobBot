import pytest

from benchmarks.agentic_planning_v1.freeze import build
from benchmarks.atlas_validity.evaluation import planning_scores
from scripts.tools.atlas_controls import encoded, planning_witness


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
