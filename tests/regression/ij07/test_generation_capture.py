import json

import pytest

from benchmarks.root_cause.generation_capture import CaptureError, correlate, protocol_reply


def example_reply():
    return {
        "id": "chatcmpl-1", "usage": {"prompt_tokens": 2, "completion_tokens": 1},
        "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
    }


def test_exact_generation_is_correlated_and_byte_preserved():
    trace = {
        "completion_id": "chatcmpl-1", "prompt_token_ids": [2, 5], "sampled_token_ids": [8],
        "stream": False, "sampled_bytes_hex": "74657374", "pre_parser_bytes_hex": "ff",
    }
    assert correlate([trace], example_reply(), False) == trace
    assert bytes.fromhex(trace["pre_parser_bytes_hex"]) == b"\xff"
    with pytest.raises(CaptureError, match="identity"):
        correlate([{**trace, "completion_id": "other"}], example_reply(), False)
    with pytest.raises(CaptureError, match="token count"):
        correlate([{**trace, "sampled_token_ids": []}], example_reply(), False)


def test_sse_requires_the_terminal_event_and_one_completion_id():
    frames = [
        {"id": "chatcmpl-1", "choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]},
        {"id": "chatcmpl-1", "choices": [], "usage": {"completion_tokens": 1}},
    ]
    wire = b"".join(b"data: " + json.dumps(frame).encode() + b"\n\n" for frame in frames)
    assert protocol_reply(wire + b"data: [DONE]\n\n", True)["choices"][0]["message"]["content"] == "ok"
    with pytest.raises(CaptureError, match="terminate"):
        protocol_reply(wire, True)
