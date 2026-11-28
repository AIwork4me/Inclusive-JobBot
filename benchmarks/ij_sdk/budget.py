"""IJ-SDK-1.1 P4A (D05): the one authoritative resource budget for a trial.

Design rules - each one is a regression test in tests/ij_sdk/test_budget.py:

  * An attempt is counted when it starts, not when it succeeds.
  * Every request receives the REMAINING budget, never the initial budget.
  * The deadline is absolute and is read from a monotonic clock.
  * A call that fails, times out or returns garbage is charged its reservation,
    never zero.
  * A permit is closed exactly once; a permit left open is charged and reported.
  * Overruns are recorded, never hidden: an enforcement failure is a finding.
  * A framework that cannot honour a limit must say so (``mark_unenforced``).
    Such a trial is not "matched budget" and is blocked from formal scoring.

Stdlib only, so the SDK environments import the same controller.
"""

from __future__ import annotations

import dataclasses
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable


@dataclass
class Budget:
    """Limits for ONE trial. Copied by the controller; never mutated in place."""
    max_model_calls: int = 16
    max_tool_calls: int = 32
    max_generated_tokens: int = 8192
    max_prompt_tokens: int = 32768
    max_request_tokens: int = 1024      # generated-token cap for a single model call
    corrective_retries: int = 0         # M0: 0; M1: <= 2 (frozen per profile)
    max_wall_seconds: float = 180.0
    max_tool_seconds: float = 30.0


@dataclass(frozen=True)
class ModelCallPermit:
    """What one model call is allowed to consume. Issued before the call starts."""
    permit_id: int
    call_index: int
    max_tokens: int
    timeout_seconds: float
    deadline: float
    issued_at: float
    remaining_at_issue: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCallPermit:
    """What one tool call is allowed to consume."""
    permit_id: int
    call_index: int
    timeout_seconds: float
    deadline: float
    started_at: float


class BudgetExhausted(Exception):
    """Raised before an attempt starts when the remaining budget cannot cover it."""

    def __init__(self, reason: str, snapshot: dict[str, Any]):
        super().__init__(reason)
        self.reason = reason
        self.snapshot = snapshot


