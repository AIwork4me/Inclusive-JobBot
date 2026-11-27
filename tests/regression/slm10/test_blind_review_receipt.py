import pytest

from benchmarks.slm10.blind_review_receipt import coverage


def test_review_coverage_requires_every_pinned_case_and_scenario_once():
    cases = [{"case_id": "a", "scenarios": [{"scenario_id": "1"}, {"scenario_id": "2"}]},
             {"case_id": "b"}]
    approved = [{"case_id": "a", "scenario_id": "1", "status": "PASS"},
                {"case_id": "a", "scenario_id": "2", "status": "BLOCKED"}]
    assert coverage(cases, approved) == {"PASS": 1, "FAIL": 0, "BLOCKED": 1, "NOT_RUN": 1}
    with pytest.raises(ValueError, match="duplicate"):
        coverage(cases, approved + [approved[0]])
    with pytest.raises(ValueError, match="outside"):
        coverage(cases, [{"case_id": "a", "scenario_id": "3", "status": "PASS"}])
