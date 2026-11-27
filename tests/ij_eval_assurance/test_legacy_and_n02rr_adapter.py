"""EA02/EA02-R legacy adapters + N02RR adapter tests — strict Boolean
handling, legacy schema negative controls, and the IJE-D001/IJE-D002
closure against the exact production record shapes from the EA00 §2.2
reproduction."""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from eval_assurance.contracts import (EvaluationStatus, EvidenceIntegrity,
                                      LegacyContractError,
                                      LegacyRepresentationError,
                                      SemanticVerdict, verify_evidence,
                                      from_legacy_boolean, to_legacy_boolean,
                                      violations)
from eval_assurance.adapters.n02rr import (n02rr_contract_error_result,
                                           n02rr_result_from_replay)

PROV = {"experiment_id": "ec5b95357e960f99", "trial_id": "t1",
        "task_id": "TS01", "model": "S1", "dataset_id": "ij_nano.n02r.suite",
        "parser_version": "arms_v2", "evaluator_version": "contract-v2"}
SHA = "b" * 64


def envelope():
    return verify_evidence(PROV, artifact_sha256_computed=SHA,
                           artifact_sha256_expected=SHA,
                           schema_validated=True, trial_identity_match=True)


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
        r.verified_evidence, r.evidence = envelope(), EvidenceIntegrity.VERIFIED
        self.assertIs(to_legacy_boolean(r), True)
        r2 = from_legacy_boolean(False, provenance=PROV)
        r2.verified_evidence = envelope()
        r2.evidence = EvidenceIntegrity.VERIFIED
        self.assertIs(to_legacy_boolean(r2), False)

    def test_non_boolean_verdicts_raise(self):
        # EA-D02 red class: "False" string used to coerce to CORRECT
        for bad in (None, "False", "True", "FAIL", "PASS", 0, 1, [], [1], {},
                    0.0, "yes"):
            with self.assertRaises(LegacyContractError, msg=repr(bad)):
                from_legacy_boolean(bad, provenance=PROV)

    def test_legacy_replay_error_never_becomes_model_failure(self):
        r = from_legacy_boolean(False, replay_error="RuntimeError: crash",
                                provenance=PROV)
        self.assertIs(r.semantic_verdict, SemanticVerdict.NOT_EVALUABLE)
        self.assertIs(r.evaluation_status, EvaluationStatus.REPLAY_ERROR)
        with self.assertRaises(LegacyRepresentationError):
            to_legacy_boolean(r)

    def test_legacy_evidence_inconsistent_never_becomes_pass(self):
        r = from_legacy_boolean(
            True, failure_class="EVIDENCE_INCONSISTENT_STAGE2_TOOL",
            provenance=PROV)
        self.assertIs(r.semantic_verdict, SemanticVerdict.NOT_EVALUABLE)

    def test_unknown_failure_class_raises(self):
        with self.assertRaises(LegacyContractError):
            from_legacy_boolean(False, failure_class="TOTALLY_NEW_CLASS",
                                provenance=PROV)

    def test_contradictory_metadata_raises(self):
        with self.assertRaises(LegacyContractError):
            from_legacy_boolean(True, replay_error="boom", provenance=PROV)
        with self.assertRaises(LegacyContractError):
            from_legacy_boolean(True, transport_error=True, provenance=PROV)
        with self.assertRaises(LegacyContractError):
            from_legacy_boolean(False, http_ok=True,
                                transport_error=True, provenance=PROV)

    def test_legacy_export_validates_complete_record(self):
        r = from_legacy_boolean(True, provenance=PROV)   # no envelope
        with self.assertRaises(Exception):
            to_legacy_boolean(r)     # missing VERIFIED evidence -> violation


class TestN02RRAdapter(unittest.TestCase):
    def test_adapter_qualified_pass(self):
        r = n02rr_result_from_replay(
            replay_record(semantic_correct=True),
            artifact_sha256_verified=SHA)
        self.assertIs(r.semantic_verdict, SemanticVerdict.CORRECT)
        self.assertEqual(violations(r), [])

    def test_adapter_without_sha_stays_unverified(self):
        r = n02rr_result_from_replay(replay_record(semantic_correct=True))
        self.assertIs(r.evidence, EvidenceIntegrity.UNVERIFIED)

    def test_adapter_replay_error_not_evaluable(self):
        """EA00 R1 exact shape: coerced False + replay_error set."""
        r = n02rr_result_from_replay(replay_record(
            semantic_correct=False, replay_error="RuntimeError: synthetic"),
            artifact_sha256_verified=SHA)
        self.assertIs(r.semantic_verdict, SemanticVerdict.NOT_EVALUABLE)
        self.assertIs(r.evaluation_status, EvaluationStatus.REPLAY_ERROR)

    def test_adapter_http_error_not_evaluable(self):
        r = n02rr_result_from_replay(replay_record(
            semantic_correct=False, http_ok=False, http_error="HTTP 500"),
            artifact_sha256_verified=SHA)
        self.assertIs(r.semantic_verdict, SemanticVerdict.NOT_EVALUABLE)

    def test_adapter_contradictory_http_raises(self):
        rec = replay_record(http_ok=True, http_error="HTTP 500 contradictory")
        with self.assertRaises(LegacyContractError):
            n02rr_result_from_replay(rec)
        # fail-closed mapping available for callers needing a record:
        try:
            n02rr_result_from_replay(rec)
        except LegacyContractError as e:
            r = n02rr_contract_error_result(rec, e)
            self.assertIs(r.semantic_verdict, SemanticVerdict.NOT_EVALUABLE)
            self.assertEqual(r.evidence_invalid_reason,
                             "LEGACY_CONTRACT_ERROR")

    def test_adapter_non_boolean_verdict_raises(self):
        with self.assertRaises(LegacyContractError):
            n02rr_result_from_replay(replay_record(semantic_correct="False"))
        with self.assertRaises(LegacyContractError):
            n02rr_result_from_replay(replay_record(semantic_correct=None))

    def test_adapter_p7s_inconsistent_not_evaluable(self):
        """EA00 R2 exact shape: verdict True but stage-2 contradicts stage-1."""
        r = n02rr_result_from_replay(replay_record(
            arm="P7S", semantic_correct=True,
            p7s_reconstruction={"stage2_executed": True,
                                "stage2_payload_matches_selection": False}),
            artifact_sha256_verified=SHA)
        self.assertIs(r.semantic_verdict, SemanticVerdict.NOT_EVALUABLE)
        self.assertEqual(r.evidence_invalid_reason,
                         "EVIDENCE_INCONSISTENT_STAGE2_TOOL")

    def test_adapter_p7s_consistent_wrong_selection_stays_qualified(self):
        """Wrong stage-1 selection executed consistently is a REAL model
        failure (RS02 semantics), not an evidence defect."""
        r = n02rr_result_from_replay(replay_record(
            arm="P7S", semantic_correct=False,
            stage1_selection_wrong_tool=True,
            p7s_reconstruction={"stage2_executed": True,
                                "stage2_payload_matches_selection": True}),
            artifact_sha256_verified=SHA)
        self.assertIs(r.semantic_verdict, SemanticVerdict.INCORRECT)


if __name__ == "__main__":
    unittest.main()
