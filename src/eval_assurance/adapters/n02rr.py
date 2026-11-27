"""EA02/EA02-R/EA15 — N02RR record adapter (legacy -> typed contract).

Converts an `n02rr_replay_lib.ReplayEngine.replay()` output dict (or an
equivalent reconciliation-row corrected block) into a typed
`EvaluationResult`, closing IJE-D001/IJE-D002 at the interface:

- `replay_error` set           -> REPLAY_ERROR + NOT_EVALUABLE (never FAIL)
- `http_error` set             -> TRANSPORT_ERROR + NOT_EVALUABLE
- p7s stage-2 payload contradicting the ACTUAL stage-1 selection
                               -> evidence-invalid + NOT_EVALUABLE
- otherwise                    -> qualified CORRECT/INCORRECT

EA02-R hardening (EA-D02): malformed legacy values, contradictory HTTP
metadata and unknown failure classes raise :class:`LegacyContractError`
(separately classified contract error) instead of coercing; callers that
need a record anyway may use :func:`n02rr_contract_error_result`.

EA-D04: pass ``artifact_sha256_verified`` (the recorded sha that the
qualified N02RR loader verified against the artifact bytes) to attach a
VerifiedEvidence envelope; without it the record stays evidence-UNVERIFIED
and cannot enter formal statistics.
"""
from __future__ import annotations

import sys
import pathlib

_SRC = pathlib.Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from eval_assurance.contracts import (EvaluationResult, EvaluationStatus,  # noqa: E402
                                      EvidenceIntegrity, ExecutionStatus,
                                      ParserStatus, SemanticVerdict,
                                      LegacyContractError,
                                      from_legacy_boolean, verify_evidence)

__all__ = ["n02rr_result_from_replay", "n02rr_contract_error_result"]


def n02rr_result_from_replay(rec: dict,
                             provenance: dict | None = None,
                             *,
                             artifact_sha256_verified: str | None = None,
                             ) -> EvaluationResult:
    prov = {
        "experiment_id": rec.get("experiment_id"),
        "trial_id": rec.get("trial_id"),
        "task_id": rec.get("task_id"),
        "model": rec.get("model"),
        "dataset_id": "ij_nano.n02r.suite",
        "parser_version": "arms_v2.parse_response",
        "evaluator_version": "n02r.scorer/contract-v2",
    }
    prov.update(provenance or {})
    http_ok = rec.get("http_ok")
    http_error = rec.get("http_error")
    if http_ok is True and http_error is not None:
        raise LegacyContractError(
            f"contradictory N02RR record {rec.get('trial_id')!r}: http_ok="
            "True alongside http_error")

    p7s = rec.get("p7s_reconstruction") or {}
    if p7s.get("stage2_payload_matches_selection") is False:
        result = from_legacy_boolean(
            rec.get("semantic_correct"),
            failure_class="EVIDENCE_INCONSISTENT_STAGE2_TOOL",
            provenance=prov)
        result.semantic_verdict = SemanticVerdict.NOT_EVALUABLE
    else:
        result = from_legacy_boolean(
            rec.get("semantic_correct"),
            replay_error=rec.get("replay_error"),
            transport_error=http_error is not None,
            http_ok=http_ok,
            provenance=prov)

    if artifact_sha256_verified:
        envelope = verify_evidence(
            prov,
            artifact_sha256_computed=artifact_sha256_verified,
            artifact_sha256_expected=artifact_sha256_verified,
            schema_validated=True,
            trial_identity_match=True,
            basis="n02rr_validated_loader_transfer")
        result.verified_evidence = envelope
        result.evidence = EvidenceIntegrity.VERIFIED
    return result


def n02rr_contract_error_result(rec: dict, error: LegacyContractError,
                                provenance: dict | None = None
                                ) -> EvaluationResult:
    """Fail-closed mapping for records that violate the legacy schema:
    separately classified contract error, never an ordinary model
    outcome."""
    prov = {
        "experiment_id": rec.get("experiment_id"),
        "trial_id": rec.get("trial_id"),
        "task_id": rec.get("task_id"),
        "model": rec.get("model"),
        "dataset_id": "ij_nano.n02r.suite",
        "parser_version": "arms_v2.parse_response",
        "evaluator_version": "n02r.scorer/contract-v2",
    }
    prov.update(provenance or {})
    return EvaluationResult(
        execution_status=ExecutionStatus.EXECUTED,
        evaluation_status=EvaluationStatus.ARTIFACT_ERROR,
        parser_status=ParserStatus.PARSER_SOFTWARE_ERROR,
        semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
        evidence=EvidenceIntegrity.REJECTED,
        evidence_invalid_reason="LEGACY_CONTRACT_ERROR",
        failure_reasons=(f"legacy contract error: {error}",),
        provenance=prov)
