import concurrent.futures
import json
from dataclasses import replace
from threading import Event
from types import SimpleNamespace

import pytest

from business_tools import BusinessStore
from model_gateway import ExecutionContext, Gateway, GatewayError, Grant, Policy, Proposal, ToolSpec
from model_gateway import execution_policy
from model_gateway.errors import TransientToolError
from model_gateway.metrics import ExecutionMetrics

APPROVED = ExecutionContext("employee-1", "support", "session-1", "reviewed", "task-1")
TICKET = Proposal("call-1", "create_ticket", '{"customer_id":"CU-01","subject":"送货追踪","priority":"高","tags":["回访"]}')
SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["customer_id", "subject", "priority", "tags"], "properties": {
              "customer_id": {"type": "string", "pattern": r"^CU-[0-9]+\Z"},
              "subject": {"type": "string", "minLength": 1, "maxLength": 30},
              "priority": {"enum": ["低", "中", "高"]},
              "tags": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
          }}


def persist_ticket(tx, arguments, context):
    tx.put("tickets", "TK-01", {**arguments, "order_id": None,
                                 "source_evidence": "synthetic-note-1", "actor": context.actor,
                                 "status": "created"})
    return {"ticket_id": "TK-01", "status": "created"}


@pytest.fixture
def setup_gateway(tmp_path):
    def create(handler=persist_ticket, *, write=True, **settings):
        db = BusinessStore(tmp_path / "business.db", initial={"customers": {"CU-01": {"tier": "gold"}}})
        rule = Grant("employee-1", "support", "create_ticket", frozenset({"CU-01"}),
                     frozenset({"reviewed"}), write=write)
        spec = ToolSpec(SCHEMA, lambda args: args["customer_id"], handler, write=write)
        return db, Gateway(db, {"create_ticket": spec}, Policy((rule,)), **settings)
    return create


@pytest.mark.parametrize("context", [
    replace(APPROVED, actor="employee-2"), replace(APPROVED, actor=""),
    replace(APPROVED, role="manager"), replace(APPROVED, role=""),
    replace(APPROVED, workflow_state="draft"), replace(APPROVED, workflow_state="committed"),
    replace(APPROVED, workflow_state=""), replace(APPROVED, operation_id=None),
    replace(APPROVED, operation_id=""), replace(APPROVED, session_id=""),
], ids=["another-actor", "missing-actor", "wrong-role", "missing-role", "draft", "committed",
        "missing-state", "no-operation", "empty-operation", "missing-session"])
def test_denial_prevents_persistence_and_approval(setup_gateway, context):
    db, gateway = setup_gateway()
    with pytest.raises(GatewayError) as failure:
        gateway.confirm(TICKET, context)
    assert failure.value.code == "POLICY_DENIED"
    with pytest.raises(GatewayError) as failure:
        gateway.execute(TICKET, context)
    assert failure.value.code == "POLICY_DENIED"
    assert db.snapshot()["tickets"] == {}
    assert db.snapshot()["approval_records"] == {}


@pytest.mark.parametrize(("patch", "code"), [
    ({"customer_id": "CU-02"}, "POLICY_DENIED"),
    ({"customer_id": " CU-01 "}, "SCHEMA_ERROR"),
    ({"customer_id": "CU-01\n"}, "SCHEMA_ERROR"),
    ({"customer_id": "ＣＵ-０１"}, "SCHEMA_ERROR"),
    ({"customer_id": ["CU-01"]}, "SCHEMA_ERROR"),
    ({"customer_id": None}, "SCHEMA_ERROR"),
    ({"subject": ""}, "SCHEMA_ERROR"),
    ({"subject": "a" * 31}, "SCHEMA_ERROR"),
    ({"subject": 1}, "SCHEMA_ERROR"),
    ({"subject": {"value": "x"}}, "SCHEMA_ERROR"),
    ({"priority": "紧急"}, "SCHEMA_ERROR"),
    ({"priority": True}, "SCHEMA_ERROR"),
    ({"priority": ["高"]}, "SCHEMA_ERROR"),
    ({"tags": "回访"}, "SCHEMA_ERROR"),
    ({"tags": [True]}, "SCHEMA_ERROR"),
    ({"tags": ["回访", "回访"]}, "SCHEMA_ERROR"),
    ({"tags": [[1]]}, "SCHEMA_ERROR"),
    ({"approved": True}, "SCHEMA_ERROR"),
    ({"actor": "manager"}, "SCHEMA_ERROR"),
    ({"operation_id": "task-2"}, "SCHEMA_ERROR"),
], ids=["wrong-resource", "surrounding-space", "trailing-newline", "lookalike-id",
        "resource-list", "null-resource", "empty-subject", "long-subject", "numeric-subject",
        "nested-subject", "outside-enum", "boolean-enum", "array-enum", "string-tags", "boolean-tags",
        "duplicate-tags", "nested-tags", "model-confirmation", "model-actor", "model-operation"])
