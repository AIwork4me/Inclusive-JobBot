"""Compatibility contract conformance + runner authorization tests
(N03 critical path coordination order)."""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance.compat import (CONTRACT_VERSION, REGISTRY,  # noqa: E402
                                   RunnerAuthorization, authorize_runner,
                                   verify_contract)
from eval_assurance.compat.contract import N03_BATCH_A
from eval_assurance.contracts import (EvidenceIntegrity, SemanticVerdict,  # noqa: E402
                                      verify_evidence)
from eval_assurance.qualification import QualificationAuthority  # noqa: E402
from eval_assurance.statistics import aggregate_semantic  # noqa: E402

PROV = {"experiment_id": "e1", "trial_id": "t1", "task_id": "k1",
        "model": "S1", "dataset_id": "d1", "parser_version": "p1",
        "evaluator_version": "v1"}
SHA = "a" * 64


def typed_record(**over):
    from eval_assurance.contracts import (EvaluationResult,
                                          EvaluationStatus,
                                          ExecutionStatus, ParserStatus,
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


def authority_store():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="compat-"))

    def f(name):
        p = tmp / f"{name}.bin"
        p.write_text(f"implementation {name} v1", encoding="utf-8")
        return p
    files = {n: f(n) for n in ("dataset", "task_contract", "parser",
                               "interpreter", "evaluator", "oracle",
                               "witnesses", "mutation")}
    return QualificationAuthority().issue_qualification(
        scope="semantic", dataset_id="d1", parser_version="p1",
        evaluator_version="v1",
        reference_evaluator_version="ref-independent-1",
        dataset_file=files["dataset"],
        task_contract_file=files["task_contract"],
        parser_file=files["parser"], interpreter_file=files["interpreter"],
        evaluator_file=files["evaluator"],
        reference_oracle_file=files["oracle"],
        witness_suite_file=files["witnesses"],
        mutation_report_file=files["mutation"],
        evidence_files=[files["witnesses"], files["mutation"]],
        replay_contract="replay-v1", protocol="proto-v1")


class TestContractConformance(unittest.TestCase):
    def test_every_declared_section_present(self):
        required = {"task_schemas", "parser_interfaces", "oracle_interfaces",
                    "evidence_envelopes", "qualification_issuance",
                    "certificate_lifecycle", "runner_authorization",
                    "canary_integration", "quarantine_recovery",
                    "qualified_aggregation"}
        self.assertEqual({i.section for i in REGISTRY}, required)

    def test_contract_conformant(self):
        self.assertEqual(verify_contract(), [])

    def test_planned_entries_are_honest(self):
        planned = [i for i in REGISTRY if i.status == "PLANNED"]
        self.assertTrue(planned)          # oracle + canary not yet built
        self.assertTrue(all("eval_assurance.reference" in i.module
                            or "eval_assurance.canary" in i.module
                            for i in planned))

    def test_evidence_artifact_exists_and_is_current(self):
        art = ROOT / "evidence" / "IJEVAL" / "COMPAT" / \
            f"contract_v{CONTRACT_VERSION}.json"
        self.assertTrue(art.exists(),
                        "run scripts/ij_eval_assurance/compat_contract.py")
        import json
        payload = json.loads(art.read_text(encoding="utf-8"))
        self.assertEqual(payload["contract_version"], CONTRACT_VERSION)
        self.assertEqual(len(payload["interfaces"]), len(REGISTRY))
        for i in payload["interfaces"]:
            if i["status"] == "IMPLEMENTED":
                self.assertTrue(i["implementation_sha256"], i["name"])

    def test_n03_batch_a_declaration(self):
        self.assertEqual(N03_BATCH_A["primitives"], "C01-C08")
        self.assertEqual(N03_BATCH_A["development_cases"], 160)
        self.assertEqual(N03_BATCH_A["protected_confirmation_cases"], 80)
        self.assertEqual(N03_BATCH_A["intake_status"], "VERIFIED")


class TestRunnerAuthorization(unittest.TestCase):
    def test_authorized_scope_produces_machine_readable_authorization(self):
        store = authority_store()
        rep = aggregate_semantic(
            [typed_record(),
             typed_record(provenance=dict(PROV, trial_id="t2"),
                          semantic_verdict=SemanticVerdict.INCORRECT)],
            certificates=store, planned_roster=["t1", "t2"])
        self.assertEqual(rep.formal_publication, "ALLOWED")
        auth = authorize_runner(rep, store)
        self.assertTrue(auth.allowed)
        self.assertEqual(auth.scope, "semantic")
        self.assertEqual(auth.qualified_eligible, 2)
        self.assertEqual(auth.correct, 1)
        self.assertTrue(auth.certificate_ids)
        self.assertTrue(auth.snapshot_checksum)
        payload = auth.to_json()
        self.assertIn('"allowed": true', payload)
        self.assertIn("authorization_checksum", payload)

    def test_blocked_scope_not_authorized(self):
        store = authority_store()
        rep = aggregate_semantic([typed_record()], certificates=store,
                                 planned_roster=["t1", "t2"])  # missing t2
        auth = authorize_runner(rep, store)
        self.assertFalse(auth.allowed)
        self.assertTrue(auth.reasons)
        # and partial scope requires explicit acceptance
        rep2 = aggregate_semantic([typed_record()], certificates=store,
                                  planned_roster=["t1", "t2"],
                                  partial_scope_allowed=True)
        self.assertFalse(authorize_runner(rep2, store).allowed)
        self.assertTrue(authorize_runner(rep2, store,
                                         accept_partial=True).allowed)

    def test_revocation_between_aggregation_and_authorization(self):
        store = authority_store()
        rep = aggregate_semantic([typed_record()], certificates=store,
                                 planned_roster=["t1"])
        snap = store.snapshot()
        cert_id = next(iter(rep.certificate_ids_used))
        store.revoke(cert_id, reason="before authorization")
        auth = authorize_runner(rep, store, snap)
        self.assertFalse(auth.allowed)
        self.assertTrue(any("recheck failed" in r for r in auth.reasons))

    def test_direct_construction_blocked(self):
        with self.assertRaises(PermissionError):
            RunnerAuthorization(schema="1", scope="s", allowed=True,
                                verdict="ALLOWED", scope_declaration="full",
                                qualified_eligible=1, correct=1,
                                planned_slots=1, evaluation_coverage=1.0,
                                conditional_semantic_accuracy=1.0,
                                certificate_ids=["x"],
                                certificate_digests=[("x", "d")],
                                snapshot_checksum="c", reasons=(),
                                authorization_checksum="z")


if __name__ == "__main__":
    unittest.main()
