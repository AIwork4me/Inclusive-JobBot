"""Buffer and validate an entire SSE response before exposing tool proposals."""

from __future__ import annotations

from .base import Completion
from .errors import GatewayError
from .openai_protocol import MAX_CALLS, MAX_WIRE_BYTES, assemble, require, text_field
from .strict_json import MAX_ARGUMENT_BYTES, strict_object


class StreamAssembler:
    """Consumes SSE data-field values, including the terminal [DONE]."""

    def __init__(self, *, max_stream_bytes=MAX_WIRE_BYTES):
        if type(max_stream_bytes) is not int or not MAX_WIRE_BYTES <= max_stream_bytes <= 4 * MAX_WIRE_BYTES:
            raise ValueError("invalid aggregate stream byte budget")
        self._max_stream_bytes = max_stream_bytes
        self._size = 0
        self._done = False
        self._invalid = False
        self._finish = None
        self._usage = False
        self._identity: dict[str, str] = {}
        self._calls: dict[int, dict] = {}
        self._content: list[str] = []
        self._reasoning: list[str] = []

    def feed(self, payload: bytes) -> None:
        try:
            self._feed(payload)
        except GatewayError:
            self._invalid = True
            raise

    def _feed(self, payload: bytes) -> None:
        require(not self._invalid and not self._done, "extra data after stream termination")
        require(isinstance(payload, bytes), "stream event must be bytes")
        self._size += len(payload)
        require(self._size <= self._max_stream_bytes, "stream byte limit exceeded")
        if payload == b"[DONE]":
            require(self._finish is not None, "stream ended before a terminal choice")
            self._done = True
            return

        event = strict_object(payload, max_bytes=MAX_WIRE_BYTES)
        for field in ("id", "model"):
            if field in event:
                value = event[field]
                require(isinstance(value, str) and bool(value), f"invalid stream {field}")
                require(self._identity.setdefault(field, value) == value, f"stream {field} changed")
        choices = event.get("choices")
        if choices == []:
            require(self._finish is not None and not self._usage and isinstance(event.get("usage"), dict),
                    "unexpected empty stream choice")
            self._usage = True
            return
        require(self._finish is None, "extra choice after stream finish")
        require(isinstance(choices, list) and len(choices) == 1, "expected one stream choice")
        choice = choices[0]
        require(isinstance(choice, dict) and type(choice.get("index")) is int and choice["index"] == 0,
                "invalid stream choice index")
        delta = choice.get("delta")
        require(isinstance(delta, dict) and set(delta) <= {"role", "content", "reasoning_content",
                                                           "tool_calls", "refusal"},
                "invalid assistant delta")
        require("role" not in delta or delta["role"] == "assistant", "invalid stream role")
        require(delta.get("refusal") is None, "response includes unsupported refusal payload")
        self._content.append(text_field(delta.get("content"), "content"))
        self._reasoning.append(text_field(delta.get("reasoning_content"), "reasoning"))
        calls = delta.get("tool_calls")
        if calls is not None:
            require(isinstance(calls, list) and len(calls) <= MAX_CALLS, "invalid stream call batch")
            self._push_calls(calls)

        finish_reason = choice.get("finish_reason")
        if finish_reason is not None:
            require(finish_reason in ("stop", "tool_calls"), "stream is incomplete or unsupported")
            self._finish = finish_reason

    def _push_calls(self, pieces: list[dict]) -> None:
        event_indices = set()
        for piece in pieces:
            require(isinstance(piece, dict) and set(piece) <= {"index", "id", "type", "function"},
                    "invalid streamed tool call")
            index = piece.get("index")
            require(type(index) is int and 0 <= index < MAX_CALLS, "invalid streamed tool index")
            require(index not in event_indices, "duplicate tool index in one stream event")
            event_indices.add(index)
            call = self._calls.setdefault(index, {"function": {"name": "", "arguments": ""}})
            for field in ("id", "type"):
                value = piece.get(field)
                if value is not None:
                    require(isinstance(value, str) and field not in call, f"invalid or repeated streamed {field}")
                    call[field] = value
            function = piece.get("function")
            if function is not None:
                require(isinstance(function, dict) and set(function) <= {"name", "arguments"},
                        "invalid streamed function delta")
                for field, limit in (("name", 64), ("arguments", MAX_ARGUMENT_BYTES)):
                    value = text_field(function.get(field), field)
                    text = call["function"][field] + value
                    require(len(text.encode("utf-8")) <= limit, f"streamed {field} exceeds byte limit")
                    call["function"][field] = text

    def finish(self) -> Completion:
        require(self._done and not self._invalid, "stream did not terminate cleanly")
        require(set(self._calls) == set(range(len(self._calls))), "stream tool indices are not contiguous")
        return assemble(
            {"role": "assistant", "content": "".join(self._content),
             "reasoning_content": "".join(self._reasoning),
             "tool_calls": [self._calls[index] for index in range(len(self._calls))]},
            self._finish,
        )
