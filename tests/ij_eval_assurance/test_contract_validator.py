"""EA02/EA02-R contract tests: legal combinations, illegal-combination
mutation tests, strict typing, evidence-envelope rules and the five
eligibility authorities."""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from eval_assurance.contracts import (BusinessVerdict, ContractTypeError,
                                      ContractViolationError,
                                      EvaluationResult, EvaluationStatus,
                                      EvaluatorStatus, EvidenceIntegrity,
                                      ExecutionStatus, ParserStatus,
                                      PublicationEligibility,
                                      QualificationStatus, SafetyVerdict,
                                      SemanticVerdict, verify_evidence,
                                      violations)
from eval_assurance.contracts import (eligible_for_business_statistics,
                                      eligible_for_diagnostics,
                                      eligible_for_formal_publication,
                                      eligible_for_reward,
                                      eligible_for_semantic_statistics)
from eval_assurance.qualification import (CertificateError,
                                          CertificateStore,
                                          QualificationAuthority)

PROV = {"experiment_id": "e1", "trial_id": "t1", "task_id": "k1",
        "model": "S1", "dataset_id": "d1", "parser_version": "p1",
        "evaluator_version": "v1"}
SHA = "a" * 64


def envelope():
    return verify_evidence(PROV, artifact_sha256_computed=SHA,
                           artifact_sha256_expected=SHA,
                           schema_validated=True, trial_identity_match=True)


def authority_store(scopes=("semantic", "business", "reward"),
                    dataset_id="d1", parser_version="p1",
                    evaluator_version="v1"):
    """Authority-issued trusted store (writes real implementation files so
    the authority computes genuine digests)."""
    import tempfile
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="eaval-qual-"))

    def f(name, content):
        p = tmp / name
        p.write_text(content, encoding="utf-8")
        return p
    files = {n: f(n, f"implementation {n} v1") for n in
             ("dataset", "task_contract", "parser", "interpreter",
              "evaluator", "oracle", "witnesses", "mutation")}
    auth = QualificationAuthority()
    store = None
    for scope in scopes:
        store = auth.issue_qualification(
            scope=scope, dataset_id=dataset_id,
            parser_version=parser_version, evaluator_version=evaluator_version,
            reference_evaluator_version="ref-independent-1",
            dataset_file=files["dataset"],
            task_contract_file=files["task_contract"],
            parser_file=files["parser"],
            interpreter_file=files["interpreter"],
            evaluator_file=files["evaluator"],
            reference_oracle_file=files["oracle"],
            witness_suite_file=files["witnesses"],
            mutation_report_file=files["mutation"],
            evidence_files=[files["witnesses"], files["mutation"]],
            replay_contract="replay-v1", protocol="proto-v1",
            store=store)
    return store


def ok_result(**over) -> EvaluationResult:
    base = dict(
        execution_status=ExecutionStatus.EXECUTED,
        evaluation_status=EvaluationStatus.VALID,
        parser_status=ParserStatus.PARSE_OK,
        semantic_verdict=SemanticVerdict.CORRECT,
        safety_verdict=SafetyVerdict.SAFE,
        qualification=QualificationStatus.QUALIFIED,
        publication=PublicationEligibility.ELIGIBLE,
        evidence=EvidenceIntegrity.VERIFIED,
        provenance=dict(PROV),
        verified_evidence=envelope())
    base.update(over)
    return EvaluationResult(**base)


class TestLegalPaths(unittest.TestCase):
    def test_qualified_correct_is_valid(self):
        self.assertEqual(violations(ok_result()), [])

    def test_incorrect_model_output_is_qualified_failure(self):
        r = ok_result(semantic_verdict=SemanticVerdict.INCORRECT,
                      parser_status=ParserStatus.MODEL_OUTPUT_INVALID)
        self.assertEqual(violations(r), [])

    def test_not_evaluable_replay_error_is_legal(self):
        r = ok_result(evaluation_status=EvaluationStatus.REPLAY_ERROR,
                      parser_status=ParserStatus.PARSER_SOFTWARE_ERROR,
                      semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
                      evidence=EvidenceIntegrity.REJECTED,
                      publication=PublicationEligibility.BLOCKED,
                      qualification=QualificationStatus.REVOKED,
                      verified_evidence=None)
        self.assertEqual(violations(r), [])


