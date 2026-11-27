"""EA02 contract tests: legal combinations, the order's §4.3 illegal
examples as invalid-state mutation tests, and the eligibility function."""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from eval_assurance.contracts import (BusinessVerdict, ContractViolationError,
                                      EvaluationResult, EvaluationStatus,
                                      EvaluatorStatus, EvidenceIntegrity,
                                      ExecutionStatus, ParserStatus,
                                      PublicationEligibility,
                                      QualificationStatus, SafetyVerdict,
                                      SemanticVerdict,
                                      eligible_for_semantic_statistics,
                                      validate_result, violations)

PROV = {"experiment_id": "e1", "trial_id": "t1", "task_id": "k1",
        "model": "S1", "dataset_id": "d1", "parser_version": "p1",
        "evaluator_version": "v1"}


def ok_result(**over) -> EvaluationResult:
    base = dict(
        execution_status=ExecutionStatus.EXECUTED,
        evaluation_status=EvaluationStatus.VALID,
        parser_status=ParserStatus.PARSE_OK,
        semantic_verdict=SemanticVerdict.CORRECT,
        business_verdict=BusinessVerdict.NOT_APPLICABLE,
        safety_verdict=SafetyVerdict.SAFE,
        qualification=QualificationStatus.QUALIFIED,
        publication=PublicationEligibility.ELIGIBLE,
        evidence=EvidenceIntegrity.VERIFIED,
        provenance=dict(PROV))
    base.update(over)
    return EvaluationResult(**base)


class TestLegalPaths(unittest.TestCase):
    def test_qualified_correct_is_valid(self):
        validate_result(ok_result())

    def test_incorrect_model_output_is_qualified_failure(self):
        r = ok_result(semantic_verdict=SemanticVerdict.INCORRECT,
                      parser_status=ParserStatus.MODEL_OUTPUT_INVALID)
        validate_result(r)
        self.assertTrue(eligible_for_semantic_statistics(r))  # case A

    def test_not_evaluable_replay_error_is_legal(self):
        r = ok_result(evaluation_status=EvaluationStatus.REPLAY_ERROR,
                      parser_status=ParserStatus.PARSER_SOFTWARE_ERROR,
                      semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
                      evidence=EvidenceIntegrity.REJECTED,
                      publication=PublicationEligibility.BLOCKED,
                      qualification=QualificationStatus.REVOKED)
        validate_result(r)
        self.assertFalse(eligible_for_semantic_statistics(r))


