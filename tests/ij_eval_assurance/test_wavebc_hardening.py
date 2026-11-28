"""Wave B/C hardening green battery — every EA-R01..EA-R04 red observation
from evidence/IJEVAL/EABC/red_reproduction.json must be closed here."""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance.contracts import (EvaluationResult, EvaluationStatus,  # noqa: E402
                                      EvidenceIntegrity, ExecutionStatus,
                                      ParserStatus, PublicationEligibility,
                                      QualificationStatus, SemanticVerdict,
                                      VerifiedEvidence,
                                      eligible_for_semantic_statistics,
                                      verify_evidence)
from eval_assurance.evidence import (VerificationReceipt,  # noqa: E402
                                     issue_verification_receipt,
                                     sha256_of_file, validate_receipt_for)
from eval_assurance.qualification import (CertificateError,  # noqa: E402
                                          CertificateStore,
                                          QualificationAuthority,
                                          QualificationCertificate,
                                          validate_certificate)
from eval_assurance.statistics import aggregate_semantic, publish_report  # noqa: E402

PROV = {"experiment_id": "e1", "trial_id": "t1", "task_id": "k1",
        "model": "S1", "dataset_id": "d1", "parser_version": "p1",
        "evaluator_version": "v1"}
SHA = "a" * 64


def typed_record(**over):
    base = dict(
        execution_status=ExecutionStatus.EXECUTED,
        evaluation_status=EvaluationStatus.VALID,
        parser_status=ParserStatus.PARSE_OK,
        semantic_verdict=SemanticVerdict.CORRECT,
        qualification=QualificationStatus.QUALIFIED,
        publication=PublicationEligibility.ELIGIBLE,
        evidence=EvidenceIntegrity.VERIFIED,
        provenance=dict(PROV))
    base.update(over)
    base["provenance"] = dict(base["provenance"])
    if base.get("evidence") is EvidenceIntegrity.VERIFIED \
            and base.get("verified_evidence") is None:
        base["verified_evidence"] = verify_evidence(
            base["provenance"], artifact_sha256_computed=SHA,
            artifact_sha256_expected=SHA, schema_validated=True,
            trial_identity_match=True)
    return EvaluationResult(**base)


def impl_files(tmp: pathlib.Path):
    files = {}
    for name in ("dataset", "task_contract", "parser", "interpreter",
                 "evaluator", "oracle", "witnesses", "mutation"):
        p = tmp / f"{name}.bin"
        p.write_text(f"implementation {name} v1", encoding="utf-8")
        files[name] = p
    return files


def issue_into(store, files, *, scope="semantic", dataset_id="d1",
               parser_version="p1", evaluator_version="v1",
               reference_evaluator_version="ref-independent-1",
               requalified=False, same_oracle=False):
    auth = QualificationAuthority()
    return auth.issue_qualification(
        scope=scope, dataset_id=dataset_id, parser_version=parser_version,
        evaluator_version=evaluator_version,
        reference_evaluator_version=reference_evaluator_version,
        dataset_file=files["dataset"],
        task_contract_file=files["task_contract"],
        parser_file=files["parser"], interpreter_file=files["interpreter"],
        evaluator_file=files["evaluator"],
        reference_oracle_file=(files["evaluator"] if same_oracle
                               else files["oracle"]),
        witness_suite_file=files["witnesses"],
        mutation_report_file=files["mutation"],
        evidence_files=[files["witnesses"], files["mutation"]],
        replay_contract="replay-v1", protocol="proto-v1",
        requalified=requalified, store=store)


