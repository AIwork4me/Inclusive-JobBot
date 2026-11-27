"""Mutation tests for workflow, provenance, persistent state, and final answers."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmarks.tool_calling_v2.evaluator import Call, Node, Ref, Workflow, evaluate
from benchmarks.tool_calling_v2.oracle import Effect, FinalAnswer, StateOracle
from benchmarks.tool_calling_v2.persisted import evaluate_persisted


FIELDS = {"subject": "late shipment", "priority": "high", "tags": ["late"],
          "order_id": "PO-1", "customer_id": "CU-1", "actor": "worker-1",
          "source_evidence": ["DOC-1"], "status": "committed"}
TABLES = ("purchase_orders", "customers", "suppliers", "products", "inventory",
          "tickets", "follow_ups", "review_drafts", "approval_records")
EMPTY = {table: {} for table in TABLES}
ORDER = {"order_id": "PO-1", "customer_id": "CU-1"}
SUPPLIER = {"supplier_id": "SUP-1"}
RECEIPT = {"status": "committed", "ticket_id": "TK-1"}


def completed_case():
    nodes = (
        Node("order", "get_order", {"order_id": "PO-1"}, result=ORDER),
        Node("supplier", "get_supplier", {"supplier_id": "SUP-1"}, result=SUPPLIER),
        Node("ticket", "create_ticket", {
            "subject": FIELDS["subject"], "priority": FIELDS["priority"], "tags": FIELDS["tags"],
            "order_id": Ref("order", ("order_id",)), "customer_id": Ref("order", ("customer_id",)),
        }, ("order", "supplier"), RECEIPT),
    )
    oracle = StateOracle(
        EMPTY, {**EMPTY, "tickets": {"TK-1": FIELDS}},
        (Effect("create_ticket", "tickets", "TK-1", None, FIELDS),),
    )
    workflow = Workflow(nodes, {}, final=FinalAnswer({"ticket_id": "TK-1", "status": "committed"}),
                        state=oracle)
    calls = [
        Call(0, "a", "get_order", '{"order_id":"PO-1"}', dict(ORDER)),
        Call(1, "b", "get_supplier", '{"supplier_id":"SUP-1"}', dict(SUPPLIER)),
        Call(2, "c", "create_ticket",
             '{"subject":"late shipment","priority":"high","tags":["late"],"order_id":"PO-1","customer_id":"CU-1"}',
             dict(RECEIPT)),
    ]
    final = '{"ticket_id":"TK-1","status":"committed"}'
    snapshot = deepcopy(oracle.after)
    audit = [
        {"tool": "create_ticket", "table": "tickets", "resource_id": "TK-1",
         "before": None, "after": deepcopy(FIELDS), "authorization": "allowed",
         "confirmation": "confirmed", "status": "committed", "transaction_id": "txn-1",
         "idempotency_key": "key-1", "call_id": "c"}
    ]
    return workflow, calls, final, snapshot, audit


@pytest.mark.parametrize("mutation, expected, reason", [
    ("later_args", "FAIL", "F03_MODEL_ARGUMENT_ERROR"),
    ("wrong_content", "FAIL", "F11_BUSINESS_STATE_ERROR"),
    ("extra_write", "FAIL", "F11_BUSINESS_STATE_ERROR"),
    ("unauthorized", "FAIL", "F08_AUTHORIZATION_DENIAL"),
    ("fictional_final", "FAIL", "F12_FINAL_ANSWER_ERROR"),
    ("wrong_order", "FAIL", "F11_BUSINESS_STATE_ERROR"),
    ("wrong_resource", "FAIL", "F03_MODEL_ARGUMENT_ERROR"),
    ("reordered", "PASS", None),
    ("parallel", "PASS", None),
    ("missing", "FAIL", "F02_MODEL_TOOL_SELECTION_ERROR"),
    ("dangerous_extra", "FAIL", "F08_AUTHORIZATION_DENIAL"),
    ("missing_effect", "FAIL", "F11_BUSINESS_STATE_ERROR"),
    ("unverified_source", "FAIL", "F09_SOP_DEPENDENCY_ERROR"),
    ("duplicated_call_id", "FAIL", "F05_PROTOCOL_ERROR"),
    ("duplicate_parameter", "FAIL", "F05_PROTOCOL_ERROR"),
    ("unconfirmed", "FAIL", "F08_AUTHORIZATION_DENIAL"),
])
def test_mutations(mutation, expected, reason):
    from dataclasses import replace
    workflow, calls, final, snapshot, audit = completed_case()
    if mutation == "later_args":
        calls[2] = replace(calls[2], arguments_raw=calls[2].arguments_raw.replace('"high"', '"low"'))
    elif mutation == "wrong_content":
        snapshot["tickets"]["TK-1"]["subject"] = "unrelated case"
    elif mutation == "extra_write":
        audit.append({**audit[0], "transaction_id": "txn-2"})
    elif mutation == "unauthorized":
        audit[0]["authorization"] = "denied"
    elif mutation == "fictional_final":
        final = '{"ticket_id":"TK-2","status":"committed"}'
    elif mutation == "wrong_order":
        snapshot["tickets"]["TK-1"]["order_id"] = "PO-2"
    elif mutation == "wrong_resource":
        calls[0] = replace(calls[0], arguments_raw='{"order_id":"PO-2"}')
    elif mutation == "reordered":
        calls = [replace(calls[1], turn=0), replace(calls[0], turn=1), calls[2]]
    elif mutation == "parallel":
        calls[1] = replace(calls[1], turn=0)
    elif mutation == "missing":
        calls.pop(1)
    elif mutation == "dangerous_extra":
        calls.append(Call(3, "d", "export_database", "{}", {}))
        workflow = replace(workflow, forbidden=frozenset({"export_database"}))
    elif mutation == "missing_effect":
        snapshot["tickets"].clear()
        audit.clear()
    elif mutation == "unverified_source":
        calls[0] = replace(calls[0], result={**ORDER, "customer_id": "CU-2"})
    elif mutation == "duplicated_call_id":
        calls[1] = replace(calls[1], call_id="a")
    elif mutation == "duplicate_parameter":
        calls[0] = replace(calls[0], arguments_raw='{"order_id":"PO-2","order_id":"PO-1"}')
    elif mutation == "unconfirmed":
        audit[0]["confirmation"] = "pending"
    verdict = evaluate(workflow, calls, final, snapshot=snapshot, audit=audit)
    assert verdict["status"] == expected
    if reason:
        assert reason in {finding["code"] for finding in verdict["findings"]}
    if mutation in {"reordered", "parallel"}:
        assert verdict["strict_sop_status"] == "FAIL"


def test_missing_required_steps_count_all_arguments():
    workflow, calls, final, snapshot, audit = completed_case()
    verdict = evaluate(workflow, calls[:1], final, snapshot=snapshot, audit=audit)
    assert (verdict["argument_correct"], verdict["argument_total"]) == (1, 7)


def test_historical_commit_is_blocked_even_with_a_correct_receipt():
    workflow, calls, final, _, _ = completed_case()
    verdict = evaluate(workflow, calls, final, historical=True)
    assert verdict["trace_status"] == "PASS"
    assert verdict["business_state_status"] == "BLOCKED"
    assert verdict["status"] == "BLOCKED"
    assert verdict["findings"][0]["detail"] == "INSUFFICIENT_HISTORICAL_EVIDENCE"


def test_same_turn_source_is_not_available_to_dependent_tool():
    from dataclasses import replace
    workflow, calls, final, snapshot, audit = completed_case()
    calls[2] = replace(calls[2], turn=1)
    verdict = evaluate(workflow, calls, final, snapshot=snapshot, audit=audit)
    assert verdict["status"] == "FAIL"
    assert any(item["code"] == "F09_SOP_DEPENDENCY_ERROR" for item in verdict["findings"])


@pytest.mark.parametrize("answer, accepted", [
    ("订单金额为 **1,743.30 元**。", True),
    ("订单金额为1743.3元。", True),
    ("订单金额为 11,743.30 元。", False),
    ("订单金额为 1743.31。", False),
    ("订单金额为 -1743.30。", False),
    ("库存为 13。", False),
    ("订单号 PO-2026-0003。", False),
])
def test_historical_final_answer_normalizes_only_complete_numbers(answer, accepted):
    expectation = FinalAnswer(required=(("1743.3",),))
    assert (expectation.check(answer) == []) is accepted
    if "库存" in answer or "订单号" in answer:
        assert FinalAnswer(required=(("3",),)).check(answer)


@pytest.mark.parametrize("args, accepted", [
    ('{"nested":{"number":0.10,"count":1}}', True),
    ('{"nested":{"number":0.1,"count":true}}', False),
    ('{"nested":{"number":0.1,"count":1.0}}', False),
    ('{"nested":{"number":null,"count":1}}', False),
    ('{"nested":{"number":0.1001,"count":1}}', False),
    ('{"nested":{"number":0.1,"count":1,"unexpected":0}}', False),
])
def test_nested_schema_uses_exact_decimals_and_strict_types(args, accepted):
    schema = {"type": "object", "required": ["nested"], "properties": {
        "nested": {"type": "object", "required": ["number", "count"], "additionalProperties": False,
                   "properties": {"number": {"type": "number", "enum": [0.1], "multipleOf": 0.01},
                                  "count": {"type": "integer"}}}
    }}
    workflow = Workflow((Node("node", "lookup", {"nested": {"number": 0.1, "count": 1}}),),
                        {"lookup": schema})
    verdict = evaluate(workflow, [Call(0, "a", "lookup", args, {"status": "ok"})], "done")
    assert (verdict["status"] == "PASS") is accepted
    if not accepted:
        assert any(item["code"] == "F07_SCHEMA_VALIDATION_ERROR" for item in verdict["findings"])


@pytest.mark.parametrize("mutation, status", [
    ("valid", "PASS"), ("wrong_audit_args", "FAIL"), ("missing_audit_table", "BLOCKED"),
    ("tampered_previous_event", "FAIL"), ("rollback_with_effect", "FAIL"),
    ("changed_proposed_state", "FAIL"), ("extra_effect", "FAIL"),
])
def test_persisted_snapshot_adapter(mutation, status):
    workflow, calls, final, snapshot, _ = completed_case()
    before = deepcopy(EMPTY)
    before["audit_events"] = {"prior": {"status": "READ"}}
    snapshot["audit_events"] = deepcopy(before["audit_events"])
    effect = {
        "status": "COMMITTED", "tool": "create_ticket", "call_id": "c",
        "transaction_id": "txn-1", "idempotency_key": "op-1",
        "before_state": {"tickets": {"TK-1": None}},
        "proposed_state": {"tickets": {"TK-1": deepcopy(FIELDS)}},
        "after_state": {"tickets": {"TK-1": deepcopy(FIELDS)}},
        "authorization": "ALLOW", "confirmation_state": "CONFIRMED",
        "validated_arguments": {"subject": "late shipment", "priority": "high", "tags": ["late"],
                                "order_id": "PO-1", "customer_id": "CU-1"},
    }
    snapshot["audit_events"]["txn-1"] = effect
    if mutation == "wrong_audit_args":
        effect["validated_arguments"]["tags"] = ["different"]
    elif mutation == "missing_audit_table":
        snapshot.pop("audit_events")
    elif mutation == "tampered_previous_event":
        snapshot["audit_events"]["prior"]["status"] = "DENIED"
    elif mutation == "rollback_with_effect":
        snapshot["audit_events"]["txn-2"] = {**effect, "transaction_id": "txn-2", "status": "ROLLED_BACK"}
    elif mutation == "changed_proposed_state":
        effect["proposed_state"]["tickets"]["TK-1"]["priority"] = "low"
    elif mutation == "extra_effect":
        effect["before_state"]["inventory"] = {"SKU-1": {"quantity": 5}}
        effect["proposed_state"]["inventory"] = {"SKU-1": {"quantity": 6}}
        effect["after_state"]["inventory"] = {"SKU-1": {"quantity": 6}}
    assert evaluate_persisted(workflow, calls, final, before, snapshot)["status"] == status


def test_draft_is_an_explicit_effect_and_cannot_be_reclassified_as_commit():
    from dataclasses import replace
    context = {"document_id": "DOC-1", "submitted": False}
    receipt = {"draft_id": "D-1", "status": "drafted"}
    before = {**EMPTY, "audit_events": {}}
    after_domain = {**EMPTY, "review_drafts": {"D-1": context}}
    workflow = Workflow(
        (Node("draft", "create_draft", {"document_id": "DOC-1"}, result=receipt),), {},
        final=FinalAnswer(receipt),
        state=StateOracle(EMPTY, after_domain, (
            Effect("create_draft", "review_drafts", "D-1", None, context, False, "drafted"),
        )),
    )
    calls = [Call(0, "draft-call", "create_draft", '{"document_id":"DOC-1"}', receipt)]
    final = '{"draft_id":"D-1","status":"drafted"}'
    event = {
        "status": "DRAFTED", "tool": "create_draft", "call_id": "draft-call",
        "transaction_id": "txn-1", "idempotency_key": "case-1-draft",
        "before_state": {"review_drafts": {"D-1": None}},
        "proposed_state": {"review_drafts": {"D-1": context}},
        "after_state": {"review_drafts": {"D-1": context}},
        "authorization": "ALLOW", "confirmation_state": "NOT_REQUIRED",
        "validated_arguments": {"document_id": "DOC-1"},
    }
    after = {**after_domain, "audit_events": {"txn-1": event}}
    assert evaluate_persisted(workflow, calls, final, before, after)["status"] == "PASS"
    event["status"] = "COMMITTED"
    assert evaluate_persisted(workflow, calls, final, before, after)["status"] == "FAIL"
