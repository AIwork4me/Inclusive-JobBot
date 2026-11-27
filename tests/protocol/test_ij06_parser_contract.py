import json
import random

import pytest

from benchmarks.tool_calling_v2.parser.assessment import assess, validators_for
from benchmarks.tool_calling_v2.parser.fixtures import build
from benchmarks.tool_calling_v2.parser.run_wire import inspect_response
from model_gateway.errors import GatewayError
from model_gateway.streaming import StreamAssembler


def event(delta, finish=None):
    return json.dumps({"id": "response", "model": "fixture", "choices": [
        {"index": 0, "delta": delta, "finish_reason": finish},
    ]}, ensure_ascii=False).encode("utf-8")


def chunks(raw, seed, *, second_id="call_b"):
    randomizer = random.Random(seed)
    starts = [0, *sorted(randomizer.sample(range(1, len(raw)), min(6, len(raw) - 1))), len(raw)]
    yield event({"role": "assistant", "reasoning_content": "独立推理"})
    yield event({"tool_calls": [
        {"index": 0, "id": "call_a", "type": "function", "function": {"name": "echo_text"}},
        {"index": 1, "id": second_id, "type": "function", "function": {"name": "echo_text", "arguments": '{"text":"second"}'}},
    ]})
    for left, right in zip(starts, starts[1:]):
        yield event({"tool_calls": [{"index": 0, "function": {"arguments": raw[left:right]}}]})
    yield event({}, "tool_calls")
    yield b"[DONE]"


@pytest.mark.parametrize("seed", range(12))
def test_random_unicode_argument_splits_preserve_two_call_identities(seed):
    raw = '{"text":"  文档📦 \\n 保留  "}'
    wire = StreamAssembler()
    for payload in chunks(raw, seed):
        wire.feed(payload)
    completion = wire.finish()
    assert completion.reasoning == "独立推理"
    assert completion.content == ""
    assert [(call.call_id, call.arguments_raw) for call in completion.calls] == [
        ("call_a", raw), ("call_b", '{"text":"second"}'),
    ]


@pytest.mark.parametrize("seed", (0, 3, 11))
def test_duplicate_arguments_are_never_coerced_across_stream_fragments(seed):
    wire = StreamAssembler()
    for payload in chunks('{"text":"first","text":"second"}', seed):
        wire.feed(payload)
    with pytest.raises(GatewayError, match="duplicate JSON key"):
        wire.finish()


def test_duplicate_call_identifier_rejected_after_assembly():
    wire = StreamAssembler()
    for payload in chunks('{"text":"first"}', 6, second_id="call_a"):
        wire.feed(payload)
    with pytest.raises(GatewayError, match="duplicate tool call ID"):
        wire.finish()


def test_native_and_strict_rejection_have_independent_statuses():
    data = build(include_lexical=True)
    fixture = next(case for case in data["fixtures"] if case["id"] == "duplicate-param-00")
    corrupted = {"tool_calls": [{"function": {"name": "echo_text", "arguments": '{"text":"a","text":"b"}'}}]}
    score = assess(fixture, {"message": corrupted, "stream_message": corrupted}, validators_for(data["tools"]))
    assert score == {"native": "FAIL", "strict_arguments": "PASS", "parser_stream_parity": "PASS"}


def test_http_parser_error_frame_preserves_native_rejection():
    error = json.dumps({"error": {
        "code": 500, "message": "The model produced output that does not match the expected peg-native format",
    }}).encode("ascii")
    raw = b"data: " + event({"role": "assistant"}) + b"\r\n\r\ndata: " + error + b"\r\n\r\n"
    assert inspect_response(200, raw, True, 1)["parser_rejected"] is True


def test_both_fixture_versions_are_stable_and_independently_identified():
    old = build()
    new = build(include_lexical=True)
    assert len(old["fixtures"]) == 130
    assert len(new["fixtures"]) == 146
    assert new["fixtures"][:130] == old["fixtures"]
    assert new["version"] != old["version"]
