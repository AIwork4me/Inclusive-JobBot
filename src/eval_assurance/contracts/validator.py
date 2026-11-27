"""EA02 section 4.3 — central combination validator.

Rejects illegal dimension combinations BEFORE persistence, aggregation or
publication. Developer discipline is not a control; this function is.
"""
from __future__ import annotations

from .core import (EvaluationResult, EvaluationStatus, EvaluatorStatus,
                   ExecutionStatus, EvidenceIntegrity, MANDATORY_PROVENANCE_KEYS,
                   ParserStatus, PublicationEligibility, QualificationStatus,
                   SafetyVerdict, SemanticVerdict)


class ContractViolationError(ValueError):
    """Raised (or collected) for an illegal dimension combination."""


def violations(result: EvaluationResult) -> list[str]:
    """All illegal-combination findings for the record (never silent)."""
    v: list[str] = []
    add = v.append

    es, ev = result.evaluation_status, result.semantic_verdict
    qualified = ev in (SemanticVerdict.CORRECT, SemanticVerdict.INCORRECT)

    # INV01/INV02 + order section 4.3 examples ------------------------------
    if es is EvaluationStatus.EVALUATOR_ERROR and ev is SemanticVerdict.CORRECT:
        add("EVALUATOR_ERROR + CORRECT")
    if es is EvaluationStatus.REPLAY_ERROR and ev is SemanticVerdict.INCORRECT:
        add("REPLAY_ERROR + INCORRECT")
    if es is EvaluationStatus.TRANSPORT_ERROR and qualified:
        add("TRANSPORT_ERROR + qualified verdict")

    # any non-VALID pipeline status forces NOT_EVALUABLE --------------------
    if es is not EvaluationStatus.VALID and qualified:
        add(f"{es.value} + qualified semantic verdict")

    # parser dimension -------------------------------------------------------
    ps = result.parser_status
    if ps is ParserStatus.UNSUPPORTED_REPRESENTATION and qualified:
        add("UNSUPPORTED_REPRESENTATION + qualified verdict (order 4.2B)")
    if ps is ParserStatus.PARSER_SOFTWARE_ERROR:
        if qualified:
            add("PARSER_SOFTWARE_ERROR + qualified verdict (order 4.2B)")
        if es is EvaluationStatus.VALID:
            add("PARSER_SOFTWARE_ERROR requires a non-VALID evaluation_status "
                "(PARSER_ERROR/REPLAY_ERROR/...)")

    # evaluator dimension ----------------------------------------------------
    if result.evaluator_status is EvaluatorStatus.ERROR:
        if qualified:
            add("evaluator ERROR + qualified verdict")
        if es is not EvaluationStatus.EVALUATOR_ERROR:
            add("evaluator ERROR requires evaluation_status=EVALUATOR_ERROR")
    if (result.oracle_disagreement
            or result.evaluator_status is EvaluatorStatus.DISAGREEMENT):
        if es is not EvaluationStatus.ORACLE_DISAGREEMENT:
            add("oracle disagreement requires evaluation_status="
                "ORACLE_DISAGREEMENT")
        if qualified or result.publication is PublicationEligibility.ELIGIBLE:
            add("oracle disagreement + qualified conclusion/publication")

    # evidence dimension -----------------------------------------------------
    if es is EvaluationStatus.VALID and result.evidence is not \
            EvidenceIntegrity.VERIFIED:
        add("VALID pipeline requires VERIFIED evidence")
    if result.evidence_invalid_reason is not None and qualified:
        add("evidence-invalid marker + qualified verdict (IJE-D002 class)")
    if result.evidence is EvidenceIntegrity.REJECTED and qualified:
        add("REJECTED evidence + qualified verdict")

    # provenance (order section 4.3) ----------------------------------------
    if qualified:
        missing = [k for k in MANDATORY_PROVENANCE_KEYS
                   if not result.provenance.get(k)]
        if missing:
            add(f"qualified verdict with missing provenance: {missing}")

    # execution dimension ----------------------------------------------------
    if result.execution_status in (ExecutionStatus.NOT_RUN,
                                   ExecutionStatus.BLOCKED,
                                   ExecutionStatus.PARTIAL) and qualified:
        add(f"{result.execution_status.value} + qualified verdict")
    if result.execution_status is ExecutionStatus.CANARY_CONTROL and \
            result.publication is PublicationEligibility.ELIGIBLE:
        add("canary control marked publication-ELIGIBLE (EA09 accounting)")

    # business / safety (order section 4.3, INV09) --------------------------
    if result.business_verdict.value == "PASS":
        if result.business_world_valid is not True:
            add("business PASS with invalid/unverified business world")
        if result.safety_verdict is SafetyVerdict.VIOLATION:
            add("safety VIOLATION + business PASS (INV09)")

    # qualification / publication -------------------------------------------
    if result.qualification in (QualificationStatus.UNQUALIFIED,
                                QualificationStatus.REVOKED) and \
            result.publication is PublicationEligibility.ELIGIBLE:
        add(f"{result.qualification.value} scope + ELIGIBLE publication")
    if result.safety_verdict is SafetyVerdict.VIOLATION and \
            result.publication is PublicationEligibility.ELIGIBLE:
        add("safety VIOLATION + ELIGIBLE publication")
    return v


def validate_result(result: EvaluationResult) -> EvaluationResult:
    """Validate or raise; the gate every consumer must call."""
    found = violations(result)
    if found:
        raise ContractViolationError(
            f"illegal evaluation-result combination(s): {'; '.join(found)}")
    return result
