"""EA02-R EA-D05 / Wave-BC EA-R03+EA-R04 — the mandatory formal Analyzer
boundary, hardened, including the EA00 injected-corruption regression run
against the ACTUAL aggregation entry point (aggregate_semantic).

Regression contract (hardened):
- sealed corrected corpus: 870 genuine successes / 2,184 evaluable rows;
- two injected corruptions (replay exception as False; causally
  inconsistent two-stage as True) are classified NOT_EVALUABLE-critical and
  BLOCK formal publication of the contaminated scope;
- the 871/2186 headline is structurally unreachable;
- formal publication requires an authority-issued certificate, a complete
  planned roster (or an explicitly declared partial scope), and survives
  the publication-time qualification recheck;
- the sealed corpus file is unchanged (INV07)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance.adapters.n02rr import n02rr_result_from_replay
from eval_assurance.contracts import (EvidenceIntegrity, SemanticVerdict,
                                      verify_evidence)
from eval_assurance.evidence import issue_verification_receipt
from eval_assurance.qualification import QualificationAuthority
from eval_assurance.statistics import aggregate_semantic, publish_report

SEALED = ROOT / "evidence" / "IJNANO" / "N02RR" / "trial_reconciliation.jsonl"

PROV = {"experiment_id": "e1", "trial_id": "t1", "task_id": "k1",
        "model": "S1", "dataset_id": "d1", "parser_version": "p1",
        "evaluator_version": "v1"}
SHA = "a" * 64
N02RR_IDS = dict(dataset_id="ij_nano.n02r.suite",
                 parser_version="arms_v2.parse_response",
                 evaluator_version="n02r.scorer/contract-v2")


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
        provenance=dict(PROV))
    base.update(over)
    base["provenance"] = dict(base["provenance"])
    if base.get("evidence") is EvidenceIntegrity.VERIFIED \
            and base.get("verified_evidence") is None:
        # per-record envelope bound to THIS record's provenance identity
        base["verified_evidence"] = verify_evidence(
            base["provenance"], artifact_sha256_computed=SHA,
            artifact_sha256_expected=SHA, schema_validated=True,
            trial_identity_match=True)
    return EvaluationResult(**base)


def authority_store(scopes=("semantic",),
                    dataset_id="d1", parser_version="p1",
                    evaluator_version="v1"):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="eaval-qual-"))

    def f(name, content):
        p = tmp / name
        p.write_text(content, encoding="utf-8")
        return p
    files = {n: f(n, f"implementation {n} v1") for n in
             ("dataset", "task_contract", "parser", "interpreter",
              "evaluator", "oracle", "witnesses", "mutation")}
    auth = QualificationAuthority()
    kw = dict(dataset_id=dataset_id, parser_version=parser_version,
              evaluator_version=evaluator_version)
    store = None
    for scope in scopes:
        store = auth.issue_qualification(
            scope=scope, reference_evaluator_version="ref-independent-1",
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
            store=store, **kw)
    return store


def load_sealed_records():
    """Sealed corpus rows -> typed records with receipts computed from the
    ACTUAL artifact bytes (class-B verification)."""
    records = []
    for line in SEALED.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        c = row["corrected"]
        rec = {
            "trial_id": row["trial_id"],
            "experiment_id": "ec5b95357e960f99", "model": row["model"],
            "task_id": row["task_id"], "http_ok": True, "http_error": None,
            "semantic_correct": c["verdict"], "replay_error": None,
            "p7s_reconstruction": c.get("p7s"),
        }
        se = row.get("source_evidence") or {}
        receipt = None
        if se.get("sha256_verified"):
            artifact = ROOT / se["artifact"]
            receipt = issue_verification_receipt(
                artifact, expected_sha256=se["sha256_recorded"],
                trial_id=row["trial_id"],
                experiment_id="ec5b95357e960f99")
        records.append(n02rr_result_from_replay(
            rec, verification_receipt=receipt))
    return records


def injected_records():
    """The two EA00 corruption shapes (no real artifacts -> evidence stays
    unverified, which is exactly their problem)."""
    r1 = n02rr_result_from_replay({
        "trial_id": "SYNTH-EA00-REPLAY-ERROR",
        "experiment_id": "ec5b95357e960f99", "model": "S1", "task_id": "TS01",
        "http_ok": True, "http_error": None, "semantic_correct": False,
        "replay_error": "RuntimeError: synthetic evaluator crash (EA00 R1)",
        "p7s_reconstruction": None})
    r2 = n02rr_result_from_replay({
        "trial_id": "SYNTH-EA00-EVIDENCE-INCONSISTENT",
        "experiment_id": "ec5b95357e960f99", "model": "S1", "task_id": "TS01",
        "http_ok": True, "http_error": None, "semantic_correct": True,
        "replay_error": None,
        "p7s_reconstruction": {"stage2_executed": True,
                               "stage2_payload_matches_selection": False}})
    return [r1, r2]


class TestBoundarySmall(unittest.TestCase):
    def test_boolean_dict_input_quarantined_and_blocks_publication(self):
        rep = aggregate_semantic([True, False, {"semantic_correct": True}])
        self.assertEqual(rep.quarantined, 3)
        self.assertEqual(rep.formal_publication, "BLOCKED_QUARANTINED")

    def test_counts_with_certificate(self):
        from eval_assurance.contracts import PublicationEligibility
        records = [
            typed_record(provenance=dict(PROV, trial_id="t1")),
            typed_record(provenance=dict(PROV, trial_id="t2"),
                         semantic_verdict=SemanticVerdict.INCORRECT),
            typed_record(provenance=dict(PROV, trial_id="t3"),
                         semantic_verdict=SemanticVerdict.NOT_APPLICABLE,
                         publication=PublicationEligibility.DIAGNOSTIC_ONLY)]
        store = authority_store()
        rep = aggregate_semantic(records, certificates=store,
                                 planned_roster=["t1", "t2", "t3"])
        self.assertEqual(rep.qualified_eligible, 2)
        self.assertEqual(rep.correct, 1)
        self.assertEqual(rep.incorrect, 1)
        self.assertEqual(rep.not_evaluable, 1)
        self.assertEqual(rep.formal_publication, "ALLOWED")

    def test_fail_closed_without_trusted_certificate(self):
        from eval_assurance.qualification import CertificateStore
        for store in (None, CertificateStore(),
                      CertificateStore(trusted=True)):   # empty trusted
            rep = aggregate_semantic([typed_record()], certificates=store)
            self.assertEqual(rep.qualified_eligible, 0)
            self.assertEqual(rep.diagnostic_correct, 1)
            self.assertTrue(rep.formal_publication.startswith("BLOCKED"),
                            rep.formal_publication)

    def test_unrelated_or_revoked_only_store_blocks(self):
        from eval_assurance.qualification import CertificateStore
        unrelated = authority_store(dataset_id="OTHER-dataset")
        revoked = authority_store()
        cert = revoked.snapshot().certificates[0]
        revoked.revoke(cert.certificate_id, reason="probe")
        for store in (unrelated, revoked):
            rep = aggregate_semantic([typed_record()], certificates=store)
            self.assertEqual(rep.formal_publication,
                             "BLOCKED_SCOPE_NOT_CERTIFIED")

    def test_duplicate_trial_ids_quarantined(self):
        store = authority_store()
        rep = aggregate_semantic([typed_record(), typed_record()],
                                 certificates=store, planned_roster=["t1"])
        self.assertEqual(rep.quarantined, 1)
        self.assertEqual(rep.duplicate_trial_ids, ["t1"])
        self.assertEqual(rep.qualified_eligible, 1)
        self.assertEqual(rep.formal_publication, "BLOCKED_QUARANTINED")

    def test_missing_roster_slots_block_or_partial(self):
        store = authority_store()
        rep = aggregate_semantic([typed_record()], certificates=store,
                                 planned_roster=["t1", "t2", "t3"])
        self.assertEqual(rep.formal_publication, "BLOCKED_INCOMPLETE_ROSTER")
        self.assertEqual(rep.missing_slots, ["t2", "t3"])
        rep2 = aggregate_semantic([typed_record()], certificates=store,
                                  planned_roster=["t1", "t2", "t3"],
                                  partial_scope_allowed=True)
        self.assertEqual(rep2.formal_publication, "ALLOWED_PARTIAL")
        self.assertEqual(rep2.scope_declaration, "partial")

    def test_critical_not_evaluable_blocks_publication(self):
        from eval_assurance.contracts import (EvaluationStatus,
                                              ParserStatus,
                                              PublicationEligibility)
        crit = typed_record(
            provenance=dict(PROV, trial_id="t2"),
            semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
            evaluation_status=EvaluationStatus.ARTIFACT_ERROR,
            parser_status=ParserStatus.PARSER_SOFTWARE_ERROR,
            evidence=EvidenceIntegrity.REJECTED,
            publication=PublicationEligibility.BLOCKED,
            verified_evidence=None)
        rep = aggregate_semantic([typed_record(), crit],
                                 certificates=authority_store(),
                                 planned_roster=["t1", "t2"])
        self.assertEqual(rep.critical_not_evaluable, 1)
        self.assertEqual(rep.formal_publication,
                         "BLOCKED_CRITICAL_NOT_EVALUABLE")

    def test_canary_never_counted(self):
        from eval_assurance.contracts import (ExecutionStatus,
                                              PublicationEligibility)
        rep = aggregate_semantic([typed_record(
            execution_status=ExecutionStatus.CANARY_CONTROL,
            publication=PublicationEligibility.DIAGNOSTIC_ONLY)],
            certificates=authority_store())
        self.assertEqual(rep.canary_controls, 1)
        self.assertEqual(rep.qualified_eligible, 0)

    def test_publish_report_rechecks_qualification(self):
        # variant 1: stale snapshot -> generation drift detected
        store = authority_store()
        rep = aggregate_semantic([typed_record()], certificates=store,
                                 planned_roster=["t1"])
        snap = store.snapshot()
        cert_id = next(iter(rep.certificate_ids_used))
        store.revoke(cert_id, reason="between aggregation and publication")
        with self.assertRaises(RuntimeError):
            publish_report(rep, store, snap)
        self.assertEqual(rep.formal_publication,
                         "BLOCKED_QUALIFICATION_CHANGED")
        # variant 2 (separate store): fresh snapshot, revoked certificate
        store2 = authority_store()
        rep2 = aggregate_semantic([typed_record()], certificates=store2,
                                  planned_roster=["t1"])
        cert_id2 = next(iter(rep2.certificate_ids_used))
        store2.revoke(cert_id2, reason="before publication")
        with self.assertRaises(RuntimeError):
            publish_report(rep2, store2)    # fresh snapshot, cert revoked
        self.assertEqual(rep2.formal_publication,
                         "BLOCKED_QUALIFICATION_REVOKED")


@unittest.skipUnless(SEALED.exists(), "sealed N02RR corpus not present")
class TestEA00CorruptionRegression(unittest.TestCase):
    def test_injected_corruption_contained_at_aggregation_entry(self):
        sealed_sha_before = hashlib.sha256(
            SEALED.read_bytes()).hexdigest()
        sealed = load_sealed_records()
        injected = injected_records()
        records = sealed + injected
        self.assertEqual(len(records), 2186)

        # phase 1: no trusted certificate -> diagnostic truth only
        rep = aggregate_semantic(records)
        self.assertEqual(rep.diagnostic_correct, 870,
                         "870 genuine successes must be preserved")
        self.assertEqual(rep.not_evaluable, 2)
        self.assertEqual(rep.critical_not_evaluable, 2)
        self.assertEqual(rep.quarantined, 0)
        self.assertEqual(rep.formal_publication,
                         "BLOCKED_NO_TRUSTED_CERTIFICATE")

        # phase 2: certificate bound BUT the two injections are unresolved
        # critical evidence faults -> publication of this scope is BLOCKED
        store = authority_store(**N02RR_IDS)
        roster = [r.provenance["trial_id"] for r in sealed]
        rep2 = aggregate_semantic(records, certificates=store,
                                  planned_roster=roster + [
                                      "SYNTH-EA00-REPLAY-ERROR",
                                      "SYNTH-EA00-EVIDENCE-INCONSISTENT"])
        self.assertEqual(rep2.diagnostic_correct, 870)
        self.assertEqual(rep2.qualified_eligible, 2184)
        self.assertEqual(rep2.correct, 870)
        self.assertEqual(rep2.not_evaluable, 2)
        self.assertNotEqual((rep2.correct, rep2.total_records), (871, 2186))
        self.assertEqual(rep2.formal_publication,
                         "BLOCKED_CRITICAL_NOT_EVALUABLE")

        # phase 3: sealed scope only (the injections are not planned slots
        # of the sealed experiment) -> full ALLOWED with exact roster
        # (certificate already bound to the N02RR identity)
        rep3 = aggregate_semantic(sealed, certificates=store,
                                  planned_roster=roster)
        self.assertEqual(rep3.qualified_eligible, 2184)
        self.assertEqual(rep3.correct, 870)
        self.assertEqual(rep3.conditional_semantic_accuracy,
                         round(870 / 2184, 4))
        self.assertEqual(rep3.evaluation_coverage, 1.0)
        self.assertEqual(rep3.formal_publication, "ALLOWED")
        publish_report(rep3, store)      # publication-time recheck passes

        # partial-scope honesty: one planned slot missing
        rep4 = aggregate_semantic(sealed[:-1], certificates=store,
                                  planned_roster=roster)
        self.assertEqual(rep4.formal_publication, "BLOCKED_INCOMPLETE_ROSTER")
        rep5 = aggregate_semantic(sealed[:-1], certificates=store,
                                  planned_roster=roster,
                                  partial_scope_allowed=True)
        self.assertEqual(rep5.formal_publication, "ALLOWED_PARTIAL")
        self.assertEqual(rep5.scope_declaration, "partial")

        # sealed evidence untouched (INV07)
        self.assertEqual(hashlib.sha256(SEALED.read_bytes()).hexdigest(),
                         sealed_sha_before)


if __name__ == "__main__":
    unittest.main()