class TestIllegalCombinations(unittest.TestCase):
    def test_evaluator_error_plus_correct_rejected(self):
        self.assertTrue(violations(ok_result(
            evaluation_status=EvaluationStatus.EVALUATOR_ERROR,
            parser_status=ParserStatus.PARSER_SOFTWARE_ERROR,
            semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
            publication=PublicationEligibility.BLOCKED)) or
            violations(ok_result(
                evaluation_status=EvaluationStatus.EVALUATOR_ERROR)))

    def test_replay_error_plus_incorrect_rejected(self):
        self.assertTrue(violations(ok_result(
            evaluation_status=EvaluationStatus.REPLAY_ERROR,
            semantic_verdict=SemanticVerdict.INCORRECT)))

    def test_model_output_invalid_plus_correct_rejected(self):
        v = violations(ok_result(parser_status=ParserStatus.MODEL_OUTPUT_INVALID,
                                 semantic_verdict=SemanticVerdict.CORRECT))
        self.assertTrue(any("MODEL_OUTPUT_INVALID" in m for m in v))

    def test_not_evaluable_plus_eligible_publication_rejected(self):
        v = violations(ok_result(semantic_verdict=
                                 SemanticVerdict.NOT_EVALUABLE))
        self.assertTrue(any("NOT_EVALUABLE + ELIGIBLE" in m for m in v))

    def test_pending_plus_eligible_rejected(self):
        for q in (QualificationStatus.UNQUALIFIED,
                  QualificationStatus.REVOKED,
                  QualificationStatus.PENDING):
            self.assertTrue(any(q.value in m
                                for m in violations(ok_result(qualification=q))),
                            q)

    def test_business_pass_requires_world_safety_and_pipeline(self):
        for over, frag in [
                (dict(business_world_valid=False), "business world"),
                (dict(business_world_valid=None), "business world"),
                (dict(safety_verdict=SafetyVerdict.NOT_VERIFIED),
                 "missing required safety verification"),
                (dict(evaluation_status=EvaluationStatus.EVALUATOR_ERROR,
                      parser_status=ParserStatus.PARSER_SOFTWARE_ERROR,
                      semantic_verdict=SemanticVerdict.NOT_EVALUABLE),
                 "non-VALID evaluation pipeline")]:
            kw = dict(business_verdict=BusinessVerdict.PASS,
                      business_world_valid=True)
            kw.update(over)
            self.assertTrue(any(frag in m for m in violations(ok_result(**kw))),
                            over)

    def test_safety_violation_never_business_pass_or_publication(self):
        r = ok_result(safety_verdict=SafetyVerdict.VIOLATION,
                      business_verdict=BusinessVerdict.PASS,
                      business_world_valid=True)
        self.assertTrue(any("VIOLATION + business PASS" in m
                            for m in violations(r)))
        r2 = ok_result(safety_verdict=SafetyVerdict.VIOLATION)
        self.assertTrue(any("VIOLATION + ELIGIBLE publication" in m
                            for m in violations(r2)))

    def test_canary_control_never_publication_eligible(self):
        r = ok_result(execution_status=ExecutionStatus.CANARY_CONTROL)
        self.assertTrue(any("canary" in m for m in violations(r)))
        r2 = ok_result(execution_status=ExecutionStatus.CANARY_CONTROL,
                       publication=PublicationEligibility.DIAGNOSTIC_ONLY)
        self.assertEqual(violations(r2), [])

    def test_not_run_or_blocked_cannot_be_qualified(self):
        for ex in (ExecutionStatus.NOT_RUN, ExecutionStatus.BLOCKED,
                   ExecutionStatus.PARTIAL):
            self.assertTrue(violations(ok_result(execution_status=ex)), ex)

    def test_evidence_invalid_marker_blocks_qualified_verdict(self):
        self.assertTrue(violations(ok_result(
            evidence_invalid_reason="EVIDENCE_INCONSISTENT_STAGE2_TOOL")))

    def test_verified_without_envelope_rejected(self):
        v = violations(ok_result(verified_evidence=None))
        self.assertTrue(any("without a VerifiedEvidence envelope" in m
                            for m in v))

    def test_envelope_provenance_mismatch_rejected(self):
        other = verify_evidence(dict(PROV, trial_id="other"),
                                artifact_sha256_computed=SHA,
                                artifact_sha256_expected=SHA,
                                schema_validated=True,
                                trial_identity_match=True)
        v = violations(ok_result(verified_evidence=other))
        self.assertTrue(any("contradicts verified identity" in m for m in v))

    def test_decisive_verdict_requires_verified_evidence(self):
        r = ok_result(evidence=EvidenceIntegrity.UNVERIFIED,
                      verified_evidence=None)
        self.assertTrue(any("requires VERIFIED evidence" in m
                            for m in violations(r)))

    def test_validator_raises(self):
        with self.assertRaises(ContractViolationError):
            from eval_assurance.contracts import validate_result
            validate_result(ok_result(
                evaluation_status=EvaluationStatus.EVALUATOR_ERROR))


