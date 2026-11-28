"""EA09 — continuous canary scheduler (order section 3.4).

Runs FAMILY-SPECIFIC positive and negative golden witnesses through the
ACTUAL production evaluation pipeline (ProductionParser +
ProductionEvaluator — never a simplified canary-only path) at the
preregistered cadence:

- preflight (before any dispatch);
- before model/protocol changes;
- every 25 trials or five minutes, whichever occurs FIRST;
- after resume;
- before sealing;
- before publication.

Canary executions are assurance controls, never model benchmark trials:
they are recorded with ``ExecutionStatus.CANARY_CONTROL`` semantics and
never enter benchmark denominators (the formal boundary already
excludes them).

A failing canary (positive witness not CORRECT, or negative witness
CORRECT) calls the breaker hook — the caller supplies the EA10
``CircuitBreaker`` so the failure is durable, not advisory.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .production.evaluator import ProductionEvaluator, ProductionVerdict
from .production.parser import parse_response

DEFAULT_INTERVAL_TRIALS = 25
DEFAULT_INTERVAL_SECONDS = 300.0


@dataclass
class CanaryResult:
    family: str
    passed: bool
    positive_checks: int = 0
    negative_checks: int = 0
    failures: list = field(default_factory=list)
    checked_utc: str = ""

    def as_control_record(self) -> dict:
        """Control-shaped record (never a benchmark trial)."""
        return {"control": "canary", "family": self.family,
                "passed": self.passed,
                "execution_status": "CANARY_CONTROL",
                "failures": list(self.failures),
                "checked_utc": self.checked_utc}


class CanaryScheduler:
    """Cadence-enforcing witness scheduler over a family-specific
    witness suite (rows as produced by the Wave B witness builder:
    ``{primitive, family, kind, raw, case_id, expected}``)."""

    def __init__(self, witnesses: list[dict], breaker=None,
                 expectations: dict | None = None,
                 interval_trials: int = DEFAULT_INTERVAL_TRIALS,
                 interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
                 clock=time.monotonic):
        if not witnesses:
            raise ValueError("canary scheduler requires witnesses")
        self.witnesses = list(witnesses)
        self.expectations = expectations or {}
        self.breaker = breaker
        self.interval_trials = interval_trials
        self.interval_seconds = interval_seconds
        self._clock = clock
        self._trials_since_canary = interval_trials   # force at preflight
        self._last_canary_at = -interval_seconds
        self._last_healthy_index = -1
        self.dispatched_since_healthy: list[str] = []
        self.history: list[CanaryResult] = []
        self._families = sorted({w["primitive"] for w in self.witnesses})
        self._family_cursor = 0

    # -- witness execution through the ACTUAL production pipeline ----------
    @staticmethod
    def _expected_verdict(w: dict) -> str:
        """The verdict the production pipeline MUST produce for the
        witness kind (expected-class discipline: EMPTY stays EMPTY,
        structural stays INVALID_OUTPUT, semantic-wrong stays
        INCORRECT, positives CORRECT)."""
        kind, exp = w["kind"], w["expected"]
        if kind == "empty" or (kind.startswith("positive")
                               and exp == "EMPTY_OUTPUT"):
            return ProductionVerdict.EMPTY_OUTPUT
        if kind in ("negative-malformed", "negative-dup-key",
                    "negative-multiline", "negative-extra-field",
                    "negative-missing-field"):
            return ProductionVerdict.INVALID_OUTPUT
        if kind in ("negative-wrong", "negative-flags-flip"):
            return ProductionVerdict.INCORRECT
        return ProductionVerdict.CORRECT

    def run_canary(self, family: str | None = None) -> CanaryResult:
        fam = family or self._families[
            self._family_cursor % len(self._families)]
        if family is None:
            self._family_cursor += 1
        rows = [w for w in self.witnesses if w["primitive"] == fam]
        if not rows:
            raise ValueError(f"no witnesses for family {fam!r}")
        result = CanaryResult(family=fam, passed=True,
                              checked_utc=time.strftime(
                                  "%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        for w in rows:
            if w["kind"] == "software-error":
                continue     # canaries are model-path controls; the
                #                  software-error class has its own suite
            parsed = parse_response(w["primitive"], {}, w["raw"])
            verdict = ProductionEvaluator().evaluate(
                {"primitive": w["primitive"]},
                self.expectations.get(w.get("case_id", ""), {}),
                parsed).verdict
            expected = self._expected_verdict(w)
            if verdict == expected:
                if expected == ProductionVerdict.CORRECT:
                    result.positive_checks += 1
                else:
                    result.negative_checks += 1
            else:
                result.passed = False
                result.failures.append(
                    {"witness": w["witness_id"], "kind": w["kind"],
                     "expected": expected, "got": verdict})
        self.history.append(result)
        self._trials_since_canary = 0
        self._last_canary_at = self._clock()
        if result.passed:
            self._last_healthy_index = len(self.history) - 1
            self.dispatched_since_healthy = []
        elif self.breaker is not None:
            self.breaker.open(
                reason=f"canary failure in family {fam}",
                affected_scope=[fam],
                contamination_window=list(self.dispatched_since_healthy))
        return result

    # -- cadence checkpoints --------------------------------------------------
    def preflight(self) -> CanaryResult:
        return self.run_canary()

    def before_change(self) -> CanaryResult:
        return self.run_canary()

    def on_trial(self, trial_id: str) -> CanaryResult | None:
        """Call after every dispatched trial. Runs a canary when the
        trial OR time interval expires (whichever first)."""
        self.dispatched_since_healthy.append(trial_id)
        self._trials_since_canary += 1
        if self._trials_since_canary >= self.interval_trials or \
                (self._clock() - self._last_canary_at) >= \
                self.interval_seconds:
            return self.run_canary()
        return None

    def after_resume(self) -> CanaryResult:
        return self.run_canary()

    def before_seal(self) -> CanaryResult:
        return self.run_canary()

    def before_publication(self) -> CanaryResult:
        return self.run_canary()
