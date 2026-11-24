"""Bounded non-streamed batch decoding for the IJ-0.7 multi-tool profile."""

from dataclasses import replace

from model_gateway.errors import ErrorCode, GatewayError
from model_gateway.openai_protocol import MAX_CALLS, MAX_WIRE_BYTES, assemble, decode_proposal, require
from model_gateway.strict_json import strict_object


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
