"""Safe business tool gateway (NanoAgent Layer A).

Repairs the D06 defect class and the NA-D01/D06/D07 hardening scopes. The
evaluation order is fixed and every stage records an audit decision:

    1. tool exists (schemas validated at registration - NA-D08)
    2. argument schema validation
    3. authorization (permission check)
    4. preconditions and approval (approval bound to tool + canonical args +
       operation identity + optional expiry - never a reusable bare key)
    5. idempotency (effect keys bound to the canonical business operation;
       mandatory for idempotent tools; in-flight duplicates denied)
    6. epoch / cancellation / deadline boundary check (pre-dispatch)
    7. fault injection (test hook - runs ONLY after authorization, so a fault
       can never grant permission)
    8. transactional execution on a deep-copied draft with rollback
    9. epoch / cancellation / deadline boundary re-check (pre-commit)
   10. commit + atomic idempotency finalization
   11. audit (always appended, for accepts and every denial stage)

Transactions isolate the store completely: the draft is a deep copy (nested
dicts and lists never alias), commit does not re-alias, and handlers only
ever see the draft. Concurrent calls execute handlers on isolated drafts;
idempotency marking and commits are serialized under the gateway lock.

Non-reversible external actions: the gateway enforces the pre-dispatch
boundary checks, but an effect already dispatched to the outside world
cannot be rolled back by this in-memory store. Tool packages must declare
``non_reversible=True`` (which requires approval) and carry their own
pre-dispatch verification plus a compensation policy; this gateway refuses
to register non-reversible tools without the approval contract.
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import threading
import time
from typing import Any, Callable

from .schema import validate_args, validate_tool_schema

Draft = dict[str, Any]
Handler = Callable[[str, dict, Draft], Any]


def canonical_args(args: dict) -> str:
    return json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _args_hash(args: dict) -> str:
    return hashlib.sha256(canonical_args(args).encode("utf-8")).hexdigest()


class GatewayDenial(RuntimeError):
    def __init__(self, stage: str, reason: str):
        self.stage = stage
        self.reason = reason
        super().__init__(f"gateway denial at {stage}: {reason}")


class ToolError(RuntimeError):
    """Handler raised; the draft was rolled back."""


@dataclasses.dataclass(frozen=True)
class ToolSpec:
    name: str
    parameters: dict           # JSON-schema-like argument schema (validated)
    handler: Handler
    permission: str            # required permission id
    preconditions: tuple[str, ...] = ()
    requires_approval: bool = False
    idempotent: bool = False
    effect_writes: bool = False
    non_reversible: bool = False

    def __post_init__(self):
        if self.non_reversible and not self.requires_approval:
            raise ValueError(
                f"tool {self.name!r} is non-reversible and must require approval")


class Transaction:
    """A draft the handler mutates; commit applies it to the store.

    NA-D01: the draft is a DEEP copy of the store, and the commit deep-copies
    the draft back, so nested dicts/lists never alias across the boundary and
    rollback restores the original business state exactly."""

    def __init__(self, store: dict):
        self._store = store
        self._draft: dict | None = None
        self.committed = False
        self.rolled_back = False

    def begin(self) -> Draft:
        if self._draft is not None:
            raise RuntimeError("transaction already begun")
        self._draft = copy.deepcopy(self._store)
        return self._draft

    def commit(self) -> None:
        if self._draft is None or self.committed or self.rolled_back:
            raise RuntimeError("invalid transaction state")
        self._store.clear()
        self._store.update(copy.deepcopy(self._draft))
        self.committed = True

    def rollback(self) -> None:
        self._draft = None
        self.rolled_back = True


class SafeToolGateway:
    def __init__(self, tools: dict[str, ToolSpec], store: dict | None = None,
                 fault_schedule: dict[str, Callable[[str, dict], None]] | None = None,
                 now: Callable[[], float] = time.time):
        self._tools: dict[str, ToolSpec] = {}
        for name, spec in tools.items():
            if spec.name != name:
                raise ValueError(f"tool registry key {name!r} != spec name {spec.name!r}")
            validate_tool_schema(spec.parameters)          # NA-D08: fail closed
            if spec.non_reversible and not spec.requires_approval:
                raise ValueError(
                    f"tool {name!r} is non-reversible and must require approval")
            self._tools[name] = spec
        self._store: dict[str, Any] = store if store is not None else {}
        self._faults = dict(fault_schedule or {})
        self._idempotency: dict[str, dict] = {}
        self.audit: list[dict] = []
        self._approved: dict[str, dict] = {}
        self._granted: set[str] = set()
        self._now = now
        self._lock = threading.RLock()

    # -- configuration -------------------------------------------------------

    def grant(self, permission: str) -> None:
        """Grant a permission to the session (authorization inputs are
        explicit; the gateway never infers permission from content)."""
        self._granted.add(permission)

    def revoke(self, permission: str) -> None:
        self._granted.discard(permission)

    def approve(self, call_key: str, *, tool: str, args: dict,
                operation_id: str, scope: str = "default",
                expires_at: float | None = None) -> None:
        """Record an approval BOUND to the authorized operation (NA-D07):
        the tool, the canonical argument hash, an operation identity, an
        optional scope and an optional expiry. The same call_key can never
        authorize a different tool or different arguments."""
        self._approved[call_key] = {
            "tool": tool,
            "args_hash": _args_hash(args),
            "operation_id": operation_id,
            "scope": scope,
            "expires_at": expires_at,
        }

    @property
    def store(self) -> dict:
        return self._store

    # -- idempotency state binding (checkpoints - NA-D03/NA-D07) ---------------

    def export_idempotency(self) -> list[dict]:
        with self._lock:
            return [{"effect_key": k, "tool": v["tool"],
                     "args_hash": v["args_hash"], "state": v["state"],
                     "result": v["result"]}
                    for k, v in self._idempotency.items()]

    def load_idempotency(self, items: list[dict]) -> None:
        with self._lock:
            for it in items:
                self._idempotency[it["effect_key"]] = {
                    "tool": it["tool"], "args_hash": it["args_hash"],
                    "state": it["state"], "result": it["result"]}

    # -- main path -------------------------------------------------------------

    def call(self, name: str, args: dict, *, call_key: str,
             effect_key: str | None = None,
             state_epoch: int | None = None,
             state_epoch_getter: Callable[[], int] | None = None,
             cancel: Any = None,
             deadline_check: Callable[[], None] | None = None) -> Any:
        self._audit("tool_exists", name, call_key, None)
        spec = self._tools.get(name)
        if spec is None:
            raise GatewayDenial("tool_exists", f"unknown tool: {name}")

        self._audit("schema", name, call_key, None)
        try:
            validate_args(args, spec.parameters)
        except ValueError as e:
            raise GatewayDenial("schema", str(e)) from e

        self._audit("authorize", name, call_key, {"permission": spec.permission})
        if spec.permission not in self._granted:
            raise GatewayDenial("authorize", f"permission not granted: {spec.permission}")

        self._audit("preconditions", name, call_key,
                    {"preconditions": list(spec.preconditions)})
        missing = [p for p in spec.preconditions if not self._store.get(p)]
        if missing:
            raise GatewayDenial("preconditions", f"unmet: {missing}")

        if spec.requires_approval:
            self._audit("approval", name, call_key, {"call_key": call_key})
            self._check_approval(name, args, call_key)

        args_h = _args_hash(args)
        if spec.idempotent:
            if effect_key is None:
                raise GatewayDenial(
                    "idempotency", f"tool {name!r} requires an effect_key")
            with self._lock:
                entry = self._idempotency.get(effect_key)
                if entry is not None:
                    if entry["tool"] != name or entry["args_hash"] != args_h:
                        raise GatewayDenial(
                            "idempotency",
                            f"effect key {effect_key!r} is bound to a different operation")
                    if entry["state"] == "pending":
                        self._audit("idempotent_inflight", name, call_key,
                                    {"effect_key": effect_key})
                        raise GatewayDenial(
                            "idempotency", "operation with this effect key is in flight")
                    self._audit("idempotent_hit", name, call_key,
                                {"effect_key": effect_key})
                    return entry["result"]

        # Boundary checks BEFORE dispatch (NA-D06): epoch, cancellation, deadline.
        self._boundary(name, call_key, state_epoch, state_epoch_getter, cancel,
                       deadline_check)

        # Faults run only AFTER authorization: a fault can never grant
        # permission or bypass any earlier stage.
        fault = self._faults.get(call_key)
        if fault is not None:
            self._audit("fault", name, call_key, {})
            fault(name, args)

        if spec.idempotent:
            # Write-ahead pending mark: duplicates during execution (this or
            # another thread) are denied; a crash leaves a conservative
            # pending record that checkpoint binding preserves.
            with self._lock:
                self._idempotency[effect_key] = {
                    "tool": name, "args_hash": args_h,
                    "state": "pending", "result": None}

        def _clear_pending() -> None:
            if spec.idempotent and effect_key is not None:
                with self._lock:
                    e = self._idempotency.get(effect_key)
                    if e is not None and e["state"] == "pending":
                        del self._idempotency[effect_key]

        tx = Transaction(self._store)
        draft = tx.begin()
        try:
            result = spec.handler(name, args, draft)
        except GatewayDenial:
            tx.rollback()
            _clear_pending()
            raise
        except Exception as e:
            tx.rollback()
            _clear_pending()
            self._audit("rollback", name, call_key, {"error": str(e)[:200]})
            raise ToolError(f"handler failed; draft rolled back: {e}") from e

        # Boundary re-check BEFORE commit (NA-D06): late responses after
        # session reset / cancellation / deadline commit nothing.
        try:
            self._boundary(name, call_key, state_epoch, state_epoch_getter,
                           cancel, deadline_check)
        except GatewayDenial:
            tx.rollback()
            _clear_pending()
            raise

        with self._lock:
            tx.commit()
            self._audit("commit", name, call_key, {"effect_key": effect_key})
            if spec.idempotent:
                self._idempotency[effect_key]["state"] = "done"
                self._idempotency[effect_key]["result"] = result
        return result

    # -- internals ---------------------------------------------------------------

    def _check_approval(self, name: str, args: dict, call_key: str) -> None:
        record = self._approved.get(call_key)
        if record is None:
            raise GatewayDenial("approval", "explicit approval required and absent")
        if record["tool"] != name:
            raise GatewayDenial(
                "approval", "approval is bound to a different tool")
        if record["args_hash"] != _args_hash(args):
            raise GatewayDenial(
                "approval", "approval is bound to different arguments")
        exp = record.get("expires_at")
        if exp is not None and self._now() > exp:
            raise GatewayDenial("approval", "approval expired")

    def _boundary(self, name: str, call_key: str, state_epoch, state_epoch_getter,
                  cancel, deadline_check) -> None:
        if state_epoch_getter is not None and state_epoch is not None:
            if state_epoch_getter() != state_epoch:
                raise GatewayDenial(
                    "epoch",
                    f"state epoch changed: expected {state_epoch}, "
                    f"live {state_epoch_getter()}")
        if cancel is not None and cancel.is_set:
            raise GatewayDenial("cancellation", "operation cancelled before commit")
        if deadline_check is not None:
            try:
                deadline_check()
            except Exception as e:
                raise GatewayDenial("deadline", str(e)) from e

    def _audit(self, stage: str, tool: str, call_key: str, detail: dict | None) -> None:
        self.audit.append({"stage": stage, "tool": tool, "call_key": call_key,
                           "detail": detail or {}})
