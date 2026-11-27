"""Authoritative budget controller (NanoAgent Layer A).

Repairs the D05 defect class and the NA-D04 hardening scope:
- attempts are counted at reservation time, not at completion;
- every failed call is charged (minimum one unit) even on exception;
- the task deadline is an absolute monotonic instant, never a sliding delta,
  and it is anchored to wall-clock time so it survives process restart
  without silently granting a new budget;
- each request sees the budget actually remaining for it, and request
- max_tokens is bound to the remaining completion budget;
- corrective retries are bounded separately from first attempts;
- reservations settle: reserved capacity, actual usage, released units and
  unknown-after-transport-failure are distinct states;
- zero-unit reservations (bypass) and negative specifications are rejected;
- reservation and settlement are atomic under concurrency.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import threading
import time
from typing import Callable

KINDS = ("model_calls", "tool_calls", "completion_tokens", "prompt_tokens", "corrective_retries")
# Kinds where unused reserved units are released at settlement (capacity
# kinds). Attempt kinds (calls) are never refunded: an attempt is an attempt.
_CAPACITY_KINDS = frozenset({"completion_tokens", "prompt_tokens"})


class BudgetExhausted(RuntimeError):
    def __init__(self, kind: str, detail: str = ""):
        self.kind = kind
        super().__init__(f"budget exhausted: {kind}" + (f" ({detail})" if detail else ""))


class DeadlineExceeded(BudgetExhausted):
    def __init__(self, detail: str = ""):
        super().__init__("wall_clock", detail)


def _is_count(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _is_secs(v) -> bool:
    return (v is None) or (isinstance(v, (int, float)) and not isinstance(v, bool)
                           and v >= 0)


@dataclasses.dataclass(frozen=True)
class BudgetSpec:
    model_calls: int = 32
    tool_calls: int = 32
    completion_tokens: int = 8192
    prompt_tokens: int | None = None
    corrective_retries: int = 4
    wall_clock_seconds: float | None = None
    tool_timeout_seconds: float | None = None

    def __post_init__(self):
        for f in ("model_calls", "tool_calls", "completion_tokens",
                  "prompt_tokens", "corrective_retries"):
            v = getattr(self, f)
            if v is not None and not _is_count(v):
                raise ValueError(f"BudgetSpec.{f} must be a non-negative integer")
        for f in ("wall_clock_seconds", "tool_timeout_seconds"):
            if not _is_secs(getattr(self, f)):
                raise ValueError(f"BudgetSpec.{f} must be None or a non-negative number")


@dataclasses.dataclass
class _Counters:
    model_calls: int = 0
    tool_calls: int = 0
    completion_tokens: int = 0
    prompt_tokens: int = 0
    corrective_retries: int = 0


class Reservation:
    """A counted-at-start hold on budget units with explicit settlement.

    States: ``reserved`` -> ``settled`` (actual usage known; unused capacity
    released; overrun charged) or ``settled_unknown`` (transport failed;
    the full hold stays charged — never silently undercount).
    """

    __slots__ = ("controller", "kind", "units", "kind_detail", "state")

    def __init__(self, controller: "BudgetController", kind: str, units: int,
                 kind_detail: str = ""):
        self.controller = controller
        self.kind = kind
        self.units = units
        self.kind_detail = kind_detail
        self.state = "reserved"

    def settle(self, actual: int) -> None:
        """Settle with the actual usage for this reservation."""
        if self.state != "reserved":
            return
        actual = int(actual)
        with self.controller._lock:
            if actual > self.units:
                self.controller._apply_locked(self.kind, actual - self.units)
            elif actual < self.units and self.kind in _CAPACITY_KINDS:
                self.controller._release_locked(self.kind, self.units - actual)
            self.units = actual
            self.state = "settled"

    def settle_unknown(self) -> None:
        """Transport failed, actual usage unknowable: keep the full hold."""
        if self.state != "reserved":
            return
        self.state = "settled_unknown"

    def charge(self, actual: int) -> None:
        """Backward-compatible alias of settle()."""
        self.settle(actual)

    def __enter__(self) -> "Reservation":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self.state == "reserved":
            self.settle_unknown()   # unreleased reservations stay charged
        return False


class BudgetController:
    """Single authoritative budget for one task execution."""

    def __init__(self, spec: BudgetSpec, clock: Callable[[], float] = time.monotonic,
                 wall_clock: Callable[[], float] = time.time):
        self.spec = spec
        self._clock = clock
        self._wall_clock = wall_clock
        self._counters = _Counters()
        self._lock = threading.RLock()
        self._started = clock()
        self._deadline = (self._started + spec.wall_clock_seconds
                          if spec.wall_clock_seconds is not None else None)
        # Wall-clock anchor: survives process restart (monotonic clocks do not).
        self._wall_deadline = (wall_clock() + spec.wall_clock_seconds
                               if spec.wall_clock_seconds is not None else None)

    # -- reservation API ---------------------------------------------------

    def reserve(self, kind: str, units: int = 1, *, corrective: bool = False,
                detail: str = "") -> Reservation:
        if kind not in KINDS:
            raise ValueError(f"unknown budget kind: {kind}")
        if not _is_count(units) or units < 1:
            raise ValueError("units must be a positive integer (>= 1)")
        with self._lock:
            self._check_deadline_locked()
            remaining = self.remaining(kind)
            if units > remaining:
                raise BudgetExhausted(kind, f"requested {units}, remaining {remaining}")
            if corrective and kind == "model_calls":
                if self._counters.corrective_retries + 1 > self.spec.corrective_retries:
                    raise BudgetExhausted("corrective_retries",
                                          f"cap {self.spec.corrective_retries}")
                self._counters.corrective_retries += 1
            self._apply_locked(kind, units)
            return Reservation(self, kind, units, detail)

    def reserve_tokens(self, completion: int = 0, prompt: int = 0) -> list[Reservation]:
        out = []
        if prompt and self.spec.prompt_tokens is not None:
            out.append(self.reserve("prompt_tokens", prompt))
        if completion:
            out.append(self.reserve("completion_tokens", completion))
        return out

    def max_completion_tokens(self, requested: int) -> int:
        """Bind a request's max_tokens to the completion budget actually left."""
        remaining = self.remaining("completion_tokens")
        return max(min(int(requested), remaining), 0)

    def tool_deadline(self) -> float | None:
        """Latest monotonic instant a tool call may run until: the tool
        timeout, capped by the task's absolute deadline (a tool may never
        outlive the task). None when neither bound exists."""
        d = None
        if self.spec.tool_timeout_seconds is not None:
            d = self._clock() + self.spec.tool_timeout_seconds
        if self._deadline is not None:
            d = self._deadline if d is None else min(d, self._deadline)
        return d

    def check_deadline(self) -> None:
        with self._lock:
            self._check_deadline_locked()

    # -- reads --------------------------------------------------------------

    def remaining(self, kind: str) -> int | None:
        if kind == "prompt_tokens" and self.spec.prompt_tokens is None:
            return None
        used = getattr(self._counters, kind)
        cap = getattr(self.spec, "prompt_tokens" if kind == "prompt_tokens" else kind)
        return max(int(cap) - used, 0)

    def remaining_for_request(self) -> dict:
        """What one more request may still consume (per-request view)."""
        with self._lock:
            self._check_deadline_locked()
            return {k: self.remaining(k) for k in KINDS if self.remaining(k) is not None}

    def seconds_remaining(self) -> float | None:
        if self._deadline is None:
            return None
        return max(self._deadline - self._clock(), 0.0)

    def snapshot(self) -> dict:
        """Detached copy (D04: usage is returned as a copy, never a live view).
        Includes the wall-clock deadline anchor for restart-safe restore."""
        with self._lock:
            wall_deadline = self._wall_deadline
            if wall_deadline is not None:
                wall_deadline_iso = dt.datetime.fromtimestamp(
                    wall_deadline, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            else:
                wall_deadline_iso = None
            return {
                "counters": dataclasses.asdict(self._counters),
                "seconds_remaining": self.seconds_remaining(),
                "corrective_retry_cap": self.spec.corrective_retries,
                "wall_deadline": wall_deadline,
                "wall_deadline_utc": wall_deadline_iso,
            }

    # -- restart -------------------------------------------------------------

    @classmethod
    def restore(cls, spec: BudgetSpec, snapshot: dict,
                clock: Callable[[], float] = time.monotonic,
                wall_clock: Callable[[], float] = time.time) -> "BudgetController":
        """Rebuild a live controller from a checkpoint snapshot.

        Counters are recovered exactly. A wall deadline is recovered from the
        snapshot anchor, not from a fresh window: a restart never silently
        grants a new budget; if the anchored deadline has passed, the first
        deadline check raises."""
        bc = cls(spec, clock=clock, wall_clock=wall_clock)
        counters = snapshot.get("counters", {})
        for k, v in counters.items():
            if k in KINDS and k != "corrective_retries":
                setattr(bc._counters, k, int(v))
        bc._counters.corrective_retries = int(counters.get("corrective_retries", 0))
        wall_deadline = snapshot.get("wall_deadline")
        if wall_deadline is not None and spec.wall_clock_seconds is not None:
            bc._wall_deadline = float(wall_deadline)
            remaining_wall = bc._wall_deadline - wall_clock()
            bc._deadline = clock() + max(remaining_wall, 0.0)
        return bc

    # -- internals -----------------------------------------------------------

    def _check_deadline_locked(self) -> None:
        if self._deadline is not None and self._clock() >= self._deadline:
            raise DeadlineExceeded("absolute monotonic deadline reached")

    def _apply(self, kind: str, units: int) -> None:
        with self._lock:
            self._apply_locked(kind, units)

    def _apply_locked(self, kind: str, units: int) -> None:
        if units <= 0:
            return
        cur = getattr(self._counters, kind)
        setattr(self._counters, kind, cur + units)

    def _release_locked(self, kind: str, units: int) -> None:
        if units <= 0:
            return
        cur = getattr(self._counters, kind)
        setattr(self._counters, kind, max(cur - units, 0))
