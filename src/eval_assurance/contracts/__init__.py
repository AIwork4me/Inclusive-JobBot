"""Typed evaluation contract (EA02 / EA02-R hardened) — public API.

Version history:
- 1.0.0 (2026-11-28): nine typed dimensions, central combination validator,
  statistical eligibility function, fail-closed legacy Boolean adapters.
- 1.1.0 (2026-11-28, EA02-R): strict runtime type validation; evidence
  defaults UNVERIFIED with VerifiedEvidence envelopes via verify_evidence();
  five eligibility authorities (diagnostic / formal semantic / formal
  business / formal publication / reward) with certificate-gated fail-closed
  formal paths; legacy schema validation rejecting non-Boolean verdicts,
  contradictory metadata and unknown failure classes; new validator rules
  (MODEL_OUTPUT_INVALID+CORRECT, undecidable+ELIGIBLE, PENDING+ELIGIBLE,
  business-PASS safety/pipeline requirements, envelope cross-check).
"""
from .core import (BusinessVerdict, ContractTypeError, EvaluationResult,
                   EvaluationStatus, EvaluatorStatus, EvidenceIntegrity,
                   ExecutionStatus, KNOWN_LEGACY_FAILURE_CLASSES,
                   MANDATORY_PROVENANCE_KEYS, ParserStatus,
                   PublicationEligibility, QualificationStatus, SafetyVerdict,
                   SemanticVerdict, VerifiedEvidence, verify_evidence)
from .eligibility import (EligibilityDecision, eligible_for_business_statistics,
                          eligible_for_diagnostics,
                          eligible_for_formal_publication,
                          eligible_for_reward,
                          eligible_for_semantic_statistics)
from .legacy import (LegacyContractError, LegacyRepresentationError,
                     from_legacy_boolean, to_legacy_boolean)
from .validator import ContractViolationError, validate_result, violations

CONTRACT_SPEC_VERSION = "1.1.0"

__all__ = [
    "BusinessVerdict", "ContractTypeError", "EvaluationResult",
    "EvaluationStatus", "EvaluatorStatus", "EvidenceIntegrity",
    "ExecutionStatus", "KNOWN_LEGACY_FAILURE_CLASSES",
    "MANDATORY_PROVENANCE_KEYS", "ParserStatus", "PublicationEligibility",
    "QualificationStatus", "SafetyVerdict", "SemanticVerdict",
    "VerifiedEvidence", "verify_evidence",
    "EligibilityDecision", "eligible_for_business_statistics",
    "eligible_for_diagnostics", "eligible_for_formal_publication",
    "eligible_for_reward", "eligible_for_semantic_statistics",
    "LegacyContractError", "LegacyRepresentationError",
    "from_legacy_boolean", "to_legacy_boolean", "ContractViolationError",
    "validate_result", "violations", "CONTRACT_SPEC_VERSION",
]
