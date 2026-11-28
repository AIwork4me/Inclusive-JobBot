from dataclasses import replace

import pytest

from business_tools import BusinessStore, create_ticket
from model_gateway import ExecutionContext, Gateway, GatewayError, Grant, Policy, Proposal, ToolSpec

CONTEXT = ExecutionContext("employee-1", "support", "session-1", "review", "task-1")
GRANT = Grant(CONTEXT.actor, CONTEXT.role, "save_draft", frozenset({"REV-01"}),
              frozenset({"review"}), write=True)
SCHEMA = {"type": "object", "required": ["review_id"], "properties": {"review_id": {"type": "string"}}}
PROPOSAL = Proposal("call-1", "save_draft", '{"review_id":"REV-01"}')


@pytest.mark.parametrize("target, status, allowed", [
    ("review_drafts", False, True), ("review_drafts", True, False),
    ("review_drafts", 0, False), ("tickets", False, False), ("approval_records", False, False),
])
def test_draft_only_capability_can_only_insert_unsubmitted_review(tmp_path, target, status, allowed):
    def handler(tx, arguments, _context):
        tx.put(target, arguments["review_id"], {"submitted": status})
        return {"review_id": arguments["review_id"]}

    spec = ToolSpec(SCHEMA, lambda args: args["review_id"], handler, write=True, draft_only=True)
    state = BusinessStore(tmp_path / "state.db")
    gateway = Gateway(state, {"save_draft": spec}, Policy((GRANT,)))
    if allowed:
        assert gateway.execute(PROPOSAL, CONTEXT) == {"review_id": "REV-01"}
        assert gateway.execute(replace(PROPOSAL, call_id="call-2"), CONTEXT) == {"review_id": "REV-01"}
        assert state.snapshot()["review_drafts"] == {"REV-01": {"submitted": False}}
        assert {event["status"] for event in state.snapshot()["audit_events"].values()} == {"DRAFTED", "REPLAYED"}
        with pytest.raises(GatewayError):
            gateway.execute(replace(PROPOSAL, call_id="call-3"), replace(CONTEXT, operation_id="task-other"))
    else:
        with pytest.raises(GatewayError) as failure:
            gateway.execute(PROPOSAL, CONTEXT)
        assert failure.value.code == "TOOL_EXECUTION_ERROR"
        assert state.snapshot()[target] == {}
    assert state.snapshot()["approval_records"] == {}


def test_create_ticket_persists_verified_relationship_and_arguments(tmp_path):
    store = BusinessStore(tmp_path / "state.db", initial={
        "customers": {"CU-01": {"tier": "gold"}, "CU-02": {"tier": "silver"}},
        "purchase_orders": {"PO-01": {"customer_id": "CU-01"}, "PO-02": {"customer_id": "CU-02"}},
    })
    schema = {
        "type": "object", "required": ["subject", "priority", "tags", "customer_id"],
        "properties": {"customer_id": {"type": "string"}, "order_id": {"type": "string"},
                       "subject": {"type": "string"}, "priority": {"enum": ["高"]}, "tags": {"type": "array"}},
    }
    grant = replace(GRANT, tool="create_ticket", resources=frozenset({"CU-01"}))
    tool = ToolSpec(schema, lambda args: args["customer_id"], create_ticket, write=True)
    gateway = Gateway(store, {"create_ticket": tool}, Policy((grant,)))
    proposal = Proposal("call-1", "create_ticket",
                        '{"customer_id":"CU-01","order_id":"PO-01","subject":" 发货跟踪 ",'
                        '"priority":"高","tags":["回访"]}')
    receipt = gateway.execute(proposal, CONTEXT, confirmation=gateway.confirm(proposal, CONTEXT))
    ticket = store.snapshot()["tickets"][receipt["ticket_id"]]
    assert ticket == {"subject": " 发货跟踪 ", "priority": "高", "tags": ["回访"],
                      "customer_id": "CU-01", "order_id": "PO-01", "actor": CONTEXT.actor, "status": "created",
                      "source_evidence": [{"table": "customers", "id": "CU-01"},
                                          {"table": "purchase_orders", "id": "PO-01"}]}
    wrong = replace(proposal, call_id="call-2", arguments_raw=proposal.arguments_raw.replace("PO-01", "PO-02"))
    next_context = replace(CONTEXT, operation_id="task-2")
    with pytest.raises(GatewayError) as failure:
        gateway.execute(wrong, next_context, confirmation=gateway.confirm(wrong, next_context))
    assert failure.value.code == "BUSINESS_VALIDATION_ERROR"
    assert store.snapshot()["tickets"] == {receipt["ticket_id"]: ticket}
