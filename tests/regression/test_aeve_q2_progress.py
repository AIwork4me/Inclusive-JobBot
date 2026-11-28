import pytest

from evaluation.aeve.progress import coverage_summary
from evaluation.aeve.history_routing import route_matrix
from evaluation.aeve.contracts import DIMENSIONS


def test_coverage_tracks_exact_roster_and_requires_a_closure_for_admission():
    stamp = {"run": "hash"}
    data = coverage_summary({"A": {"one", "two"}, "B": {"one"}}, {"one", "two"}, ("A", "B"), stamp)
    assert data["recorded"] == 3
    assert data["remaining"] == 1
    assert data["roster_status"] == "NOT_RUN"
    assert data["status"] == "NOT_RUN"
    with pytest.raises(ValueError, match="frozen roster"):
        coverage_summary({"A": {"unknown"}}, {"one"}, ("A",), stamp)
    complete = coverage_summary({"A": {"one"}}, {"one"}, ("A",), stamp)
    assert complete["roster_status"] == "PASS"
    assert complete["status"] == "NOT_RUN"


def test_history_matrix_records_absent_qualification_at_every_scope():
    matrix = route_matrix([], ["Qwen", "MiniCPM", "unknown"])
    assert matrix["subject_family_count"] == 3
    assert matrix["scope_count"] == 3 * len(DIMENSIONS) * 3
    assert matrix["covered_scopes"] == 0
    assert matrix["subjects"]["Qwen"]["D24/critical"]["status"] == "BLOCKED"
    assert matrix["subjects"]["unknown"]["D24/critical"]["status"] == "BLOCKED"