def test_rejected_proposal_has_no_business_effect(setup_gateway, patch, code):
    db, gateway = setup_gateway()
    arguments = {**json.loads(TICKET.arguments_raw), **patch}
    proposal = replace(TICKET, arguments_raw=json.dumps(arguments))
    with pytest.raises(GatewayError) as failure:
        gateway.execute(proposal, APPROVED)
    assert failure.value.code == code
    assert db.snapshot()["tickets"] == {}


@pytest.mark.parametrize(("changes", "allowed"), [
    ({}, True), ({"session_id": "another-session"}, False),
    ({"operation_id": "another-operation"}, False),
])
def test_confirmation_binds_operation_to_session(setup_gateway, changes, allowed):
    db, gateway = setup_gateway()
    confirmation = gateway.confirm(TICKET, APPROVED)
    context = replace(APPROVED, **changes)
    if allowed:
        assert gateway.execute(TICKET, context, confirmation=confirmation)["status"] == "created"
        assert db.snapshot()["approval_records"][confirmation]["status"] == "CONSUMED"
        assert db.snapshot()["tickets"]["TK-01"] == {
            "customer_id": "CU-01", "subject": "送货追踪", "priority": "高", "tags": ["回访"],
            "order_id": None, "actor": "employee-1", "source_evidence": "synthetic-note-1", "status": "created",
        }
    else:
        with pytest.raises(GatewayError) as failure:
            gateway.execute(TICKET, context, confirmation=confirmation)
        assert failure.value.code == "POLICY_DENIED"
        assert db.snapshot()["tickets"] == {}


def test_confirmation_rejects_changed_argument(setup_gateway):
    db, gateway = setup_gateway()
    confirmation = gateway.confirm(TICKET, APPROVED)
    amended = replace(TICKET, arguments_raw=TICKET.arguments_raw.replace('"高"', '"低"'))
    with pytest.raises(GatewayError, match="confirmation"):
        gateway.execute(amended, APPROVED, confirmation=confirmation)
    assert db.snapshot()["tickets"] == {}


def test_retry_with_new_id_preserves_receipt_and_duplicate_call_id_denied(setup_gateway):
    db, gateway = setup_gateway()
    confirmation = gateway.confirm(TICKET, APPROVED)
    receipt = gateway.execute(TICKET, APPROVED, confirmation=confirmation)
    with pytest.raises(GatewayError, match="call ID"):
        gateway.execute(TICKET, APPROVED, confirmation=confirmation)
    assert gateway.execute(replace(TICKET, call_id="call-2"), APPROVED, confirmation=confirmation) == receipt
    snapshot = db.snapshot()
    assert len(snapshot["tickets"]) == 1
    assert sorted(row["status"] for row in snapshot["audit_events"].values()) == ["COMMITTED", "DENIED", "REPLAYED"]


def test_unconfirmed_write_cannot_save_ticket(setup_gateway):
    db, gateway = setup_gateway()
    with pytest.raises(GatewayError, match="confirmation"):
        gateway.execute(TICKET, APPROVED)
    assert db.snapshot()["tickets"] == {}


def test_read_capability_cannot_write_even_if_its_handler_attempts_to(setup_gateway):
    db, gateway = setup_gateway(write=False)
    with pytest.raises(GatewayError) as failure:
        gateway.execute(TICKET, APPROVED)
    assert failure.value.code == "TOOL_EXECUTION_ERROR"
    assert db.snapshot()["tickets"] == {}


def test_attempted_write_rolls_back_and_keeps_audit(setup_gateway):
    def incomplete(tx, arguments, context):
        persist_ticket(tx, arguments, context)
        raise ValueError("intentional deterministic simulator fault")

    db, gateway = setup_gateway(incomplete)
    confirmation = gateway.confirm(TICKET, APPROVED)
    with pytest.raises(GatewayError) as failure:
        gateway.execute(TICKET, APPROVED, confirmation=confirmation)
    assert failure.value.code == "TOOL_EXECUTION_ERROR"
    snapshot = db.snapshot()
    assert snapshot["tickets"] == {}
    assert snapshot["approval_records"][confirmation]["status"] == "CONFIRMED"
    (audit,) = snapshot["audit_events"].values()
    assert audit["status"] == "ROLLED_BACK"
    assert audit["before_state"]["tickets"]["TK-01"] is None
    assert audit["proposed_state"]["tickets"]["TK-01"]["subject"] == "送货追踪"
    assert audit["after_state"]["tickets"]["TK-01"] is None


def test_retry_has_bounded_attempts_without_partial_commit(setup_gateway):
    attempts = []

    def transient(tx, arguments, context):
        attempts.append(True)
        persist_ticket(tx, arguments, context)
        raise TransientToolError("simulated busy business dependency")

    db, gateway = setup_gateway(transient, max_attempts=2)
    confirmation = gateway.confirm(TICKET, APPROVED)
    with pytest.raises(GatewayError) as failure:
        gateway.execute(TICKET, APPROVED, confirmation=confirmation)
    assert failure.value.code == "RECOVERY_EXHAUSTED"
    snapshot = db.snapshot()
    assert snapshot["tickets"] == {}
    assert len(attempts) == 2
    assert next(iter(snapshot["audit_events"].values()))["attempts"] == 2


