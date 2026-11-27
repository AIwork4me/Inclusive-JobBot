"""The persisted oracle consumes actual gateway-owned SQLite snapshots."""

import hashlib
import json

import pytest

from benchmarks.tool_calling_v2.evaluator import Call, Node, Workflow
from benchmarks.tool_calling_v2.oracle import Effect, FinalAnswer, StateOracle
from benchmarks.tool_calling_v2.persisted import evaluate_persisted
from business_tools import BusinessStore
from model_gateway import ExecutionContext, Gateway, Grant, Policy, Proposal, ToolSpec


@pytest.mark.parametrize("wrong_association", [False, True], ids=["valid_commit", "wrong_persisted_association"])
def test_sqlite_ticket_state_is_verified_independently(tmp_path, wrong_association):
    initial = {"purchase_orders": {"PO-1": {"order_id": "PO-1"}}}
    database = tmp_path / "qualification.sqlite3"
    store = BusinessStore(database, initial=initial)
    before_snapshot = store.snapshot()
    expected_args = {"order_id": "PO-1", "subject": "late shipment", "priority": "high", "tags": ["late"]}
    ticket_id = "TK-1"
    receipt = {"ticket_id": ticket_id, "status": "committed"}
    expected_ticket = {
        **expected_args, "status": "committed", "actor": "worker-1", "source_evidence": ["DOC-1"],
    }

    def save_ticket(tx, args, ctx):
        ticket = {**args, "actor": ctx.actor, "status": "committed", "source_evidence": ["DOC-1"]}
        if wrong_association:
            ticket["order_id"] = "PO-2"
        tx.put("tickets", ticket_id, ticket)
        return receipt

    schema = {
        "type": "object", "additionalProperties": False,
        "required": list(expected_args),
        "properties": {
            "order_id": {"type": "string"}, "subject": {"type": "string"},
            "priority": {"enum": ["high", "low"]}, "tags": {"type": "array", "items": {"type": "string"}},
        },
    }
    spec = ToolSpec(schema, lambda args: args["order_id"], save_ticket, write=True)
    context = ExecutionContext("worker-1", "reviewer", "session-1", "ready", "operation-1")
    grant = Grant("worker-1", "reviewer", "create_ticket", frozenset({"PO-1"}), frozenset({"ready"}), True)
    gateway = Gateway(store, {"create_ticket": spec}, Policy((grant,)))
    raw = json.dumps(expected_args)
    proposal = Proposal("tool-1", "create_ticket", raw)
    confirmation = gateway.confirm(proposal, context)
    observed = gateway.execute(proposal, context, confirmation=confirmation)

    # The confirmation handle comes from the trusted action. The expected
    # fields and approval transition are specified independently of SQLite.
    fingerprint_input = (
        "create_ticket", raw, "PO-1", "worker-1", "reviewer", "session-1", "ready", "operation-1",
    )
    expected_approval = {
        "actor": "worker-1", "role": "reviewer", "session_id": "session-1", "operation_id": "operation-1",
        "workflow_state": "ready", "tool": "create_ticket", "resource": "PO-1", "status": "CONSUMED",
        "validated_arguments": expected_args,
        "fingerprint": hashlib.sha256(json.dumps(fingerprint_input).encode("utf-8")).hexdigest(),
    }
    initial_state = {name: {} for name in (
        "purchase_orders", "suppliers", "products", "inventory", "customers",
        "tickets", "follow_ups", "review_drafts", "approval_records",
    )}
    initial_state.update(initial)
    final_state = {**initial_state, "tickets": {ticket_id: expected_ticket},
                   "approval_records": {confirmation: expected_approval}}
    workflow = Workflow(
        (Node("create", "create_ticket", expected_args, result=receipt),), {"create_ticket": schema},
        final=FinalAnswer(receipt),
        state=StateOracle(initial_state, final_state,
                          (Effect("create_ticket", "tickets", ticket_id, None, expected_ticket),)),
    )
    result = evaluate_persisted(
        workflow, [Call(0, proposal.call_id, proposal.name, raw, observed)], json.dumps(observed),
        before_snapshot, BusinessStore(database).snapshot(),
    )
    assert observed == receipt
    assert result["trace_status"] == "PASS"
    assert result["business_state_status"] == ("FAIL" if wrong_association else "PASS")
    assert result["status"] == result["business_state_status"]
