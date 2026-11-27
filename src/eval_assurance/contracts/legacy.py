"""EA02 section 4.4 — legacy Boolean compatibility adapters.

A legacy Boolean `semantic_correct` can represent only CORRECT/INCORRECT.
Reading legacy rows is allowed; erasing NOT_EVALUABLE is not. Converting a
typed record with an unevaluable verdict back to a Boolean FAILS CLOSED
(raises) instead of silently mapping to False.
"""
from __future__ import annotations

from .core import (EvaluationResult, EvaluationStatus, EvidenceIntegrity,
                   ExecutionStatus, ParserStatus, SemanticVerdict)

__all__ = ["from_legacy_boolean", "to_legacy_boolean",
           "LegacyRepresentationError"]


class LegacyRepresentationError(ValueError):
    """The typed verdict cannot be represented as a legacy Boolean."""


def from_legacy_boolean(semantic_correct: bool, *,
                        replay_error: str | None = None,
                        failure_class: str | None = None,
                        transport_error: bool = False,
                        provenance: dict | None = None) -> EvaluationResult:
    """Adapt a legacy N02RR-style record to the typed contract, fail-closed.

    Precedence (every branch keeps the verdict OUT of model-failure
    statistics unless the legacy evidence genuinely supports it):
    1. replay_error                    -> REPLAY_ERROR + NOT_EVALUABLE
    2. transport_error                 -> TRANSPORT_ERROR + NOT_EVALUABLE
    3. failure_class EVIDENCE_*        -> evidence-invalid + NOT_EVALUABLE
    4. otherwise                       -> CORRECT/INCORRECT (qualified)
    """
    prov = dict(provenance or {})
    if replay_error:
        return EvaluationResult(
            execution_status=ExecutionStatus.EXECUTED,
            evaluation_status=EvaluationStatus.REPLAY_ERROR,
            parser_status=ParserStatus.PARSER_SOFTWARE_ERROR,
            semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
            evidence=EvidenceIntegrity.REJECTED,
            failure_reasons=(f"replay_error: {replay_error}",),
            provenance=prov)
    if transport_error:
        return EvaluationResult(
            execution_status=ExecutionStatus.EXECUTED,
            evaluation_status=EvaluationStatus.TRANSPORT_ERROR,
            parser_status=ParserStatus.UNSUPPORTED_REPRESENTATION,
            semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
            evidence=EvidenceIntegrity.REJECTED,
            failure_reasons=("transport_error",),
            provenance=prov)
    fc = (failure_class or "")
    if fc.startswith("EVIDENCE_INCONSISTENT") or fc == "EVIDENCE_INSUFFICIENT":
        return EvaluationResult(
            execution_status=ExecutionStatus.EXECUTED,
            evaluation_status=EvaluationStatus.VALID,
            parser_status=ParserStatus.PARSE_OK,
            semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
            evidence_invalid_reason=fc or "evidence_inconsistent",
            failure_reasons=(fc or "evidence_inconsistent",),
            provenance=prov)
    return EvaluationResult.evaluated(
        semantic=bool(semantic_correct), provenance=prov)


def to_legacy_boolean(result: EvaluationResult) -> bool:
    """Downgrade to a legacy Boolean — NEVER silently.

    CORRECT -> True, INCORRECT -> False; anything else raises
    LegacyRepresentationError (fail closed per order section 4.4). Callers
    that need a counts-safe view must use eligible_for_semantic_statistics
    instead of coercing verdicts.
    """
    if result.semantic_verdict is SemanticVerdict.CORRECT:
        return True
    if result.semantic_verdict is SemanticVerdict.INCORRECT:
        return False
    raise LegacyRepresentationError(
        f"cannot represent {result.semantic_verdict.value} as a legacy "
        "Boolean; refusing to erase NOT_EVALUABLE/NOT_APPLICABLE")
