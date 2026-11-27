"""EA02 — typed evaluation contract core (IJ-EVAL-ASSURANCE-1.0).

Nine independent dimensions (mission order section 4.1); a single Boolean may
never represent them (INV01/INV02: unknown is neither incorrect nor correct).

Dimension semantics:
- ExecutionStatus      — did the trial physically run, and is it a real
                         benchmark trial or an assurance control?
- EvaluationStatus     — evidence/pipeline software status (the suggested
                         enum of order section 4.1 verbatim).
- ParserStatus         — PARSE_OK, or WHY parsing did not yield a typed
                         payload. MODEL_OUTPUT_INVALID is a *qualified model
                         failure* (order section 4.2 case A);
                         UNSUPPORTED_REPRESENTATION and PARSER_SOFTWARE_ERROR
                         are NOT (case B).
- EvaluatorStatus      — production evaluator outcome at the software level.
- SemanticVerdict      — the semantic dimension only.
- BusinessVerdict      — business postcondition dimension.
- SafetyVerdict        — safety/authorization dimension; VIOLATION overrides
                         every other dimension (INV09).
- QualificationStatus  — standing of the scope's certificate.
- PublicationEligibility — what may consume this record.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ExecutionStatus(Enum):
    EXECUTED = "EXECUTED"
    NOT_RUN = "NOT_RUN"
    BLOCKED = "BLOCKED"
    PARTIAL = "PARTIAL"
    CANARY_CONTROL = "CANARY_CONTROL"      # assurance control, never a trial


class EvaluationStatus(Enum):
    VALID = "VALID"
    ARTIFACT_ERROR = "ARTIFACT_ERROR"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    PARSER_ERROR = "PARSER_ERROR"
    EVALUATOR_ERROR = "EVALUATOR_ERROR"
    REPLAY_ERROR = "REPLAY_ERROR"
    ORACLE_DISAGREEMENT = "ORACLE_DISAGREEMENT"
    INVALID_DATASET = "INVALID_DATASET"
    UNSUPPORTED_CONTRACT = "UNSUPPORTED_CONTRACT"


class ParserStatus(Enum):
    PARSE_OK = "PARSE_OK"
    MODEL_OUTPUT_INVALID = "MODEL_OUTPUT_INVALID"        # case A (model)
    UNSUPPORTED_REPRESENTATION = "UNSUPPORTED_REPRESENTATION"  # case B
    PARSER_SOFTWARE_ERROR = "PARSER_SOFTWARE_ERROR"      # case B


class EvaluatorStatus(Enum):
    OK = "OK"
    ERROR = "ERROR"
    DISAGREEMENT = "DISAGREEMENT"


class SemanticVerdict(Enum):
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class BusinessVerdict(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_VERIFIED = "NOT_VERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SafetyVerdict(Enum):
    SAFE = "SAFE"
    VIOLATION = "VIOLATION"
    NOT_VERIFIED = "NOT_VERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class QualificationStatus(Enum):
    QUALIFIED = "QUALIFIED"
    UNQUALIFIED = "UNQUALIFIED"
    REVOKED = "REVOKED"
    PENDING = "PENDING"


class PublicationEligibility(Enum):
    ELIGIBLE = "ELIGIBLE"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    BLOCKED = "BLOCKED"


class EvidenceIntegrity(Enum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    MISSING = "MISSING"


#: provenance keys mandatory before any qualified semantic verdict may be
#: issued (order EA08 evidence identity, applied at contract level).
MANDATORY_PROVENANCE_KEYS = (
    "experiment_id", "trial_id", "task_id", "model", "dataset_id",
    "parser_version", "evaluator_version",
)


@dataclass
class EvaluationResult:
    """One typed evaluation record. All dimensions are explicit; none is
    derived from another silently. validator.validate_result() is the single
    authority for legal combinations; persistence/aggregation/publication
    must call it (order section 4.3)."""
    execution_status: ExecutionStatus
    evaluation_status: EvaluationStatus
    parser_status: ParserStatus
    semantic_verdict: SemanticVerdict
    evaluator_status: EvaluatorStatus = EvaluatorStatus.OK
    business_verdict: BusinessVerdict = BusinessVerdict.NOT_APPLICABLE
    safety_verdict: SafetyVerdict = SafetyVerdict.NOT_APPLICABLE
    qualification: QualificationStatus = QualificationStatus.UNQUALIFIED
    publication: PublicationEligibility = PublicationEligibility.BLOCKED
    evidence: EvidenceIntegrity = EvidenceIntegrity.VERIFIED
    evidence_invalid_reason: str | None = None
    oracle_disagreement: bool = False
    business_world_valid: bool | None = None
    provenance: dict = field(default_factory=dict)
    failure_reasons: tuple[str, ...] = ()

    # -- convenience constructors for the two verdict-stable paths ----------
    @classmethod
    def evaluated(cls, *, semantic: bool, **kw) -> "EvaluationResult":
        """Qualified evaluation path: pipeline VALID, parser OK."""
        return cls(
            execution_status=ExecutionStatus.EXECUTED,
            evaluation_status=EvaluationStatus.VALID,
            parser_status=ParserStatus.PARSE_OK,
            semantic_verdict=(SemanticVerdict.CORRECT if semantic
                              else SemanticVerdict.INCORRECT),
            **kw)

    @classmethod
    def not_evaluable(cls, *, evaluation_status: EvaluationStatus,
                      reason: str, **kw) -> "EvaluationResult":
        """Fail-closed path (INV01/INV02): software/evidence failure is never
        a model failure."""
        return cls(
            execution_status=kw.pop("execution_status",
                                    ExecutionStatus.EXECUTED),
            evaluation_status=evaluation_status,
            parser_status=kw.pop("parser_status",
                                 ParserStatus.PARSER_SOFTWARE_ERROR),
            semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
            failure_reasons=(reason,), **kw)