def test_cancelled_call_never_reaches_handler(setup_gateway):
    db, gateway = setup_gateway()
    stop = Event()
    stop.set()
    with pytest.raises(GatewayError) as failure:
        gateway.execute(TICKET, APPROVED, cancel=stop)
    assert failure.value.code == "CANCELLED"
    assert db.snapshot()["tickets"] == {}


def test_serialized_transactions_commit_once_with_concurrent_replay(setup_gateway):
    db, gateway = setup_gateway()
    confirmation = gateway.confirm(TICKET, APPROVED)

    def run(proposal):
        return gateway.execute(proposal, APPROVED, confirmation=confirmation)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(run, (TICKET, replace(TICKET, call_id="call-2"))))
    assert result == [{"ticket_id": "TK-01", "status": "created"}] * 2
    snapshot = db.snapshot()
    assert sorted(row["status"] for row in snapshot["audit_events"].values()) == ["COMMITTED", "REPLAYED"]
    assert len(snapshot["tickets"]) == 1


def test_cancel_after_a_write_rolls_back(setup_gateway):
    stop = Event()

    def cancelled(tx, arguments, context):
        result = persist_ticket(tx, arguments, context)
        stop.set()
        return result

    db, gateway = setup_gateway(cancelled)
    confirmation = gateway.confirm(TICKET, APPROVED)
    with pytest.raises(GatewayError) as failure:
        gateway.execute(TICKET, APPROVED, cancel=stop, confirmation=confirmation)
    assert failure.value.code == "CANCELLED"
    assert db.snapshot()["tickets"] == {}
    assert db.snapshot()["approval_records"][confirmation]["status"] == "CONFIRMED"


def test_expired_handler_cannot_commit_its_write(setup_gateway, monkeypatch):
    now = 0.0
    monkeypatch.setattr(execution_policy, "time", SimpleNamespace(monotonic=lambda: now))

    def expired(tx, arguments, context):
        nonlocal now
        result = persist_ticket(tx, arguments, context)
        now = 2.0
        return result

    db, gateway = setup_gateway(expired, timeout=1.0)
    confirmation = gateway.confirm(TICKET, APPROVED)
    with pytest.raises(GatewayError) as failure:
        gateway.execute(TICKET, APPROVED, confirmation=confirmation)
    assert failure.value.code == "TIMEOUT"
    snapshot = db.snapshot()
    assert snapshot["tickets"] == {}
    audit = next(iter(snapshot["audit_events"].values()))
    assert audit["status"] == "ROLLED_BACK"
    assert audit["proposed_state"]["tickets"]["TK-01"]["status"] == "created"
    assert audit["after_state"]["tickets"]["TK-01"] is None


def test_open_circuit_blocks_handler_and_reports_escalation(setup_gateway):
    def broken(tx, arguments, context):
        persist_ticket(tx, arguments, context)
        raise RuntimeError("synthetic tool fault")

    db, gateway = setup_gateway(broken, circuit_failures=1)
    confirmation = gateway.confirm(TICKET, APPROVED)
    with pytest.raises(GatewayError) as failure:
        gateway.execute(TICKET, APPROVED, confirmation=confirmation)
    assert failure.value.code == "TOOL_EXECUTION_ERROR"
    with pytest.raises(GatewayError) as failure:
        gateway.execute(replace(TICKET, call_id="call-2"), APPROVED, confirmation=confirmation)
    assert failure.value.code == "RECOVERY_EXHAUSTED"
    snapshot = db.snapshot()
    assert snapshot["tickets"] == {}
    audits = {row["call_id"]: row for row in snapshot["audit_events"].values()}
    assert audits["call-2"]["attempts"] == 0


def test_metrics_keep_retry_cost_when_second_attempt_succeeds(setup_gateway):
    attempts = []

    def recover_once(tx, arguments, context):
        result = persist_ticket(tx, arguments, context)
        attempts.append(True)
        if len(attempts) == 1:
            raise TransientToolError("intentional simulator failure")
        return result

    db, gateway = setup_gateway(recover_once)
    confirmation = gateway.confirm(TICKET, APPROVED)
    gateway.execute(TICKET, APPROVED, confirmation=confirmation)
    gateway.execute(replace(TICKET, call_id="call-2"), APPROVED, confirmation=confirmation)
    metrics = ExecutionMetrics.from_audit(db.snapshot()["audit_events"].values())
    assert metrics.proposals == 2
    assert metrics.tool_attempts == 2
    assert metrics.retries == 1
    assert metrics.first_pass_failures == 1
    assert metrics.business_commits == 1
    assert metrics.replays == 1
    assert metrics.cumulative_latency_ms >= 0
