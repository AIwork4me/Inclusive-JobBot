"""Synthetic checks for the paired JOB-V1 analysis contract."""

from collections import Counter
from copy import deepcopy
import hashlib

import pytest

from benchmarks.job_productivity_v1.statistics import (
    ARMS,
    analyze,
    exact_mcnemar,
    repeat_summary,
    select_repeats,
    wilson_interval,
    zero_event_upper_95,
)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def planned(n=60):
    counts = (n // 2, n // 3, n - n // 2 - n // 3)
    categories = ("document_review", "product_information", "customer_service")
    return [
        {"case_id": f"{category}-{index}", "category": category,
         "pairing_sha256": digest(f"{category}-{index}")}
        for category, count in zip(categories, counts)
        for index in range(count)
    ]


def sample_arms(n=12):
    cases = planned(n)
    arms = {}
    for arm in ARMS:
        arms[arm] = [
            {
                **case, "status": "FAIL" if index in (0, 2) and arm in "AB" else "PASS",
                "first_pass_success": index not in (0, 2) or arm not in "AB",
                "completed": index not in (0, 2) or arm not in "AB",
                "routine": True, "machine_ms": 1000 + index * 10,
                "model_calls": 0 if arm == "F" else 1, "argument_total": 2,
                "argument_correct": 0 if index == 0 and arm in "AB" else 2,
                "prompt_tokens": 0 if arm == "F" else 80, "completion_tokens": 0 if arm == "F" else 20,
                "tool_calls": 2, "invalid_calls": 0,
                "unauthorized_effects": 0, "unconfirmed_commits": 0, "duplicate_commits": 0,
                "false_approvals": 0, "correct_escalations": 0,
            }
            for index, case in enumerate(cases)
        ]
    return arms


@pytest.mark.parametrize("left_only, right_only, p", [(0, 0, 1), (1, 0, 1), (0, 5, 0.0625), (1, 4, 0.375)])
def test_mcnemar_exact(left_only, right_only, p):
    assert exact_mcnemar(left_only, right_only) == p


def test_confidence_intervals_and_zero_observations():
    assert wilson_interval(0, 0) is None
    assert wilson_interval(0, 10) == pytest.approx([0.0, 0.2775328])
    assert wilson_interval(10, 10) == pytest.approx([0.7224672, 1.0])
    assert zero_event_upper_95(0) is None
    assert zero_event_upper_95(30) == pytest.approx(0.09503385)


def test_paired_case_counts_and_costs_use_all_attempts():
    arms = sample_arms()
    arms["A"][1]["status"] = "PASS"
    arms["A"][1]["completed"] = False
    arms["A"][1]["correct_escalations"] = 1
    result = analyze(arms, bootstrap_samples=200, seed=10)
    arm = result["arms"]["A"]
    assert arm["task_success"]["numerator"] == 10
    assert arm["routine_completion"]["numerator"] == 9
    assert arm["correct_escalations"] == 1
    assert arm["model_calls_per_successful_task"] == pytest.approx(12 / 9)
    assert arm["tokens_per_successful_task"] == pytest.approx(1200 / 9)
    assert arm["all_step_argument_accuracy"]["numerator"] == 22
    assert arm["all_step_argument_accuracy"]["denominator"] == 24
    assert arm["safety"]["unauthorized_effects"]["cases_observed"] == 12
    assert arm["safety"]["unauthorized_effects"]["zero_event_one_sided_upper_95"] == zero_event_upper_95(12)
    paired = result["comparisons"]["B-C"]
    assert paired["old_only"] == 0
    assert paired["new_only"] == 2
    assert paired["absolute_gain_percentage_points"] == pytest.approx(100 / 6)
    assert paired["relative_improvement"] == pytest.approx(0.2)
    assert paired["exact_mcnemar_p"] == 0.5
    assert paired["paired_bootstrap_ci95_percentage_points"][0] >= 0
    assert analyze(arms, bootstrap_samples=200, seed=10) == result


@pytest.mark.parametrize("mutation", ["missing_arm", "missing_case", "duplicate_case", "different_identity",
                                       "wrong_category", "invalid_state", "wrong_counts", "no_llm_tokens"])
def test_analysis_rejects_unpaired_or_inconsistent_evidence(mutation):
    arms = sample_arms()
    if mutation == "missing_arm":
        del arms["B"]
    elif mutation == "missing_case":
        arms["C"].pop()
    elif mutation == "duplicate_case":
        arms["D"].append(arms["D"][0])
    elif mutation == "different_identity":
        arms["E"][0]["pairing_sha256"] = "0" * 64
    elif mutation == "wrong_category":
        arms["A"][0]["category"] = "other_role"
    elif mutation == "invalid_state":
        arms["D"][0]["status"] = "BLOCKED"
    elif mutation == "wrong_counts":
        arms["D"][0]["argument_correct"] = 20
    elif mutation == "no_llm_tokens":
        arms["F"][0]["prompt_tokens"] = 1
    with pytest.raises(ValueError):
        analyze(arms, bootstrap_samples=200, seed=1)


def test_omitting_same_case_in_all_arms_fails_frozen_coverage():
    arms = sample_arms()
    for rows in arms.values():
        rows.pop()
    with pytest.raises(ValueError, match="differs from planned roster"):
        analyze(arms, bootstrap_samples=200, seed=1, planned_cases=planned(12))


def test_stratified_repeats_are_fixed_before_results_and_reused_across_arms():
    cases = planned()
    selection = select_repeats(cases, n=50, seed=23001, trial_seeds=(17, 31, 83))
    assert len(selection["cases"]) == 50
    assert selection == select_repeats(list(reversed(cases)), n=50, seed=23001, trial_seeds=(17, 31, 83))
    assert Counter(case["category"] for case in selection["cases"]) == {
        "document_review": 25, "product_information": 17, "customer_service": 8,
    }
    arms_by_id = {arm: {row["case_id"]: row for row in values} for arm, values in sample_arms(60).items()}
    repeats = {
        arm: [
            {**arms_by_id[arm][case["case_id"]], "trial_seed": trial}
            for case in selection["cases"]
            for trial in (17, 31, 83)
        ]
        for arm in ARMS
    }
    target_anchor = selection["cases"][0]["case_id"]
    target = next(row for row in repeats["D"] if row["case_id"] == target_anchor)
    target.update(status="FAIL", completed=False, first_pass_success=False)
    summary = repeat_summary(selection, repeats)
    assert summary["arms"]["D"]["all_three_successful"]["numerator"] == 49
    assert summary["arms"]["D"]["all_three_successful"]["denominator"] == 50
    assert summary["arms"]["E"]["all_three_successful"]["numerator"] == 50
    missing = deepcopy(repeats)
    missing["E"].pop()
    with pytest.raises(ValueError):
        repeat_summary(selection, missing)
    changed_seeds = {**selection, "trial_seeds": [17, 31, 85]}
    with pytest.raises(ValueError, match="digest mismatch"):
        repeat_summary(changed_seeds, repeats)
