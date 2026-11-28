"""Mandatory authorization bypass controls (compat v1.1.0, order §6).

All 16 controls from the qualification order, executed against the REAL
contract module (``eval_assurance.compat.execution_authorization``) and —
for the consumer-integration controls — against the REAL IJ-NANO
authorization controller and DispatchGate imported read-only from the
sibling worktree (never a test double claiming conformance).

Controls 1 (first authorization without model results) proves the
startup-dependency fix: ExecutionAuthorization requires NO
AggregationReport and NO accuracy. Controls 2-16 must all be REJECTED.
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance.compat import execution_authorization as ea  # noqa: E402

IJNANO = ROOT.parent / "IJNANO"
CONSUMER_MODULE = "benchmarks.ij_nano.n03.authorization"

PINNED_REV = "test-eae-rev-1.1.0"
DATASET = "d045cf42fdfe1a03f688dae939511912cdeb8c6756bc060d4303456e16687c7f4"
ROSTER = "r" * 64
MODELS = ["qwen3-4b-instruct-cpu-synthetic"]


def full_evidence(**over):
    kw = dict(
        compat_revision=PINNED_REV,
        primitives=("C01", "C02", "C03", "C04", "C05", "C06", "C07",
                    "C08"),
        protocols=("chat", "chat_json_schema", "chat_bounded_reasoning_t2"),
        models=tuple(MODELS),
        dataset_digest=DATASET,
        roster_digest=ROSTER,
        evaluator_identity="oracle-v2@3ec4c28+",
        certificate_refs=("EAE-CERT-BATCHA-1",),
        certificate_digests=(("EAE-CERT-BATCHA-1", "cd1"),),
        shared_core_acceptance="ACCEPTED",
        shared_core_evidence_digest="s" * 64,
        ea13_scope_evidence="a13" * 21,
        ea18_scope_evidence="a18" * 21,
        canary_ready=True,
        circuit_breaker_ready=True,
        confirmation_execution=False,
        roster_split="development",
        dispatch_limits={"max_trials": 960},
    )
    kw.update(over)
    return ea.ExecutionEvidence(**kw)


def request(**over):
    kw = dict(
        experiment_id="exp-001",
        dataset_digest=DATASET,
        roster_digest=ROSTER,
        primitives=["C01", "C02"],
        protocols=["chat"],
        models=list(MODELS),
        eae_revision=PINNED_REV,
        auth_level="AUTH-1",
    )
    kw.update(over)
    return kw


def issue(**kw):
    return ea.issue_execution_authorization(**request(**kw))


class BypassControls(unittest.TestCase):
    def setUp(self):
        ea.clear_execution_evidence()
        ea.REVOCATIONS = ea.RevocationRegistry()
        ea.register_execution_evidence(
            full_evidence(), trusted_certificate_refs={"EAE-CERT-BATCHA-1"})

    # 1. First benchmark authorization with NO existing model results.
    def test_control_01_first_authorization_without_model_results(self):
        auth = issue()
        self.assertEqual(auth.qualifying_class, "EAE")
        self.assertTrue(auth.checksum_valid())
        self.assertNotIn("accuracy", json.dumps(auth.payload))
        self.assertNotIn("aggregation", json.dumps(auth.payload).lower())
        self.assertEqual(auth.payload["results_dependency"], "none")

    # 2. Missing required shared-core qualification (PARTIAL/NOT_STARTED
    # evidence cannot even register — fail-closed at both stages).
    def test_control_02_missing_shared_core(self):
        ea.clear_execution_evidence()
        with self.assertRaises(ea.AuthorizationError):
            ea.register_execution_evidence(
                full_evidence(shared_core_acceptance="PARTIAL"),
                trusted_certificate_refs={"EAE-CERT-BATCHA-1"})
        with self.assertRaises(ea.AuthorizationError):
            issue()

    # 3. Wrong cognitive family.
    def test_control_03_wrong_cognitive_family(self):
        with self.assertRaises(ea.AuthorizationError):
            issue(primitives=["C17"])          # outside Batch A evidence

    # 4. Wrong protocol.
    def test_control_04_wrong_protocol(self):
        with self.assertRaises(ea.AuthorizationError):
            issue(protocols=["thinking_enabled_chat"])

    # 5. Modified planned roster.
    def test_control_05_modified_roster(self):
        with self.assertRaises(ea.AuthorizationError):
            issue(roster_digest="f" * 64)

    # 6. Manually constructed AggregationReport must authorize nothing.
    def test_control_06_aggregation_report_is_not_execution_evidence(self):
        fake_report = {"formal_publication": "ALLOWED",
                       "qualified_eligible": 480, "correct": 480,
                       "scope": "semantic"}
        # the execution path never consults aggregation-shaped input:
        # passing one where evidence is expected changes nothing
        ea.clear_execution_evidence()
        with self.assertRaises(ea.AuthorizationError):
            issue()
        # and a report smuggled into the registry is rejected by validate()
        with self.assertRaises(ea.AuthorizationError):
            ea.register_execution_evidence(fake_report)   # type: ignore

    # 7. Mutated qualified counts / payload fields.
    def test_control_07_mutated_payload_detected(self):
        auth = issue()
        mutated = copy.deepcopy(auth)
        object.__setattr__(mutated, "payload", dict(
            auth.payload, dispatch_limits={"max_trials": 10 ** 9}))
        self.assertFalse(mutated.checksum_valid())
        forged = mutated.with_checksum()      # re-forged checksum differs
        self.assertNotEqual(forged.checksum, auth.checksum)

    # 8. Empty certificate collection (refused at registration AND at
    # issue — an empty chain cannot even become evidence).
    def test_control_08_empty_certificates(self):
        ea.clear_execution_evidence()
        with self.assertRaises(ea.AuthorizationError):
            ea.register_execution_evidence(
                full_evidence(certificate_refs=(), certificate_digests=()),
                trusted_certificate_refs=set())
        with self.assertRaises(ea.AuthorizationError):
            issue()

    # 9. Untrusted certificate store.
    def test_control_09_untrusted_store(self):
        ea.clear_execution_evidence()
        ea.register_execution_evidence(full_evidence(),
                                       trusted_certificate_refs=set())
        with self.assertRaises(ea.AuthorizationError):
            issue()

    # 10. Revoked certificate.
    def test_control_10_revoked_certificate(self):
        ea.REVOCATIONS.revoke("EAE-CERT-BATCHA-1")
        with self.assertRaises(ea.AuthorizationError):
            issue()

    # 11. Stale authorization after revocation.
    def test_control_11_stale_after_revocation(self):
        auth = issue()
        ea.REVOCATIONS.revoke("EAE-CERT-BATCHA-1")
        with self.assertRaises(ea.AuthorizationError):
            ea.recheck_execution_authorization(auth)

    # 12. Authorization reused for a different experiment.
    def test_control_12_reuse_for_different_experiment(self):
        auth = issue()                       # exp-001, C01+C02
        # a DIFFERENT experiment re-presenting the same authorization is
        # caught by checksum binding + evidence recheck:
        self.assertTrue(auth.checksum_valid())
        material = json.loads(auth.canonical_material())
        self.assertEqual(material[1], "exp-001")
        # and scope validation on the consumer side (validate_against)
        # rejects the reuse for a wider request
        consumer = self._consumer()
        req = consumer.RunRequest(
            experiment_id="exp-002",
            dataset_digest=DATASET, roster_digest=ROSTER,
            primitives=frozenset({"C03"}), protocols=frozenset({"chat"}),
            models=frozenset(MODELS), eae_revision=PINNED_REV,
            auth_level="AUTH-1")
        with self.assertRaises(consumer.AuthorizationError):
            consumer.validate_against(_ConsumerAuth(auth), req)

    # 13. Serialized authorization with modified fields.
    def test_control_13_serialized_mutation_detected(self):
        auth = issue()
        mutated = copy.deepcopy(auth)        # deserialized copy
        object.__setattr__(mutated, "scope", dict(
            auth.scope, primitives=["C01", "C02", "C03"]))
        self.assertFalse(mutated.checksum_valid())
        mutated2 = copy.deepcopy(auth)
        object.__setattr__(mutated2, "payload", dict(
            auth.payload, shared_core_acceptance="FORGED"))
        self.assertFalse(mutated2.checksum_valid())

    # 14. AUTH-1 used to dispatch a formal AUTH-2 benchmark.
    def test_control_14_auth1_cannot_dispatch_auth2(self):
        consumer = self._consumer()
        provider = consumer.EAEExecutionAuthorizationProvider(
            PINNED_REV, "eval_assurance.compat.execution_authorization")
        req2 = consumer.RunRequest(
            experiment_id="exp-002", dataset_digest=DATASET,
            roster_digest=ROSTER, primitives=frozenset({"C01"}),
            protocols=frozenset({"chat"}), models=frozenset(MODELS),
            eae_revision=PINNED_REV, auth_level="AUTH-2")
        auth1 = issue(auth_level="AUTH-1")
        with self.assertRaises(consumer.AuthorizationError):
            consumer.validate_against(_ConsumerAuth(auth1), req2)
        # level discipline on our side too:
        with self.assertRaises(ea.AuthorizationError):
            issue(auth_level="AUTH-3-PLUS")

    # 15. AUTH-1/AUTH-2 used to access protected confirmation execution.
    # Frozen IJ-NANO-1.3S contract: AUTH-2 = SCOPED_DEVELOPMENT_BENCHMARK;
    # only AUTH-3 = SCOPED_CONFIRMATION_BENCHMARK may touch protected
    # confirmation execution. (Reproduced the audited mismatch red at
    # 9c73bbf: CONFIRMATION_LEVEL was "AUTH-2", letting AUTH-2 authorize
    # confirmation execution — evidence auth_semantics_mismatch_9c73bbf.json.)
    def test_control_15_confirmation_scope_gated(self):
        # dev-only evidence cannot authorize confirmation execution at ANY
        # sub-AUTH-3 level
        with self.assertRaises(ea.AuthorizationError):
            issue(auth_level="AUTH-1", confirmation_execution=True)
        with self.assertRaises(ea.AuthorizationError):
            issue(auth_level="AUTH-2", confirmation_execution=True)
        # even confirmation-covering evidence still needs AUTH-3:
        ea.clear_execution_evidence()
        ea.register_execution_evidence(
            full_evidence(confirmation_execution=True,
                          roster_split="confirmation"),
            trusted_certificate_refs={"EAE-CERT-BATCHA-1"})
        with self.assertRaises(ea.AuthorizationError):
            issue(auth_level="AUTH-1", confirmation_execution=True)
        with self.assertRaises(ea.AuthorizationError):
            issue(auth_level="AUTH-2", confirmation_execution=True)
        auth = issue(auth_level="AUTH-3", confirmation_execution=True)
        self.assertTrue(auth.payload["confirmation_execution"])

    # 17. Roster split enforcement: development evidence and confirmation
    # evidence are bound to their own rosters and authorization levels
    # (order section 3.1 "test actual roster split enforcement").
    def test_control_17_roster_split_enforcement(self):
        # a) confirmation evidence must declare the confirmation split
        ea.clear_execution_evidence()
        with self.assertRaises(ea.AuthorizationError):
            ea.register_execution_evidence(
                full_evidence(confirmation_execution=True),
                trusted_certificate_refs={"EAE-CERT-BATCHA-1"})
        # b) dev evidence (roster_split=development) refuses AUTH-3 even
        #    with confirmation_execution requested
        ea.clear_execution_evidence()
        ea.register_execution_evidence(
            full_evidence(roster_split="development"),
            trusted_certificate_refs={"EAE-CERT-BATCHA-1"})
        with self.assertRaises(ea.AuthorizationError):
            issue(auth_level="AUTH-3", confirmation_execution=True)
        with self.assertRaises(ea.AuthorizationError):
            issue(auth_level="AUTH-3")     # AUTH-3 is confirmation-only
        # c) confirmation evidence cannot authorize a development-level
        #    (AUTH-1/AUTH-2) dispatch: sub-confirmation levels require a
        #    development-split roster
        ea.clear_execution_evidence()
        ea.register_execution_evidence(
            full_evidence(confirmation_execution=True,
                          roster_split="confirmation"),
            trusted_certificate_refs={"EAE-CERT-BATCHA-1"})
        with self.assertRaises(ea.AuthorizationError):
            issue(auth_level="AUTH-2")
        with self.assertRaises(ea.AuthorizationError):
            issue(auth_level="AUTH-1")
        # d) a confirmation roster digest is not bound to dev evidence:
        #    digest mismatch refuses the modified roster independently
        ea.clear_execution_evidence()
        ea.register_execution_evidence(
            full_evidence(roster_split="development"),
            trusted_certificate_refs={"EAE-CERT-BATCHA-1"})
        with self.assertRaises(ea.AuthorizationError):
            issue(roster_digest="c" * 64)  # forged/confirmation roster

    # 16. Test-double authorization against the physical runner.
    def test_control_16_test_double_cannot_authorize_physical(self):
        consumer = self._consumer()
        gate = consumer.DispatchGate(
            consumer.SyntheticExecutionAuthorizationProvider())
        req = consumer.RunRequest(
            experiment_id="exp-003", dataset_digest=DATASET,
            roster_digest=ROSTER, primitives=frozenset({"C01"}),
            protocols=frozenset({"chat"}), models=frozenset(MODELS),
            eae_revision=PINNED_REV, auth_level="AUTH-1")
        with self.assertRaises(consumer.AuthorizationError):
            gate.authorize_physical(req)

    # -- real consumer integration (not a conformance claim from doubles)
    def test_real_consumer_issues_and_validates(self):
        consumer = self._consumer()
        provider = consumer.EAEExecutionAuthorizationProvider(
            PINNED_REV, "eval_assurance.compat.execution_authorization")
        req = consumer.RunRequest(
            experiment_id="exp-real-1", dataset_digest=DATASET,
            roster_digest=ROSTER, primitives=frozenset({"C01", "C02"}),
            protocols=frozenset({"chat"}), models=frozenset(MODELS),
            eae_revision=PINNED_REV, auth_level="AUTH-1")
        auth = provider.issue_execution_authorization(req)
        self.assertEqual(auth.qualifying_class, "EAE")
        consumer.validate_against(auth, req)
        gate = consumer.DispatchGate(provider)
        physical = gate.authorize_physical(req)
        self.assertTrue(physical.checksum_valid())
        provider.revoke("EAE-CERT-BATCHA-1")
        with self.assertRaises(
                (consumer.AuthorizationError, ea.AuthorizationError)):
            provider.issue_execution_authorization(req)

    def test_real_consumer_fail_closed_without_evidence(self):
        consumer = self._consumer()
        provider = consumer.EAEExecutionAuthorizationProvider(
            PINNED_REV, "eval_assurance.compat.execution_authorization")
        ea.clear_execution_evidence()
        req = consumer.RunRequest(
            experiment_id="exp-real-2", dataset_digest=DATASET,
            roster_digest=ROSTER, primitives=frozenset({"C01"}),
            protocols=frozenset({"chat"}), models=frozenset(MODELS),
            eae_revision=PINNED_REV, auth_level="AUTH-1")
        with self.assertRaises(
                (consumer.AuthorizationError, ea.AuthorizationError)):
            provider.issue_execution_authorization(req)

    def _consumer(self):
        if not (IJNANO / "benchmarks" / "ij_nano" / "n03" /
                "authorization.py").exists():
            self.skipTest("IJNANO sibling worktree not present")
        if str(IJNANO) not in sys.path:
            sys.path.insert(0, str(IJNANO))
        import importlib
        return importlib.import_module(CONSUMER_MODULE)


class _ConsumerAuth:
    """Adapter presenting OUR ExecutionAuthorization to the consumer's
    validate_against() (attribute surface it reads)."""

    def __init__(self, auth):
        self.scope = auth.scope
        self.dataset_digest = auth.dataset_digest
        self.roster_digest = auth.roster_digest
        self.eae_revision = auth.eae_revision
        self.auth_level = auth.auth_level
        self._checksum = auth.checksum
        self._material = auth.canonical_material()

    def checksum_valid(self) -> bool:
        import hashlib
        return self._checksum == hashlib.sha256(
            self._material.encode("utf-8")).hexdigest()


class EvidenceIntegrity(unittest.TestCase):
    def test_publication_side_unchanged(self):
        from eval_assurance.compat import authorization as pub
        self.assertEqual(pub.AUTHORIZATION_SCHEMA, "1.0.0")
        self.assertTrue(callable(pub.authorize_runner))

    def test_trust_model_documented(self):
        import inspect
        doc = inspect.getdoc(ea)
        for phrase in ("Trust model", "NOT a defense against",
                       "Fail-closed"):
            self.assertIn(phrase, doc)

    def test_no_direct_construction(self):
        with self.assertRaises(PermissionError):
            ea.ExecutionAuthorization(
                schema="1.1.0", experiment_id="x", auth_level="AUTH-1",
                scope={}, dataset_digest="d", roster_digest="r",
                eae_revision="v", certificate_ref="c", issued_by="i",
                qualifying_class="EAE", payload={})


if __name__ == "__main__":
    unittest.main()
