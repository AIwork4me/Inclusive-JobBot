from collections import Counter
import json
import pytest

from benchmarks.slm10.ha11_panel import plan, require_effective_controls
from benchmarks.slm10 import ha11_panel_report


def test_transfer_panel_preserves_480_and_adds_240_with_balanced_first_positions():
    batches, metadata = plan("transfer")
    rows = [row for batch in batches for row in batch]
    assert metadata["planned"] == len(rows) == len({row["slot_id"] for row in rows}) == 720
    assert Counter(row["profile"] for row in rows) == {
        "DIRECT": 240, "ORIGINAL_SDK": 240, "SDK_MATCHED_CONTEXT_PhaseAware": 240,
    }
    assert len({row["case_id"] for row in rows}) == 60
    for batch in batches:
        assert Counter(row["profile"] for row in batch[::3]) == {
            "DIRECT": 5, "ORIGINAL_SDK": 5, "SDK_MATCHED_CONTEXT_PhaseAware": 5,
        }
    for start in range(0, len(batches), 4):
        assert len({batch[0]["weight"] for batch in batches[start:start + 4]}) == 4


def test_full_panel_uses_new_matched_original_and_all_frozen_repeats():
    batches, metadata = plan("tc-extension")
    rows = [row for batch in batches for row in batch]
    assert metadata["planned"] == len(rows) == len({row["slot_id"] for row in rows}) == 6600
    for weight in ("Original", "HA-O", "HA-P", "HA-H"):
        actual = [row for row in rows if row["weight"] == weight]
        assert Counter(row["track"] for row in actual) == {
            "direct_first": 500, "sdk_first": 500, "sdk_streaming": 500, "sdk_repeat": 150,
        }
        assert Counter(row["seed"] for row in actual if row["track"] == "sdk_repeat") == {101: 50, 211: 50, 307: 50}


def test_capture_gate_reads_effective_ml_budget_and_seed_for_each_forwarded_request():
    base = {"seed": 101, "stream": False, "temperature": 0, "cache_prompt": False,
            "max_completion_tokens": 768, "parallel_tool_calls": True,
            "chat_template_kwargs": {"enable_thinking": False}}
    slot = {"seed": 101, "track": "sdk_repeat"}
    require_effective_controls({"wire": [{"provider_request": json.dumps(base)}]}, slot)
    with pytest.raises(ValueError):
        require_effective_controls({"wire": [{"provider_request": json.dumps(
            base | {"max_completion_tokens": 65535})}]}, slot)


def test_native_token_exhaustion_has_distinct_diagnosis_from_sdk_transport_502():
    event = {"provider_request": '{"max_completion_tokens":768}', "provider_stop_reason": "length",
             "usage": {"completion_tokens": 768}, "native_evidence": {"status": "PASS"},
             "status": "FAIL", "failure": {"type": "GatewayError", "function": "require"}}
    trial = {"wire": [event], "calls": [], "failure": {"type": "AntigravityExecutionError"}}
    metrics = {"metrics": {"TERMINATION_CORRECTNESS": "BLOCKED"}}
    assert ha11_panel_report.failure_signature(trial, metrics) == "MODEL_OUTPUT_LIMIT"


def test_typed_binding_distinguishes_observed_rejection_missing_delivery_and_no_tool():
    turns = [{"reply": object()}]
    proposals = [{"call_id": "one"}]
    callback = {"call_id": "one", "status": "PASS",
                "binding": {"integer_conversions": [["profile", "max_width"]]}}
    status, counts = ha11_panel_report.typed_binding_evidence(turns, proposals, [callback])
    assert status == "PASS"
    assert counts == {"wire_proposals": 1, "callback_pass": 1, "callback_fail": 0,
                      "integer_conversions": 1, "missing_callbacks": 0}
    assert ha11_panel_report.typed_binding_evidence(turns, proposals, [])[0] == "BLOCKED"
    assert ha11_panel_report.typed_binding_evidence(turns, [], [callback])[0] == "FAIL"
    assert ha11_panel_report.typed_binding_evidence(turns, proposals, [callback, callback])[0] == "FAIL"
    rejected = {"call_id": "one", "status": "FAIL"}
    assert ha11_panel_report.typed_binding_evidence(turns, proposals, [rejected])[0] == "FAIL"
    assert ha11_panel_report.typed_binding_evidence([{}], [], [])[0] == "BLOCKED"
    assert ha11_panel_report.typed_binding_evidence(turns, [], [])[0] == "NOT_RUN"


def test_matched_weight_effect_keeps_gains_losses_and_unresolved_pairs():
    key = "SCOPED_COMPLETION"
    def rows(values):
        return {index: {"metrics": dict.fromkeys((*ha11_panel_report.REPORTED,
                                                 "EXACT_TOOL_ARGUMENT_MULTISET", key,
                                                 "TYPED_CALLBACK_BINDING"), value),
                        "duplicate_proposals": 0, "redundant_executions": 0}
                for index, value in enumerate(values)}

    comparison = ha11_panel_report.estimate([
        (rows(["PASS", "FAIL", "PASS", "BLOCKED"]), 1),
        (rows(["FAIL", "PASS", "PASS", "FAIL"]), -1),
    ])[key]
    assert comparison["pass_gain_pairs"] == comparison["pass_loss_pairs"] == 1
    assert comparison["adjudicated_pairs"] == 3
    assert comparison["shared_observed"] == 4
    assert comparison["difference_pp"] == 0
