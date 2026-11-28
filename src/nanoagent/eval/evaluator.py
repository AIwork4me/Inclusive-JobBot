"""Independent cognitive evaluator (N05A).

The evaluator owns the control registry and all expectations. The tested
runtime submits only a ``Response``; it never receives an ``Expectation``,
a control class or a reason code. ``evaluate(case_id, response)`` is the
only public entry point; ``describe`` exposes safe metadata (family and
control class) for coverage publication.

This qualification is SCOPED: passing the control battery and mutation
tests qualifies the cognitive evaluators only. It never grants end-to-end
business Oracle qualification (mission order section 5).
"""
from __future__ import annotations

from .comparators import evaluate_family
from .contracts import (ControlCase, EvaluationResult, Expectation,  # noqa: F401
                        Response)


class CaseNotFound(KeyError):
    pass


class CognitiveEvaluator:
    def __init__(self, cases: list[ControlCase] | None = None):
        if cases is None:
            from .controls import battery
            cases = battery()
        self._cases: dict[str, ControlCase] = {}
        for c in cases:
            if c.case_id in self._cases:
                raise ValueError(f"duplicate case id: {c.case_id}")
            self._cases[c.case_id] = c

    # -- runtime-facing API ---------------------------------------------------

    def evaluate(self, case_id: str, response: Response) -> EvaluationResult:
        try:
            c = self._cases[case_id]
        except KeyError as e:
            raise CaseNotFound(case_id) from e
        reasons = evaluate_family(c.expectation, response)
        return EvaluationResult(case_id, c.family, not reasons, tuple(reasons))

    def describe(self, case_id: str) -> dict:
        """Safe metadata for coverage publication (no expectations)."""
        c = self._cases[case_id]
        return {"case_id": c.case_id, "family": c.family,
                "control_class": c.control_class}

    def case_ids(self) -> list[str]:
        return sorted(self._cases)

    # -- coverage -------------------------------------------------------------

    def coverage(self) -> dict:
        """Coverage per cognitive family: control counts per class and the
        reason codes exercised (each negative fails for exactly its single
        declared reason in the qualifying run)."""
        fam: dict[str, dict] = {}
        for c in self._cases.values():
            f = fam.setdefault(c.family, {"positives": 0, "negatives": 0,
                                          "reason_codes": set()})
            if c.control_class == "positive":
                f["positives"] += 1
            else:
                f["negatives"] += 1
                f["reason_codes"].add(c.control_class.split(":", 1)[1])
        for f in fam.values():
            f["reason_codes"] = sorted(f["reason_codes"])
        return fam
