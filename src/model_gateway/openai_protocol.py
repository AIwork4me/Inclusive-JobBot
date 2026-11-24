"""Read one completed OpenAI-compatible Chat Completions message."""

from __future__ import annotations

import re

from .base import Completion, Proposal
from .errors import ErrorCode, GatewayError
from .strict_json import strict_object

MAX_WIRE_BYTES = 512 * 1024
MAX_CALLS = 16
MAX_NONSTREAM_CALLS = 32
NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")
CALL_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GatewayError(ErrorCode.PROTOCOL_ERROR, message)


def text_field(value, label: str) -> str:
    require(value is None or isinstance(value, str), f"{label} must be text or null")
    return "" if value is None else value


def decode_proposal(call: dict) -> Proposal:
    require(isinstance(call, dict) and set(call) == {"type", "id", "function"},
            "invalid tool call envelope")
    require(call["type"] == "function", "unsupported tool call type")
    function = call["function"]
    require(isinstance(function, dict) and set(function) == {"name", "arguments"},
            "invalid function envelope")
    proposal = Proposal(call["id"], function["name"], function["arguments"])
    parse_proposal(proposal)
    return proposal


def parse_proposal(proposal: Proposal) -> dict:
    require(isinstance(proposal.call_id, str) and bool(CALL_ID.fullmatch(proposal.call_id)),
            "invalid tool call ID")
    require(isinstance(proposal.name, str) and bool(NAME.fullmatch(proposal.name)),
            "invalid tool name")
    require(isinstance(proposal.arguments_raw, str), "tool arguments must be a JSON string")
    return strict_object(proposal.arguments_raw)


def assemble(message: dict, finish_reason: str, *, max_calls: int = MAX_CALLS) -> Completion:
    if type(max_calls) is not int or not 1 <= max_calls <= MAX_NONSTREAM_CALLS:
        raise ValueError("non-streamed tool batch limit must be between 1 and 32")
    require(isinstance(message, dict) and message.get("role") == "assistant",
            "expected an assistant message")
    require("function_call" not in message, "legacy function calls are unsupported")
    require(finish_reason in ("stop", "tool_calls"), "response is incomplete or unsupported")
    calls = message.get("tool_calls")
    if calls is None:
        calls = []
    require(isinstance(calls, list) and len(calls) <= max_calls, "invalid tool call batch")
    require(bool(calls) == (finish_reason == "tool_calls"), "tool call batch and finish reason disagree")
    proposals = tuple(decode_proposal(call) for call in calls)
    require(len({item.call_id for item in proposals}) == len(proposals), "duplicate tool call ID")
    return Completion(proposals, text_field(message.get("content"), "content"),
                      text_field(message.get("reasoning_content"), "reasoning"), finish_reason)


def decode_completion(raw: bytes | str, *, max_calls: int = MAX_CALLS) -> Completion:
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
