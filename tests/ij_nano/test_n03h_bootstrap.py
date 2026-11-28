"""IJ-NANO-48H wiring tests (AUTH-0, CPU-only): pinned-EAE bootstrap,
real-consumer authorization, and fail-closed negative controls. No GPU,
no network: authorization exercises the pinned contract only.

Consumer-state truth at pin 3cdd066: the EAE's post-release
consumer-verification revocation drill durably revoked certificate
512efb617a9cb4c8 (registry generation 2, revoked_utc
2026-11-28T04:04:08Z, reason "drill"), so fresh ExecutionEvidence
registration fails closed with "no applicable certificates" — the
correct consumer behavior. Issuance-path tests activate automatically
once a requalified pin (new certificate generation) replaces this one.
"""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.ij_nano.n03.authorization import (  # noqa: E402
    AuthorizationError, RunRequest, validate_against)
from benchmarks.ij_nano.n03h import eae as eae_mod   # noqa: E402

REVOKED_CERT = "512efb617a9cb4c8"


def _issuable(scope: str) -> bool:
    try:
        eae_mod.bootstrap(scope)
        return True
    except Exception:
        return False


class TestPinVerification(unittest.TestCase):
    def test_pin_verifies_against_manifest(self):
        report = eae_mod.verify_pin()
        self.assertEqual(report["files_verified"], 84)

    def test_pin_tamper_refused(self):
        pin = eae_mod.PIN / "evidence" / "IJEVAL" / "AUTH1" / "release.json"
        original = pin.read_bytes()
        try:
            pin.write_bytes(original + b" ")
            with self.assertRaises(RuntimeError):
                eae_mod.verify_pin()
        finally:
            pin.write_bytes(original)
        eae_mod.verify_pin()          # restored


class TestFailClosedRevokedRegistry(unittest.TestCase):
    """The published 3cdd066 registry carries the drill revocation:
    registration must refuse (no applicable certificates), never
    downgrade, never bypass."""

    def test_auth1_registration_refused_by_revoked_certificate(self):
        with self.assertRaises(Exception) as cm:
            eae_mod.bootstrap("AUTH-1")
        self.assertIn("no applicable certificates", str(cm.exception))

    def test_auth2_registration_refused_by_revoked_certificate(self):
        with self.assertRaises(Exception) as cm:
            eae_mod.bootstrap("AUTH-2")
        self.assertIn("no applicable certificates", str(cm.exception))

    def test_revocation_is_durably_recorded_in_pin(self):
        reg = json.loads((eae_mod.PIN / "evidence" / "IJEVAL" / "EA03_N03"
                          / "certificates" / "registry.json")
                         .read_text(encoding="utf-8"))
        certs = {c["certificate_id"]: c for c in reg["certificates"]}
        self.assertIn(REVOKED_CERT, certs)
        self.assertIsNotNone(certs[REVOKED_CERT].get("revoked_utc"))
        state = json.loads((eae_mod.PIN / "evidence" / "IJEVAL" / "AUTH2"
                            / "authoritative_state.json")
                           .read_text(encoding="utf-8"))
        self.assertTrue(any(r["certificate_id"] == REVOKED_CERT
                            for r in state["revocations"]))


@unittest.skipUnless(_issuable("AUTH-1"),
                     "certificate revoked at pin 3cdd066 (drill); "
                     "activates on a requalified pin")
class TestBootstrapAndAuthorization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bt = eae_mod.bootstrap("AUTH-1")

    def _request(self, **over):
        ident = self.bt["identity"]
        kw = dict(
            experiment_id=ident["experiment_id"],
            dataset_digest=ident["dataset_digest"],
            roster_digest=ident["roster_digest"],
            primitives=frozenset(ident["primitives"]),
            protocols=frozenset(ident["protocols"]),
            models=frozenset(ident["models"]),
            eae_revision=ident["eae_revision"],
            auth_level=ident["auth_level"])
        kw.update(over)
        return RunRequest(**kw)

    def test_real_consumer_physical_authorization(self):
        auth = self.bt["gate"].authorize_physical(self._request())
        self.assertEqual(auth.qualifying_class, "EAE")
        self.assertTrue(auth.checksum_valid())
        validate_against(auth, self._request())

    def test_scope_enforcement(self):
        with self.assertRaises(AuthorizationError):
            self.bt["gate"].authorize_physical(
                self._request(primitives=frozenset({"C09"})))
        with self.assertRaises(AuthorizationError):
            self.bt["gate"].authorize_physical(
                self._request(protocols=frozenset({"chat_json_schema"})))
        with self.assertRaises(AuthorizationError):
            self.bt["gate"].authorize_physical(
                self._request(models=frozenset({"LFM3-8B"})))
        with self.assertRaises(AuthorizationError):
            self.bt["gate"].authorize_physical(
                self._request(eae_revision="1.1.0"))
        with self.assertRaises(AuthorizationError):
            self.bt["gate"].authorize_physical(
                self._request(roster_digest="0" * 64))

    def test_test_double_structurally_rejected(self):
        from benchmarks.ij_nano.n03.authorization import (
            DispatchGate, SyntheticExecutionAuthorizationProvider)
        gate = DispatchGate(SyntheticExecutionAuthorizationProvider())
        with self.assertRaises(AuthorizationError):
            gate.authorize_physical(self._request())


