"""Exercise the fixed-denominator paired TC-V3 report."""

from benchmarks.slm10.tc_priority_report import pairs, summarize


def test_pair_never_joins_different_seeds_and_keeps_unresolved_slots():
    left, right = "direct_first", "sdk_first"
    table = {
        ("a", 7): {left: "PASS", right: "FAIL"},
        ("b", 7): {left: "PASS", right: "BLOCKED"},
        ("c", 7): {left: "FAIL"},
        ("c", 8): {right: "PASS"},
    }
    result = pairs(table, left, right)
    assert result["planned_pairs"] == 2
    assert result["evaluable_pairs"] == 1
    assert result["transitions"] == {"PASS/BLOCKED": 1, "PASS/FAIL": 1}
    assert result["sdk_minus_reference"] == -1
    assert result["difference_95"] is not None


def test_intervals_report_both_frozen_and_evaluable_denominators():
    result = summarize(["PASS", "FAIL", "BLOCKED", "NOT_RUN"])
    assert result["planned"] == 4
    assert result["evaluable"] == 2
    assert result["BLOCKED"] == result["NOT_RUN"] == 1
    assert result["wilson_95"][0] < .5 < result["wilson_95"][1]
