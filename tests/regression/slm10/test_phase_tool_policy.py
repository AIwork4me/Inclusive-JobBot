import json

import pytest

from model_gateway import GatewayError
from model_gateway.phase_tool_policy import Phase, PhaseToolPolicy


TOOLS = [
    {"type": "function", "function": {"name": name, "parameters": {"type": "object"}}}
    for name in ("read_layout", "read_asset")
]
RAW = json.dumps({"model": "fixed", "tools": TOOLS, "tool_choice": "none",
                  "messages": [{"role": "user", "content": "Read the layout"}]})


def test_phase_transitions_allow_only_current_grants_and_preserve_context():
    policy = PhaseToolPolicy("fixed", TOOLS)
    assert json.loads(policy.request(RAW)) == json.loads(RAW) | {"tools": [], "tool_choice": "none"}
    policy.advance(Phase.ACT, {"read_layout"})
    assert json.loads(policy.request(RAW)) == json.loads(RAW) | {"tools": TOOLS[:1], "tool_choice": "auto"}
    policy.advance(Phase.OBSERVE)
    with pytest.raises(ValueError):
        policy.request(RAW)
    policy.advance(Phase.REPLAN, {"read_asset"})
    assert json.loads(policy.request(RAW))["tools"] == TOOLS[1:]
    policy.advance(Phase.FINAL)
    assert json.loads(policy.request(RAW))["tool_choice"] == "none"
    policy.advance(Phase.STOP)
    with pytest.raises(ValueError):
        policy.request(RAW)
    with pytest.raises(ValueError):
        policy.advance(Phase.ACT, {"read_layout"})


def test_clarification_cannot_grant_or_reopen_tools():
    policy = PhaseToolPolicy("fixed", TOOLS)
    with pytest.raises(ValueError):
        policy.advance(Phase.CLARIFY, {"read_layout"})
    policy.advance(Phase.CLARIFY)
    assert json.loads(policy.request(RAW))["tools"] == []
    with pytest.raises(ValueError):
        policy.advance(Phase.ACT, {"read_layout"})


def test_rejects_adapter_override_duplicate_keys_and_unregistered_grants():
    policy = PhaseToolPolicy("fixed", TOOLS)
    with pytest.raises(ValueError):
        policy.advance(Phase.ACT, {"business_write"})
    for body in (json.loads(RAW) | {"lora": []}, json.loads(RAW) | {"model": "other"}):
        with pytest.raises(ValueError):
            policy.request(json.dumps(body))
    with pytest.raises(GatewayError):
        policy.request('{"model":"fixed","model":"other"}')
