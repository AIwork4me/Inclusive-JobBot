"""Check the Planning V2 public authoring boundary and workload coverage."""

from collections import Counter

from benchmarks.slm10.planning_controls import LEVELS, validate_public
from benchmarks.slm10.planning_public_authoring import public_cases
from benchmarks.slm10.planning_roster import historical_tasks


def test_public_cases_cover_exact_levels_without_exposing_proofs():
    cases = list(public_cases())
    historical = historical_tasks()
    assert Counter(case["level"] for case in cases) == dict.fromkeys(LEVELS, 100)
    assert len({case["task"] for case in cases}) == len(cases)
    for case in cases:
        validate_public(case, historical)
        assert "approval" not in case["public"]
        assert {"steps", "facts", "worlds", "witness"}.isdisjoint(case)


def test_long_tasks_cover_11_through_20_and_zero_tasks_can_clarify():
    cases = list(public_cases())
    zero = [case for case in cases if case["level"] == "L0"]
    assert sum("reference" not in case["public"] for case in zero) == 50
    assert all(not case["contract"]["tools"] for case in zero)
    long = [case for case in cases if case["level"] == "L6"]
    assert Counter(case["limits"]["tool_calls"] for case in long) == dict.fromkeys(range(11, 21), 10)
    for case in long:
        checks = case["public"]["checks"]
        assert len(set(checks)) == len(checks) == case["limits"]["tool_calls"] - 2
        assert all(check in case["task"] for check in checks)
