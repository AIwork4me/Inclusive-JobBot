"""Typed task state with complete reset and epoch protection (Layer A).

Repairs the D04 defect class and the NA-D05 hardening scope:
- one state instance per trial; `reset()` returns a completely fresh state
  (counters, facts, logs, epoch) - no hidden cross-trial residue;
- late writes from a previous epoch are rejected (epoch abort);
- generated text never overwrites trusted state: facts enter only through
  `apply_verified`, which now REQUIRES a verified source event - an event
  that exists in the bound event log, belongs to this trial and was produced
  by an authorized source stage. A nonempty source_event_id string proves
  nothing by itself;
- fact records are validated (entity identity, property, data type, unit,
  value, source, validity scope) and stored as detached copies so nested
  values cannot be mutated through the caller's reference;
- usage snapshots handed out are deep copies (see BudgetController.snapshot).
"""
from __future__ import annotations

import copy
import dataclasses
from typing import Any

EPOCH_NONE = -1

# Event stages authorized to act as the source of a verified fact. Requests
# and decoded model text are deliberately NOT authorized sources: arbitrary
# model-generated data must never enter trusted state as a verified fact.
AUTHORIZED_FACT_SOURCES = ("tool_call_finished",)

_DATA_TYPES = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
}


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

    def __init__(self, epoch: int = 0, trial_id: str = "",
                 event_log: Any = None):
        self.trial_id = trial_id
        self._log = event_log
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

    def apply_verified(self, fact: Fact, *, epoch: int, log: Any = None) -> None:
        """Add or replace a fact backed by a VERIFIED source event.

        The source event must exist in the bound (or given) event log, belong
        to this trial's log identity and carry an authorized source stage.
        The fact itself is validated (identity, property, data type, unit)
        and stored as a detached copy.
        """
        self._check_epoch(epoch)
        source_log = log if log is not None else self._log
        if not fact.source_event_id:
            raise UnverifiedSourceError("facts require source_event_id from the event log")
        if source_log is None:
            raise UnverifiedSourceError(
                "no event log bound to this state; a source id string proves nothing")
        ev = source_log.event_by_id(fact.source_event_id)
        if ev is None:
            raise UnverifiedSourceError(f"source event not found: {fact.source_event_id}")
        if ev.trial_id != self.trial_id:
            raise UnverifiedSourceError(
                f"source event belongs to trial {ev.trial_id!r}, not {self.trial_id!r}")
        if ev.stage not in AUTHORIZED_FACT_SOURCES:
            raise UnverifiedSourceError(
                f"source stage {ev.stage!r} is not an authorized fact source")
        if not isinstance(fact.entity_id, str) or not fact.entity_id:
            raise ValueError("fact entity_id must be a non-empty string")
        if not isinstance(fact.property, str) or not fact.property:
            raise ValueError("fact property must be a non-empty string")
        if fact.data_type not in _DATA_TYPES:
            raise ValueError(f"fact data_type must be one of {sorted(_DATA_TYPES)}")
        if not _DATA_TYPES[fact.data_type](fact.value):
            raise ValueError(
                f"fact value {fact.value!r} does not match data_type {fact.data_type!r}")
        if fact.unit is not None and (not isinstance(fact.unit, str) or not fact.unit):
            raise ValueError("fact unit must be None or a non-empty string")
        key = (fact.entity_id, fact.property)
        self.version += 1
        self.facts[key] = dataclasses.replace(
            fact, value=copy.deepcopy(fact.value), state_version=self.version)

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
            "trial_id": self.trial_id, "epoch": self.epoch,
            "version": self.version, "goal": self.goal,
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

    @classmethod
    def _from_snapshot(cls, snap: dict, event_log: Any = None) -> "_TypedTaskState":
        st = cls(epoch=int(snap.get("epoch", 0)),
                 trial_id=snap.get("trial_id", ""),
                 event_log=event_log)
        st.version = int(snap.get("version", 0))
        st.goal = snap.get("goal")
        st.facts = {(f["entity_id"], f["property"]): Fact(**f)
                    for f in snap.get("facts", [])}
        st.completed_actions = list(snap.get("completed_actions", []))
        st.pending_actions = list(snap.get("pending_actions", []))
        st.outstanding_prerequisites = list(snap.get("outstanding_prerequisites", []))
        st.active_permissions = set(snap.get("active_permissions", []))
        st.open_questions = list(snap.get("open_questions", []))
        st.recent_errors = list(snap.get("recent_errors", []))
        st.recovery_history = list(snap.get("recovery_history", []))
        return st


class Session:
    """Owns exactly one live trial state. `reset` gives the next trial a
    completely fresh state and aborts the previous epoch."""

    def __init__(self, trial_id: str = "", event_log: Any = None):
        self._state = _TypedTaskState(epoch=0, trial_id=trial_id, event_log=event_log)
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
        self._state = _TypedTaskState(epoch=self._state.epoch + 1,
                                      trial_id=self._state.trial_id,
                                      event_log=self._state._log)
        return self._state

    def epoch_was_aborted(self, epoch: int) -> bool:
        return epoch in self._aborted_epochs

    @classmethod
    def restore(cls, snapshot: dict, trial_id: str = "",
                event_log: Any = None) -> "Session":
        """Resume from a checkpoint state snapshot: the restored epoch stays
        live (writes at that epoch are accepted) and prior facts survive."""
        s = cls(trial_id=trial_id or snapshot.get("trial_id", ""),
                event_log=event_log)
        s._state = _TypedTaskState._from_snapshot(snapshot, event_log)
        return s
