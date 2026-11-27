"""EA02-R EA-D05 — the mandatory formal Analyzer boundary, including the
EA00 injected-corruption regression run against the ACTUAL aggregation entry
point (aggregate_semantic), not just the adapter.

Regression contract (addendum section 1 EA-D05):
- sealed corrected corpus: 870 genuine successes / 2,184;
- inject one replay exception misrepresented as False and one causally
  inconsistent two-stage result misrepresented as True;
- the qualified pipeline must preserve 870, classify both injections as
  NOT_EVALUABLE (reported separately), make the contaminated 871/2186
  headline unreachable, keep formal publication fail-closed without a
  certificate, and leave the sealed corpus file unchanged.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance.adapters.n02rr import n02rr_result_from_replay
from eval_assurance.contracts import (EvidenceIntegrity, SemanticVerdict,
                                      verify_evidence)
from eval_assurance.qualification import CertificateStore
from eval_assurance.statistics import aggregate_semantic

SEALED = ROOT / "evidence" / "IJNANO" / "N02RR" / "trial_reconciliation.jsonl"

PROV = {"experiment_id": "e1", "trial_id": "t1", "task_id": "k1",
        "model": "S1", "dataset_id": "d1", "parser_version": "p1",
        "evaluator_version": "v1"}
SHA = "a" * 64


def env():
    return verify_evidence(PROV, artifact_sha256_computed=SHA,
                           artifact_sha256_expected=SHA,
                           schema_validated=True, trial_identity_match=True)


def typed_record(**over):
    from eval_assurance.contracts import (EvaluationResult,
                                          EvaluationStatus, ExecutionStatus,
                                          ParserStatus,
                                          PublicationEligibility,
                                          QualificationStatus)
    base = dict(
        execution_status=ExecutionStatus.EXECUTED,
        evaluation_status=EvaluationStatus.VALID,
        parser_status=ParserStatus.PARSE_OK,
        semantic_verdict=SemanticVerdict.CORRECT,
        qualification=QualificationStatus.QUALIFIED,
        publication=PublicationEligibility.ELIGIBLE,
        evidence=EvidenceIntegrity.VERIFIED,
        provenance=dict(PROV), verified_evidence=env())
    base.update(over)
    return EvaluationResult(**base)


def n02rr_store():
    store = CertificateStore()
    store.issue(scope="semantic", dataset_id="ij_nano.n02r.suite",
                parser_version="arms_v2.parse_response",
                evaluator_version="n02r.scorer/contract-v2",
                reference_evaluator_version="n02rr-replay",
                evidence_ref="evidence/IJNANO/N02RR/replay_qualification.json")
    return store


def load_sealed_records():
    records = []
    for line in SEALED.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        c = row["corrected"]
        rec = {
            "trial_id": row["trial_id"], "experiment_id":
                "ec5b95357e960f99", "model": row["model"],
            "task_id": row["task_id"], "http_ok": True, "http_error": None,
            "semantic_correct": c["verdict"], "replay_error": None,
            "p7s_reconstruction": c.get("p7s"),
        }
        se = row.get("source_evidence") or {}
        sha = se.get("sha256_recorded") if se.get("sha256_verified") else None
        records.append(n02rr_result_from_replay(
            rec, artifact_sha256_verified=sha))
    return records


def injected_records():
    """The two EA00 corruption shapes, built through the adapter."""
    r1 = n02rr_result_from_replay({
        "trial_id": "SYNTH-EA00-REPLAY-ERROR",
        "experiment_id": "ec5b95357e960f99", "model": "S1", "task_id": "TS01",
        "http_ok": True, "http_error": None, "semantic_correct": False,
        "replay_error": "RuntimeError: synthetic evaluator crash (EA00 R1)",
        "p7s_reconstruction": None}, artifact_sha256_verified=SHA)
    r2 = n02rr_result_from_replay({
        "trial_id": "SYNTH-EA00-EVIDENCE-INCONSISTENT",
        "experiment_id": "ec5b95357e960f99", "model": "S1", "task_id": "TS01",
        "http_ok": True, "http_error": None, "semantic_correct": True,
        "replay_error": None,
        "p7s_reconstruction": {"stage2_executed": True,
                               "stage2_payload_matches_selection": False}},
        artifact_sha256_verified=SHA)
    return [r1, r2]


class TestBoundarySmall(unittest.TestCase):
    def test_boolean_dict_input_quarantined_and_blocks_publication(self):
        rep = aggregate_semantic([True, False, {"semantic_correct": True}])
        self.assertEqual(rep.quarantined, 3)
        self.assertEqual(rep.formal_publication, "BLOCKED")

    def test_counts_with_certificate(self):
        from eval_assurance.contracts import PublicationEligibility
        records = [
            typed_record(),
            typed_record(semantic_verdict=SemanticVerdict.INCORRECT),
            typed_record(semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
                         evidence_invalid_reason="x",
                         publication=PublicationEligibility.DIAGNOSTIC_ONLY)]
        store = CertificateStore()
        store.issue(scope="semantic", dataset_id="d1", parser_version="p1",
                    evaluator_version="v1",
                    reference_evaluator_version="r")
        rep = aggregate_semantic(records, certificates=store)
        self.assertEqual(rep.qualified_eligible, 2)
        self.assertEqual(rep.correct, 1)
        self.assertEqual(rep.incorrect, 1)
        self.assertEqual(rep.not_evaluable, 1)
        self.assertEqual(rep.formal_publication, "ALLOWED")

    def test_fail_closed_without_certificate(self):
        rep = aggregate_semantic([typed_record()])
        self.assertEqual(rep.qualified_eligible, 0)
        self.assertEqual(rep.diagnostic_correct, 1)
        self.assertEqual(rep.formal_publication, "BLOCKED_NO_CERTIFICATE_BOUND")

    def test_canary_never_counted(self):
        from eval_assurance.contracts import (ExecutionStatus,
                                              PublicationEligibility)
        rep = aggregate_semantic([typed_record(
            execution_status=ExecutionStatus.CANARY_CONTROL,
            publication=PublicationEligibility.DIAGNOSTIC_ONLY)],
            certificates=n02rr_store())
        self.assertEqual(rep.canary_controls, 1)
        self.assertEqual(rep.qualified_eligible, 0)


@unittest.skipUnless(SEALED.exists(), "sealed N02RR corpus not present")
class TestEA00CorruptionRegression(unittest.TestCase):
    def test_injected_corruption_contained_at_aggregation_entry(self):
        sealed_sha_before = hashlib.sha256(
            SEALED.read_bytes()).hexdigest()
        records = load_sealed_records() + injected_records()
        self.assertEqual(len(records), 2186)

        # phase 1: no certificate -> fail-closed formal, diagnostic truth
        rep = aggregate_semantic(records)
        self.assertEqual(rep.diagnostic_correct, 870,
                         "870 genuine successes must be preserved")
        self.assertEqual(rep.not_evaluable, 2,
                         "both injections must be classified invalid")
        self.assertEqual(rep.quarantined, 0)
        self.assertEqual(rep.formal_publication,
                         "BLOCKED_NO_CERTIFICATE_BOUND")

        # phase 2: certificate bound -> qualified statistics
        rep2 = aggregate_semantic(records, certificates=n02rr_store())
        self.assertEqual(rep2.qualified_eligible, 2184)
        self.assertEqual(rep2.correct, 870)
        self.assertEqual(rep2.not_evaluable, 2)
        self.assertEqual(rep2.conditional_semantic_accuracy,
                         round(870 / 2184, 4))
        # the contaminated headline is structurally unreachable:
        self.assertNotEqual((rep2.correct, rep2.total_records), (871, 2186))
        self.assertEqual(rep2.formal_publication, "ALLOWED")

        # sealed evidence untouched (INV07)
        self.assertEqual(hashlib.sha256(SEALED.read_bytes()).hexdigest(),
                         sealed_sha_before)


if __name__ == "__main__":
    unittest.main()
