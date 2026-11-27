"""EA02-R EA-D05 / EA11 preview — the mandatory formal Analyzer boundary.

Every formal aggregation path must consume validated, scope-bound records
through this boundary. There is deliberately NO entry point that accepts
arbitrary Boolean dictionaries: records arrive as typed ``EvaluationResult``
objects (built through validated adapters), are re-validated here, and are
classified before any counting happens:

- qualified   : formal-eligible rows (certificates required, else fail-closed
                to diagnostic);
- not_evaluable : classified invalid-evidence rows (reported separately,
                never inside accuracy numerators or denominators);
- quarantined : records that are themselves illegal or unclassifiable —
                these BLOCK formal publication;
- canary      : assurance controls (never model observations).

The EA00 injected-corruption regression is the acceptance test: the sealed
corrected corpus (870 genuine successes / 2,184) plus one replay-exception
row (legacy False) and one causally inconsistent row (legacy True) must
aggregate to 870 correct / 2,184 evaluable / 2 not_evaluable — the
contaminated 871/2186 headline is structurally unreachable, and formal
publication is blocked while no qualification certificate is bound.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts import (EvaluationResult, EvaluationStatus,
                         ExecutionStatus, SemanticVerdict,
                         ContractViolationError,
                         eligible_for_diagnostics,
                         eligible_for_semantic_statistics, validate_result)
from ..qualification import CertificateStore


@dataclass
class AggregationReport:
    scope: str
    total_records: int = 0
    qualified_eligible: int = 0
    correct: int = 0
    incorrect: int = 0
    not_evaluable: int = 0
    quarantined: int = 0
    canary_controls: int = 0
    diagnostic_eligible: int = 0
    diagnostic_correct: int = 0
    diagnostic_incorrect: int = 0
    quarantine_reasons: list[str] = field(default_factory=list)
    not_evaluable_reasons: list[str] = field(default_factory=list)
    formal_publication: str = "BLOCKED"          # fail-closed default

    @property
    def conditional_semantic_accuracy(self) -> float | None:
        n = self.qualified_eligible
        return round(self.correct / n, 4) if n else None

    @property
    def evaluation_coverage(self) -> float | None:
        # coverage over records that claimed to be real trials
        base = (self.total_records - self.canary_controls)
        return round(self.qualified_eligible / base, 4) if base else None

    def headline(self) -> str:
        return (f"{self.correct}/{self.qualified_eligible} qualified "
                f"(+{self.not_evaluable} NOT_EVALUABLE, "
                f"+{self.quarantined} quarantined)")


def aggregate_semantic(records, *, scope: str = "semantic",
                       certificates: CertificateStore | None = None,
                       ) -> AggregationReport:
    """The qualified aggregation entry point. Accepts ONLY typed records."""
    rep = AggregationReport(scope=scope)
    for idx, rec in enumerate(records):
        rep.total_records += 1
        if not isinstance(rec, EvaluationResult):
            rep.quarantined += 1
            rep.quarantine_reasons.append(
                f"record[{idx}]: not an EvaluationResult (Booleans/dicts are "
                "not accepted by the formal boundary)")
            continue
        # 1. central validator first: illegal records are quarantined
        try:
            validate_result(rec)
        except ContractViolationError as e:
            rep.quarantined += 1
            rep.quarantine_reasons.append(f"{rec.provenance.get('trial_id')}"
                                          f": {e}")
            continue
        # 2. canary accounting (EA09): controls are counted, never model rows
        if rec.execution_status is ExecutionStatus.CANARY_CONTROL:
            rep.canary_controls += 1
            continue
        # 3. classified invalid evidence -> reported separately
        if rec.semantic_verdict is SemanticVerdict.NOT_EVALUABLE:
            rep.not_evaluable += 1
            rep.not_evaluable_reasons.append(
                f"{rec.provenance.get('trial_id')}: "
                f"{rec.evaluation_status.value}"
                f"{'/' + rec.evidence_invalid_reason if rec.evidence_invalid_reason else ''}")
            continue
        if rec.semantic_verdict is SemanticVerdict.NOT_APPLICABLE:
            rep.not_evaluable += 1
            rep.not_evaluable_reasons.append(
                f"{rec.provenance.get('trial_id')}: NOT_APPLICABLE")
            continue
        # 4. decisive verdicts: eligibility authorities decide admission
        if eligible_for_diagnostics(rec).eligible:
            rep.diagnostic_eligible += 1
            if rec.semantic_verdict is SemanticVerdict.CORRECT:
                rep.diagnostic_correct += 1
            else:
                rep.diagnostic_incorrect += 1
        if eligible_for_semantic_statistics(rec, certificates).eligible:
            rep.qualified_eligible += 1
            if rec.semantic_verdict is SemanticVerdict.CORRECT:
                rep.correct += 1
            else:
                rep.incorrect += 1
        # decisive verdicts that fail formal eligibility (no certificate /
        # qualification) are diagnostic-only and never silently counted
    # 5. formal publication gate: fail-closed without certificates; any
    #    quarantine blocks publication outright
    if rep.quarantined:
        rep.formal_publication = "BLOCKED"
    elif certificates is None:
        rep.formal_publication = "BLOCKED_NO_CERTIFICATE_BOUND"
    else:
        rep.formal_publication = "ALLOWED"
    return rep
