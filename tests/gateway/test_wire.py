import json

import pytest

from model_gateway import GatewayError, StreamAssembler, decode_completion

ARGUMENTS = '{"order_id":"PO-01","note":" 保留空白 📚 "}'
CALL = {"id": "call-1", "type": "function",
        "function": {"name": "lookup_order", "arguments": ARGUMENTS}}


def data(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def completion(**message):
    return {"choices": [{"index": 0, "finish_reason": "tool_calls", "message":
                         {"role": "assistant", "tool_calls": [CALL], **message}}]}


def chunk(delta, *, finish=None, index=0):
    return data({"id": "cmpl-test", "model": "local", "choices": [
        {"index": index, "delta": delta, "finish_reason": finish}
    ]})


def streamed_call(arguments=ARGUMENTS, *, index=0, call_id="call-1", tool="lookup_order"):
    return {"tool_calls": [{"index": index, "id": call_id, "type": "function",
                            "function": {"name": tool, "arguments": arguments}}]}


@pytest.mark.parametrize("cut", [1, 2, 3, 5, 8, 13, 16, 19, 22, 25, 27, 30, 33, 37])
def test_argument_chunk_boundaries_produce_the_same_complete_proposal(cut):
    stream = StreamAssembler()
    stream.feed(chunk({"role": "assistant", "reasoning_content": "先查订单"}))
    stream.feed(chunk(streamed_call(ARGUMENTS[:cut])))
    stream.feed(chunk({"tool_calls": [
        {"index": 0, "function": {"arguments": ARGUMENTS[cut:]}}
    ]}))
    stream.feed(chunk({}, finish="tool_calls"))
    stream.feed(b"[DONE]")
    observed = stream.finish()
    expected = decode_completion(data(completion(reasoning_content="先查订单")))
    assert observed == expected
    assert observed.calls[0].arguments_raw == ARGUMENTS
    assert observed.content == ""
    assert observed.reasoning == "先查订单"


@pytest.mark.parametrize("message", [
    {"role": "tool"},
    {"content": []},
    {"reasoning_content": {}},
    {"function_call": {"name": "legacy"}},
    {"tool_calls": []},
    {"tool_calls": {}},
    {"tool_calls": [{}]},
    {"tool_calls": [{**CALL, "type": "unknown"}]},
    {"tool_calls": [{**CALL, "id": ""}]},
    {"tool_calls": [{**CALL, "id": "id with spaces"}]},
    {"tool_calls": [{**CALL, "function": {**CALL["function"], "name": ""}}]},
    {"tool_calls": [{**CALL, "function": {**CALL["function"], "name": "not a name"}}]},
    {"tool_calls": [{**CALL, "function": {**CALL["function"], "arguments": {}}}]},
    {"tool_calls": [{**CALL, "function": {**CALL["function"], "arguments": "[]" }}]},
    {"tool_calls": [{**CALL, "function": {**CALL["function"], "arguments": '{"x":0,"x":1}'}}]},
    {"tool_calls": [CALL, CALL]},
    {"tool_calls": [CALL, {}]},
], ids=["role", "content-type", "reasoning-type", "legacy", "empty", "map", "missing-fields",
        "call-type", "empty-id", "id-format", "empty-name", "name-format", "decoded-arguments",
        "array-arguments", "duplicate-inner-fields", "duplicate-call", "invalid-batch-member"])
def test_terminal_wire_rejects_invalid_tool_message(message):
    with pytest.raises(GatewayError) as problem:
        decode_completion(data(completion(**message)))
    assert problem.value.code == "PROTOCOL_ERROR"


@pytest.mark.parametrize("events", [
    [],
    [b"[DONE]"],
    [chunk({}, finish="length"), b"[DONE]"],
    [chunk({}, finish="tool_calls"), b"[DONE]"],
    [chunk(streamed_call()), chunk({}, finish="stop"), b"[DONE]"],
    [chunk(streamed_call()), chunk({}, finish="tool_calls")],
    [chunk(streamed_call()), b"[DONE]"],
    [chunk(streamed_call(index=1)), chunk({}, finish="tool_calls"), b"[DONE]"],
    [chunk(streamed_call(index=-1))],
    [chunk(streamed_call(index=True))],
    [chunk(streamed_call(index=31))],
    [chunk(streamed_call(index="0"))],
    [chunk(streamed_call()), chunk(streamed_call(call_id="replacement"))],
    [chunk(streamed_call()), chunk(streamed_call(index=1)), chunk({}, finish="tool_calls"), b"[DONE]"],
    [chunk(streamed_call('{"x": 1,"x": 2}')), chunk({}, finish="tool_calls"), b"[DONE]"],
    [chunk(streamed_call('{"x": 1')), chunk({}, finish="tool_calls"), b"[DONE]"],
    [chunk(streamed_call('[]')), chunk({}, finish="tool_calls"), b"[DONE]"],
    [chunk(streamed_call()), chunk({}, finish="tool_calls"), chunk({"content": "extra"}), b"[DONE]"],
    [chunk(streamed_call()), chunk({}, finish="tool_calls"), b"[DONE]", chunk({"content": "extra"})],
    [chunk({}, finish="stop"), b"[DONE]", b"[DONE]"],
    [chunk({"role": "user"}), chunk({}, finish="stop"), b"[DONE]"],
    [chunk({"function_call": {"name": "legacy"}})],
    [chunk({}, index=1)],
    [chunk({}, index=True)],
    [b'{"choices": [], "choices": []}'],
], ids=["unstarted", "done-only", "incomplete-finish", "missing-calls", "stop-with-call",
        "missing-done", "missing-finish", "index-gap", "negative-index", "boolean-index",
        "too-many-calls", "string-index", "replaced-id", "duplicate-id", "duplicate-inner-fields",
        "truncated-arguments", "array-arguments", "delta-after-finish", "delta-after-done",
        "double-done", "wrong-role", "legacy-function", "wrong-choice", "boolean-choice",
        "duplicate-envelope-field"])
def test_stream_rejects_incomplete_ambiguous_or_invalid_batch(events):
    stream = StreamAssembler()
    with pytest.raises(GatewayError) as problem:
        for event in events:
            stream.feed(event)
        stream.finish()
    assert problem.value.code == "PROTOCOL_ERROR"

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
