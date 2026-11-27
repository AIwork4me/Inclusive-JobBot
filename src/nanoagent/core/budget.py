"""Authoritative budget controller (NanoAgent Layer A).

Repairs the D05 defect class by construction:
- attempts are counted at reservation time, not at completion;
- every failed call is charged (minimum one unit) even on exception;
- the task deadline is an absolute monotonic instant, never a sliding delta;
- each request sees the budget actually remaining for it;
- corrective retries are bounded separately from first attempts;
- tool calls carry their own timeout budget.

The controller is the single authority: callers may read `remaining(...)` but
never mutate counters directly. All exceptions carry the exhausted kind.
"""
from __future__ import annotations

import dataclasses
import time
from typing import Callable, Hashable

KINDS = ("model_calls", "tool_calls", "completion_tokens", "prompt_tokens", "corrective_retries")


class BudgetExhausted(RuntimeError):
    def __init__(self, kind: str, detail: str = ""):
        self.kind = kind
        super().__init__(f"budget exhausted: {kind}" + (f" ({detail})" if detail else ""))


class DeadlineExceeded(BudgetExhausted):
    def __init__(self, detail: str = ""):
        super().__init__("wall_clock", detail)


@dataclasses.dataclass(frozen=True)
class BudgetSpec:
    model_calls: int = 32
    tool_calls: int = 32
    completion_tokens: int = 8192
    prompt_tokens: int | None = None
    corrective_retries: int = 4
    wall_clock_seconds: float | None = None
    tool_timeout_seconds: float | None = None


@dataclasses.dataclass
class _Counters:
    model_calls: int = 0
    tool_calls: int = 0
    completion_tokens: int = 0
    prompt_tokens: int = 0
    corrective_retries: int = 0


class Reservation:
    """A counted-at-start hold on budget units.

    The units are consumed by `BudgetController.reserve` the moment the
    reservation is made (D05: attempts count at start, so failed calls are
    inherently charged). `charge` only adds any usage that exceeded the
    reservation.
    """

    __slots__ = ("controller", "kind", "units", "kind_detail")

    def __init__(self, controller: "BudgetController", kind: str, units: int, kind_detail: str = ""):
        self.controller = controller
        self.kind = kind
        self.units = units
        self.kind_detail = kind_detail

    def charge(self, actual: int) -> None:
        """Charge usage beyond the reserved units (overrun only)."""
        extra = max(int(actual) - self.units, 0)
        if extra > 0:
            self.controller._apply(self.kind, extra)
            self.units = int(actual)

    def __enter__(self) -> "Reservation":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False  # already fully charged at reservation time


class BudgetController:
    """Single authoritative budget for one task execution."""

    def __init__(self, spec: BudgetSpec, clock: Callable[[], float] = time.monotonic):
        self.spec = spec
        self._clock = clock
        self._counters = _Counters()
        self._started = clock()
        self._deadline = (self._started + spec.wall_clock_seconds
                          if spec.wall_clock_seconds is not None else None)
        self._epoch = 0

    # -- reservation API ---------------------------------------------------

    def reserve(self, kind: str, units: int = 1, *, corrective: bool = False,
                detail: str = "") -> Reservation:
        if kind not in KINDS:
            raise ValueError(f"unknown budget kind: {kind}")
        self._check_deadline()
        if units < 0:
            raise ValueError("units must be >= 0")
        remaining = self.remaining(kind)
        if units > remaining:
            raise BudgetExhausted(kind, f"requested {units}, remaining {remaining}")
        if corrective and kind == "model_calls":
            if self._counters.corrective_retries + 1 > self.spec.corrective_retries:
                raise BudgetExhausted("corrective_retries",
                                      f"cap {self.spec.corrective_retries}")
            self._counters.corrective_retries += 1
        self._apply(kind, units)
        return Reservation(self, kind, units, detail)

    def reserve_tokens(self, completion: int = 0, prompt: int = 0) -> list[Reservation]:
        out = []
        if prompt and self.spec.prompt_tokens is not None:
            out.append(self.reserve("prompt_tokens", prompt))
        if completion:
            out.append(self.reserve("completion_tokens", completion))
        return out

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
        self._check_deadline()

    # -- reads --------------------------------------------------------------

    def remaining(self, kind: str) -> int | None:
        if kind == "prompt_tokens" and self.spec.prompt_tokens is None:
            return None
        used = getattr(self._counters, kind)
        cap = getattr(self.spec, "prompt_tokens" if kind == "prompt_tokens" else kind)
        return max(int(cap) - used, 0)

    def remaining_for_request(self) -> dict:
        """What one more request may still consume (per-request view)."""
        self._check_deadline()
        return {k: self.remaining(k) for k in KINDS if self.remaining(k) is not None}

    def seconds_remaining(self) -> float | None:
        if self._deadline is None:
            return None
        return max(self._deadline - self._clock(), 0.0)

    def snapshot(self) -> dict:
        """Detached copy (D04: usage is returned as a copy, never a live view)."""
        return {
            "counters": dataclasses.asdict(self._counters),
            "seconds_remaining": self.seconds_remaining(),
            "corrective_retry_cap": self.spec.corrective_retries,
        }

    # -- internals -----------------------------------------------------------

    def _check_deadline(self) -> None:
        if self._deadline is not None and self._clock() >= self._deadline:
            raise DeadlineExceeded("absolute monotonic deadline reached")

    def _apply(self, kind: str, units: int) -> None:
        if units <= 0:
            return
        cur = getattr(self._counters, kind)
        setattr(self._counters, kind, cur + units)
