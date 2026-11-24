from pathlib import Path

import pytest

from scripts.tools.atlas_progress import count_trials, historical


def test_missing_trials_and_blocked_attempts_keep_their_denominator():
    result = count_trials([("a", "PASS"), ("b", "FAIL"), ("c", "BLOCKED")], 5)
    assert result["outcomes"] == {"PASS": 1, "FAIL": 1, "BLOCKED": 1, "NOT_RUN": 2}
    assert result["executed"] == 3
    assert result["valid_evidence"] == 2
    assert result["coverage"] == 3 / 5
    assert result["strict_pass_rate"] == 1 / 5


def test_duplicate_unknown_and_overflow_are_rejected():
    for rows, expected in [
        ([("a", "PASS"), ("a", "FAIL")], 2),
        ([("a", "UNKNOWN")], 2),
        ([("a", "PASS")], 0),
    ]:
        with pytest.raises(ValueError):
            count_trials(rows, expected)


def test_archived_runs_have_distinct_outcomes_and_units():
    result = historical(Path("evidence/IJ07"))
    for name, passed, planned in [
        ("tc-v2-vulkan-first", 349, 500), ("tc-v2-rocm-first", 347, 500),
        ("multitool-primary", 129, 600), ("planning-primary-A", 0, 800),
        ("planning-primary-P", 0, 800), ("planning-repeat-combined", 0, 960),
        ("job-f-primary", 592, 600), ("job-f-correction", 600, 600),
        ("competitive-b-first-checkpoint", 15, 1150),
    ]:
        assert result[name]["outcomes"]["PASS"] == passed, name
        assert result[name]["planned"] == planned, name
    assert result["historical-replay"]["executed"] == 2000
    assert result["historical-replay"]["model_requests"] == 4422
    assert result["multitool-repeat"]["repeat_cases_passing_any"] == 22
    assert result["multitool-repeat"]["repeat_cases_passing_all"] == 22
    assert result["ag11-vulkan"]["outcomes"]["BLOCKED"] == 1
