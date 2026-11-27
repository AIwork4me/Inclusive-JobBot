import json

import pytest

from benchmarks.root_cause.wire_profiles import decode_batched_completion
from model_gateway import GatewayError, decode_completion


def envelope(count, *, duplicate=False):
    calls = [{"id": f"call-{index}", "type": "function",
              "function": {"name": "read_stock", "arguments": '{"record_id":"BIN-2"}'}}
             for index in range(count)]
    if duplicate:
        calls[-1] = calls[0]
    return json.dumps({"choices": [{"index": 0, "finish_reason": "tool_calls",
                                    "message": {"role": "assistant", "tool_calls": calls}}]})


def test_benchmark_profile_accepts_long_parallel_batch_with_original_guardrails():
    raw = envelope(17)
    with pytest.raises(GatewayError, match="invalid tool call batch"):
        decode_completion(raw)
    assert len(decode_batched_completion(raw, max_calls=32).calls) == 17
    assert decode_batched_completion(envelope(16), max_calls=32) == decode_completion(envelope(16))
    with pytest.raises(GatewayError, match="invalid tool call batch"):
        decode_batched_completion(envelope(33), max_calls=32)
    with pytest.raises(ValueError, match="batch limit"):
        decode_batched_completion(raw, max_calls=33)
    with pytest.raises(GatewayError, match="duplicate tool call ID"):
        decode_batched_completion(envelope(17, duplicate=True), max_calls=32)


@pytest.mark.parametrize("count", (16, 17, 32, 33))
def test_explicit_wire_budget_preserves_stream_and_completion_parity(count):
    from benchmarks.root_cause.generation_capture import check_gateway

    calls = [{"id": f"call-{i}", "type": "function",
              "function": {"name": "test_read", "arguments": "{}"}} for i in range(count)]
    complete = {"choices": [{"message": {"role": "assistant", "tool_calls": calls}, "finish_reason": "tool_calls"}]}
    delta = {"choices": [{"index": 0,
                          "delta": {"tool_calls": [{"index": i, **call} for i, call in enumerate(calls)]},
                          "finish_reason": "tool_calls"}]}
    raw_stream = f"data: {json.dumps(delta)}\n\ndata: [DONE]\n\n".encode()
    raw_complete = json.dumps(complete).encode()
    assert check_gateway(raw_stream, True, max_calls=32)["status"] == ("PASS" if count <= 32 else "FAIL")
    assert check_gateway(raw_complete, False, max_calls=32)["status"] == ("PASS" if count <= 32 else "FAIL")
    assert check_gateway(raw_stream, True)["status"] == ("PASS" if count <= 16 else "FAIL")
    assert check_gateway(raw_complete, False)["status"] == ("PASS" if count <= 16 else "FAIL")


@pytest.mark.parametrize("problem", ("gap", "duplicate-id"))
def test_stream_rejects_invalid_batch_across_group_boundary(problem):
    from benchmarks.root_cause.wire_profiles import decode_batched_stream

    calls = [{"index": i, "id": f"call-{i}", "type": "function",
              "function": {"name": "test_read", "arguments": "{}"}} for i in range(17)]
    if problem == "gap":
        del calls[15]
    else:
        calls[-1]["id"] = calls[0]["id"]
    frame = {"choices": [{"index": 0, "delta": {"tool_calls": calls}, "finish_reason": "tool_calls"}]}
    with pytest.raises(GatewayError, match="not contiguous|duplicate tool call ID"):
        decode_batched_stream([json.dumps(frame).encode(), b"[DONE]"], max_calls=32)
