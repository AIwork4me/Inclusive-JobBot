"""Typed task state with complete reset and epoch protection (Layer A).

Repairs the D04 defect class by construction:
- one state instance per trial; `reset()` returns a completely fresh state
  (counters, facts, logs, epoch) - no hidden cross-trial residue;
- late writes from a previous epoch are rejected (epoch abort);
- generated text never overwrites trusted state: only `apply_verified`
  (backed by an event id) can add facts;
- facts are typed records with provenance, validity scope and state version;
- usage snapshots handed out are deep copies (see BudgetController.snapshot).
"""
from __future__ import annotations

import dataclasses
from typing import Any

EPOCH_NONE = -1


@dataclasses.dataclass(frozen=True)
class Fact:
    entity_id: str
    property: str
    value: Any
    data_type: str
    unit: str | None = None
    source_event_id: str = ""
    validity_scope: str = "session"
    state_version: int = 0


class StaleEpochError(RuntimeError):
    pass


class UnverifiedSourceError(RuntimeError):
    pass


class _TypedTaskState:
    """Mutable typed state for one trial. Not shared across trials."""

    def __init__(self, epoch: int = 0):
        self.epoch = epoch
        self._aborted = False
        self.version = 0
        self.goal: str | None = None
        self.facts: dict[tuple[str, str], Fact] = {}
        self.completed_actions: list[str] = []
        self.pending_actions: list[str] = []
        self.outstanding_prerequisites: list[str] = []
        self.active_permissions: set[str] = set()
        self.open_questions: list[str] = []
        self.recent_errors: list[str] = []
        self.recovery_history: list[str] = []

    # -- writes (verified events only) ---------------------------------------

    def set_goal(self, goal: str, *, epoch: int) -> None:
        self._check_epoch(epoch)
        self.goal = goal
        self._bump()

    def apply_verified(self, fact: Fact, *, epoch: int) -> None:
        """Add or replace a fact. Only verified (event-backed) facts enter."""
        self._check_epoch(epoch)
        if not fact.source_event_id:
            raise UnverifiedSourceError("facts require source_event_id from the event log")
        key = (fact.entity_id, fact.property)
        self.version += 1
        self.facts[key] = dataclasses.replace(fact, state_version=self.version)

    def invalidate_scope(self, scope: str, *, epoch: int) -> int:
        """Drop all facts whose validity scope is no longer valid."""
        self._check_epoch(epoch)
        stale = [k for k, f in self.facts.items() if f.validity_scope == scope]
        for k in stale:
            del self.facts[k]
        if stale:
            self._bump()
        return len(stale)

    def record_action(self, action_id: str, *, epoch: int, completed: bool = True) -> None:
        self._check_epoch(epoch)
        if completed:
            self.completed_actions.append(action_id)
            self.pending_actions = [a for a in self.pending_actions if a != action_id]
        else:
            self.pending_actions.append(action_id)
        self._bump()

    def record_error(self, message: str, *, epoch: int) -> None:
        self._check_epoch(epoch)
        self.recent_errors.append(message)
        self._bump()

    # -- reads ----------------------------------------------------------------

    def fact(self, entity_id: str, property: str) -> Fact | None:
        return self.facts.get((entity_id, property))

    def snapshot(self) -> dict:
        """Detached, JSON-serializable view for checkpoints and evidence."""
        return {
            "epoch": self.epoch, "version": self.version, "goal": self.goal,
            "facts": [dataclasses.asdict(f) for f in self.facts.values()],
            "completed_actions": list(self.completed_actions),
            "pending_actions": list(self.pending_actions),
            "outstanding_prerequisites": list(self.outstanding_prerequisites),
            "active_permissions": sorted(self.active_permissions),
            "open_questions": list(self.open_questions),
            "recent_errors": list(self.recent_errors),
            "recovery_history": list(self.recovery_history),
        }

    # -- internals --------------------------------------------------------------

    def _abort(self) -> None:
        """Called by Session.reset(): this state object is no longer live and
        must reject every later write, even from a caller that still holds the
        matching epoch number."""
        self._aborted = True

    def _check_epoch(self, epoch: int) -> None:
        if self._aborted:
            raise StaleEpochError("write rejected: this state epoch was aborted by reset")
        if epoch != self.epoch:
            raise StaleEpochError(
                f"write rejected: state epoch is {self.epoch}, caller holds {epoch}")

    def _bump(self) -> None:
        self.version += 1


class Session:
    """Owns exactly one live trial state. `reset` gives the next trial a
    completely fresh state and aborts the previous epoch."""

    def __init__(self):
        self._state = _TypedTaskState(epoch=0)
        self._aborted_epochs: set[int] = set()

    @property
    def state(self) -> _TypedTaskState:
        return self._state

    @property
    def epoch(self) -> int:
        return self._state.epoch

    def reset(self) -> _TypedTaskState:
        """Complete per-trial reset (D04): the old epoch is aborted and every
        field starts empty in a new epoch."""
        self._aborted_epochs.add(self._state.epoch)
        self._state._abort()
        self._state = _TypedTaskState(epoch=self._state.epoch + 1)
        return self._state

    def epoch_was_aborted(self, epoch: int) -> bool:
        return epoch in self._aborted_epochs
