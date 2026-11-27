"""Safe business tool gateway (NanoAgent Layer A).

Repairs the D06 defect class by construction. The evaluation order is fixed
and every stage records an audit decision:

    1. tool exists
    2. argument schema validation
    3. authorization (permission check)
    4. preconditions and approval
    5. idempotency (duplicate-effect prevention)
    6. fault injection (test hook - runs ONLY after authorization, so a fault
       can never grant permission)
    7. transactional execution on a draft state with rollback
    8. audit (always appended, for accepts and every denial stage)

Handlers run against a transaction draft; mutations commit only on success.
Denials are exceptions carrying the stage and reason.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Callable

from .schema import validate_args

Draft = dict[str, Any]
Handler = Callable[[str, dict, Draft], Any]


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
    parameters: dict           # JSON-schema-like argument schema
    handler: Handler
    permission: str            # required permission id
    preconditions: tuple[str, ...] = ()
    requires_approval: bool = False
    idempotent: bool = False
    effect_writes: bool = False


class Transaction:
    """A draft the handler mutates; commit applies it to the store."""

    def __init__(self, store: dict):
        self._store = store
        self._draft: dict | None = None
        self.committed = False
        self.rolled_back = False

    def begin(self) -> Draft:
        if self._draft is not None:
            raise RuntimeError("transaction already begun")
        self._draft = dict(self._store)          # shallow draft of the top level
        return self._draft

    def commit(self) -> None:
        if self._draft is None or self.committed or self.rolled_back:
            raise RuntimeError("invalid transaction state")
        self._store.clear()
        self._store.update(self._draft)
        self.committed = True

    def rollback(self) -> None:
        self._draft = None
        self.rolled_back = True


class SafeToolGateway:
    def __init__(self, tools: dict[str, ToolSpec], store: dict | None = None,
                 fault_schedule: dict[str, Callable[[str, dict], None]] | None = None):
        self._tools = dict(tools)
        self._store: dict[str, Any] = store if store is not None else {}
        self._faults = dict(fault_schedule or {})
        self._idempotency: dict[str, Any] = {}
        self.audit: list[dict] = []
        self._approved: set[str] = set()
        self._granted: set[str] = set()

    # -- configuration -------------------------------------------------------

    def grant(self, permission: str) -> None:
        """Grant a permission to the session (authorization inputs are
        explicit; the gateway never infers permission from content)."""
        self._granted.add(permission)

    def revoke(self, permission: str) -> None:
        self._granted.discard(permission)

    def approve(self, call_key: str) -> None:
        self._approved.add(call_key)

    @property
    def store(self) -> dict:
        return self._store

    # -- main path -------------------------------------------------------------

    def call(self, name: str, args: dict, *, call_key: str, effect_key: str | None = None,
             state_epoch_getter: Callable[[], int] | None = None) -> Any:
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

        self._audit("preconditions", name, call_key, {"preconditions": list(spec.preconditions)})
        missing = [p for p in spec.preconditions if not self._store.get(p)]
        if missing:
            raise GatewayDenial("preconditions", f"unmet: {missing}")
        if spec.requires_approval:
            self._audit("approval", name, call_key, {"call_key": call_key})
            if call_key not in self._approved:
                raise GatewayDenial("approval", "explicit approval required and absent")

        if spec.idempotent and effect_key is not None:
            self._audit("idempotency", name, call_key, {"effect_key": effect_key})
            if effect_key in self._idempotency:
                self._audit("idempotent_hit", name, call_key, {"effect_key": effect_key})
                return self._idempotency[effect_key]

        # Faults run only AFTER authorization: a fault can never grant
        # permission or bypass any earlier stage.
        fault = self._faults.get(call_key)
        if fault is not None:
            self._audit("fault", name, call_key, {})
            fault(name, args)

        tx = Transaction(self._store)
        draft = tx.begin()
        try:
            result = spec.handler(name, args, draft)
        except GatewayDenial:
            tx.rollback()
            raise
        except Exception as e:
            tx.rollback()
            self._audit("rollback", name, call_key, {"error": str(e)[:200]})
            raise ToolError(f"handler failed; draft rolled back: {e}") from e
        tx.commit()
        self._audit("commit", name, call_key, {"effect_key": effect_key})
        if spec.idempotent and effect_key is not None:
            self._idempotency[effect_key] = result
        return result

    # -- internals ---------------------------------------------------------------

    def _audit(self, stage: str, tool: str, call_key: str, detail: dict | None) -> None:
        self.audit.append({"stage": stage, "tool": tool, "call_key": call_key,
                           "detail": detail or {}})
