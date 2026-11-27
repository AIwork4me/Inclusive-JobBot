"""Bounded batch decoding for the IJ-0.7 multi-tool profile."""

from dataclasses import replace
import json

from model_gateway.errors import ErrorCode, GatewayError
from model_gateway.openai_protocol import MAX_CALLS, MAX_WIRE_BYTES, assemble, decode_proposal, require
from model_gateway.strict_json import strict_object
from model_gateway.streaming import StreamAssembler


MAX_NONSTREAM_CALLS = 32


def decode_batched_completion(raw, *, max_calls):
    if type(max_calls) is not int or not MAX_CALLS <= max_calls <= MAX_NONSTREAM_CALLS:
        raise ValueError("non-streamed benchmark batch limit must be between 16 and 32")
    envelope = strict_object(raw, max_bytes=MAX_WIRE_BYTES)
    if isinstance(envelope.get("error"), dict):
        raise GatewayError(ErrorCode.MODEL_ERROR, "model returned an error envelope")
    choices = envelope.get("choices")
    require(isinstance(choices, list) and len(choices) == 1, "expected one completion choice")
    choice = choices[0]
    require(isinstance(choice, dict), "invalid completion choice")
    index = choice.get("index", 0)
    require(type(index) is int and index == 0, "invalid completion choice index")
    message, finish_reason = choice.get("message"), choice.get("finish_reason")
    calls = message.get("tool_calls") if isinstance(message, dict) else None
    if not isinstance(calls, list) or len(calls) <= MAX_CALLS:
        return assemble(message, finish_reason)
    require(len(calls) <= max_calls, "invalid tool call batch")
    base = assemble({**message, "tool_calls": calls[:MAX_CALLS]}, finish_reason)
    proposals = base.calls + tuple(decode_proposal(call) for call in calls[MAX_CALLS:])
    require(len({item.call_id for item in proposals}) == len(proposals), "duplicate tool call ID")
    return replace(base, calls=proposals)

def decode_batched_stream(events, *, max_calls):
    """Buffer a wide benchmark batch using the original bounded SSE validators."""
    if type(max_calls) is not int or not MAX_CALLS <= max_calls <= MAX_NONSTREAM_CALLS:
        raise ValueError("streamed benchmark batch limit must be between 16 and 32")
    if max_calls == MAX_CALLS:
        gate = StreamAssembler()
        for event in events:
            gate.feed(event)
        return gate.finish()

    events = list(events)
    require(sum(map(len, events)) <= MAX_WIRE_BYTES, "stream byte limit exceeded")
    first, second = StreamAssembler(), StreamAssembler()
    has_second = False
    for payload in events:
        if payload == b"[DONE]":
            first.feed(payload)
            if has_second:
                second.feed(payload)
            continue
        event = strict_object(payload, max_bytes=MAX_WIRE_BYTES)
        choices = event.get("choices")
        choice = choices[0] if isinstance(choices, list) and len(choices) == 1 else None
        delta = choice.get("delta") if isinstance(choice, dict) else None
        calls = delta.get("tool_calls") if isinstance(delta, dict) else None
        if calls is None:
            first.feed(payload)
            second.feed(payload)
            continue
        require(isinstance(calls, list) and len(calls) <= max_calls, "invalid stream call batch")
        parts = ([], [])
        for call in calls:
            index = call.get("index") if isinstance(call, dict) else None
            require(type(index) is int and 0 <= index < max_calls, "invalid streamed tool index")
            group, offset = divmod(index, MAX_CALLS)
            parts[group].append({**call, "index": offset})
        has_second |= bool(parts[1])
        for gate, batch in zip((first, second), parts, strict=True):
            frame_choice = {**choice, "delta": {**delta, "tool_calls": batch}}
            frame = {**event, "choices": [frame_choice]}
            gate.feed(json.dumps(frame, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    base = first.finish()
    if not has_second:
        return base
    tail = second.finish()
    require(len(base.calls) == MAX_CALLS, "stream tool indices are not contiguous")
    proposals = base.calls + tail.calls
    require(len({item.call_id for item in proposals}) == len(proposals), "duplicate tool call ID")
    return replace(base, calls=proposals)
