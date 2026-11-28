"""Trusted workflow phases determine which tool schemas a provider receives."""

from copy import deepcopy
from enum import StrEnum
import json

from .openai_protocol import MAX_WIRE_BYTES
from .strict_json import strict_object


class Phase(StrEnum):
    PLAN = "PLAN"
    ACT = "ACT"
    OBSERVE = "OBSERVE"
    REPLAN = "REPLAN"
    FINAL = "FINAL"
    CLARIFY = "CLARIFY"
    STOP = "STOP"


_TOOL_PHASES = {Phase.ACT, Phase.REPLAN}
_TRANSITIONS = {
    Phase.PLAN: {Phase.ACT, Phase.FINAL, Phase.CLARIFY, Phase.STOP},
    Phase.ACT: {Phase.OBSERVE, Phase.FINAL, Phase.CLARIFY, Phase.STOP},
    Phase.OBSERVE: {Phase.REPLAN, Phase.FINAL, Phase.CLARIFY, Phase.STOP},
    Phase.REPLAN: {Phase.ACT, Phase.OBSERVE, Phase.FINAL, Phase.CLARIFY, Phase.STOP},
    Phase.FINAL: {Phase.STOP},
    Phase.CLARIFY: {Phase.STOP},
    Phase.STOP: set(),
}


class PhaseToolPolicy:
    """A single host-owned, serial policy for a fixed model route."""

    def __init__(self, alias, tools):
        self._alias = alias
        self._tools = {item["function"]["name"]: item for item in deepcopy(tools)}
        if not alias or len(self._tools) != len(tools):
            raise ValueError("Fixed alias and unique tool definitions required")
        self._phase = Phase.PLAN
        self._allowed = frozenset()

    @property
    def phase(self):
        return self._phase

    @property
    def allowed(self):
        return self._allowed

    def advance(self, phase, allowed=()):
        allowed = frozenset(allowed)
        if (phase not in _TRANSITIONS[self._phase] or not allowed <= self._tools.keys()
                or (allowed and phase not in _TOOL_PHASES)):
            raise ValueError("Invalid phase transition or tool grant")
        self._phase = phase
        self._allowed = allowed

    def request(self, raw):
        if self._phase in {Phase.OBSERVE, Phase.STOP}:
            raise ValueError("Current phase does not permit a provider request")
        source = strict_object(raw, max_bytes=MAX_WIRE_BYTES)
        if source.get("model") != self._alias or "lora" in source:
            raise ValueError("Request must use the fixed model and its pinned adapter")
        tools = [item for name, item in self._tools.items() if name in self._allowed]
        updates = {"tools": tools, "tool_choice": "auto" if tools else "none"}
        body = json.loads(raw) | updates
        encoded = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
        if strict_object(encoded, max_bytes=MAX_WIRE_BYTES) != source | updates:
            raise ValueError("Phase policy rewrite loses provider request precision")
        return encoded
