"""IJ-NANO-48H wiring tests (AUTH-0, CPU-only): pinned-EAE bootstrap,
real-consumer authorization, and fail-closed negative controls. No GPU,
no network: authorization exercises the pinned contract only.

One EAE pin revision per process is enforced by eae.bootstrap, so every
test that bootstraps a scope runs in a subprocess helper. In-process
tests cover pin verification, the pinned dual-path legs (loaded from
the CURRENT pin), the renderer and the execution plan.

Consumer-state truth: certificate 512efb617a9cb4c8 (Batch A) is revoked
by the drill recorded at 3cdd066; AUTH-2B (Batch B) and AUTH-2C (Batch
C) are the live scopes at their respective pins.
"""
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.ij_nano.n03h import eae as eae_mod   # noqa: E402

REVOKED_CERT = "512efb617a9cb4c8"
NL = chr(10)

_SCOPE_PROBE = [
    "import sys; sys.path.insert(0, r'%s')" % ROOT,
    "from benchmarks.ij_nano.n03h import eae as e",
    "from benchmarks.ij_nano.n03.authorization import (RunRequest,",
    "    validate_against)",
    "bt = e.bootstrap(sys.argv[1])",
    "ident = bt['identity']",
    "req = RunRequest(experiment_id=ident['experiment_id'],",
    "                 dataset_digest=ident['dataset_digest'],",
    "                 roster_digest=ident['roster_digest'],",
    "                 primitives=frozenset(ident['primitives']),",
    "                 protocols=frozenset(ident['protocols']),",
    "                 models=frozenset(ident['models']),",
    "                 eae_revision=ident['eae_revision'],",
    "                 auth_level=ident['auth_level'])",
    "auth = bt['gate'].authorize_physical(req)",
    "validate_against(auth, req)",
    "print('ISSUED', auth.checksum)",
]


def run_py(lines, scope=None):
    code = NL.join(lines)
    argv = [sys.executable, "-c", code]
    if scope is not None:
        argv.append(scope)
    return subprocess.run(argv, capture_output=True,
                          encoding="utf-8", errors="replace",
                          timeout=180, cwd=str(ROOT))


class TestPinVerification(unittest.TestCase):
    def test_current_pin_verifies_against_manifest(self):
        report = eae_mod.verify_pin()
        self.assertEqual(report["files_verified"], 148)
        self.assertEqual(eae_mod.CURRENT_PIN_REV, "a50c3c5")

    def test_historical_pins_still_verify(self):
        self.assertEqual(
            eae_mod.verify_pin("7a3e8dc")["files_verified"], 125)
        self.assertEqual(
            eae_mod.verify_pin("3cdd066")["files_verified"], 84)

    def test_pin_tamper_refused(self):
        pin = eae_mod._pin_paths(eae_mod.CURRENT_PIN_REV)["pin"]
        target = pin / "evidence" / "IJEVAL" / "AUTH2C" / "release.json"
        original = target.read_bytes()
        try:
            target.write_bytes(original + b" ")
            with self.assertRaises(RuntimeError):
                eae_mod.verify_pin()
        finally:
            target.write_bytes(original)
        eae_mod.verify_pin()          # restored