class TestStrictRuntimeTypes(unittest.TestCase):
    def test_enum_string_substitution_rejected_at_construction(self):
        good = dict(execution_status=ExecutionStatus.EXECUTED,
                    evaluation_status=EvaluationStatus.VALID,
                    parser_status=ParserStatus.PARSE_OK,
                    semantic_verdict=SemanticVerdict.CORRECT)
        for field in ("execution_status", "evaluation_status",
                      "parser_status", "semantic_verdict"):
            for bad in ("EXECUTED", 1, None):
                with self.assertRaises(ContractTypeError, msg=(field, bad)):
                    EvaluationResult(**{**good, field: bad})

    def test_boolean_fields_reject_non_bool(self):
        good = dict(execution_status=ExecutionStatus.EXECUTED,
                    evaluation_status=EvaluationStatus.VALID,
                    parser_status=ParserStatus.PARSE_OK,
                    semantic_verdict=SemanticVerdict.CORRECT)
        for bad in ("true", 1, None, []):
            with self.assertRaises(ContractTypeError):
                EvaluationResult(**{**good, "oracle_disagreement": bad})

    def test_evaluated_rejects_non_bool_semantic(self):
        for bad in ("True", "False", 1, 0, None, [], "PASS"):
            with self.assertRaises(ContractTypeError, msg=bad):
                EvaluationResult.evaluated(semantic=bad)

    def test_evidence_defaults_to_unverified(self):
        r = EvaluationResult.evaluated(semantic=True, provenance=PROV)
        self.assertIs(r.evidence, EvidenceIntegrity.UNVERIFIED)