class TestEAR01TrustedIssuance(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="ear01-"))
        self.files = impl_files(self.tmp)

    def test_arbitrary_store_never_authorizes(self):
        store = CertificateStore()          # caller-created
        dec = eligible_for_semantic_statistics(typed_record(), store)
        self.assertFalse(dec.eligible)
        self.assertTrue(any("untrusted" in r for r in dec.reasons))

    def test_issuance_requires_gate_evidence(self):
        auth = QualificationAuthority()
        with self.assertRaises(CertificateError):    # no evidence files
            auth.issue_qualification(
                scope="semantic", dataset_id="d1", parser_version="p1",
                evaluator_version="v1", reference_evaluator_version="r",
                dataset_file=self.files["dataset"],
                task_contract_file=self.files["task_contract"],
                parser_file=self.files["parser"],
                interpreter_file=self.files["interpreter"],
                evaluator_file=self.files["evaluator"],
                reference_oracle_file=self.files["oracle"],
                witness_suite_file=self.files["witnesses"],
                mutation_report_file=self.files["mutation"],
                evidence_files=[], replay_contract="r", protocol="p")
        ev = self.tmp / "empty.bin"
        ev.write_text("", encoding="utf-8")
        with self.assertRaises(CertificateError):    # empty evidence file
            issue_into(None, {**self.files, "witnesses": ev})

    def test_empty_reference_identity_rejected(self):
        with self.assertRaises(CertificateError):
            issue_into(None, self.files, reference_evaluator_version="")

    def test_reference_identical_to_production_rejected(self):
        with self.assertRaises(CertificateError):
            issue_into(None, self.files, same_oracle=True)

    def test_authority_certificate_binds_actual_digests(self):
        store = issue_into(None, self.files)
        cert = store.snapshot().certificates[0]
        for name in ("dataset_sha256", "task_contract_sha256",
                     "parser_sha256", "interpreter_sha256",
                     "evaluator_sha256", "reference_oracle_sha256",
                     "witness_suite_sha256", "mutation_sha256"):
            self.assertTrue(getattr(cert, name), name)
        self.assertEqual(cert.dataset_sha256, sha256_of_file(
            self.files["dataset"]))
        self.assertTrue(cert.evidence_refs)
        self.assertNotEqual(cert.evaluator_sha256, cert.reference_oracle_sha256)
        # and the authority store DOES authorize formal eligibility
        self.assertTrue(eligible_for_semantic_statistics(
            typed_record(), store).eligible)

    def test_incomplete_certificate_rejected_by_validator(self):
        cert = QualificationCertificate(
            scope="s", dataset_id="d", parser_version="p",
            evaluator_version="e", reference_evaluator_version="",
            issued_utc="now", certificate_id="x")
        with self.assertRaises(CertificateError):
            validate_certificate(cert)
        bad = QualificationCertificate(
            scope="s", dataset_id="d", parser_version="p",
            evaluator_version="e", reference_evaluator_version="r",
            issued_utc="now", certificate_id="x",
            dataset_sha256="not-a-digest",
            evidence_refs=("evidence/exists.json",))
        with self.assertRaises(CertificateError):
            validate_certificate(bad)


class TestEAR02EvidenceProvenance(unittest.TestCase):
    def test_non_hash_and_short_digests_rejected(self):
        for bad in ("banana", "a" * 63, "a" * 65, "", "G" * 64 + "!"):
            with self.assertRaises(ValueError, msg=bad):
                verify_evidence(PROV, artifact_sha256_computed=bad,
                                artifact_sha256_expected=bad,
                                schema_validated=True,
                                trial_identity_match=True)

    def test_uppercase_hex_digests_normalized(self):
        env = verify_evidence(PROV, artifact_sha256_computed=SHA.upper(),
                              artifact_sha256_expected=SHA.upper(),
                              schema_validated=True,
                              trial_identity_match=True)
        self.assertEqual(env.artifact_sha256, SHA)

    def test_direct_envelope_construction_blocked(self):
        with self.assertRaises(PermissionError):
            VerifiedEvidence(schema_version="1.0.0", verified_keys=tuple(PROV), identity=dict(PROV), artifact_sha256=SHA, verification_checks={})

    def test_envelope_mappings_immutable(self):
        env = verify_evidence(PROV, artifact_sha256_computed=SHA,
                              artifact_sha256_expected=SHA,
                              schema_validated=True,
                              trial_identity_match=True)
        with self.assertRaises(TypeError):
            env.identity["trial_id"] = "hacked"
        with self.assertRaises(TypeError):
            env.verification_checks["forged"] = True

    def test_receipt_verifies_actual_bytes(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="ear02-"))
        art = tmp / "artifact.json"
        art.write_bytes(b"actual bytes")
        receipt = issue_verification_receipt(
            art, expected_sha256=sha256_of_file(art),
            trial_id="t1", experiment_id="e1")
        self.assertIsInstance(receipt, VerificationReceipt)
        # forged expectation fails closed:
        with self.assertRaises(ValueError):
            issue_verification_receipt(
                art, expected_sha256=SHA, trial_id="t1", experiment_id="e1")
        # unreadable artifact fails closed:
        with self.assertRaises(Exception):
            issue_verification_receipt(
                tmp / "missing.json", expected_sha256=SHA,
                trial_id="t1", experiment_id="e1")

    def test_receipt_identity_binding(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="ear02-"))
        art = tmp / "artifact.json"
        art.write_bytes(b"bytes")
        receipt = issue_verification_receipt(
            art, expected_sha256=sha256_of_file(art),
            trial_id="t1", experiment_id="e1")
        with self.assertRaises(ValueError):   # wrong trial
            validate_receipt_for(receipt, trial_id="t2", experiment_id="e1")
        with self.assertRaises(ValueError):   # wrong experiment
            validate_receipt_for(receipt, trial_id="t1", experiment_id="e2")
        ok = validate_receipt_for(receipt, trial_id="t1", experiment_id="e1")
        self.assertIn("verification_receipt", ok.envelope_kwargs()["basis"])

    def test_direct_receipt_construction_blocked(self):
        with self.assertRaises(PermissionError):
            VerificationReceipt(schema_version="1.0.0", artifact_path="p", artifact_sha256=SHA, artifact_bytes=1, trial_id="t", experiment_id="e", verifier="v")


