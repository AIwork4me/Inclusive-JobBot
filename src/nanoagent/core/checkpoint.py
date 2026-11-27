"""Cancellation tokens and checkpoints (NanoAgent Layer A).

A checkpoint captures budget snapshot + typed state snapshot + sealed-so-far
event log; restoring validates integrity (event chain verifies, epochs and
sequence continue, ids match). Cancellation is cooperative: long operations
check the token; cancelling also aborts the state epoch so late writes fail.
"""
from __future__ import annotations

import json
from typing import Any

from .budget import BudgetController
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


class Checkpoint:
    """Immutable checkpoint record with integrity binding."""

    def __init__(self, trial_id: str, epoch: int, budget: dict, state: dict,
                 events: list[dict], event_count: int):
        self.trial_id = trial_id
        self.epoch = epoch
        self.budget = budget
        self.state = state
        self.events = events
        self.event_count = event_count

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, sort_keys=True)

    @classmethod
    def capture(cls, session: Session, budget: BudgetController, log: EventLog) -> "Checkpoint":
        st = session.state
        return cls(log.trial_id, st.epoch, budget.snapshot(), st.snapshot(),
                   [e.to_json() for e in log.events()], len(log.events()))

    @classmethod
    def restore(cls, raw: str | dict) -> tuple["Checkpoint", EventLog]:
        d = json.loads(raw) if isinstance(raw, str) else dict(raw)
        log = EventLog.from_events(d["trial_id"], d["events"])
        return cls(d["trial_id"], d["epoch"], d["budget"], d["state"],
                   d["events"], d["event_count"]), log

    def validate(self) -> bool:
        """Structural validation: counts consistent, event chain verifies."""
        if self.event_count != len(self.events):
            return False
        log = EventLog.from_events(self.trial_id, self.events)
        return log.verify() and self.state.get("epoch") == self.epoch