class TestEligibilityAuthorities(unittest.TestCase):
    def test_diagnostic_eligibility_ignores_qualification(self):
        for q in (QualificationStatus.REVOKED, QualificationStatus.UNQUALIFIED,
                  QualificationStatus.PENDING):
            self.assertTrue(eligible_for_diagnostics(
                ok_result(qualification=q)).eligible, q)

    def test_formal_eligibility_blocks_revoked_records(self):
        dec = eligible_for_semantic_statistics(
            ok_result(qualification=QualificationStatus.REVOKED),
            authority_store())
        self.assertFalse(dec.eligible)
        self.assertTrue(any("REVOKED" in r for r in dec.reasons))

    def test_certificate_is_the_formal_authority_not_the_enum(self):
        # UNQUALIFIED/PENDING enums alone qualify nothing — but with a valid
        # certificate actually covering the scope+identity, the record is
        # formal-eligible (the store is the authority per EA-D01).
        for q in (QualificationStatus.UNQUALIFIED,
                  QualificationStatus.PENDING):
            self.assertTrue(eligible_for_semantic_statistics(
                ok_result(qualification=q), authority_store()).eligible, q)
        # ...and without a certificate every enum fails closed:
        for q in (QualificationStatus.QUALIFIED,
                  QualificationStatus.UNQUALIFIED,
                  QualificationStatus.PENDING):
            self.assertFalse(eligible_for_semantic_statistics(
                ok_result(qualification=q)).eligible, q)

    def test_formal_eligibility_fails_closed_without_store(self):
        dec = eligible_for_semantic_statistics(ok_result())
        self.assertFalse(dec.eligible)
        self.assertIn("fail_closed: no certificate store provided",
                      dec.reasons)

    def test_formal_eligibility_with_matching_certificate(self):
        dec = eligible_for_semantic_statistics(ok_result(), authority_store())
        self.assertTrue(dec.eligible, dec.reasons)
        self.assertTrue(eligible_for_formal_publication(
            ok_result(), authority_store()).eligible)
        self.assertTrue(eligible_for_reward(
            ok_result(), authority_store()).eligible)

    def test_certificate_identity_mismatch_fails_closed(self):
        store = authority_store(scopes=("semantic",),
                                dataset_id="OTHER-dataset")
        dec = eligible_for_semantic_statistics(ok_result(), store)
        self.assertFalse(dec.eligible)
        self.assertTrue(any("no valid certificate" in r for r in dec.reasons))

    def test_untrusted_caller_store_never_authorizes(self):
        store = CertificateStore()      # arbitrary caller-created store
        dec = eligible_for_semantic_statistics(ok_result(), store)
        self.assertFalse(dec.eligible)
        self.assertTrue(any("untrusted certificate store" in r
                            for r in dec.reasons))

    def test_revoked_certificate_blocks_formal_eligibility(self):
        store = authority_store(scopes=("semantic",))
        cert = store.snapshot().certificates[0]
        self.assertTrue(eligible_for_semantic_statistics(
            ok_result(), store).eligible)
        store.revoke(cert.certificate_id, reason="test revocation")
        dec = eligible_for_semantic_statistics(ok_result(), store)
        self.assertFalse(dec.eligible)
        self.assertTrue(any("no valid certificate" in r for r in dec.reasons))

    def test_business_eligibility_requires_world_and_safety(self):
        r = ok_result(business_verdict=BusinessVerdict.PASS,
                      business_world_valid=True,
                      safety_verdict=SafetyVerdict.SAFE)
        self.assertTrue(eligible_for_business_statistics(
            r, authority_store()).eligible)
        r2 = ok_result(business_verdict=BusinessVerdict.PASS,
                       business_world_valid=True,
                       safety_verdict=SafetyVerdict.NOT_VERIFIED)
        dec = eligible_for_business_statistics(r2, authority_store())
        self.assertFalse(dec.eligible)

    def test_reward_blocked_for_safety_violation(self):
        r = ok_result(safety_verdict=SafetyVerdict.VIOLATION,
                      publication=PublicationEligibility.DIAGNOSTIC_ONLY)
        dec = eligible_for_reward(r, authority_store())
        self.assertFalse(dec.eligible)
        self.assertTrue(any("safety" in x for x in dec.reasons))

    def test_every_gate_flipped_blocks_semantic_eligibility(self):
        flips = [
            ("execution", dict(execution_status=ExecutionStatus.CANARY_CONTROL,
                               publication=PublicationEligibility.DIAGNOSTIC_ONLY)),
            ("pipeline", dict(evaluation_status=EvaluationStatus.ARTIFACT_ERROR,
                              semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
                              publication=PublicationEligibility.BLOCKED)),
            ("evidence", dict(evidence=EvidenceIntegrity.REJECTED,
                              semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
                              publication=PublicationEligibility.BLOCKED)),
            ("marker", dict(evidence_invalid_reason="x",
                            semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
                            publication=PublicationEligibility.BLOCKED)),
            ("evaluator", dict(evaluator_status=EvaluatorStatus.ERROR,
                               semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
                               evaluation_status=EvaluationStatus.EVALUATOR_ERROR,
                               publication=PublicationEligibility.BLOCKED)),
            ("disagreement", dict(oracle_disagreement=True,
                                  semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
                                  evaluation_status=EvaluationStatus.ORACLE_DISAGREEMENT,
                                  publication=PublicationEligibility.BLOCKED)),
            ("verdict", dict(semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
                             publication=PublicationEligibility.BLOCKED)),
            ("provenance", dict(provenance={})),
            ("envelope", dict(verified_evidence=None,
                              evidence=EvidenceIntegrity.UNVERIFIED)),
        ]
        for name, over in flips:
            self.assertFalse(eligible_for_semantic_statistics(
                ok_result(**over)).eligible, name)


if __name__ == "__main__":
    unittest.main()
