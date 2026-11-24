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
