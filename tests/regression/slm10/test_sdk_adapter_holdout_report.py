from copy import deepcopy
from hashlib import sha256

import pytest


def test_holdout_pair_validation_rejects_missing_duplicate_or_tampered_trials():
    from benchmarks.slm10.sdk_adapter_holdout_report import validate_pairs
    from benchmarks.slm10.sdk_adapter_development import load_plan
    from evaluation.aeve.runtime import fingerprint

    plan, cases = load_plan()
    profiles = {"reference": {"component": "reference"}, "treatment": {"component": "compact_result_codec"}}
    run_id = "ijslm-adapters-" + "1" * 32
    rows = [{"case_id": case["case_id"], "arm": arm, "capture": {
        "trial_id": fingerprint([run_id, case["case_id"], arm, case["seed"]]),
        "profile": profiles[arm], "seed": case["seed"],
    }} for case in plan["cases"] for arm in case["arm_order"]]
    report = {"run_id": run_id, "profiles": profiles, "planned_case_ids": [c["case_id"] for c in plan["cases"]],
              "results": rows}
    assert len(validate_pairs(report, cases)) == 24
    for damaged in (rows[:-1], rows[:-1] + [rows[0]], [rows[1], rows[0], *rows[2:]]):
        with pytest.raises(ValueError, match="roster"):
            validate_pairs(report | {"results": damaged}, cases)
    altered = deepcopy(report)
    altered["results"][0]["capture"]["seed"] += 1
    with pytest.raises(ValueError, match="trial identity"):
        validate_pairs(altered, cases)


def test_absent_holdout_preserves_exact_six_arm_dispositions():
    from benchmarks.slm10.sdk_adapter_holdout_report import holdout_report

    report = holdout_report()
    assert report["physical_execution"] == "NOT_RUN"
    assert report["scoped_effect"]["finding"] == "INDETERMINATE"
    assert report["measured_trajectories"] == report["formal_trial_attribution"] == 0
    assert report["planned_trajectories"] == 24
    quality = report["summary"]["categorical"]["business_facts"]
    numeric = report["summary"]["numeric"]["input_tokens"]
    assert quality["not_run_pairs"] == numeric["not_run_pairs"] == 12
    assert quality["paired_difference_95"]["status"] == numeric["paired_mean_difference_95"]["status"] == "NOT_RUN"
    assert quality["paired_difference_95"]["interval"] is None
    assert numeric["paired_mean_difference_95"]["interval"] is None
    assert numeric["paired_mean_difference_95"]["replicates"] == 0
    causal = report["six_arm_dispositions"]
    assert causal["counts"] == {"PASS": 513, "FAIL": 0, "BLOCKED": 10, "NOT_RUN": 17}
    assert len(causal["unmeasured"]) == 27
    assert {row["reason"] for row in causal["unmeasured"] if row["physical_capture"] == "BLOCKED"} == {
        "missing matched request history"
    }
    assert {row["arm"] for row in causal["unmeasured"] if row["physical_capture"] == "NOT_RUN"} == {"A4"}


def test_effect_requires_resolved_pairs_treatment_exposure_and_positive_exact_test():
    from benchmarks.slm10.sdk_adapter_holdout_report import CATEGORICAL, scoped_effect

    def arm(status, exposure):
        metrics = dict.fromkeys(CATEGORICAL, status)
        return {"metrics": metrics, "request_byte_integrity": "BLOCKED", "compact_exposure": exposure,
                "physical_evidence": "PASS", "native_evidence_complete": "PASS"}

    pairs = [{"reference": arm("FAIL" if i < 5 else "PASS", "NOT_RUN"), "treatment": arm("PASS", "PASS")}
             for i in range(12)]
    result = scoped_effect(pairs)
    assert result["finding"] == "SUPPORTED_IN_HOLDOUT_SCOPE"
    assert result["one_sided_exact_sign_p"] == 0.03125
    assert scoped_effect(pairs[:-1])["finding"] == "INDETERMINATE"
    changed = deepcopy(pairs)
    changed[0]["treatment"]["compact_exposure"] = "NOT_RUN"
    assert scoped_effect(changed)["finding"] == "INDETERMINATE"
    changed = deepcopy(pairs)
    changed[-1]["treatment"]["metrics"]["output_contract"] = "FAIL"
    assert scoped_effect(changed)["finding"] == "INDETERMINATE"


