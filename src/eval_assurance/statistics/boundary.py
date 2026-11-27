"""EA02-R EA-D05 / Wave-BC EA-R03+EA-R04 — the mandatory formal Analyzer
boundary, hardened.

Hardening over the audited implementation (all reproduced red first):
- an EMPTY, UNRELATED or REVOKED-only certificate store can never produce
  ALLOWED (the requested aggregation scope must hold a currently-valid,
  authority-issued applicable certificate);
- zero qualified rows never publishes;
- NOT_EVALUABLE rows caused by unresolved critical evaluation-integrity
  faults (error pipeline status / rejected evidence / evidence-invalid
  markers) BLOCK formal publication of the affected scope;
- duplicate trial identities are quarantined, never double-counted;
- planned-roster reconciliation: every applicable planned slot is reported,
  missing slots block unless an explicit partial scope is declared (and a
  partial report is never full closure);
- ``publish_report`` rechecks the qualification snapshot at publication
  time, so a revocation between aggregation and publication fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts import (EvaluationResult, EvaluationStatus,
                         ExecutionStatus, EvidenceIntegrity, SemanticVerdict,
                         ContractViolationError,
                         eligible_for_diagnostics,
                         eligible_for_semantic_statistics, validate_result)
from ..qualification import CertificateStore, QualificationSnapshot

_CRITICAL_PIPELINE = {s for s in EvaluationStatus
                      if s is not EvaluationStatus.VALID}


@dataclass
class AggregationReport:
    scope: str
    total_records: int = 0
    qualified_eligible: int = 0
    correct: int = 0
    incorrect: int = 0
    not_evaluable: int = 0
    critical_not_evaluable: int = 0
    quarantined: int = 0
    canary_controls: int = 0
    diagnostic_eligible: int = 0
    diagnostic_correct: int = 0
    diagnostic_incorrect: int = 0
    duplicate_trial_ids: list[str] = field(default_factory=list)
    missing_slots: list[str] = field(default_factory=list)
    planned_slots: int = 0
    certificate_ids_used: set = field(default_factory=set)
    quarantine_reasons: list[str] = field(default_factory=list)
    not_evaluable_reasons: list[str] = field(default_factory=list)
    formal_publication: str = "BLOCKED"          # fail-closed default
    scope_declaration: str = "full"

    @property
    def conditional_semantic_accuracy(self) -> float | None:
        n = self.qualified_eligible
        return round(self.correct / n, 4) if n else None

    @property
    def evaluation_coverage(self) -> float | None:
        base = (self.planned_slots if self.planned_slots
                else self.total_records - self.canary_controls)
        return round(self.qualified_eligible / base, 4) if base else None

    def headline(self) -> str:
        return (f"{self.correct}/{self.qualified_eligible} qualified "
                f"(+{self.not_evaluable} NOT_EVALUABLE of which "
                f"{self.critical_not_evaluable} critical, "
                f"+{self.quarantined} quarantined)")


def _is_critical_not_evaluable(rec: EvaluationResult) -> bool:
    """Unresolved critical evaluation-integrity fault on the row."""
    if rec.semantic_verdict is not SemanticVerdict.NOT_EVALUABLE:
        return False
    return (rec.evaluation_status in _CRITICAL_PIPELINE
            or rec.evidence in (EvidenceIntegrity.REJECTED,
                                EvidenceIntegrity.MISSING)
            or rec.evidence_invalid_reason is not None)


def aggregate_semantic(records, *, scope: str = "semantic",
                       certificates: CertificateStore | None = None,
                       planned_roster=None,
                       partial_scope_allowed: bool = False
                       ) -> AggregationReport:
    """The qualified aggregation entry point. Accepts ONLY typed records."""
    rep = AggregationReport(
        scope=scope,
        scope_declaration=("partial" if partial_scope_allowed else "full"))
    seen_trial_ids: set[str] = set()
    applicable_cert_seen = False
    for idx, rec in enumerate(records):
        rep.total_records += 1
        if not isinstance(rec, EvaluationResult):
            rep.quarantined += 1
            rep.quarantine_reasons.append(
                f"record[{idx}]: not an EvaluationResult (Booleans/dicts are "
                "not accepted by the formal boundary)")
            continue
        try:
            validate_result(rec)
        except ContractViolationError as e:
            rep.quarantined += 1
            rep.quarantine_reasons.append(f"{rec.provenance.get('trial_id')}"
                                          f": {e}")
            continue
        trial_id = rec.provenance.get("trial_id")
        if trial_id in seen_trial_ids:
            rep.quarantined += 1
            rep.duplicate_trial_ids.append(str(trial_id))
            rep.quarantine_reasons.append(
                f"{trial_id}: duplicate trial identity (denominator "
                "protection)")
            continue
        seen_trial_ids.add(str(trial_id))
        if rec.execution_status is ExecutionStatus.CANARY_CONTROL:
            rep.canary_controls += 1
            continue
        # certificate applicability is scope-wide: ANY real trial passing
        # validation demonstrates the scope's certification (EA-R03)
        if certificates is not None:
            cert = certificates.valid_certificate_for(rec.provenance, scope)
            if cert is not None:
                applicable_cert_seen = True
                rep.certificate_ids_used.add(cert.certificate_id)
        if rec.semantic_verdict is SemanticVerdict.NOT_EVALUABLE:
            rep.not_evaluable += 1
            if _is_critical_not_evaluable(rec):
                rep.critical_not_evaluable += 1
            rep.not_evaluable_reasons.append(
                f"{trial_id}: {rec.evaluation_status.value}"
                f"{'/' + rec.evidence_invalid_reason if rec.evidence_invalid_reason else ''}")
            continue
        if rec.semantic_verdict is SemanticVerdict.NOT_APPLICABLE:
            rep.not_evaluable += 1
            rep.not_evaluable_reasons.append(f"{trial_id}: NOT_APPLICABLE")
            continue
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

    # ---- planned-roster reconciliation (EA-R03) ---------------------------
    if planned_roster is not None:
        roster = [str(t) for t in planned_roster]
        rep.planned_slots = len(roster)
        rep.missing_slots = [t for t in roster if t not in seen_trial_ids]

    # ---- publication decision (fail-closed chain) -------------------------
    if rep.quarantined:
        rep.formal_publication = "BLOCKED_QUARANTINED"
    elif certificates is None or not certificates.trusted:
        rep.formal_publication = "BLOCKED_NO_TRUSTED_CERTIFICATE"
    elif not applicable_cert_seen:
        rep.formal_publication = "BLOCKED_SCOPE_NOT_CERTIFIED"
    elif rep.critical_not_evaluable:
        rep.formal_publication = "BLOCKED_CRITICAL_NOT_EVALUABLE"
    elif rep.qualified_eligible == 0:
        rep.formal_publication = "BLOCKED_NO_QUALIFIED_ROWS"
    elif planned_roster is not None and rep.missing_slots:
        rep.formal_publication = (
            "ALLOWED_PARTIAL" if partial_scope_allowed
            else "BLOCKED_INCOMPLETE_ROSTER")
    else:
        rep.formal_publication = "ALLOWED"
    return rep


def publish_report(report: AggregationReport, certificates: CertificateStore,
                   snapshot: QualificationSnapshot | None = None,
                   ) -> AggregationReport:
    """Formal publication step (EA-R04 time-of-check): the qualification
    snapshot must still be current (no revocation/issuance since
    aggregation) and every certificate the aggregation consumed must still
    be valid. Any drift fails closed with RuntimeError; the report's
    formal_publication is downgraded to BLOCKED."""
    snap = snapshot if snapshot is not None else certificates.snapshot()
    if not certificates.snapshot_is_current(snap):
        report.formal_publication = "BLOCKED_QUALIFICATION_CHANGED"
        raise RuntimeError(
            "qualification state changed between aggregation and "
            "publication (revocation or reissue detected) — publication "
            "refused (EA-R04)")
    for cert_id in report.certificate_ids_used:
        cert = certificates.get(cert_id)
        if cert is None or not cert.is_valid():
            report.formal_publication = "BLOCKED_QUALIFICATION_REVOKED"
            raise RuntimeError(
                f"certificate {cert_id} no longer valid at publication "
                "time (EA-R04)")
    if not report.formal_publication.startswith("ALLOWED"):
        raise RuntimeError(
            f"report is not publishable: {report.formal_publication}")
    return report
