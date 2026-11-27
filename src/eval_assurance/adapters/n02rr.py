"""EA02/EA15 — N02RR record adapter (legacy -> typed contract).

Converts an `n02rr_replay_lib.ReplayEngine.replay()` output dict (or a
reconciliation-row `corrected` block with equivalent fields) into a typed
`EvaluationResult`, closing IJE-D001/IJE-D002 at the interface:

- `replay_error` set           -> REPLAY_ERROR + NOT_EVALUABLE (never FAIL)
- `http_error` set             -> TRANSPORT_ERROR + NOT_EVALUABLE
- p7s stage-2 payload contradicting the ACTUAL stage-1 selection
                               -> evidence-invalid + NOT_EVALUABLE
- otherwise                    -> qualified CORRECT/INCORRECT

The adapter never re-scores; verdicts are only re-TYPED. Statistical
consumption must then go through eligible_for_semantic_statistics.
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
                                      from_legacy_boolean)

__all__ = ["n02rr_result_from_replay"]


def n02rr_result_from_replay(rec: dict,
                             provenance: dict | None = None) -> EvaluationResult:
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

    p7s = rec.get("p7s_reconstruction") or {}
    if p7s.get("stage2_payload_matches_selection") is False:
        r = from_legacy_boolean(
            bool(rec.get("semantic_correct")),
            failure_class="EVIDENCE_INCONSISTENT_STAGE2_TOOL",
            provenance=prov)
        # keep the evidence-invalid marker even if the legacy boolean was True
        r.semantic_verdict = SemanticVerdict.NOT_EVALUABLE
        return r

    return from_legacy_boolean(
        bool(rec.get("semantic_correct")),
        replay_error=rec.get("replay_error"),
        transport_error=rec.get("http_error") is not None,
        failure_class=None,
        provenance=prov)
