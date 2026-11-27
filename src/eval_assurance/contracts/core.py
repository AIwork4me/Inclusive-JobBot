"""EA02/EA02-R — typed evaluation contract core (IJ-EVAL-ASSURANCE-1.0).

Nine independent dimensions (mission order section 4.1); a single Boolean may
never represent them (INV01/INV02: unknown is neither incorrect nor correct).

EA02-R hardening (addendum EA-D02/EA-D03/EA-D04):
- strict runtime type validation: enum fields must be genuine Enum members,
  Booleans must be genuine bools; string/int substitutions raise
  ContractTypeError at construction time;
- evidence defaults to UNVERIFIED (never VERIFIED-by-omission); VERIFIED
  requires a VerifiedEvidence envelope produced by the actual verification
  path (verify_evidence), binding artifact hash, trial identity, schema and
  evaluator identity;
- provenance distinguishes CLAIMED fields from VERIFIED identity; the
  validator cross-checks the envelope against the record's provenance so a
  caller-provided dictionary cannot overwrite verified identity undetected.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ContractTypeError(TypeError):
    """A contract dimension carries a value of the wrong runtime type."""


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
    UNVERIFIED = "UNVERIFIED"      # default: trust nothing by omission
    PENDING = "PENDING"            # verification started, not finished
    VERIFIED = "VERIFIED"          # only via verify_evidence()
    REJECTED = "REJECTED"
    MISSING = "MISSING"


#: provenance identity keys mandatory before any qualified semantic verdict
#: (order EA08 evidence identity, applied at contract level).
MANDATORY_PROVENANCE_KEYS = (
    "experiment_id", "trial_id", "task_id", "model", "dataset_id",
    "parser_version", "evaluator_version",
)

ENVELOPE_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class VerifiedEvidence:
    """Versioned verified-evidence envelope (EA-D04).

    Constructed ONLY by :func:`verify_evidence` after the actual verification
    checks complete. Binds the evidence to the identity fields it verified;
    the validator cross-checks these against the record's provenance, so a
    caller-supplied provenance dict that disagrees with the envelope is
    detected rather than trusted.
    """
    schema_version: str
    verified_keys: tuple[str, ...]
    identity: dict
    artifact_sha256: str
    verification_checks: dict

    def matches_provenance(self, provenance: dict) -> bool:
        return all(self.identity.get(k) == provenance.get(k)
                   for k in self.verified_keys)


def verify_evidence(claimed_provenance: dict, *,
                    artifact_sha256_computed: str,
                    artifact_sha256_expected: str,
                    schema_validated: bool,
                    trial_identity_match: bool,
                    evaluator_identity_match: bool = True,
                    basis: str = "direct") -> VerifiedEvidence:
    """The actual evidence verification path (EA-D04).

    Takes CLAIMED provenance plus the results of real checks (hash computed
    over the artifact bytes vs the recorded expectation, strict schema
    validation outcome, trial-identity and evaluator-identity matches) and,
    only if every check passes, returns the VerifiedEvidence envelope.
    Raises ValueError (fail closed) on any failed check.

    ``basis`` records HOW verification happened: "direct" (bytes re-hashed
    now) or a named qualified loader whose verification result is being
    transferred (e.g. the N02RR validated loader).
    """
    if not schema_validated:
        raise ValueError("evidence verification failed: schema not validated")
    if not trial_identity_match:
        raise ValueError("evidence verification failed: trial identity "
                         "mismatch")
    if not evaluator_identity_match:
        raise ValueError("evidence verification failed: evaluator identity "
                         "mismatch")
    if (not isinstance(artifact_sha256_computed, str)
            or not isinstance(artifact_sha256_expected, str)
            or artifact_sha256_computed.lower()
            != artifact_sha256_expected.lower()
            or len(artifact_sha256_computed) == 0):
        raise ValueError("evidence verification failed: artifact sha256 "
                         "mismatch")
    missing = [k for k in MANDATORY_PROVENANCE_KEYS
               if not isinstance(claimed_provenance.get(k), str)
               or not claimed_provenance.get(k)]
    if missing:
        raise ValueError(f"evidence verification failed: claimed provenance "
                         f"incomplete: {missing}")
    return VerifiedEvidence(
        schema_version=ENVELOPE_SCHEMA_VERSION,
        verified_keys=MANDATORY_PROVENANCE_KEYS,
        identity={k: claimed_provenance[k]
                  for k in MANDATORY_PROVENANCE_KEYS},
        artifact_sha256=artifact_sha256_computed.lower(),
        verification_checks={
            "artifact_sha256_match": True,
            "schema_validated": True,
            "trial_identity_match": True,
            "evaluator_identity_match": True,
            "basis": basis})


#: legacy failure classes with defined contract meaning. Anything else is a
#: contract error, never an ordinary model outcome (EA-D02).
KNOWN_LEGACY_FAILURE_CLASSES = frozenset({
    # evidence/software classes -> never model outcomes
    "REPLAY_ERROR", "TRANSPORT_ERROR", "EVIDENCE_INSUFFICIENT",
    "EVIDENCE_INCONSISTENT_STAGE2_TOOL",
    # genuine model-outcome classes (N02RR taxonomy)
    "SUCCESS", "SEMANTIC_ERROR", "STRUCTURAL_GENERATION_ERROR",
    "STRUCTURAL_GENERATION_ERROR_DUP_KEY", "TOOL_CALL_ONLY_UNPARSED",
    "EMPTY_FINAL_CONTENT_STOPPED", "EMPTY_FINAL_CONTENT_TRUNCATED",
    "GENERATION_TRUNCATED", "STAGE1_SELECTION_FAILED",
})


_ENUM_FIELDS = {
    "execution_status": ExecutionStatus,
    "evaluation_status": EvaluationStatus,
    "parser_status": ParserStatus,
    "evaluator_status": EvaluatorStatus,
    "semantic_verdict": SemanticVerdict,
    "business_verdict": BusinessVerdict,
    "safety_verdict": SafetyVerdict,
    "qualification": QualificationStatus,
    "publication": PublicationEligibility,
    "evidence": EvidenceIntegrity,
}


@dataclass
class EvaluationResult:
    """One typed evaluation record with strict runtime type validation."""
    execution_status: ExecutionStatus
    evaluation_status: EvaluationStatus
    parser_status: ParserStatus
    semantic_verdict: SemanticVerdict
    evaluator_status: EvaluatorStatus = EvaluatorStatus.OK
    business_verdict: BusinessVerdict = BusinessVerdict.NOT_APPLICABLE
    safety_verdict: SafetyVerdict = SafetyVerdict.NOT_APPLICABLE
    qualification: QualificationStatus = QualificationStatus.UNQUALIFIED
    publication: PublicationEligibility = PublicationEligibility.BLOCKED
    evidence: EvidenceIntegrity = EvidenceIntegrity.UNVERIFIED
    evidence_invalid_reason: str | None = None
    oracle_disagreement: bool = False
    business_world_valid: bool | None = None
    provenance: dict = field(default_factory=dict)
    failure_reasons: tuple[str, ...] = ()
    verified_evidence: VerifiedEvidence | None = None

    def __post_init__(self):
        # EA-D02/EA-D03: no implicit coercion anywhere in the contract.
        for name, enum_type in _ENUM_FIELDS.items():
            value = getattr(self, name)
            if not isinstance(value, enum_type):
                raise ContractTypeError(
                    f"{name} must be {enum_type.__name__}, got "
                    f"{type(value).__name__}: {value!r}")
        if type(self.oracle_disagreement) is not bool:
            raise ContractTypeError("oracle_disagreement must be bool, got "
                                    f"{type(self.oracle_disagreement).__name__}")
        if self.business_world_valid is not None and \
                type(self.business_world_valid) is not bool:
            raise ContractTypeError("business_world_valid must be bool|None, "
                                    f"got "
                                    f"{type(self.business_world_valid).__name__}")
        if self.evidence_invalid_reason is not None and \
                not isinstance(self.evidence_invalid_reason, str):
            raise ContractTypeError("evidence_invalid_reason must be str|None")
        if not isinstance(self.provenance, dict):
            raise ContractTypeError("provenance must be a dict")
        if any(not isinstance(k, str) for k in self.provenance):
            raise ContractTypeError("provenance keys must be strings")
        if not isinstance(self.failure_reasons, tuple) or \
                any(not isinstance(r, str) for r in self.failure_reasons):
            raise ContractTypeError("failure_reasons must be a tuple of str")
        if self.verified_evidence is not None and \
                not isinstance(self.verified_evidence, VerifiedEvidence):
            raise ContractTypeError(
                "verified_evidence must be a VerifiedEvidence envelope "
                "produced by verify_evidence()")

    # -- convenience constructors for the two verdict-stable paths ----------
    @classmethod
    def evaluated(cls, *, semantic: bool, **kw) -> "EvaluationResult":
        """Qualified evaluation path: pipeline VALID, parser OK. The verdict
        argument must be a genuine Boolean (EA-D02)."""
        if type(semantic) is not bool:
            raise ContractTypeError(
                f"semantic must be a genuine bool, got "
                f"{type(semantic).__name__}: {semantic!r}")
        kw.setdefault("evidence", EvidenceIntegrity.UNVERIFIED)
        return cls(
            execution_status=kw.pop("execution_status",
                                    ExecutionStatus.EXECUTED),
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
