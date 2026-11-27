from copy import deepcopy

import pytest

from benchmarks.agentic_planning_v2.contract import UNKNOWN, predicate
from benchmarks.agentic_planning_v2.oracle import verify
from benchmarks.agentic_planning_v2.alignment import match_prefix


def ref(source, field):
    return {"from": source, "field": field}


def decision(value):
    return {"op": "eq", "left": ref("event", "decision"), "right": value}


def has(source, field):
    return {"op": "exists", "ref": ref(source, field)}


def fixture():
    contract = {"goal": "publish", "public_fields": ["draft"], "event_fields": ["decision", "approval", "draft_id"],
                "action_budget": 2, "tools": {"request_confirmation": {"inputs": ["draft_id"], "outputs": ["reply"]},
                                             "commit": {"inputs": ["draft_id", "approval"], "outputs": ["receipt"]}}}
    ask = {"id": "ask", "tool": "request_confirmation", "arguments": {"draft_id": ref("public", "draft")},
           "depends_on": [], "when": True}
    commit = {"id": "send", "tool": "commit", "arguments": {"draft_id": ref("public", "draft"),
              "approval": ref("event", "approval")}, "depends_on": ["ask"], "when": decision("approved")}
    plan = {"version": 2, "goal": "publish", "actions": [ask, commit],
            "stops": [{"when": decision("declined"), "disposition": "escalate"},
                      {"when": has("send", "receipt"), "disposition": "completed"}]}
    worlds = []
    for choice in ("approved", "declined"):
        event = {"decision": choice, "draft_id": "D1", "approval": "external-value"}
        steps = [{"tool": "request_confirmation", "args": {"draft_id": "D1"}, "result": {"reply": choice},
                  "event": event}]
        if choice == "approved":
            steps.append({"tool": "commit", "args": {"draft_id": "D1", "approval": "external-value"},
                          "result": {"receipt": "R1"}})
        worlds.append({"public": {"draft": "D1"}, "steps": steps,
                       "disposition": "completed" if choice == "approved" else "escalate"})
    return plan, contract, worlds


def test_public_counterfactuals_and_budget():
    plan, contract, worlds = fixture()
    dead = {**deepcopy(plan["actions"][1]), "id": "spare", "when": False}
    plan["actions"].insert(1, dead)
    result = verify(plan, contract, worlds)
    assert result["status"] == "PASS"
    assert [len(r["calls"]) for r in result["worlds"]] == [2, 1]
    assert verify(plan, {**contract, "action_budget": 1}, worlds)["status"] == "FAIL"


@pytest.mark.parametrize("mutation", ["disable", "declined", "cycle", "undefined", "unchecked", "stale"])
def test_reject_mutations(mutation):
    plan, contract, worlds = fixture()
    ask, commit = plan["actions"]
    if mutation == "disable":
        ask["when"] = {"op": "and", "args": [True, False]}
    if mutation == "declined":
        commit["when"] = decision("declined")
    if mutation == "cycle":
        ask["depends_on"] = ["send"]
    if mutation == "undefined":
        commit["when"] = has("ask", "private_future")
    if mutation == "unchecked":
        worlds[0]["steps"][0]["event"]["draft_id"] = "unrelated"
    if mutation == "stale":
        worlds[0]["steps"][0]["event"] = {"scope_changed": True}
    assert verify(plan, contract, worlds)["status"] == "FAIL"


def test_unknown_and_absence():
    expr = has("ask", "reply")
    assert predicate(expr, {}) is UNKNOWN
    assert predicate(expr, {"ask": {}}) is False
    assert predicate({"op": "not", "arg": expr}, {}) is UNKNOWN
    assert predicate({"op": "or", "args": [True, expr]}, {}) is True
    assert predicate({"op": "and", "args": [False, expr]}, {}) is False
    assert predicate({"op": "eq", "left": False, "right": 0}, {}) is False


def test_alignment_explores_ambiguous_bindings():
    calls = [{"tool": "read", "args": {}, "observation": {"data": {"id": "x"}}},
             {"tool": "follow", "args": {"id": "x"}, "observation": {"data": {}}}]
    actions = [{"id": k, "tool": "read", "depends_on": [], "arguments": {}} for k in ("a", "b")]
    actions.append({"id": "c", "tool": "follow", "depends_on": ["b"], "arguments": {"id": ref("b", "id")}})
    assert match_prefix(actions, calls, "") == 2
    calls[1]["args"] = {"id": "unseen"}
    assert match_prefix(actions, calls, "") == 1
