"""EA02 legacy adapters + N02RR adapter tests — the IJE-D001/IJE-D002
closure demonstrated against the exact production record shapes from the
EA00 §2.2 reproduction."""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from eval_assurance.contracts import (EvaluationStatus,
                                      LegacyRepresentationError,
                                      SemanticVerdict,
                                      eligible_for_semantic_statistics,
                                      from_legacy_boolean, to_legacy_boolean)
from eval_assurance.adapters.n02rr import n02rr_result_from_replay

PROV = {"experiment_id": "ec5b95357e960f99", "trial_id": "t1",
        "task_id": "TS01", "model": "S1", "dataset_id": "ij_nano.n02r.suite",
        "parser_version": "arms_v2", "evaluator_version": "contract-v2"}


def replay_record(**over):
    """Shape of n02rr_replay_lib.ReplayEngine.replay() output."""
    base = dict(experiment_id="ec5b95357e960f99", trial_id="t1",
                model="S1", arm="M-P1", task_id="TS01",
                family="tool_selection", http_ok=True, http_error=None,
                semantic_correct=True, replay_error=None,
                p7s_reconstruction=None,
                stage1_selection_wrong_tool=None)
    base.update(over)
    return base


class TestLegacyBooleanAdapter(unittest.TestCase):
    def test_legacy_true_false_roundtrip(self):
        r = from_legacy_boolean(True, provenance=PROV)
        self.assertIs(r.semantic_verdict, SemanticVerdict.CORRECT)
        self.assertIs(to_legacy_boolean(r), True)
        r2 = from_legacy_boolean(False, provenance=PROV)
        self.assertIs(to_legacy_boolean(r2), False)

    def test_legacy_replay_error_never_becomes_model_failure(self):
        r = from_legacy_boolean(False, replay_error="RuntimeError: crash",
                                provenance=PROV)
        self.assertIs(r.semantic_verdict, SemanticVerdict.NOT_EVALUABLE)
        self.assertIs(r.evaluation_status, EvaluationStatus.REPLAY_ERROR)
        self.assertFalse(eligible_for_semantic_statistics(r))
        with self.assertRaises(LegacyRepresentationError):
            to_legacy_boolean(r)

    def test_legacy_evidence_inconsistent_never_becomes_pass(self):
        r = from_legacy_boolean(
            True, failure_class="EVIDENCE_INCONSISTENT_STAGE2_TOOL",
            provenance=PROV)
        self.assertIs(r.semantic_verdict, SemanticVerdict.NOT_EVALUABLE)
        self.assertFalse(eligible_for_semantic_statistics(r))

    def test_legacy_transport_error_not_evaluable(self):
        r = from_legacy_boolean(False, transport_error=True, provenance=PROV)
        self.assertIs(r.semantic_verdict, SemanticVerdict.NOT_EVALUABLE)
        self.assertFalse(eligible_for_semantic_statistics(r))


class TestN02RRAdapter(unittest.TestCase):
    def test_adapter_qualified_pass(self):
        r = n02rr_result_from_replay(replay_record(semantic_correct=True))
        self.assertIs(r.semantic_verdict, SemanticVerdict.CORRECT)
        self.assertTrue(eligible_for_semantic_statistics(r))

    def test_adapter_qualified_fail(self):
        r = n02rr_result_from_replay(replay_record(semantic_correct=False))
        self.assertIs(r.semantic_verdict, SemanticVerdict.INCORRECT)
        self.assertTrue(eligible_for_semantic_statistics(r))

    def test_adapter_replay_error_not_evaluable(self):
        """EA00 R1 exact shape: coerced False + replay_error set."""
        r = n02rr_result_from_replay(replay_record(
            semantic_correct=False, replay_error="RuntimeError: synthetic"))
        self.assertIs(r.semantic_verdict, SemanticVerdict.NOT_EVALUABLE)
        self.assertIs(r.evaluation_status, EvaluationStatus.REPLAY_ERROR)
        self.assertFalse(eligible_for_semantic_statistics(r))

    def test_adapter_http_error_not_evaluable(self):
        r = n02rr_result_from_replay(replay_record(
            semantic_correct=False, http_error="HTTP 500"))
        self.assertIs(r.semantic_verdict, SemanticVerdict.NOT_EVALUABLE)

    def test_adapter_p7s_inconsistent_not_evaluable(self):
        """EA00 R2 exact shape: verdict True but stage-2 contradicts stage-1."""
        r = n02rr_result_from_replay(replay_record(
            arm="P7S", semantic_correct=True,
            p7s_reconstruction={"stage2_executed": True,
                                "stage2_payload_matches_selection": False}))
        self.assertIs(r.semantic_verdict, SemanticVerdict.NOT_EVALUABLE)
        self.assertEqual(r.evidence_invalid_reason,
                         "EVIDENCE_INCONSISTENT_STAGE2_TOOL")
        self.assertFalse(eligible_for_semantic_statistics(r))

    def test_adapter_p7s_consistent_wrong_selection_stays_qualified(self):
        """Wrong stage-1 selection executed consistently is a REAL model
        failure (RS02 semantics), not an evidence defect."""
        r = n02rr_result_from_replay(replay_record(
            arm="P7S", semantic_correct=False,
            stage1_selection_wrong_tool=True,
            p7s_reconstruction={"stage2_executed": True,
                                "stage2_payload_matches_selection": True}))
        self.assertIs(r.semantic_verdict, SemanticVerdict.INCORRECT)
        self.assertTrue(eligible_for_semantic_statistics(r))


if __name__ == "__main__":
    unittest.main()
