import pytest

from evaluation.aeve.q2_closure import require_coverage, wall_summary


def test_full_report_requires_every_candidate_case():
    expected = {"A": {"1", "2"}, "B": {"1", "2"}}
    with pytest.raises(ValueError, match="B: 1/2"):
        require_coverage(expected, {"A": {"1", "2"}, "B": {"1"}})
    with pytest.raises(ValueError, match="A: 1/2"):
        require_coverage(expected, {"A": {"1", "3"}, "B": {"1", "2"}})
    require_coverage(expected, {"A": {"1", "2"}, "B": {"1", "2"}})


def test_wall_summary_includes_latency_tail_and_measured_wall_time():
    result = wall_summary([1000] * 18 + [2000, 4000])
    assert result == {
        "requests": 20,
        "p50_wall_ms": 1000,
        "p95_wall_ms": 2000,
        "total_request_wall_ms": 24000,
        "evaluations_per_request_wall_second": 20 / 24,
    }
