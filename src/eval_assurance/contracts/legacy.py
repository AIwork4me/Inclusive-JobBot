"""EA02 §4.4 / EA02-R EA-D02 — legacy Boolean compatibility adapters.

Hardened rules:
- only a GENUINE Boolean from a validated legacy schema may map to a decisive
  semantic verdict; ``type(x) is bool`` is enforced, nothing coerces;
- the legacy record is validated as a complete schema: contradictory
  metadata (http_ok True + http_error set; replay_error set + verdict True)
  and unknown failure classes raise :class:`LegacyContractError` — they
  never silently become ordinary model outcomes;
- converting a typed record back to a Boolean validates the COMPLETE record
  first and raises for anything unevaluable (fail closed, never silent
  False).
"""
from __future__ import annotations

from .core import (EvaluationResult, EvaluationStatus, EvidenceIntegrity,
                   ExecutionStatus, KNOWN_LEGACY_FAILURE_CLASSES,
                   ParserStatus, SemanticVerdict)
from .validator import validate_result

__all__ = ["from_legacy_boolean", "to_legacy_boolean",
           "LegacyRepresentationError", "LegacyContractError"]


class LegacyRepresentationError(ValueError):
    """The typed verdict cannot be represented as a legacy Boolean."""


class LegacyContractError(ValueError):
    """The legacy record violates the validated legacy schema (wrong types,
    contradictory metadata, or an unknown failure class). Separately
    classified contract error — never an ordinary model outcome."""


def _validate_legacy_schema(*, semantic_correct, replay_error,
                            transport_error, failure_class, http_ok=None):
    if type(semantic_correct) is not bool:
        raise LegacyContractError(
            "legacy semantic_correct must be a genuine bool, got "
            f"{type(semantic_correct).__name__}: {semantic_correct!r}")
    if replay_error is not None and not isinstance(replay_error, str):
        raise LegacyContractError("legacy replay_error must be str|None")
    if transport_error is not None and not isinstance(transport_error, bool):
        raise LegacyContractError("legacy transport_error must be bool|None")
    if failure_class is not None:
        if not isinstance(failure_class, str):
            raise LegacyContractError("legacy failure_class must be str|None")
        if failure_class not in KNOWN_LEGACY_FAILURE_CLASSES:
            raise LegacyContractError(
                f"unknown legacy failure class {failure_class!r} — refusing "
                "to map an unclassified failure to an ordinary model outcome")
    if replay_error is not None and semantic_correct:
        raise LegacyContractError(
            "contradictory legacy metadata: replay_error set alongside "
            "semantic_correct=True")
    if transport_error and semantic_correct:
        raise LegacyContractError(
            "contradictory legacy metadata: transport_error alongside "
            "semantic_correct=True")
    if http_ok is True and transport_error:
        # http_ok=True + replay_error is LEGITIMATE (transport succeeded,
        # evaluator crashed); only a transport contradiction is impossible.
        raise LegacyContractError(
            "contradictory legacy metadata: http_ok=True alongside a "
            "transport error")


def from_legacy_boolean(semantic_correct: bool, *,
                        replay_error: str | None = None,
                        failure_class: str | None = None,
                        transport_error: bool = False,
                        http_ok: bool | None = None,
                        provenance: dict | None = None) -> EvaluationResult:
    """Adapt a legacy N02RR-style record to the typed contract, fail-closed.

    Precedence (every branch keeps the verdict OUT of model-failure
    statistics unless the validated legacy evidence genuinely supports it):
    1. replay_error                    -> REPLAY_ERROR + NOT_EVALUABLE
    2. transport_error                 -> TRANSPORT_ERROR + NOT_EVALUABLE
    3. failure_class EVIDENCE_*        -> evidence-invalid + NOT_EVALUABLE
    4. otherwise                       -> CORRECT/INCORRECT (qualified)
    Unknown failure classes, non-Boolean verdicts and contradictory metadata
    raise LegacyContractError BEFORE any mapping happens.
    """
    _validate_legacy_schema(semantic_correct=semantic_correct,
                            replay_error=replay_error,
                            transport_error=transport_error,
                            failure_class=failure_class, http_ok=http_ok)
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
            evidence_invalid_reason=fc,
            failure_reasons=(fc,),
            provenance=prov)
    return EvaluationResult.evaluated(semantic=semantic_correct,
                                      provenance=prov)


def to_legacy_boolean(result: EvaluationResult) -> bool:
    """Downgrade to a legacy Boolean — NEVER silently. Validates the
    COMPLETE record first; CORRECT -> True, INCORRECT -> False; anything
    else raises LegacyRepresentationError."""
    validate_result(result)      # complete-record validation (EA-D02)
    if result.semantic_verdict is SemanticVerdict.CORRECT:
        return True
    if result.semantic_verdict is SemanticVerdict.INCORRECT:
        return False
    raise LegacyRepresentationError(
        f"cannot represent {result.semantic_verdict.value} as a legacy "
        "Boolean; refusing to erase NOT_EVALUABLE/NOT_APPLICABLE")
