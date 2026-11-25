"""Bounded batch decoding for the IJ-0.7 multi-tool profile."""

from model_gateway.errors import ErrorCode, GatewayError
from model_gateway.openai_protocol import MAX_BATCH_CALLS, MAX_WIRE_BYTES, assemble, require, validate_call_limit
from model_gateway.streaming import StreamAssembler
from model_gateway.strict_json import strict_object


MAX_NONSTREAM_CALLS = MAX_BATCH_CALLS


def decode_batched_completion(raw, *, max_calls):
    validate_call_limit(max_calls)
    envelope = strict_object(raw, max_bytes=MAX_WIRE_BYTES)
    if isinstance(envelope.get("error"), dict):
        raise GatewayError(ErrorCode.MODEL_ERROR, "model returned an error envelope")
    choices = envelope.get("choices")
    require(isinstance(choices, list) and len(choices) == 1, "expected one completion choice")
    choice = choices[0]
    require(isinstance(choice, dict), "invalid completion choice")
    index = choice.get("index", 0)
    require(type(index) is int and index == 0, "invalid completion choice index")
    return assemble(choice.get("message"), choice.get("finish_reason"), max_calls=max_calls)


def decode_batched_stream(events, *, max_calls):
    gate = StreamAssembler(max_calls=max_calls)
    for event in events:
        gate.feed(event)
    return gate.finish()
