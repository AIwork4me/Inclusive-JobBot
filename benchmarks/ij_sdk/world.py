"""IJ-SDK-1.1 P4A (D03 / D06): the live business store the tool gateway acts on.

This is the ENVIRONMENT the system under test operates in. It is not an
evaluator: ``evaluation/ij_sdk/reference_world.py`` is a separately implemented
reference machine and must never import this module.

State is plain JSON: ``{table: {entity_id: record}}``. A handler never writes
the store directly. It writes a private ``Transaction`` draft, which becomes
visible only on ``commit()``. A transaction that was aborted, or whose handler
finished after its deadline, can never commit - so a failed or late handler
cannot leave a partial effect behind.

Approval tokens are issued by the harness (the trusted approver) inside the
frozen world specification and are bound to one order, one operation and a
maximum amount. Each token can be used once.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from typing import Any

from benchmarks.ij_sdk.schema import canonical_json

_current = threading.local()


def current_transaction() -> "Transaction | None":
    """The draft a handler should write to. None when no gateway call is in flight."""
    return getattr(_current, "tx", None)


def _set_current(tx: "Transaction | None") -> None:
    _current.tx = tx


def state_digest(state: Any) -> str:
    return hashlib.sha256(canonical_json(state).encode("utf-8")).hexdigest()


def diff_states(before: dict, after: dict) -> list[dict[str, Any]]:
    """Field-level differences between two table states (what actually changed)."""
    changes: list[dict[str, Any]] = []
    for table in sorted(set(before) | set(after)):
        b_table, a_table = before.get(table, {}), after.get(table, {})
        for key in sorted(set(b_table) | set(a_table)):
            b_rec, a_rec = b_table.get(key), a_table.get(key)
            if b_rec is None and a_rec is not None:
                changes.append({"table": table, "key": key, "field": None, "before": None, "after": a_rec})
                continue
            if a_rec is None and b_rec is not None:
                changes.append({"table": table, "key": key, "field": None, "before": b_rec, "after": None})
                continue
            for field in sorted(set(b_rec) | set(a_rec)):
                if b_rec.get(field) != a_rec.get(field):
                    changes.append({"table": table, "key": key, "field": field,
                                    "before": b_rec.get(field), "after": a_rec.get(field)})
    return changes


class Transaction:
    """A private draft of the store plus the list of effects the handler intends."""

    def __init__(self, world: "BusinessWorld", epoch: int):
        self.draft: dict[str, Any] = copy.deepcopy(world._state)
        self._world = world
        self._epoch = epoch
        self.live = True
        self.effects: list[dict[str, Any]] = []
        self.meta: dict[str, Any] = {}     # gateway-to-handler notes, e.g. which approval token was verified

    @property
    def world(self) -> "BusinessWorld":
        return self._world

    def table(self, name: str) -> dict:
        return self.draft.setdefault(name, {})

    def get(self, table: str, key: str) -> dict | None:
        return self.table(table).get(key)

    def set(self, table: str, key: str, field: str, value: Any) -> None:
        record = self.table(table)[key]
        self.effects.append({"table": table, "key": key, "field": field, "before": record.get(field), "after": value})
        record[field] = value

    def remove(self, table: str, key: str) -> None:
        self.effects.append({"table": table, "key": key, "field": None, "before": self.table(table).get(key), "after": None})
        self.table(table).pop(key, None)

    def commit(self) -> bool:
        """Publish the draft. False when the transaction is no longer live or the store
        was reset underneath it; the draft is discarded in that case."""
        with self._world._lock:
            if not self.live or self._epoch != self._world._epoch:
                self.live = False
                return False
            self._world._state = self.draft
            self._world._epoch += 1
            self.live = False
            return True

    def abort(self) -> None:
        self.live = False


class BusinessWorld:
    """Live store for one trial. ``reset`` gives the next trial a fresh world.

    Approval grants live in the same transactional state under the reserved
    table ``_approvals`` (names starting with "_" are never business state), so
    consuming a token commits or rolls back together with the write it authorizes.
    """

    APPROVALS = "_approvals"

    def __init__(self, spec: dict[str, Any] | None = None):
        self._lock = threading.RLock()
        self._epoch = 0
        self.spec: dict[str, Any] = {}
        self.reset(spec)

    def reset(self, spec: dict[str, Any] | None = None) -> None:
        """Start a new trial. With ``spec`` the world is re-frozen to that specification; without
        it the same frozen specification is reloaded, so the next trial is fresh but identical."""
        with self._lock:
            self._epoch += 1                      # any transaction still open can no longer commit
            if spec is not None:
                self.spec = copy.deepcopy(spec)
            if not self.spec:
                self.spec = {"state": {}, "policies": {}, "approvals": {}, "roles": {}}
            self._state = copy.deepcopy(self.spec.get("state") or {})
            self._state[self.APPROVALS] = copy.deepcopy(self.spec.get("approvals") or {})
            self._policies = copy.deepcopy(self.spec.get("policies") or {})

    @property
    def epoch(self) -> int:
        return self._epoch

    @staticmethod
    def business_tables(state: dict[str, Any]) -> dict[str, Any]:
        return {table: rows for table, rows in state.items() if not table.startswith("_")}

    def snapshot(self) -> dict[str, Any]:
        """Business tables only (approval grants are not business state)."""
        with self._lock:
            return copy.deepcopy(self.business_tables(self._state))

    def digest(self) -> str:
        with self._lock:
            return state_digest(self.business_tables(self._state))

    def policies(self) -> dict[str, Any]:
        return copy.deepcopy(self._policies)

    def begin(self) -> Transaction:
        with self._lock:
            return Transaction(self, self._epoch)

    def verify_approval(self, tx: Transaction, token: Any, *, order_id: str, amount: float,
                        currency: str = "CNY", operation: str = "approve_order") -> bool:
        """Trusted approval verification against the draft: the token must exist, be unused,
        and be bound to exactly this order, operation and a maximum amount covering ``amount``."""
        if not isinstance(token, str):
            return False
        grant = tx.draft.get(self.APPROVALS, {}).get(token)
        if not grant:
            return False
        try:
            covers = float(grant.get("max_amount", 0)) >= float(amount)
        except (TypeError, ValueError):
            covers = False
        return (grant.get("order_id") == order_id and grant.get("operation") == operation
                and not grant.get("used", False) and covers and grant.get("currency", currency) == currency)

    def consume_approval(self, tx: Transaction, token: str) -> None:
        """Mark a token used inside ``tx``: it commits or rolls back with the authorized write."""
        tx.set(self.APPROVALS, token, "used", True)

    def approvals(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state.get(self.APPROVALS, {}))

    def describe(self) -> dict[str, Any]:
        with self._lock:
            business = self.business_tables(self._state)
            return {"epoch": self._epoch, "digest": state_digest(business),
                    "entities": {table: len(rows) for table, rows in business.items()},
                    "policies": sorted(self._policies), "approvals": len(self._state.get(self.APPROVALS, {}))}


def load_json_state(text: str) -> dict[str, Any]:
    """Parse a world specification; reject anything that is not a JSON object of tables."""
    state = json.loads(text)
    if not isinstance(state, dict):
        raise ValueError("world state must be a JSON object")
    return state
