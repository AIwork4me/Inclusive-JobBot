"""Typed evaluation contract (EA02) — public API.

Version history:
- 1.0.0 (2026-11-28): nine typed dimensions, central combination validator,
  statistical eligibility function, fail-closed legacy Boolean adapters.
"""
from .core import (BusinessVerdict, EvaluationResult, EvaluationStatus,
                   EvaluatorStatus, EvidenceIntegrity, ExecutionStatus,
                   MANDATORY_PROVENANCE_KEYS, ParserStatus,
                   PublicationEligibility, QualificationStatus, SafetyVerdict,
                   SemanticVerdict)
from .eligibility import eligible_for_semantic_statistics
from .legacy import LegacyRepresentationError, from_legacy_boolean, \
    to_legacy_boolean
from .validator import ContractViolationError, validate_result, violations

CONTRACT_SPEC_VERSION = "1.0.0"

__all__ = [
    "BusinessVerdict", "EvaluationResult", "EvaluationStatus",
    "EvaluatorStatus", "EvidenceIntegrity", "ExecutionStatus",
    "MANDATORY_PROVENANCE_KEYS", "ParserStatus", "PublicationEligibility",
    "QualificationStatus", "SafetyVerdict", "SemanticVerdict",
    "eligible_for_semantic_statistics", "LegacyRepresentationError",
    "from_legacy_boolean", "to_legacy_boolean", "ContractViolationError",
    "validate_result", "violations", "CONTRACT_SPEC_VERSION",
]
