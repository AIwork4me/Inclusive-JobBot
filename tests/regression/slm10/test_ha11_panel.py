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
