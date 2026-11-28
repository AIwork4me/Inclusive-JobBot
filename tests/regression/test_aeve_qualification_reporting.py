import pytest

from evaluation.aeve.report_qualification import assessment, build, measures, render


def fixture_row(case_id, prediction, label, base=None):
    return {"case_id": case_id, "base_id": base or case_id, "prediction": prediction, "label": label,
            "tags": ["business_error", "injection"], "attempted_decision": prediction in {"PASS", "FAIL"},
            "citation_correct": prediction in {"PASS","FAIL"}, "risk": "read", "output_length": "short",
            "language": "en", "dimension": "D22", "category": "business_error", "complexity": 2}


def test_observed_points_exclude_pending_and_preserve_abstention_denominators():
    rows = [fixture_row("one", "FAIL", "FAIL"), fixture_row("two", "BLOCKED", "FAIL"),
            fixture_row("three", "NOT_RUN", "FAIL"), fixture_row("four", "PASS", "FAIL"),
            fixture_row("five", "FAIL", "PASS"), fixture_row("six", "INVALID", "PASS")]
    rates, basic = measures(rows)
    observed = rates["business_error_recall"]
    assert observed["planned"] == 4 and observed["recorded"] == 3
    assert observed["numerator"] == observed["abstained"] == observed["not_run"] == 1
    assert observed["point_among_recorded"] == pytest.approx(1/3)
    assert basic["explicit_false_negative_rate_among_recorded_error_cases"] == pytest.approx(1/3)
    assert basic["missed_detection_including_abstentions_and_invalid"] == pytest.approx(2/3)
    assert rates["coverage"]["point_among_recorded"] == pytest.approx(3/5)
    assert rates["citation_accuracy"]["point_among_recorded"] == pytest.approx(1/3)
    assert rates["injection_error_recall"] == observed
    assert rates["false_success_recall"]["point_among_recorded"] is None


def test_paired_consistency_requires_both_physical_responses():
    rows = [fixture_row("one-a", "PASS", "PASS", "one"), fixture_row("one-b", "PASS", "PASS", "one"),
            fixture_row("two-a", "FAIL", "FAIL", "two"), fixture_row("two-b", "NOT_RUN", "FAIL", "two")]
    rates, _ = measures(rows)
    assert rates["paired_consistency"] == {"planned_pairs": 2, "recorded_pairs": 1, "numerator": 1,
                                          "point_among_recorded": 1.0}


def test_source_exhibits_and_model_rationale_are_separately_verifiable():
    row = fixture_row("one", "PASS", "FAIL")
    case = {"tags": row["tags"], "required_refs": ["x","y"], "expected": "FAIL",
            "packet": {"events": [{"id": "x", "value": 3}, {"id": "y", "value": 2}, {"id": "z", "value": 5}]}}
    with pytest.raises(ValueError, match="missing"):
        assessment(row, case, None)
    capture = {"run": "fixture", "job": "fixture", "attempt": 1, "transport": "PASS",
               "evaluation": {"verdict": "PASS", "reason_summary": "fixture", "evidence_refs": ["x", "z"]}}
    result = assessment(row, case, capture)
    assert result["observed_error_types"] == ["accepted_error", "omitted_gold_evidence", "cited_additional_evidence"]
    assert result["missing_refs"] == ["y"] and result["extra_refs"] == ["z"]
    assert result["gold_exhibits"] == case["packet"]["events"][:2]


def test_empty_archive_retains_entire_formal_roster_with_undefined_estimates(tmp_path):
    report = build(tmp_path)
    assert report["session_manifests"] == {}
    assert "0 of 3,228 planned assessments" in render(report)
    for family in report["families"].values():
        assert len(family["case_results"]) == family["counts"]["planned"] == 807
        assert family["formal_admission"]["status"] == "NOT_RUN"
        assert family["threshold_comparison"]["business_error_recall"]["observed_point"] is None
        assert all(r["prediction"] == "NOT_RUN" for r in family["case_results"])
