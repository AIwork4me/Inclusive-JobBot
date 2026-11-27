"""Evidence event log with correlation, ordering and integrity (Layer A).

Repairs the D07 (event-log half) defect class by construction:
- decoded response content and token ids are distinct stages, never merged;
- every event carries its own id and an optional parent id for correlation
  by call id;
- the per-trial sequence is resume-safe (continues from a checkpoint);
- the log is a hash chain and can be sealed; appending after sealing fails;
- verification detects any payload tampering or reordering.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import uuid

# Canonical stages. 'response_decoded' (text the model produced) and
# 'token_ids' (sampled id sequence) are deliberately distinct stages.
STAGES = (
    "task_started",
    "request_sent",            # outgoing request (prompt, tools, constraints)
    "token_ids",               # sampled token id sequence
    "response_decoded",        # decoded text / parsed structure
    "tool_call_started",
    "tool_call_finished",
    "state_applied",
    "recovery_started",
    "recovery_finished",
    "budget_event",
    "checkpoint_saved",
    "task_finished",
    "audit",                   # gateway authorization / denial records
)


def _utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _canonical(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclasses.dataclass(frozen=True)
class Event:
    trial_id: str
    seq: int
    stage: str
    kind: str
    payload: dict
    ts_utc: str
    event_id: str
    parent_id: str | None
    prev_hash: str
    hash: str

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


class EventLog:
    """Append-only hash-chained event log for one trial."""

    def __init__(self, trial_id: str, initial: list[Event] | None = None):
        self.trial_id = trial_id
        self._events: list[Event] = list(initial or [])
        self._sealed = False

    # -- construction --------------------------------------------------------

    def append(self, stage: str, kind: str, payload: dict | None = None,
               parent: Event | str | None = None) -> Event:
        if self._sealed:
            raise RuntimeError("event log is sealed; no further appends")
        if stage not in STAGES:
            raise ValueError(f"unknown stage: {stage}")
        parent_id = parent.event_id if isinstance(parent, Event) else parent
        payload = dict(payload or {})
        seq = len(self._events)
        prev_hash = self._events[-1].hash if self._events else "0" * 64
        ts = _utc()
        event_id = uuid.uuid4().hex
        h = hashlib.sha256(
            (prev_hash + "|" + self.trial_id + "|" + str(seq) + "|" + stage + "|"
             + kind + "|" + event_id + "|" + _canonical(payload)).encode("utf-8")
        ).hexdigest()
        ev = Event(self.trial_id, seq, stage, kind, payload, ts, event_id, parent_id,
                   prev_hash, h)
        self._events.append(ev)
        return ev

    def seal(self) -> dict:
        """Freeze the log and return its seal (integrity summary)."""
        self._sealed = True
        return {
            "trial_id": self.trial_id,
            "count": len(self._events),
            "final_hash": self._events[-1].hash if self._events else "0" * 64,
            "sealed_utc": _utc(),
        }

    # -- reads ---------------------------------------------------------------

    def events(self) -> list[Event]:
        return list(self._events)

    def by_call(self, call_id: str) -> list[Event]:
        """All events correlated to one logical call via parent id."""
        return [e for e in self._events if e.parent_id == call_id]

    def next_seq(self) -> int:
        """Resume-safe continuation point for a restored log."""
        return len(self._events)

    def verify(self) -> bool:
        prev = "0" * 64
        for i, e in enumerate(self._events):
            if e.seq != i or e.prev_hash != prev:
                return False
            h = hashlib.sha256(
                (e.prev_hash + "|" + e.trial_id + "|" + str(e.seq) + "|" + e.stage + "|"
                 + e.kind + "|" + e.event_id + "|" + _canonical(e.payload)).encode("utf-8")
            ).hexdigest()
            if h != e.hash:
                return False
            prev = e.hash
        return True

    # -- persistence -----------------------------------------------------------

    @classmethod
    def from_events(cls, trial_id: str, rows: list[dict]) -> "EventLog":
        events = [Event(**{**r, "payload": r.get("payload", {})}) for r in rows]
        log = cls(trial_id, events)
        if not log.verify():
            raise ValueError("cannot restore: event chain does not verify")
        return log
