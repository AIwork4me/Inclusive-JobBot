"""EA02 section 4.5 — the single statistical eligibility function.

No analyzer may decide row eligibility on its own (closes EA00 finding R3 /
IJE-D001: `n02rr_analyze` counted REPLAY_ERROR and
EVIDENCE_INCONSISTENT_STAGE2_TOOL rows as ordinary verdicts).
"""
from __future__ import annotations

from .core import (EvaluationResult, EvaluationStatus, EvaluatorStatus,
                   ExecutionStatus, EvidenceIntegrity, MANDATORY_PROVENANCE_KEYS,
                   ParserStatus, SemanticVerdict)


def eligible_for_semantic_statistics(result: EvaluationResult) -> bool:
    """True only for records that may enter semantic accuracy numerators and
    denominators: physically executed real trials with verified evidence, a
    VALID pipeline, a decisive parser outcome, an OK evaluator, no
    disagreement, no evidence-invalid marker and complete provenance."""
    return (
        result.execution_status is ExecutionStatus.EXECUTED
        and result.evaluation_status is EvaluationStatus.VALID
        and result.evidence is EvidenceIntegrity.VERIFIED
        and result.evidence_invalid_reason is None
        and result.parser_status in (ParserStatus.PARSE_OK,
                                     ParserStatus.MODEL_OUTPUT_INVALID)
        and result.evaluator_status is EvaluatorStatus.OK
        and not result.oracle_disagreement
        and result.semantic_verdict in (SemanticVerdict.CORRECT,
                                        SemanticVerdict.INCORRECT)
        and all(result.provenance.get(k) for k in MANDATORY_PROVENANCE_KEYS)
    )
