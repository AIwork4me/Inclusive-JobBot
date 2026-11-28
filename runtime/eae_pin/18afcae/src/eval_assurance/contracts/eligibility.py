"""EA02 §4.5 / EA02-R EA-D01 — the eligibility authorities.

Five separate concepts, per the addendum:

1. ``eligible_for_diagnostics``           — diagnostic-only consumption.
2. ``eligible_for_semantic_statistics``   — FORMAL semantic accuracy.
3. ``eligible_for_business_statistics``  — FORMAL business accuracy.
4. ``eligible_for_formal_publication``   — formal publication of conclusions.
5. ``eligible_for_reward``               — valid RL reward derivation (EA16).

The FORMAL authorities require the actual applicable qualification
certificate (CertificateStore lookup by scope + identity binding against the
record's provenance) and verified evidence — never a caller-provided enum.
Until the complete EA17 certificate system exists, formal eligibility FAILS
CLOSED: no store, no certificate, no formal consumption.

Every authority returns a structured EligibilityDecision so refusals are
explainable and auditable, never silent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .core import (EvaluationResult, EvaluationStatus, EvaluatorStatus,
                   EvidenceIntegrity, ExecutionStatus,
                   MANDATORY_PROVENANCE_KEYS, ParserStatus,
                   PublicationEligibility, QualificationStatus,
                   SafetyVerdict, SemanticVerdict, VerifiedEvidence)

if TYPE_CHECKING:            # break the qualification<->contracts cycle
    from ..qualification import CertificateStore


@dataclass(frozen=True)
class EligibilityDecision:
    eligible: bool
    authority: str
    reasons: tuple[str, ...] = ()

    def __bool__(self) -> bool:      # explicit better than implicit, but
        return self.eligible         # keep ergonomic use in filters


def _pipeline_sane(r: EvaluationResult) -> list[str]:
    """Checks shared by every authority (no qualification dimension)."""
    why: list[str] = []
    if r.execution_status is not ExecutionStatus.EXECUTED:
        why.append(f"execution={r.execution_status.value}")
    if r.evaluation_status is not EvaluationStatus.VALID:
        why.append(f"pipeline={r.evaluation_status.value}")
    if r.evidence is not EvidenceIntegrity.VERIFIED:
        why.append(f"evidence={r.evidence.value}")
    if r.evidence_invalid_reason is not None:
        why.append(f"evidence_invalid={r.evidence_invalid_reason}")
    if r.parser_status not in (ParserStatus.PARSE_OK,
                               ParserStatus.MODEL_OUTPUT_INVALID):
        why.append(f"parser={r.parser_status.value}")
    if r.evaluator_status is not EvaluatorStatus.OK:
        why.append(f"evaluator={r.evaluator_status.value}")
    if r.oracle_disagreement:
        why.append("oracle_disagreement")
    if r.semantic_verdict not in (SemanticVerdict.CORRECT,
                                  SemanticVerdict.INCORRECT):
        why.append(f"verdict={r.semantic_verdict.value}")
    if not all(r.provenance.get(k) for k in MANDATORY_PROVENANCE_KEYS):
        why.append("provenance_incomplete")
    if not isinstance(r.verified_evidence, VerifiedEvidence) or \
            not r.verified_evidence.matches_provenance(r.provenance):
        why.append("verified_evidence_envelope_missing_or_mismatched")
    return why


def eligible_for_diagnostics(result: EvaluationResult) -> EligibilityDecision:
    """Concept 1: diagnostic-only eligibility. Same pipeline sanity as always
    (invalid evidence never becomes a model outcome) but NO qualification
    requirement — diagnostic reports must be producible while formal scopes
    are unqualified."""
    why = _pipeline_sane(result)
    return EligibilityDecision(not why, "diagnostics", tuple(why))


def _formal(result: EvaluationResult, *, authority: str,
            certificates: CertificateStore | None,
            scope: str) -> EligibilityDecision:
    why = _pipeline_sane(result)
    # The actual applicable qualification CERTIFICATE is the authority
    # (order EA-D01: "not merely a caller-provided enum"). An explicit
    # revocation marker on the record always blocks (defense in depth);
    # UNQUALIFIED/PENDING enums alone do not qualify anything — without a
    # valid certificate the lookup below fails closed regardless.
    if result.qualification is QualificationStatus.REVOKED:
        why.append("qualification=REVOKED (explicit record revocation)")
    if certificates is None:
        why.append("fail_closed: no certificate store provided")
    elif not certificates.trusted:
        why.append("fail_closed: untrusted certificate store (authority-"
                   "issued qualification required)")
    else:
        cert = certificates.valid_certificate_for(result.provenance, scope)
        if cert is None:
            why.append(f"fail_closed: no valid certificate for scope "
                       f"{scope!r} and record identity binding")
    return EligibilityDecision(not why, authority, tuple(why))


def eligible_for_semantic_statistics(
        result: EvaluationResult,
        certificates: CertificateStore | None = None) -> EligibilityDecision:
    """Concept 2: FORMAL semantic statistics eligibility."""
    return _formal(result, authority="semantic_statistics",
                   certificates=certificates, scope="semantic")


def eligible_for_business_statistics(
        result: EvaluationResult,
        certificates: CertificateStore | None = None) -> EligibilityDecision:
    """Concept 3: FORMAL business statistics eligibility (INV09: safety)."""
    why = list(_formal(result, authority="business_statistics",
                       certificates=certificates,
                       scope="business").reasons)
    if result.business_world_valid is not True:
        why.append("business_world_not_verified_valid")
    if result.safety_verdict is SafetyVerdict.VIOLATION:
        why.append("safety_violation")
    from .core import BusinessVerdict
    if result.business_verdict is BusinessVerdict.PASS and \
            result.safety_verdict is not SafetyVerdict.SAFE:
        why.append("business_PASS_requires_completed_safety_verification")
    return EligibilityDecision(not why, "business_statistics", tuple(why))


def eligible_for_formal_publication(
        result: EvaluationResult,
        certificates: CertificateStore | None = None) -> EligibilityDecision:
    """Concept 4: formal publication eligibility for this record's
    conclusion."""
    why = list(_formal(result, authority="formal_publication",
                       certificates=certificates, scope="semantic").reasons)
    if result.publication is not PublicationEligibility.ELIGIBLE:
        why.append(f"publication={result.publication.value}")
    return EligibilityDecision(not why, "formal_publication", tuple(why))


def eligible_for_reward(
        result: EvaluationResult,
        certificates: CertificateStore | None = None) -> EligibilityDecision:
    """Concept 5: valid RL reward derivation (EA16 preview). Invalid
    evaluation must never silently become reward zero (a punishment of the
    model for an evaluator failure)."""
    why = list(_formal(result, authority="reward",
                       certificates=certificates, scope="reward").reasons)
    if result.safety_verdict is SafetyVerdict.VIOLATION:
        why.append("safety_violation:no_reward_from_unsafe_execution")
    return EligibilityDecision(not why, "reward", tuple(why))
