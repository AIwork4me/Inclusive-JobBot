"""Verify competitive statistics on synthetic evidence with known outcomes."""

from copy import deepcopy

import pytest

from benchmarks.competitive_slm.statistics import analyze, digest, frozen_suite, holm


def example():
    cases = [{"case_id": f"C-{i}", "pairing_sha256": digest(i), "task_type": "recovery" if i < 3 else "ordinary",
              "complexity": "deep" if i % 2 else "short", "language": "zh" if i < 3 else "en"} for i in range(1, 5)]
    common = {"backend": "vulkan", "device": "gfx1151", "track": "controlled", "thinking": False,
              "quantization": "Q8_0", "protocol": "native-tool-calling",
              "controls_sha256": digest("same tools, evaluator and budgets")}
    plan = {
        "schema_version": 1, "suite": "synthetic-fixture", "dataset_sha256": digest(cases),
        "cases": cases, "first_seed": 7, "repeat": {"case_ids": ["C-1", "C-2"], "seeds": [13, 17, 19]},
        "bootstrap": {"seed": 41, "samples": 100},
        "arms": {arm: {**common, "model": f"model-{arm}", "configuration_sha256": digest(arm)} for arm in "AB"},
        "comparisons": [{"id": "A-to-B", "left": "A", "right": "B", "vary": "model"}],
    }
    runs = {f"run-{arm}": {"arm": arm, "configuration_sha256": plan["arms"][arm]["configuration_sha256"],
                           "run_configuration_sha256": digest(f"run-configuration-{arm}"),
                           "dataset_sha256": plan["dataset_sha256"], "phases": ["first", "repeat"]} for arm in "AB"}
    return plan, {"schema_version": 1, "evidence_class": "synthetic_software_test", "runs": runs, "rows": []}


def add_row(plan, bundle, arm, case_id, status, *, phase="first", index=1, **overrides):
    case = next(row for row in plan["cases"] if row["case_id"] == case_id)
    seed = plan["first_seed"] if phase == "first" else plan["repeat"]["seeds"][index - 1]
    row = {
        "arm": arm, "case_id": case_id, "pairing_sha256": case["pairing_sha256"], "phase": phase,
        "repeat_index": None if phase == "first" else index, "attempt": 1, "seed": seed, "status": status,
        "run_id": f"run-{arm}", "configuration_sha256": plan["arms"][arm]["configuration_sha256"],
        "run_configuration_sha256": bundle["runs"][f"run-{arm}"]["run_configuration_sha256"],
        "evidence_sha256": digest([arm, case_id, seed, status]), "failure_class": "plan" if status == "FAIL" else None,
        **overrides,
    }
    bundle["rows"].append(row)
    return row


def run(plan, bundle):
    return analyze(plan, bundle, expected_plan_sha256=digest(plan))


def test_complete_pairs_reproduce_known_effect_and_adjustment():
    plan, bundle = example()
    for index in range(1, 5):
        add_row(plan, bundle, "A", f"C-{index}", "PASS" if index == 1 else "FAIL")
        add_row(plan, bundle, "B", f"C-{index}", "PASS")
    report = run(plan, bundle)
    overall = report["comparisons"]["A-to-B"]["scopes"]["overall"]
    assert overall["paired_cases"] == 4
    assert overall["counts"] == {"both_pass": 1, "both_fail": 0, "left_only": 0, "right_only": 3}
    assert overall["gain_percentage_points"] == 75
    assert overall["mcnemar_p"] == 0.25
    assert overall["holm_adjusted_p"] == 1.0
    assert report["comparison_family"]["tests"] == 7
    assert report["arms"]["B"]["first"]["overall"]["wilson_ci95"][1] == 1
    assert report == run(plan, bundle)
    bundle["rows"].reverse()
    shuffled_report = run(plan, bundle)
    assert report["comparisons"] == shuffled_report["comparisons"]
    assert report["arms"] == shuffled_report["arms"]
    assert holm({"a": 0.01, "b": 0.03, "c": 0.2, "d": None}) == {
        "a": 0.04, "b": 0.09, "c": 0.4, "d": None,
    }


def test_incomplete_pair_keeps_four_statuses_and_suppresses_inference():
    plan, bundle = example()
    for i, status in enumerate(("PASS", "FAIL", "BLOCKED"), 1):
        add_row(plan, bundle, "A", f"C-{i}", status)
    for i in range(1, 5):
        add_row(plan, bundle, "B", f"C-{i}", "PASS")
    report = run(plan, bundle)
    arm = report["arms"]["A"]["first"]["overall"]
    assert arm["status_counts"] == {"PASS": 1, "FAIL": 1, "BLOCKED": 1, "NOT_RUN": 1}
    assert arm["rate_bounds"] == [0.25, 0.75]
    assert arm["wilson_ci95"] is None
    overall = report["comparisons"]["A-to-B"]["scopes"]["overall"]
    assert overall["status"] == "BLOCKED"
    assert overall["mcnemar_p"] is None
    assert overall["gain_percentage_points"] is None
    assert report["comparisons"]["A-to-B"]["scopes"]["language:zh"]["mcnemar_p"] == 1


