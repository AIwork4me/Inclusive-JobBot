"""EA10 — persistent circuit breaker (order section 3.5).

Durable, restart-safe containment for affected dispatch:

- ``open`` suspends NEW affected dispatch immediately (``may_dispatch``
  fails closed);
- in-flight requests are accounted (``register_dispatch`` /
  ``complete_dispatch``) — the contamination scope includes them;
- quarantine records and preserved-evidence hashes are durable;
- state survives process restart (checksummed atomic file);
- recovery is ONLY through independent requalification: a new
  authoritative evidence generation plus a passing canary — never a
  hand-cleared flag.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import threading
import time

BREAKER_SCHEMA = "1.0.0"


class CircuitBreakerOpen(RuntimeError):
    """Raised on any new affected dispatch while the breaker is open."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class CircuitBreaker:
    """Persistent breaker over a durable state file."""

    def __init__(self, state_file: pathlib.Path):
        self._lock = threading.RLock()
        self.state_file = pathlib.Path(state_file)
        self._state = {"schema": BREAKER_SCHEMA, "state": "CLOSED",
                       "opened_utc": "", "reason": "",
                       "affected_scope": [], "quarantined_trials": [],
                       "preserved_evidence": [], "in_flight": [],
                       "open_count": 0, "generation": 0}
        if self.state_file.exists():
            self._load()

    # -- persistence -----------------------------------------------------
    def _checksum(self, payload: dict) -> str:
        core = {k: v for k, v in payload.items()
                if k not in ("checksum",)}
        return hashlib.sha256(json.dumps(core, sort_keys=True,
                                         ensure_ascii=False).encode()
                              ).hexdigest()

    def _save(self) -> None:
        payload = dict(self._state)
        payload["checksum"] = self._checksum(payload)
        tmp = self.state_file.with_suffix(".tmp")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(self.state_file)

    def _load(self) -> None:
        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise CircuitBreakerOpen(
                f"breaker state unreadable: {e}") from e
        if raw.get("schema") != BREAKER_SCHEMA or \
                self._checksum(raw) != raw.get("checksum"):
            raise CircuitBreakerOpen(
                "breaker state checksum mismatch (tampered?); dispatch "
                "stays suspended")
        self._state = raw

    # -- dispatch gating ----------------------------------------------------
    def may_dispatch(self, trial_id: str = "") -> None:
        with self._lock:
            if self._state["state"] == "OPEN":
                raise CircuitBreakerOpen(
                    f"circuit breaker OPEN since "
                    f"{self._state['opened_utc']}: "
                    f"{self._state['reason']}")

    def register_dispatch(self, trial_id: str) -> None:
        """In-flight accounting: concurrent requests dispatched under a
        still-healthy breaker are part of the contamination scope when
        the breaker opens."""
        with self._lock:
            self.may_dispatch(trial_id)
            if trial_id not in self._state["in_flight"]:
                self._state["in_flight"].append(trial_id)

    def complete_dispatch(self, trial_id: str) -> None:
        with self._lock:
            self._state["in_flight"] = [
                t for t in self._state["in_flight"] if t != trial_id]

    # -- opening / containment ------------------------------------------------
    def open(self, *, reason: str, affected_scope=None,
             contamination_window=None) -> None:
        with self._lock:
            if self._state["state"] == "OPEN":
                return
            self._state.update({
                "state": "OPEN", "opened_utc": _now(), "reason": reason,
                "affected_scope": sorted(affected_scope or []),
                "quarantined_trials": sorted(
                    set(list(self._state["in_flight"])
                        + list(contamination_window or []))),
                "open_count": self._state["open_count"] + 1})
            self._save()

    def quarantine(self, trial_ids) -> None:
        with self._lock:
            self._state["quarantined_trials"] = sorted(
                set(self._state["quarantined_trials"])
                | set(trial_ids))
            self._save()

    def preserve_evidence(self, artifact_hashes) -> list:
        """Freeze the content-addressed artifact hashes of the
        contamination window (evidence preservation: replayable)."""
        with self._lock:
            self._state["preserved_evidence"] = sorted(
                set(self._state["preserved_evidence"])
                | set(artifact_hashes))
            self._save()
            return list(self._state["preserved_evidence"])

    # -- restart safety -----------------------------------------------------
    def reload(self) -> None:
        with self._lock:
            self._load()

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._state["state"] == "OPEN"

    @property
    def contamination_scope(self) -> dict:
        with self._lock:
            return {"affected_scope": list(self._state["affected_scope"]),
                    "quarantined_trials":
                        list(self._state["quarantined_trials"]),
                    "in_flight": list(self._state["in_flight"]),
                    "preserved_evidence":
                        list(self._state["preserved_evidence"])}

    # -- recovery -----------------------------------------------------------------
    def recover_via_requalification(self, *, new_evidence_generation: int,
                                    authoritative_generation: int,
                                    canary_passed: bool) -> None:
        """Close ONLY through independent requalification: the
        authoritative state must have moved to a NEW evidence
        generation (fresh qualification evidence, not a re-cleared
        flag) and a canary must pass after it. The recovery is recorded
        in the durable generation counter."""
        with self._lock:
            if not canary_passed:
                raise CircuitBreakerOpen(
                    "recovery refused: canary did not pass after "
                    "requalification")
            if new_evidence_generation <= \
                    self._state["generation"] or \
                    authoritative_generation != new_evidence_generation:
                raise CircuitBreakerOpen(
                    "recovery refused: no new authoritative evidence "
                    "generation (independent requalification required)")
            self._state.update({
                "state": "CLOSED", "reason": "",
                "affected_scope": [], "quarantined_trials": [],
                "in_flight": [], "generation": new_evidence_generation})
            self._save()
