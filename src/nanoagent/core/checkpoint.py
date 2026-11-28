"""Cancellation tokens and checkpoints (NanoAgent Layer A).

A checkpoint captures budget spec + budget snapshot + typed state snapshot +
sealed-so-far event chain + idempotency state + pending transactions, and
binds ALL of them under one integrity hash plus the evidence seal
(NA-D03). Restoring VALIDATES: an invalid checkpoint raises
``CheckpointInvalid`` during restore - callers cannot forget a separate
validation step. Publication is atomic (temp file + os.replace); an
interrupted write is never loadable as a checkpoint.

Budget recovery is real recovery: ``BudgetController.restore`` rebuilds live
counters and re-derives the deadline from the checkpointed wall-clock anchor,
so a restart never silently grants a new budget.

Cancellation is cooperative: long operations check the token; cancelling
also aborts the state epoch so late writes fail.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from typing import Any

from .budget import BudgetController, BudgetSpec
from .events import Event, EventLog
from .state import Session


class CancellationToken:
    def __init__(self) -> None:
        self._set = False

    def set(self) -> None:
        self._set = True

    @property
    def is_set(self) -> bool:
        return self._set

    def raise_if_set(self) -> None:
        if self._set:
            raise OperationCancelled("cancellation requested")


class OperationCancelled(RuntimeError):
    pass


class CheckpointInvalid(ValueError):
    """The checkpoint record failed integrity or consistency validation."""


def _canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _integrity_hash(record: dict) -> str:
    payload = {k: v for k, v in record.items() if k != "integrity"}
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


class Checkpoint:
    """Immutable checkpoint record with integrity binding (NA-D03)."""

    FIELDS = ("schema_version", "trial_id", "experiment_id", "epoch",
              "budget_spec", "budget", "state", "events", "event_count",
              "seal", "idempotency", "pending_transactions")

    def __init__(self, trial_id: str, epoch: int, budget: dict, state: dict,
                 events: list[dict], event_count: int, *, experiment_id: str = "",
                 budget_spec: dict | None = None, seal: dict | None = None,
                 idempotency: list | None = None,
                 pending_transactions: list | None = None):
        self.trial_id = trial_id
        self.experiment_id = experiment_id
        self.epoch = epoch
        self.budget = budget
        self.budget_spec = budget_spec if budget_spec is not None else {}
        self.state = state
        self.events = events
        self.event_count = event_count
        self.seal = seal if seal is not None else {}
        self.idempotency = idempotency if idempotency is not None else []
        self.pending_transactions = (pending_transactions if pending_transactions
                                     is not None else [])
        self.schema_version = 2

    # -- construction ---------------------------------------------------------

    @classmethod
    def capture(cls, session: Session, budget: BudgetController, log: EventLog, *,
                experiment_id: str = "", idempotency: list | None = None,
                pending_transactions: list | None = None) -> "Checkpoint":
        st = session.state
        events = [e.to_json() for e in log.events()]
        seal = {"final_hash": events[-1]["hash"] if events else "0" * 64,
                "count": len(events)}
        cp = cls(log.trial_id, st.epoch, budget.snapshot(), st.snapshot(),
                 events, len(events), experiment_id=experiment_id,
                 budget_spec=dataclass_asdict(budget.spec), seal=seal,
                 idempotency=list(idempotency or []),
                 pending_transactions=list(pending_transactions or []))
        cp.integrity = _integrity_hash(cp.record())
        return cp

    def record(self) -> dict:
        d = {f: getattr(self, f) for f in self.FIELDS}
        d["integrity"] = getattr(self, "integrity", "")
        return d

    def to_json(self) -> str:
        return _canonical(self.record())

    # -- restore (validating) ---------------------------------------------------

    @classmethod
    def restore(cls, raw: str | dict) -> tuple["Checkpoint", EventLog]:
        """Parse, validate and rebuild. Raises CheckpointInvalid on ANY
        integrity or consistency failure - callers cannot skip validation."""
        try:
            d = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except (json.JSONDecodeError, TypeError) as e:
            raise CheckpointInvalid(f"unreadable checkpoint: {e}") from e
        try:
            integrity = d.pop("integrity", "")
            if not integrity or _integrity_hash(d) != integrity:
                raise CheckpointInvalid("integrity hash mismatch")
            for f in cls.FIELDS:
                if f not in d:
                    raise CheckpointInvalid(f"missing field: {f}")
            try:
                log = EventLog.from_events(d["trial_id"], d["events"])
            except ValueError as e:
                raise CheckpointInvalid(f"event chain invalid: {e}") from e
            if d["event_count"] != len(d["events"]):
                raise CheckpointInvalid("event_count does not match events")
            if d["seal"].get("count") != len(d["events"]):
                raise CheckpointInvalid("seal count does not match events")
            final_hash = (d["events"][-1]["hash"] if d["events"] else "0" * 64)
            if d["seal"].get("final_hash") != final_hash:
                raise CheckpointInvalid("seal hash does not match event chain")
            if d["state"].get("epoch") != d["epoch"]:
                raise CheckpointInvalid("state epoch does not match checkpoint epoch")
            if d["state"].get("trial_id") != d["trial_id"]:
                raise CheckpointInvalid("state trial_id does not match checkpoint")
            try:
                BudgetSpec(**d["budget_spec"])
            except (TypeError, ValueError) as e:
                raise CheckpointInvalid(f"budget spec invalid: {e}") from e
            counters = d["budget"].get("counters")
            if not isinstance(counters, dict):
                raise CheckpointInvalid("budget snapshot has no counters")
        except CheckpointInvalid:
            raise
        except (KeyError, TypeError, AttributeError) as e:
            raise CheckpointInvalid(f"malformed checkpoint: {e}") from e
        cp = cls(d["trial_id"], d["epoch"], d["budget"], d["state"],
                 d["events"], d["event_count"], experiment_id=d["experiment_id"],
                 budget_spec=d["budget_spec"], seal=d["seal"],
                 idempotency=d["idempotency"],
                 pending_transactions=d["pending_transactions"])
        cp.integrity = integrity
        return cp, log

    def validate(self) -> bool:
        """Evidence-facing boolean view of the same validation restore does."""
        try:
            if _integrity_hash(self.record()) != getattr(self, "integrity", ""):
                return False
            Checkpoint.restore(self.to_json())
            return True
        except CheckpointInvalid:
            return False

    # -- atomic publication ------------------------------------------------------

    def save(self, path: str) -> None:
        """Publish atomically: write to a temp file in the same directory,
        fsync, then os.replace. An interrupted save leaves either the old
        checkpoint or no loadable file - never a half-written one."""
        data = self.to_json()
        directory = os.path.dirname(os.path.abspath(path)) or "."
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".checkpoint-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    @classmethod
    def load(cls, path: str) -> tuple["Checkpoint", EventLog]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls.restore(f.read())
        except OSError as e:
            raise CheckpointInvalid(f"cannot read checkpoint: {e}") from e


def dataclass_asdict(obj: Any) -> dict:
    import dataclasses
    return dataclasses.asdict(obj)


__all__ = ["CancellationToken", "OperationCancelled", "Checkpoint",
           "CheckpointInvalid", "Event", "EventLog"]
