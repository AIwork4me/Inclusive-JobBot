"""Prepare, confirm and transactionally execute authorized business operations."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass
from threading import Event, Lock

from business_tools import BusinessStore, UnitOfWork
from business_tools.store import InvalidBusinessData

from .authorization import ExecutionContext, Policy
from .base import Proposal
from .errors import ErrorCode, GatewayError, TransientToolError
from .openai_protocol import CALL_ID, parse_proposal
from .tool_validation import ToolSpec, compile_schema, validate_schema


@dataclass(frozen=True, slots=True)
class Prepared:
    resource: str
    arguments: dict


class Gateway:
    def __init__(self, store: BusinessStore, tools: dict[str, ToolSpec], policy: Policy, *,
                 max_attempts: int = 2, timeout: float = 5.0,
                 circuit_failures: int = 3, circuit_cooldown: float = 10.0):
        if not 1 <= max_attempts <= 5 or circuit_failures < 1:
            raise ValueError("invalid recovery attempt or circuit bounds")
        if not math.isfinite(timeout) or not math.isfinite(circuit_cooldown) or min(timeout, circuit_cooldown) <= 0:
            raise ValueError("invalid timeout or circuit cooldown")
        self._store = store
        self._tools = dict(tools)
        self._validators = {name: compile_schema(spec) for name, spec in tools.items()}
        self._policy = policy
        self._max_attempts = max_attempts
        self._timeout = timeout
        self._circuit_failures = circuit_failures
        self._circuit_cooldown = circuit_cooldown
        self._circuit_lock = Lock()
        self._circuits: dict[str, tuple[int, float]] = {}

    @staticmethod
    def _context_valid(context: ExecutionContext) -> bool:
        return all(isinstance(value, str) and 0 < len(value) <= 128
                   for value in (context.actor, context.role, context.session_id, context.workflow_state))

    def prepare(self, proposal: Proposal, context: ExecutionContext) -> Prepared:
        arguments = parse_proposal(proposal)
        spec = self._tools.get(proposal.name)
        if not self._context_valid(context) or spec is None:
            raise GatewayError(ErrorCode.POLICY_DENIED, "tool or session is unauthorized")
        validate_schema(self._validators[proposal.name], arguments)
        try:
            if spec.validate is not None:
                spec.validate(deepcopy(arguments))
            resource = spec.resource(deepcopy(arguments))
        except (KeyError, TypeError, ValueError) as failure:
            raise GatewayError(ErrorCode.BUSINESS_VALIDATION_ERROR, "invalid business arguments") from failure
        if not isinstance(resource, str) or not resource:
            raise GatewayError(ErrorCode.BUSINESS_VALIDATION_ERROR, "invalid resource identity")
        if not self._policy.allows(context, proposal.name, resource, write=spec.write):
            raise GatewayError(ErrorCode.POLICY_DENIED, "actor, resource or workflow state is unauthorized")
        if spec.write and (not isinstance(context.operation_id, str) or not 0 < len(context.operation_id) <= 128):
            raise GatewayError(ErrorCode.POLICY_DENIED, "write requires a trusted operation ID")
        return Prepared(resource, arguments)

    @staticmethod
    def _fingerprint(proposal: Proposal, context: ExecutionContext, resource: str) -> str:
        fields = (proposal.name, proposal.arguments_raw, resource, context.actor, context.role,
                  context.session_id, context.workflow_state, context.operation_id)
        return hashlib.sha256(json.dumps(fields).encode("utf-8")).hexdigest()

    def confirm(self, proposal: Proposal, context: ExecutionContext) -> str:
        """Called by the trusted human-review path after showing exact proposed values."""
        prepared = self.prepare(proposal, context)
        spec = self._tools[proposal.name]
        if not spec.write or spec.draft_only:
            raise GatewayError(ErrorCode.POLICY_DENIED, "tool requires no confirmation")
        key = str(uuid.uuid4())
        approval = {
            "actor": context.actor, "role": context.role, "session_id": context.session_id,
            "operation_id": context.operation_id, "workflow_state": context.workflow_state,
            "tool": proposal.name, "resource": prepared.resource, "status": "CONFIRMED",
            "validated_arguments": prepared.arguments,
            "fingerprint": self._fingerprint(proposal, context, prepared.resource),
        }
        with self._store._transaction() as db:
            self._store._put_system_row(db, "approval_records", key, approval)
        return key

    def _circuit_check(self, tool: str) -> None:
        with self._circuit_lock:
            failures, cooldown_end = self._circuits.get(tool, (0, 0.0))
            if failures >= self._circuit_failures:
                if time.monotonic() < cooldown_end:
                    raise GatewayError(ErrorCode.RECOVERY_EXHAUSTED, "tool circuit is open for human escalation")
                self._circuits.pop(tool)

    def _circuit_update(self, tool: str, failed: bool) -> None:
        with self._circuit_lock:
            if failed:
                failures, _ = self._circuits.get(tool, (0, 0.0))
                self._circuits[tool] = failures + 1, time.monotonic() + self._circuit_cooldown
            else:
                self._circuits.pop(tool, None)

    def execute(self, proposal: Proposal, context: ExecutionContext, *,
                confirmation: str | None = None, cancel: Event | None = None) -> dict:
        started = time.monotonic()
        deadline = started + self._timeout

        def checkpoint() -> None:
            if cancel is not None and cancel.is_set():
                raise GatewayError(ErrorCode.CANCELLED, "business operation cancelled")
            if time.monotonic() >= deadline:
                raise GatewayError(ErrorCode.TIMEOUT, "business operation exceeded its deadline")

        transaction_id = str(uuid.uuid4())
        audit = {
            "transaction_id": transaction_id, "call_id": proposal.call_id, "tool": proposal.name,
            "actor": context.actor, "role": context.role, "session_id": context.session_id,
            "workflow_state": context.workflow_state, "idempotency_key": context.operation_id,
            "authorization": "NOT_EVALUATED", "confirmation_state": "NOT_REQUIRED",
            "status": "DENIED", "validated_arguments": None, "resource": None,
            "before_state": {}, "proposed_state": {}, "after_state": {}, "attempts": 0,
            "result": None, "error_code": None,
        }
        failure = None
        try:
            with self._store._transaction(timeout=self._timeout) as db:
                try:
                    checkpoint()
                    if (self._context_valid(context) and isinstance(proposal.call_id, str)
                            and CALL_ID.fullmatch(proposal.call_id) and not self._store._reserve_call(
                                db, context.actor, context.session_id, proposal.call_id)):
                        raise GatewayError(ErrorCode.PROTOCOL_ERROR, "duplicate tool call ID")
                    self._execute(db, proposal, context, confirmation, checkpoint, audit)
                except GatewayError as error:
                    failure = error
                    audit["error_code"] = error.code
                    if error.code == ErrorCode.POLICY_DENIED and audit["authorization"] != "ALLOW":
                        audit["authorization"] = "DENY"
                audit["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
                self._store._put_system_row(db, "audit_events", transaction_id, audit)
        except sqlite3.OperationalError as error:
            if error.sqlite_errorcode in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                raise GatewayError(ErrorCode.TIMEOUT, "business database is busy") from None
            raise GatewayError(ErrorCode.TOOL_EXECUTION_ERROR, "business database transaction failed") from None
        if failure is not None:
            raise failure
        return audit["result"]

    def _execute(self, db, proposal, context, confirmation, checkpoint, audit) -> None:
        prepared = self.prepare(proposal, context)
        spec = self._tools[proposal.name]
        audit.update(authorization="ALLOW", resource=prepared.resource, validated_arguments=prepared.arguments)
        approval = None
        if spec.write:
            fingerprint = self._fingerprint(proposal, context, prepared.resource)
            if spec.draft_only:
                if confirmation is not None:
                    raise GatewayError(ErrorCode.POLICY_DENIED, "draft capability does not accept confirmations")
                confirmation = ""
            else:
                audit["confirmation_state"] = "REQUIRED"
                if isinstance(confirmation, str) and 0 < len(confirmation) <= 64:
                    approval = self._store._system_row(db, "approval_records", confirmation)
                if approval is None or approval["fingerprint"] != fingerprint:
                    audit["confirmation_state"] = "REJECTED" if confirmation is not None else "REQUIRED"
                    raise GatewayError(ErrorCode.POLICY_DENIED, "exact-operation confirmation is required")
                audit["confirmation_state"] = "CONFIRMED"

            prior = self._store._receipt(db, context.actor, context.operation_id)
            if prior is not None:
                prior_fingerprint, prior_confirmation, result = prior
                if prior_fingerprint != fingerprint or prior_confirmation != confirmation:
                    audit["confirmation_state"] = "REJECTED"
                    raise GatewayError(ErrorCode.POLICY_DENIED, "operation ID is bound to an earlier commit")
                audit.update(status="REPLAYED", result=result)
                return
            if approval is not None and approval["status"] != "CONFIRMED":
                audit["confirmation_state"] = "REJECTED"
                raise GatewayError(ErrorCode.POLICY_DENIED, "confirmation was already consumed")

        self._circuit_check(proposal.name)
        for number in range(1, self._max_attempts + 1):
            audit["attempts"] = number
            tx = UnitOfWork(db, writable=spec.write, checkpoint=checkpoint,
                            draft_resource=prepared.resource if spec.draft_only else None)
            db.execute("SAVEPOINT tool_attempt")
            try:
                checkpoint()
                result = tx.result(spec.handler(tx, deepcopy(prepared.arguments), context))
                if spec.write:
                    if result.get("error") or not tx.proposed_state:
                        raise GatewayError(ErrorCode.TOOL_EXECUTION_ERROR, "write did not produce a business state change")
                    if approval is not None:
                        self._store._put_system_row(db, "approval_records", confirmation,
                                                    {**approval, "status": "CONSUMED"})
                    self._store._save_receipt(db, context.actor, context.operation_id,
                                              fingerprint, confirmation, result)
                checkpoint()
            except Exception as error:
                db.execute("ROLLBACK TO tool_attempt")
                db.execute("RELEASE tool_attempt")
                audit.update(status="ROLLED_BACK", before_state=tx.before_state,
                             proposed_state=tx.proposed_state, after_state=tx.before_state)
                if isinstance(error, TransientToolError) and number < self._max_attempts:
                    continue
                if isinstance(error, TransientToolError):
                    error = GatewayError(ErrorCode.RECOVERY_EXHAUSTED, "bounded tool retries exhausted")
                elif isinstance(error, InvalidBusinessData):
                    error = GatewayError(ErrorCode.BUSINESS_VALIDATION_ERROR, str(error))
                elif not isinstance(error, GatewayError):
                    error = GatewayError(ErrorCode.TOOL_EXECUTION_ERROR, "local business handler failed")
                if error.code in (ErrorCode.TOOL_EXECUTION_ERROR, ErrorCode.TIMEOUT, ErrorCode.RECOVERY_EXHAUSTED):
                    self._circuit_update(proposal.name, True)
                raise error from None
            else:
                db.execute("RELEASE tool_attempt")
                self._circuit_update(proposal.name, False)
                status = "DRAFTED" if spec.draft_only else "COMMITTED" if spec.write else "READ"
                audit.update(status=status, before_state=tx.before_state,
                             proposed_state=tx.proposed_state, after_state=tx.proposed_state, result=result)
                return