class TestIllegalCombinations(unittest.TestCase):
    """Order section 4.3 examples as invalid-state mutation tests."""

    def test_evaluator_error_plus_correct_rejected(self):
        self.assertTrue(violations(ok_result(
            evaluation_status=EvaluationStatus.EVALUATOR_ERROR)))

    def test_replay_error_plus_incorrect_rejected(self):
        self.assertTrue(violations(ok_result(
            evaluation_status=EvaluationStatus.REPLAY_ERROR,
            semantic_verdict=SemanticVerdict.INCORRECT)))

    def test_missing_provenance_plus_qualified_verdict_rejected(self):
        r = ok_result(provenance={"experiment_id": "e1"})
        self.assertTrue(any("provenance" in m for m in violations(r)))

    def test_invalid_business_world_plus_business_pass_rejected(self):
        for world in (False, None):
            r = ok_result(business_verdict=BusinessVerdict.PASS,
                          business_world_valid=world)
            self.assertTrue(any("business world" in m
                                for m in violations(r)), world)

    def test_oracle_disagreement_plus_qualified_conclusion_rejected(self):
        r = ok_result(oracle_disagreement=True)
        self.assertTrue(any("disagreement" in m for m in violations(r)))
        r2 = ok_result(oracle_disagreement=True,
                       semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
                       evaluation_status=EvaluationStatus.ORACLE_DISAGREEMENT,
                       publication=PublicationEligibility.BLOCKED)
        self.assertEqual(violations(r2), [])

    def test_safety_violation_never_business_pass_or_publication(self):
        r = ok_result(safety_verdict=SafetyVerdict.VIOLATION,
                      business_verdict=BusinessVerdict.PASS,
                      business_world_valid=True)
        self.assertTrue(any("VIOLATION + business PASS" in m
                            for m in violations(r)))
        r2 = ok_result(safety_verdict=SafetyVerdict.VIOLATION)
        self.assertTrue(any("VIOLATION + ELIGIBLE publication" in m
                            for m in violations(r2)))

    def test_unqualified_scope_cannot_publish_eligible(self):
        for q in (QualificationStatus.UNQUALIFIED,
                  QualificationStatus.REVOKED):
            self.assertTrue(any(q.value in m
                                for m in violations(ok_result(qualification=q))))

    def test_canary_control_never_publication_eligible(self):
        r = ok_result(execution_status=ExecutionStatus.CANARY_CONTROL)
        self.assertTrue(any("canary" in m for m in violations(r)))
        r2 = ok_result(execution_status=ExecutionStatus.CANARY_CONTROL,
                       publication=PublicationEligibility.DIAGNOSTIC_ONLY)
        self.assertEqual(violations(r2), [])
        self.assertFalse(eligible_for_semantic_statistics(r2))

    def test_not_run_or_blocked_cannot_be_qualified(self):
        for ex in (ExecutionStatus.NOT_RUN, ExecutionStatus.BLOCKED,
                   ExecutionStatus.PARTIAL):
            self.assertTrue(violations(ok_result(execution_status=ex)), ex)

    def test_transport_error_cannot_be_qualified(self):
        self.assertTrue(violations(ok_result(
            evaluation_status=EvaluationStatus.TRANSPORT_ERROR,
            semantic_verdict=SemanticVerdict.INCORRECT)))

    def test_unsupported_representation_cannot_be_qualified(self):
        self.assertTrue(violations(ok_result(
            parser_status=ParserStatus.UNSUPPORTED_REPRESENTATION,
            semantic_verdict=SemanticVerdict.INCORRECT)))

    def test_evidence_invalid_marker_blocks_qualified_verdict(self):
        # IJE-D002 class: inconsistent stage-2 evidence must not stay CORRECT
        self.assertTrue(violations(ok_result(
            evidence_invalid_reason="EVIDENCE_INCONSISTENT_STAGE2_TOOL")))

    def test_validator_raises(self):
        with self.assertRaises(ContractViolationError):
            validate_result(ok_result(
                evaluation_status=EvaluationStatus.EVALUATOR_ERROR))


class TestEligibility(unittest.TestCase):
    def test_eligibility_requires_every_gate(self):
        self.assertTrue(eligible_for_semantic_statistics(ok_result()))
        flips = [
            ("execution", dict(execution_status=ExecutionStatus.CANARY_CONTROL)),
            ("pipeline", dict(evaluation_status=EvaluationStatus.ARTIFACT_ERROR,
                              semantic_verdict=SemanticVerdict.NOT_EVALUABLE)),
            ("evidence", dict(evidence=EvidenceIntegrity.REJECTED,
                              semantic_verdict=SemanticVerdict.NOT_EVALUABLE)),
            ("marker", dict(evidence_invalid_reason="x",
                            semantic_verdict=SemanticVerdict.NOT_EVALUABLE)),
            ("evaluator", dict(evaluator_status=EvaluatorStatus.ERROR,
                               semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
                               evaluation_status=EvaluationStatus.EVALUATOR_ERROR)),
            ("disagreement", dict(oracle_disagreement=True,
                                  semantic_verdict=SemanticVerdict.NOT_EVALUABLE)),
            ("verdict", dict(semantic_verdict=SemanticVerdict.NOT_EVALUABLE)),
            ("provenance", dict(provenance={})),
        ]
        for name, over in flips:
            self.assertFalse(eligible_for_semantic_statistics(
                ok_result(**over)), name)


if __name__ == "__main__":
    unittest.main()