def _pair(before, after, *, before_state="PASS", after_state="PASS", before_physical="PASS", after_physical="PASS"):
    from benchmarks.slm10.sdk_adapter_holdout_report import CATEGORICAL, NUMERIC

    return {arm: {"metrics": dict.fromkeys(CATEGORICAL, state), "physical_evidence": physical,
                  "measurements": {key: {"status": "BLOCKED" if value is None else "PASS", "value": value}
                                   for key in NUMERIC}}
            for arm, value, state, physical in (("reference", before, before_state, before_physical),
                                                 ("treatment", after, after_state, after_physical))}


def test_exact_quality_interval_retains_concordant_pairs_and_handles_extreme_counts():
    from benchmarks.slm10.sdk_adapter_holdout_report import _paired_metrics

    def metric(pairs):
        return _paired_metrics(pairs, planned_pairs=12)["categorical"]["business_facts"]

    # Solve P(X=0)=(1-p)^12 and P(X=12)=p^12 at each Bonferroni tail independently.
    extreme = 0.0125 ** (1 / 12)
    all_ties = metric([_pair(10, 10)] * 12)
    all_gains = metric([_pair(10, 10, before_state="FAIL")] * 12)
    all_losses = metric([_pair(10, 10, after_state="FAIL")] * 12)
    assert all_ties["resolved_pairs"] == 12
    assert all_ties["paired_pass_rate_difference"] == 0
    assert all_ties["paired_difference_95"]["interval"] == pytest.approx([extreme - 1, 1 - extreme])
    assert all_gains["paired_pass_rate_difference"] == 1
    assert all_gains["paired_difference_95"]["interval"] == pytest.approx([2 * extreme - 1, 1])
    assert all_losses["paired_difference_95"]["interval"] == pytest.approx([-1, 1 - 2 * extreme])


def test_numeric_interval_resamples_whole_pairs_and_reports_missing_denominator():
    from benchmarks.slm10.sdk_adapter_holdout_report import _paired_metrics

    pairs = [_pair(30, 10), _pair(20, 10, after_state="FAIL"), _pair(5, None),
             _pair(7, 999, after_physical="BLOCKED"), _pair(42, 41, after_state="NOT_RUN", after_physical="NOT_RUN")]
    report = _paired_metrics(pairs, planned_pairs=12)
    assert report == _paired_metrics(list(reversed(pairs)), planned_pairs=12)
    numeric = report["numeric"]["input_tokens"]
    assert numeric["planned_pairs"] == 12
    assert numeric["resolved_pairs"] == 2
    assert numeric["blocked_pairs"] == 2
    assert numeric["not_run_pairs"] == 8
    assert numeric["unresolved_pairs"] == 10
    assert numeric["mean_treatment_minus_reference"] == -15
    # The empirical resampling distribution is -20, -15, -10 with probabilities 1/4, 1/2, 1/4.
    assert numeric["paired_mean_difference_95"]["interval"] == [-20, -10]
    assert numeric["paired_mean_difference_95"]["replicates"] == 10_000
    quality = report["categorical"]["business_facts"]
    assert quality["resolved_pairs"] == 3
    assert quality["blocked_pairs"] == 1 and quality["not_run_pairs"] == 8
    assert quality["paired_pass_rate_difference"] == pytest.approx(-1 / 3)
    one = _paired_metrics([pairs[0]], planned_pairs=12)["numeric"]["input_tokens"]
    assert one["resolved_pairs"] == 1 and one["mean_treatment_minus_reference"] == -20
    assert one["paired_mean_difference_95"]["status"] == "BLOCKED"
    assert one["paired_mean_difference_95"]["interval"] is None