class TestEAR03PublicationBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="ear03-"))
        self.store = issue_into(None, impl_files(self.tmp))

    def test_untrusted_empty_unrelated_revoked_never_allowed(self):
        from eval_assurance.qualification import CertificateStore
        cases = [None, CertificateStore(), CertificateStore(trusted=True),
                 issue_into(None, impl_files(
                     pathlib.Path(tempfile.mkdtemp(prefix="ear03b-"))),
                     dataset_id="OTHER")]
        for store in cases:
            rep = aggregate_semantic([typed_record()], certificates=store,
                                     planned_roster=["t1"])
            self.assertTrue(rep.formal_publication.startswith("BLOCKED"),
                            (store, rep.formal_publication))
        revoked = issue_into(None, impl_files(
            pathlib.Path(tempfile.mkdtemp(prefix="ear03c-"))))
        cert = revoked.snapshot().certificates[0]
        revoked.revoke(cert.certificate_id, reason="t")
        rep = aggregate_semantic([typed_record()], certificates=revoked,
                                 planned_roster=["t1"])
        self.assertEqual(rep.formal_publication, "BLOCKED_SCOPE_NOT_CERTIFIED")

    def test_scope_enforcement(self):
        # semantic certificate does not authorize a business-scope report
        rep = aggregate_semantic([typed_record()], certificates=self.store,
                                 scope="business", planned_roster=["t1"])
        self.assertEqual(rep.formal_publication, "BLOCKED_SCOPE_NOT_CERTIFIED")

    def test_zero_qualified_rows_blocked(self):
        rep = aggregate_semantic([typed_record(
            provenance=dict(PROV, trial_id="t9"),
            semantic_verdict=SemanticVerdict.NOT_APPLICABLE,
            publication=PublicationEligibility.DIAGNOSTIC_ONLY)],
            certificates=self.store, planned_roster=["t9"])
        self.assertEqual(rep.formal_publication, "BLOCKED_NO_QUALIFIED_ROWS")

    def test_partial_never_claimed_as_full(self):
        rep = aggregate_semantic([typed_record()], certificates=self.store,
                                 planned_roster=["t1", "t2"],
                                 partial_scope_allowed=True)
        self.assertEqual(rep.formal_publication, "ALLOWED_PARTIAL")
        self.assertEqual(rep.scope_declaration, "partial")
        self.assertIn("partial", rep.headline() + rep.scope_declaration)


class TestEAR04RevocationTimeOfCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="ear04-"))
        self.files = impl_files(self.tmp)
        self.registry = self.tmp / "registry.json"
        self.store = issue_into(None, self.files)

    def test_registry_roundtrip_and_corruption_fail_closed(self):
        # persist via a trusted store, then reload and verify fail-closed
        auth_store = CertificateStore(persist_to=self.registry, trusted=True)
        issue_into(auth_store, self.files)
        loaded = CertificateStore.load_registry(self.registry)
        self.assertTrue(loaded.trusted)
        corrupt = self.tmp / "corrupt.json"
        corrupt.write_text("{corrupt", encoding="utf-8")
        with self.assertRaises(CertificateError):
            CertificateStore.load_registry(corrupt)
        # tampered registry (valid JSON, broken checksum)
        raw = json.loads(self.registry.read_text(encoding="utf-8"))
        raw["certificates"][0]["dataset_id"] = "tampered"
        tampered = self.tmp / "tampered.json"
        tampered.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaises(CertificateError):
            CertificateStore.load_registry(tampered)

    def test_snapshot_currency_and_publication_recheck(self):
        rep = aggregate_semantic([typed_record()], certificates=self.store,
                                 planned_roster=["t1"])
        snap = self.store.snapshot()
        self.assertTrue(self.store.snapshot_is_current(snap))
        cert_id = next(iter(rep.certificate_ids_used))
        self.store.revoke(cert_id, reason="time-of-check test")
        self.assertFalse(self.store.snapshot_is_current(snap))
        with self.assertRaises(RuntimeError):
            publish_report(rep, self.store, snap)
        self.assertEqual(rep.formal_publication,
                         "BLOCKED_QUALIFICATION_CHANGED")

    def test_revoked_binding_requires_requalification_to_reissue(self):
        cert = self.store.snapshot().certificates[0]
        self.store.revoke(cert.certificate_id, reason="revoked")
        with self.assertRaises(CertificateError):
            issue_into(self.store, self.files)      # no requalified flag
        reissued = issue_into(self.store, self.files, requalified=True)
        self.assertTrue(reissued.trusted)

    def test_revocation_history_durable(self):
        cert = self.store.snapshot().certificates[0]
        self.store.revoke(cert.certificate_id, reason="audit trail")
        snap = self.store.snapshot()
        self.assertEqual(len(snap.revocations), 1)
        self.assertEqual(snap.revocations[0]["reason"], "audit trail")


if __name__ == "__main__":
    unittest.main()
