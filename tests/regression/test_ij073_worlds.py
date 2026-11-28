import json

from benchmarks.agentic_planning_v2.budgets import assess_budgets
from benchmarks.agentic_planning_v2.execution import execute
from benchmarks.agentic_planning_v2.oracle import verify
from benchmarks.agentic_planning_v2.reachability import missing_effects
from benchmarks.agentic_planning_v2.safety import reconcile
from benchmarks.agentic_planning_v2.runner import evaluate_raw, plan_request


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
    contract["tools"]["mirror"] = contract["tools"]["hours"]
    nodes[0]["tool"] = "mirror"
    assert verify(plan, contract, [world])["status"] == "FAIL"
    world["steps"][0]["equivalent_tools"] = ["mirror"]
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

def test_model_boundary_and_public_inputs_only():
    contract = {"goal": "clarify", "public_fields": ["subject"], "event_fields": [], "tools": {},
                "action_budget": 0, "private_future": "sentinel"}
    world = {"public": {"subject": "task"}, "disposition": "clarify", "steps": [], "facts": {"subject": "task"}}
    plan = {"version": 2, "goal": "clarify", "actions": [], "stops": [
        {"when": True, "disposition": "clarify", "facts": {"subject": {"from": "public", "field": "subject"}}}]}
    request = plan_request("local", "Ask for missing input", world["public"], contract, {"tool_calls": 0})
    assert json.loads(request["messages"][1]["content"])["public"] == world["public"]
    assert "sentinel" not in json.dumps(request)
    assert "response_format" not in request
    assert evaluate_raw(json.dumps(plan), contract, [world])["status"] == "PASS"
    assert evaluate_raw(json.dumps(plan), contract, [])["status"] == "BLOCKED"
    for raw in ('{"version":2,"version":2}', '[]', 'not JSON'):
        assert evaluate_raw(raw, contract, [world])["status"] == "FAIL"

def test_denied_write_requires_unchanged_state_and_audit():
    clean = {"drafts": {}, "deliverables": {}}
    leaked = {"drafts": {"unapproved": {"state": "pending"}}, "deliverables": {}}
    row = {"tool": "stage", "args": {"reference": "A"}, "observation": {"code": "permission_denied", "data": {}},
           "before": clean, "after": clean}
    assert reconcile({"subject": "A"}, [row])["status"] == "PASS"
    assert reconcile({"subject": "A"}, [{**row, "after": leaked}])["status"] == "FAIL"
    assert reconcile({"subject": "A"}, [{**row, "before": None}])["status"] == "BLOCKED"