class TestDualPathAndRenderer(unittest.TestCase):
    """These do not require authorization: they exercise the pinned
    evaluation pipeline and the frozen renderer directly."""

    @classmethod
    def setUpClass(cls):
        # direct pin imports without evidence registration
        src = str(eae_mod.PIN_SRC)
        if src not in sys.path:
            sys.path.insert(0, src)
        from eval_assurance.dualpath import DualPathSession
        cls.DualPathSession = DualPathSession
        cls.witnesses = json.loads(
            (eae_mod.EVID / "dualpath_witnesses.json")
            .read_text(encoding="utf-8"))["rows"]
        cls.exps = {json.loads(l)["case_id"]: json.loads(l) for l in
                    (eae_mod.EVID / "pinned" / "n03_dev_expectations.jsonl")
                    .read_text(encoding="utf-8").splitlines() if l.strip()}
        cls.cases = {json.loads(l)["case_id"]: json.loads(l) for l in
                     (eae_mod.EVID / "pinned" /
                      "n03_cases.public.jsonl").read_text(
                          encoding="utf-8").splitlines() if l.strip()}

    def test_positive_and_negative_witnesses_through_pinned_pipeline(self):
        from eval_assurance.dualpath import evaluate_dual
        checks = 0
        for w in self.witnesses:
            if w["primitive"] not in {f"C{i:02d}" for i in range(1, 9)}:
                continue
            if w["kind"] == "software-error":
                continue
            case = self.cases[w["case_id"]]
            exp = self.exps[w["case_id"]]
            res = evaluate_dual(case, exp, w["raw"])
            self.assertEqual(res.classification, w["expected"],
                             f"witness {w['witness_id']} misclassified")
            checks += 1
        self.assertGreater(checks, 90)

    def test_dualpath_session_rejects_duplicate_identities(self):
        dp = self.DualPathSession(ROOT / ".scratch" / "48h" / "test_dualpath2")
        w = next(x for x in self.witnesses if x["kind"] == "positive")
        case, exp = self.cases[w["case_id"]], self.exps[w["case_id"]]
        first = dp.run_trial(case, exp, w["raw"], model="dup-test")
        second = dp.run_trial(case, exp, w["raw"], model="dup-test")
        self.assertEqual(first.classification, "CORRECT")
        self.assertEqual(second.classification, "DUPLICATE_TRIAL")

    def test_renderer_deterministic_and_instruction_last(self):
        from benchmarks.ij_nano.n03h.transport import (
            render_chat_user_content)
        case = {"public_payload": {
            "utterance": "the dashboard is down",
            "intent_catalog": {"a": "desc a", "b": "desc b"},
            "instruction": "Choose one label."}}
        a = render_chat_user_content(case)
        self.assertEqual(a, render_chat_user_content(case))
        self.assertTrue(a.endswith("Task: Choose one label."))
        self.assertIn("- a: desc a", a)

    def test_renderer_covers_all_batch_a_payload_shapes(self):
        from benchmarks.ij_nano.n03h.transport import (
            render_chat_user_content)
        with_task = 0
        for cid, case in self.cases.items():
            out = render_chat_user_content(case)
            self.assertIsInstance(out, str)
            self.assertGreater(len(out), 20, f"empty render for {cid}")
            if "instruction" in (case.get("public_payload") or {}):
                self.assertIn("Task:", out)
                with_task += 1
        self.assertGreater(with_task, 100)   # most payloads carry one

    def test_execution_plan_balanced_rotation(self):
        from benchmarks.ij_nano.n03h.campaign import Campaign
        camp = Campaign.__new__(Campaign)      # no bootstrap needed
        camp.roster_slots = [
            {"case_id": f"c{i:03d}"} for i in range(40)]
        plan = camp.execution_plan()
        self.assertEqual(len(plan), 2)         # 40 cases / 20 per block
        first = plan[0]["trials"]
        self.assertEqual(first[0]["case_id"], first[1]["case_id"])
        self.assertEqual(len({t["model"] for t in first[:3]}), 3)


if __name__ == "__main__":
    unittest.main()