class TestFailClosedAndScopes(unittest.TestCase):
    """Batch A scopes stay blocked (drill-revoked certificate); the
    per-process pin guard refuses cross-revision bootstrap; the live
    scopes reproduce their released checksums exactly."""

    def test_auth1_scope_refused(self):
        r = run_py(["import sys; sys.path.insert(0, r'%s')" % ROOT,
                    "from benchmarks.ij_nano.n03h import eae as e",
                    "e.bootstrap('AUTH-1')"], scope=None)
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(
            "no applicable certificates" in r.stderr
            or "checksum mismatch" in r.stderr
            or "not consumable" in r.stderr,
            f"unexpected outcome: {r.stderr[-400:]}")

    def test_auth2_scope_refused(self):
        r = run_py(["import sys; sys.path.insert(0, r'%s')" % ROOT,
                    "from benchmarks.ij_nano.n03h import eae as e",
                    "e.bootstrap('AUTH-2')"], scope=None)
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(
            "no applicable certificates" in r.stderr
            or "checksum mismatch" in r.stderr
            or "not consumable" in r.stderr,
            f"unexpected outcome: {r.stderr[-400:]}")

    def test_cross_pin_scope_switch_refused_in_process(self):
        lines = [
            "import sys; sys.path.insert(0, r'%s')" % ROOT,
            "from benchmarks.ij_nano.n03h import eae as e",
            "e.bootstrap('AUTH-2B')",
            "try:",
            "    e.bootstrap('AUTH-2C')",
            "    raise SystemExit('SWITCH ALLOWED')",
            "except RuntimeError as ex:",
            "    assert 'One EAE revision per process' in str(ex)",
            "print('GUARDED')",
        ]
        r = run_py(lines)
        self.assertIn("GUARDED", r.stdout, r.stderr[-400:])

    def test_auth2b_issuance_matches_released_checksum(self):
        r = run_py(_SCOPE_PROBE, scope="AUTH-2B")
        self.assertIn(
            "ISSUED fc4cdb2c0d36f189dd9f0249edbba2310a5b957f3ecd40"
            "b99af8a1c8d2a9133d", r.stdout, r.stderr[-400:])

    def test_auth2c_issuance_matches_released_checksum(self):
        r = run_py(_SCOPE_PROBE, scope="AUTH-2C")
        self.assertIn(
            "ISSUED c90f234af01db24a2c73796db505e25c7ae68c1afd66f0fd4"
            "a21954088b9d29f", r.stdout, r.stderr[-400:])

    def test_scope_boundary_negatives(self):
        lines = [
            "import sys; sys.path.insert(0, r'%s')" % ROOT,
            "from benchmarks.ij_nano.n03h import eae as e",
            "from benchmarks.ij_nano.n03.authorization import RunRequest",
            "bt = e.bootstrap('AUTH-2C')",
            "ident = bt['identity']",
            "base = dict(experiment_id=ident['experiment_id'],",
            "            dataset_digest=ident['dataset_digest'],",
            "            roster_digest=ident['roster_digest'],",
            "            primitives=frozenset(ident['primitives']),",
            "            protocols=frozenset(ident['protocols']),",
            "            models=frozenset(ident['models']),",
            "            eae_revision=ident['eae_revision'],",
            "            auth_level=ident['auth_level'])",
            "PinnedRefusal = bt['contract'].AuthorizationError",
            "for over in [{'primitives': frozenset({'C01'})},",
            "             {'roster_digest': '0' * 64},",
            "             {'protocols': frozenset({'chat_json_schema'})},",
            "             {'models': frozenset({'LFM3-8B'})}]:",
            "    try:",
            "        bt['gate'].authorize_physical("
            "RunRequest(**{**base, **over}))",
            "        raise SystemExit('REFUSAL MISSING: %r' % over)",
            "    except PinnedRefusal:",
            "        pass",
            "print('BOUNDARIES')",
        ]
        r = run_py(lines)
        self.assertIn("BOUNDARIES", r.stdout, r.stderr[-400:])

    def test_revocation_is_durably_recorded_in_pin(self):
        pin = eae_mod._pin_paths("3cdd066")["pin"]
        reg = json.loads(
            (pin / "evidence" / "IJEVAL" / "EA03_N03" / "certificates"
             / "registry.json").read_text(encoding="utf-8"))
        certs = {c["certificate_id"]: c for c in reg["certificates"]}
        self.assertIn(REVOKED_CERT, certs)
        self.assertIsNotNone(certs[REVOKED_CERT].get("revoked_utc"))
        state = json.loads(
            (pin / "evidence" / "IJEVAL" / "AUTH2"
             / "authoritative_state.json").read_text(encoding="utf-8"))
        self.assertTrue(any(r["certificate_id"] == REVOKED_CERT
                            for r in state["revocations"]))


class TestDualPathAndRenderer(unittest.TestCase):
    """In-process: the pinned evaluation legs (from the CURRENT pin),
    the frozen renderer and the execution plan."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(eae_mod.PIN_SRC))
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
        dp = self.DualPathSession(ROOT / ".scratch" / "48h" / "test_dp")
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
        models = ["m1", "m2", "m3"]
        camp.roster_slots = [
            {"case_id": f"c{i:03d}",
             "model": models[i % 3]} for i in range(120)]
        plan = camp.execution_plan()
        self.assertEqual(len(plan), 6)         # 120 cases / 20 per block
        first = plan[0]["trials"]
        self.assertEqual(first[0]["case_id"], first[1]["case_id"])
        self.assertEqual(len({t["model"] for t in first[:3]}), 3)


if __name__ == "__main__":
    unittest.main()