def test_capture_scores_actual_wire_delivery_and_separates_missing_token_evidence():
    from benchmarks.slm10.sdk_adapter_holdout_report import analyze_capture, CATEGORICAL
    from benchmarks.slm10.sdk_adapter_development import load_plan
    from evaluation.aeve.runtime import canonical

    _, cases = load_plan()
    case = cases[0]
    oracle = case["oracle"]
    node = oracle["nodes"][0]
    profile = {"component": "compact_result_codec"}
    snapshot = {"releases": {}, "external_approval": None}
    capture = {"trial_id": "fixture-trial", "profile": profile, "answer": canonical(oracle["answer"]).decode(),
               "failure": None, "wire": [], "request_audits": [], "before": snapshot, "after": snapshot,
               "host_protected_callbacks": [], "wall_ms": 21.75}
    args = canonical(node["arguments"]).decode()
    call = {"turn": 0, "tool": node["tool"], "arguments": node["arguments"], "arguments_raw": args,
            "decision": "EXECUTED", "result": node["result"], "trial_id": capture["trial_id"],
            "call_id": "call-source", "provider_request_id": "provider-0", "completion_id": "cmpl-0"}
    capture["calls"] = [call]

    def add_turn(turn, messages, content, finish, usage):
        body = canonical({"messages": messages, "stream": False}).decode()
        body_sha = sha256(body.encode()).hexdigest()
        response = canonical({"id": f"cmpl-{turn}", "object": "chat.completion", "created": 1, "model": "fixture",
                              "choices": [{"index": 0, "finish_reason": finish,
                                           "message": {"role": "assistant", **content}}], "usage": usage}).decode()
        audit = {"sdk_request_id": f"sdk-{turn}", "after_sha256": body_sha, "message_indices": [1] if turn else [],
                 "callback_sources": [["provider-0", "cmpl-0", "call-source"]] if turn else [], "profile": profile}
        capture["request_audits"].append(audit | {"provider_request_id": f"provider-{turn}", "status": "PASS"})
        capture["wire"].append({"sdk_request_id": f"sdk-{turn}", "provider_request_id": f"provider-{turn}",
                                "trial_id": capture["trial_id"], "adapter_audit": audit, "status": "PASS",
                                "provider_request": body, "provider_request_sha256": body_sha,
                                "response": response, "response_sha256": sha256(response.encode()).hexdigest(),
                                "completion_id": f"cmpl-{turn}", "http_status": 200, "response_capture_complete": True,
                                "content_type": "application/json", "native_evidence": {"status": "NOT_RUN"}})

    initial = {"role": "user", "content": case["public"]["prompt"]}
    add_turn(0, [initial], {"tool_calls": [{"id": call["call_id"], "type": "function",
                                            "function": {"name": node["tool"], "arguments": args}}]},
             "tool_calls", {"prompt_tokens": 20, "completion_tokens": 3, "total_tokens": 23})
    add_turn(1, [initial, {"role": "tool", "tool_call_id": call["call_id"], "name": call["tool"],
                           "content": canonical(node["result"]).decode()}], {"content": capture["answer"]}, "stop", None)
    measured = analyze_capture(capture, oracle, {}, public=case["public"])
    assert measured["physical_evidence"] == "BLOCKED"
    assert measured["metrics"] == dict.fromkeys(CATEGORICAL, "PASS")
    assert measured["compact_exposure"] == "PASS"
    assert measured["measurements"]["model_requests"] == {"status": "PASS", "value": 2}
    assert measured["measurements"]["input_tokens"] == {"status": "BLOCKED", "value": None}
    assert measured["measurements"]["end_to_end_latency_ms"] == {"status": "PASS", "value": 21.75}
    with pytest.raises(ValueError, match="public prompt"):
        analyze_capture(capture, oracle, {}, public=case["public"] | {"prompt": "another task"})
