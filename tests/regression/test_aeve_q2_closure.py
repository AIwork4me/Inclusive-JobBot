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


def test_runtime_cost_retains_missing_measurements_and_real_zeroes():
    from evaluation.aeve.q2_closure import measured_cost

    result = measured_cost([
        {"wall_ms": 10, "usage": {"prompt_tokens": 7, "completion_tokens": 0},
         "timings": {"prompt_ms": 3.2, "predicted_ms": 0}},
        {"wall_ms": 30, "usage": {}, "timings": {}},
    ])
    assert result["requests"] == 2
    assert result["p95_wall_ms"] == 30
    assert result["prompt_tokens"] == {"recorded": 1, "total": 7}
    assert result["completion_tokens"] == {"recorded": 1, "total": 0}
    assert result["native_inference_ms"] == {"recorded": 1, "total": 3.2}