def test_bootstrap_resamples_case_pairs_within_strata():
    plan, bundle = example()
    plan["comparisons"][0]["business_minimum_gain_pp"] = 15
    for index, case in enumerate(plan["cases"]):
        case.update(task_type="ordinary", complexity="short", language="en")
        add_row(plan, bundle, "A", case["case_id"], "PASS" if index == 0 else "FAIL")
        add_row(plan, bundle, "B", case["case_id"], "PASS")
    result = run(plan, bundle)["comparisons"]["A-to-B"]["scopes"]["overall"]
    low, high = result["paired_bootstrap_ci95_pp"]
    assert low < result["gain_percentage_points"] < high
    assert result["bootstrap_strata"] == {"cells": 1, "singleton_cells": 0}
    assert result["statistically_significant"] is False
    assert result["point_estimate_meets_business_minimum"] is True


def test_repeat_metrics_follow_prespecified_seed_order():
    plan, bundle = example()
    for case, outcomes in (("C-1", ["PASS", "FAIL", "PASS"]), ("C-2", ["PASS", "PASS", "PASS"])):
        for index, outcome in enumerate(outcomes, 1):
            add_row(plan, bundle, "A", case, outcome, phase="repeat", index=index)
    report = run(plan, bundle)["arms"]["A"]["repeat"]["overall"]
    assert report["repeat_first_pass"]["rate"] == 1
    assert report["pass_at_3"]["rate"] == 1
    assert report["pass_all_3"]["rate"] == 0.5
    assert report["seed_pass_rate_variance"] == pytest.approx(1 / 18)
    assert report["transitions"]["13->17"]["PASS"]["FAIL"] == 1
    assert report["failure_class_transitions"]["17->19"]["FAIL:plan"]["PASS"] == 1
    bundle["rows"].pop()
    partial = run(plan, bundle)["arms"]["A"]["repeat"]["overall"]
    assert partial["status"] == "BLOCKED"
    assert partial["pass_at_3"]["rate"] == 1
    assert partial["pass_all_3"]["rate_bounds"] == [0, 0.5]
    assert partial["seed_pass_rate_variance"] is None
    assert partial["transitions"]["17->19"]["PASS"]["NOT_RUN"] == 1


@pytest.mark.parametrize("overrides", [
    {"attempt": 2}, {"seed": 99}, {"case_id": "other"}, {"run_id": "run-B"},
    {"configuration_sha256": "a" * 64}, {"pairing_sha256": "b" * 64},
    {"run_configuration_sha256": "c" * 64},
    {"evidence_sha256": "untied"}, {"status": "SKIPPED"},
])
def test_inexact_trial_identity_is_rejected(overrides):
    plan, bundle = example()
    row = add_row(plan, bundle, "A", "C-1", "PASS")
    row.update(overrides)
    with pytest.raises(ValueError):
        run(plan, bundle)


def test_unplanned_repeat_duplicate_and_changed_plan_are_refused():
    plan, bundle = example()
    with pytest.raises(ValueError, match="repeat panel"):
        add_row(plan, bundle, "A", "C-3", "PASS", phase="repeat")
        run(plan, bundle)
    bundle["rows"].clear()
    row = add_row(plan, bundle, "A", "C-1", "PASS")
    bundle["rows"].append({**row, "status": "FAIL", "failure_class": "plan"})
    with pytest.raises(ValueError, match="duplicate"):
        run(plan, bundle)
    original = digest(plan)
    altered = deepcopy(plan)
    altered["arms"]["B"]["backend"] = "rocm"
    with pytest.raises(ValueError, match="plan digest"):
        analyze(altered, bundle, expected_plan_sha256=original)
    with pytest.raises(ValueError, match="matched controls"):
        run(altered, bundle)


def test_separate_first_and_repeat_runs_retain_exact_phase_identities():
    plan, bundle = example()
    original = bundle["runs"]["run-A"]
    original["phases"] = ["first"]
    phase_digest = digest("different frozen repeat manifest")
    bundle["runs"]["repeat-A"] = {
        **original, "phases": ["repeat"], "run_configuration_sha256": phase_digest,
    }
    add_row(plan, bundle, "A", "C-1", "PASS", phase="repeat", run_id="repeat-A", run_configuration_sha256=phase_digest)
    report = run(plan, bundle)
    assert report["runs"]["repeat-A"]["run_configuration_sha256"] == phase_digest
    assert report["arms"]["A"]["repeat"]["overall"]["repeat_first_pass"]["status_counts"]["PASS"] == 1
    bundle["runs"]["other-repeat-A"] = dict(bundle["runs"]["repeat-A"])
    with pytest.raises(ValueError, match="multiple repeat runs"):
        run(plan, bundle)


@pytest.mark.parametrize("suite,cases,repeat", [
    ("TC-V2", 500, 50), ("MULTITOOL-V1", 600, 100), ("AGENTIC-PLAN-V1", 800, 160),
])
def test_canonical_profiles_use_frozen_panels(suite, cases, repeat):
    profile = frozen_suite(suite)
    assert len(profile["cases"]) == cases
    assert len(profile["repeat"]["case_ids"]) == repeat
    assert len(set(profile["repeat"]["seeds"])) == 3
    assert {case["case_id"] for case in profile["cases"]} >= set(profile["repeat"]["case_ids"])