class BudgetController:
    """Authoritative accounting shared by adapters, the transport and the tool gateway."""

    def __init__(self, budget: Budget | None = None, *, clock: Callable[[], float] = time.monotonic):
        self._budget = replace(budget) if budget is not None else Budget()
        self._clock = clock
        self._started = clock()
        self._lock = threading.RLock()
        self._next_permit = 0
        self._open: dict[int, ModelCallPermit | ToolCallPermit] = {}   # permit_id -> open permit
        self._cancelled: str | None = None
        # attempts and outcomes
        self.model_calls_attempted = 0
        self.model_calls_completed = 0
        self.model_calls_failed = 0
        self.model_calls_timed_out = 0
        self.tool_calls_attempted = 0
        self.tool_calls_completed = 0
        self.tool_calls_failed = 0
        self.tool_calls_timed_out = 0
        # tokens actually charged (unknown outcomes are charged their reservation)
        self.prompt_tokens_charged = 0
        self.completion_tokens_charged = 0
        self.completion_tokens_reported = 0
        self.completion_tokens_unreported = 0
        self.retries = 0
        # findings
        self.enforcement_failures: list[dict[str, Any]] = []
        self.overruns: list[dict[str, Any]] = []
        self.unenforced: list[dict[str, str]] = []
        self.events: list[dict[str, Any]] = []

    # -- queries ------------------------------------------------------------
    @property
    def budget(self) -> Budget:
        return replace(self._budget)

    def now(self) -> float:
        return self._clock()

    def deadline(self) -> float:
        return self._started + self._budget.max_wall_seconds

    def elapsed(self) -> float:
        return max(0.0, self._clock() - self._started)

    def wall_remaining(self) -> float:
        return max(0.0, self.deadline() - self._clock())

    @property
    def cancelled(self) -> str | None:
        return self._cancelled

    def remaining(self) -> dict[str, Any]:
        """What any subsequent request may consume. This is what a request receives."""
        with self._lock:
            return {
                "wall_seconds": round(self.wall_remaining(), 6),
                "model_calls": max(0, self._budget.max_model_calls - self.model_calls_attempted),
                "tool_calls": max(0, self._budget.max_tool_calls - self.tool_calls_attempted),
                "generated_tokens": max(0, self._budget.max_generated_tokens - self.completion_tokens_charged),
                "prompt_tokens": max(0, self._budget.max_prompt_tokens - self.prompt_tokens_charged),
                "retries": max(0, self._budget.corrective_retries - self.retries),
            }

    def _guard(self, what: str) -> None:
        if self._cancelled is not None:
            raise BudgetExhausted(f"cancelled: {self._cancelled}", self.snapshot())
        if self._clock() >= self.deadline():
            raise BudgetExhausted("deadline_exceeded", self.snapshot())
        left = self.remaining()
        if left[what] <= 0:
            raise BudgetExhausted(f"{what}_exhausted", self.snapshot())

    # -- model calls --------------------------------------------------------
    def begin_model_call(self, requested_max_tokens: int | None = None,
                         prompt_tokens_lower_bound: int | None = None) -> ModelCallPermit:
        """Count an attempt and issue what it may consume. Raises BudgetExhausted before
        the attempt is counted when the remaining budget cannot cover any call."""
        with self._lock:
            self._guard("model_calls")
            if prompt_tokens_lower_bound is not None and prompt_tokens_lower_bound > self.remaining()["prompt_tokens"]:
                raise BudgetExhausted("prompt_tokens_exhausted", self.snapshot())
            left = self.remaining()
            cap = self._budget.max_request_tokens if requested_max_tokens is None else min(requested_max_tokens,
                                                                                           self._budget.max_request_tokens)
            max_tokens = min(cap, left["generated_tokens"])
            if max_tokens <= 0:
                raise BudgetExhausted("generated_tokens_exhausted", self.snapshot())
            self.model_calls_attempted += 1
            self._next_permit += 1
            now = self._clock()
            permit = ModelCallPermit(permit_id=self._next_permit, call_index=self.model_calls_attempted,
                                     max_tokens=max_tokens, timeout_seconds=left["wall_seconds"],
                                     deadline=self.deadline(), issued_at=now, remaining_at_issue=dict(left))
            self._open[permit.permit_id] = permit
            self._log("model_call_begin", permit=permit.permit_id, max_tokens=max_tokens)
            return permit

    def end_model_call(self, permit: ModelCallPermit, *, prompt_tokens: int | None = None,
                       completion_tokens: int | None = None, error: str | None = None,
                       timed_out: bool = False, finish_reason: str | None = None) -> None:
        """Close a model call. Unknown usage (error, timeout, unparseable) is charged the
        reservation so that a failed call never looks free."""
        with self._lock:
            if not self._close(permit, "model"):          # already closed: nothing is charged a second time
                return
            if timed_out:
                self.model_calls_timed_out += 1
            elif error is not None:
                self.model_calls_failed += 1
            else:
                self.model_calls_completed += 1
            if completion_tokens is None:
                charged = permit.max_tokens
                self.completion_tokens_unreported += charged
            else:
                charged = max(0, int(completion_tokens))
                self.completion_tokens_reported += charged
            self.completion_tokens_charged += charged
            if charged > permit.max_tokens:
                self._overrun("generated_tokens_exceeded_permit", {"charged": charged, "permitted": permit.max_tokens})
            if prompt_tokens is not None:
                self.prompt_tokens_charged += max(0, int(prompt_tokens))
                if self.prompt_tokens_charged > self._budget.max_prompt_tokens:
                    self._overrun("prompt_tokens_exceeded", {"charged": self.prompt_tokens_charged,
                                                             "permitted": self._budget.max_prompt_tokens})
            self._log("model_call_end", permit=permit.permit_id, charged=charged, error=error,
                      timed_out=timed_out, finish_reason=finish_reason)

    def precheck_prompt_tokens(self, lower_bound: int) -> None:
        """Refuse to send a request whose prompt is already known to exceed the remaining budget."""
        with self._lock:
            self._guard("model_calls")
            if lower_bound > self.remaining()["prompt_tokens"]:
                raise BudgetExhausted("prompt_tokens_exhausted", self.snapshot())

    # -- tool calls ---------------------------------------------------------
    def begin_tool_call(self) -> ToolCallPermit:
        with self._lock:
            self._guard("tool_calls")
            left = self.remaining()
            timeout = min(self._budget.max_tool_seconds, left["wall_seconds"])
            self.tool_calls_attempted += 1
            self._next_permit += 1
            now = self._clock()
            permit = ToolCallPermit(permit_id=self._next_permit, call_index=self.tool_calls_attempted,
                                    timeout_seconds=timeout, deadline=min(now + timeout, self.deadline()),
                                    started_at=now)
            self._open[permit.permit_id] = permit
            self._log("tool_call_begin", permit=permit.permit_id, timeout=timeout)
            return permit

    def end_tool_call(self, permit: ToolCallPermit, *, error: str | None = None, timed_out: bool = False) -> None:
        with self._lock:
            if not self._close(permit, "tool"):           # already closed: nothing is counted a second time
                return
            if timed_out:
                self.tool_calls_timed_out += 1
            elif error is not None:
                self.tool_calls_failed += 1
            else:
                self.tool_calls_completed += 1
            duration = max(0.0, self._clock() - permit.started_at)
            if self._clock() > permit.deadline + 1e-9:
                self._overrun("tool_deadline_exceeded", {"duration": round(duration, 6),
                                                         "permitted": round(permit.timeout_seconds, 6)})
            self._log("tool_call_end", permit=permit.permit_id, error=error, timed_out=timed_out)

    # -- retries, limits the framework cannot honour ------------------------
    def charge_retry(self, reason: str = "") -> bool:
        """Charge one corrective retry. Returns False when the retry budget is already spent."""
        with self._lock:
            if self.retries >= self._budget.corrective_retries:
                self._log("retry_refused", reason=reason)
                return False
            self.retries += 1
            self._log("retry_charged", reason=reason, retries=self.retries)
            return True

    def mark_unenforced(self, aspect: str, detail: str) -> None:
        """Record a limit this framework could not honour. Blocks matched-budget qualification."""
        with self._lock:
            self.unenforced.append({"aspect": aspect, "detail": detail})
            self._log("unenforced", aspect=aspect)

    def cancel(self, reason: str) -> None:
        with self._lock:
            if self._cancelled is None:
                self._cancelled = reason
                self._log("cancelled", reason=reason)

    # -- state --------------------------------------------------------------
    def matched_budget(self) -> bool:
        """True only when every limit was enforced and none was exceeded."""
        with self._lock:
            return not self.unenforced and not self.enforcement_failures and not self._open

    def finalize(self) -> dict[str, Any]:
        """Close the trial: any permit still open is charged its reservation and reported."""
        with self._lock:
            for permit in list(self._open.values()):
                self._fail("permit_left_open", {"permit": permit.permit_id,
                                                "kind": "model" if isinstance(permit, ModelCallPermit) else "tool"})
                if isinstance(permit, ModelCallPermit):
                    self.completion_tokens_charged += permit.max_tokens
                    self.completion_tokens_unreported += permit.max_tokens
            self._open.clear()
            return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "model_calls": self.model_calls_attempted,
                "model_calls_completed": self.model_calls_completed,
                "model_calls_failed": self.model_calls_failed,
                "model_calls_timed_out": self.model_calls_timed_out,
                "tool_calls": self.tool_calls_attempted,
                "tool_calls_completed": self.tool_calls_completed,
                "tool_calls_failed": self.tool_calls_failed,
                "tool_calls_timed_out": self.tool_calls_timed_out,
                "prompt_tokens": self.prompt_tokens_charged,
                "completion_tokens": self.completion_tokens_charged,
                "completion_tokens_reported": self.completion_tokens_reported,
                "completion_tokens_unreported": self.completion_tokens_unreported,
                "retries": self.retries,
                "wall_seconds": round(self.elapsed(), 6),
                "limits": dataclasses.asdict(self._budget),
                "remaining": self.remaining(),
                "enforcement_failures": list(self.enforcement_failures),
                "overruns": list(self.overruns),
                "unenforced": list(self.unenforced),
                "cancelled": self._cancelled,
                "open_permits": len(self._open),
                "matched_budget": self.matched_budget(),
            }

    # -- internals ----------------------------------------------------------
    def _close(self, permit: ModelCallPermit | ToolCallPermit, kind: str) -> bool:
        """Take the permit out of the open set. False (and an enforcement failure) when it was
        already closed or never issued."""
        if self._open.pop(permit.permit_id, None) is None:
            self._fail("permit_closed_twice_or_unknown", {"permit": permit.permit_id, "kind": kind})
            return False
        return True

    def _fail(self, code: str, detail: dict[str, Any]) -> None:
        self.enforcement_failures.append({"code": code, **detail, "at": round(self.elapsed(), 6)})

    def _overrun(self, code: str, detail: dict[str, Any]) -> None:
        row = {"code": code, **detail, "at": round(self.elapsed(), 6)}
        self.overruns.append(row)
        self.enforcement_failures.append(row)

    def _log(self, event: str, **fields: Any) -> None:
        self.events.append({"event": event, "at": round(self.elapsed(), 6), **fields})
