from copy import deepcopy

from benchmarks.agentic_planning_v2.budgets import assess_budgets
from benchmarks.agentic_planning_v2.execution import execute
from benchmarks.agentic_planning_v2.oracle import validate, verify
from benchmarks.agentic_planning_v2.reachability import missing_effects


def test_independent_read_order_and_wrong_final():
    contract = {"goal": "compare", "public_fields": [], "event_fields": [], "action_budget": 2,
                "tools": {tool: {"inputs": [], "outputs": ["count"]} for tool in ("hours", "items")}}
    nodes = [{"id": name, "tool": name, "arguments": {}, "when": True, "depends_on": []} for name in contract["tools"]]
    left, right = ({"from": node["id"], "field": "count"} for node in nodes)
    guard = {"op": "and", "args": [{"op": "exists", "ref": term} for term in [left, right]]}
    plan = {"version": 2, "goal": "compare", "actions": nodes, "stops": [{
        "when": guard, "disposition": "completed", "facts": {"answer": {"if": {"op": "ge", "left": left, "right": right},
                                                                       "then": "yes", "else": "no"}}}]}
    world = {"public": {}, "disposition": "completed", "facts": {"answer": "no"},
             "steps": [{"tool": n["tool"], "args": {}, "result": {"count": i}, "after": []} for i, n in enumerate(nodes)]}
    assert verify(plan, contract, [world])["status"] == "PASS"
    plan["actions"].reverse()
    assert verify(plan, contract, [world])["status"] == "PASS"
    plan["stops"][0]["facts"]["answer"] = "yes"
    assert verify(plan, contract, [world])["status"] == "FAIL"


def test_optional_node_can_be_unreachable():
    nodes = [{"id": "first", "tool": "read", "when": False, "depends_on": []},
             {"id": "alternative", "tool": "mirror", "when": True, "depends_on": []}]
    assert missing_effects(nodes, [{"read", "mirror"}], {}) == []
    assert missing_effects(nodes, [{"read"}], {}) == [["read"]]


def test_retry_and_context_are_independent_of_graph_size():
    result = assess_budgets({"actions": [{"when": True}, {"when": False}]},
                            {"tool_calls": 1, "model_requests": 1, "peak_context_tokens": 32, "retries": 0},
                            calls=1, model_requests=2, retries=1)
    assert result["graph_nodes"] == 2 and result["conditional_nodes"] == 1
    statuses = {k: v["status"] for k, v in result["dimensions"].items()}
    assert statuses == {"tool_calls": "PASS", "model_requests": "FAIL", "peak_context_tokens": "NOT_RUN", "retries": "FAIL"}


def test_scope_revision_invalidates_old_observation():
    def node(name, tool, **args):
        return {"id": name, "tool": tool, "when": True, "arguments": args, "depends_on": []}
    lookup = node("get", "lookup")
    follow = {**node("follow", "read", id={"from": "get", "field": "id"}), "depends_on": ["get"]}
    plan = {"actions": [lookup, follow], "stops": []}
    def invoke(tool, args):
        assert tool == "lookup"
        return {"code": "ok", "data": {"id": "outdated"},
                "external_event": {"source": "synthetic_external_user", "revised_reference": "new"}}
    assert execute(plan, {}, 2, invoke)["reason"] == "no enabled action"
