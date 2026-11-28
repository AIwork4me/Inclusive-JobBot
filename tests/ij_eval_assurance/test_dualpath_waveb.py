"""Wave B closure regression controls (EA04/EA05/EA07/EA08).

Permanent controls for the production/reference dual-path integration:
independence (import-level), class discipline (empty vs invalid vs
software vs disagreement), witness spot-checks through the ACTUAL
integrated path, fault-detection spot checks, and EA08 session
integrity (duplicate rejection, exact resume, replay, tamper,
missing-evidence distinction).
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
PINNED = EVID / "pinned"


def _load():
    lines = (PINNED / "n03_cases.public.jsonl").read_text(
        encoding="utf-8").splitlines()
    cases = [json.loads(l) for l in lines if l.strip()]
    lines = (PINNED / "n03_dev_expectations.jsonl").read_text(
        encoding="utf-8").splitlines()
    exps = {json.loads(l)["case_id"]: json.loads(l)
            for l in lines if l.strip()}
    return {c["case_id"]: c for c in cases}, exps


class Independence(unittest.TestCase):
    def test_reference_imports_no_production(self):
        from eval_assurance.reference import interpreter, oracle
        for mod in (interpreter, oracle):
            src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
            self.assertNotIn("eval_assurance.production", src)
            self.assertNotIn("ij_nano", src)

    def test_production_imports_no_reference(self):
        from eval_assurance.production import evaluator, parser
        for mod in (parser, evaluator):
            src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
            self.assertNotIn("eval_assurance.reference", src)
            self.assertNotIn("eval_assurance.dualpath", src)

    def test_oracle_and_evaluator_are_distinct_files(self):
        from eval_assurance.production import evaluator
        from eval_assurance.reference import oracle
        self.assertNotEqual(
            pathlib.Path(evaluator.__file__).read_bytes(),
            pathlib.Path(oracle.__file__).read_bytes())


class ClassDiscipline(unittest.TestCase):
    """Empty output / invalid output / software error / missing evidence
    / disagreement are five DISTINCT outcomes (order section 2)."""

    def setUp(self):
        self.cases, self.exps = _load()
        self.case = next(c for c in self.cases.values()
                         if c["primitive"] == "C01")
        self.exp = self.exps[self.case["case_id"]]

    def test_empty_output_own_class(self):
        from eval_assurance.dualpath import evaluate_dual
        r = evaluate_dual(self.case, self.exp, "")
        self.assertEqual(r.classification, "EMPTY_OUTPUT")

    def test_software_error_never_model_failure(self):
        from eval_assurance import faults
        from eval_assurance.dualpath import evaluate_dual
        r = evaluate_dual(self.case, self.exp, "anything",
                          production_parser=faults.RaisingParser()
                          .parse_response)
        self.assertEqual(r.classification, "PARSER_SOFTWARE_ERROR")
        self.assertTrue(r.quarantine)

    def test_disagreement_is_not_evaluable_and_quarantined(self):
        from eval_assurance import faults
        from eval_assurance.dualpath import evaluate_dual
        truth = self.exp["expected"]["label"]
        r = evaluate_dual(self.case, self.exp, truth,
                          production_evaluator=faults
                          .make_evaluator_fault(
                              "E01_any_catalog_member"))
        # E01 accepts any catalog member; the truth IS a member so the
        # wrong-answer witness is the detector:
        cat = list((self.case.get("public_payload") or {})
                   .get("intent_catalog") or {})
        other = next(k for k in cat if k != truth)
        r2 = evaluate_dual(self.case, self.exp, other,
                           production_evaluator=faults
                           .make_evaluator_fault(
                               "E01_any_catalog_member"))
        self.assertEqual(r2.classification, "NOT_EVALUABLE")
        self.assertTrue(r2.quarantine)

    def test_duplicate_key_rejection(self):
        from eval_assurance.dualpath import evaluate_dual
        r = evaluate_dual(self.case, self.exp,
                          '{"intent": "a", "intent": "b"}')
        self.assertEqual(r.classification, "INVALID_OUTPUT")

    def test_no_silent_identifier_normalization(self):
        from eval_assurance.dualpath import evaluate_dual
        truth = self.exp["expected"]["label"]
        r = evaluate_dual(self.case, self.exp, "  " + truth.upper() +
                          "  ")
        # trim + case-normalize is the declared policy; a mutant token is
        # never normalized into a different identity
        self.assertIn(r.classification, ("CORRECT", "NOT_EVALUABLE"))


class WitnessSpotChecks(unittest.TestCase):
    """The committed witness suite passes and covers every family."""

    @classmethod
    def setUpClass(cls):
        cls.suite = json.loads(
            (EVID / "dualpath_witnesses.json").read_text(encoding="utf-8"))

    def test_all_witnesses_passed(self):
        self.assertEqual(self.suite["summary"]["failed"], 0)
        self.assertGreater(self.suite["summary"]["total"], 100)

    def test_every_primitive_and_family_covered(self):
        cases, _ = _load()
        fams = {(c["primitive"], c["family"]) for c in cases.values()
                if c.get("split") == "development"}
        covered = {(r["primitive"], r["family"])
                   for r in self.suite["rows"]}
        self.assertTrue(fams <= covered)

    def test_kinds_include_contract_boundaries(self):
        kinds = {r["kind"] for r in self.suite["rows"]}
        for k in ("positive", "positive-fenced", "negative-wrong",
                  "negative-malformed", "negative-dup-key", "empty",
                  "software-error", "negative-extra-field",
                  "negative-missing-field", "negative-flags-flip",
                  "negative-multiline"):
            self.assertIn(k, kinds)


class MutationCampaign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.campaign = json.loads((EVID / "production_mutation_campaign.json")
                                  .read_text(encoding="utf-8"))
        cls.suite = json.loads(
            (EVID / "dualpath_witnesses.json").read_text(encoding="utf-8"))

    def test_no_escapes(self):
        self.assertEqual(self.campaign["summary"]["escapes"], [])

    def test_equivalents_are_justified(self):
        for f in self.campaign["faults"]:
            if f["verdict"] == "EQUIVALENT":
                self.assertTrue(f["equivalent_justification"])

    def test_fault_detection_live_spot_check(self):
        # the committed evidence is not trusted blindly: re-run one fault
        from eval_assurance import faults
        from eval_assurance.dualpath import evaluate_dual
        cases, exps = _load()
        w = next(r for r in self.suite["rows"]
                 if r["kind"] == "negative-extra-field")
        case = cases[w["case_id"]]
        clean = evaluate_dual(case, exps[w["case_id"]], w["raw"])
        faulty = evaluate_dual(case, exps[w["case_id"]], w["raw"],
                               production_parser=faults.make_parser_fault(
                                   "P03_drop_extra_fields"))
        self.assertNotEqual(clean.classification, faulty.classification)


class EA08SessionControls(unittest.TestCase):
    def setUp(self):
        self.cases, self.exps = _load()
        self.tmp = tempfile.TemporaryDirectory(
            dir=str(ROOT / ".runtime"))
        self.addCleanup(self.tmp.cleanup)
        self.workdir = pathlib.Path(self.tmp.name)

    def _c01(self):
        case = next(c for c in self.cases.values()
                    if c["primitive"] == "C01")
        return case, self.exps[case["case_id"]]

    def test_duplicate_rejection_preserves_original(self):
        from eval_assurance.dualpath import (DUPLICATE_TRIAL,
                                             DualPathSession)
        case, exp = self._c01()
        s = DualPathSession(self.workdir / "d")
        first = s.run_trial(case, exp, "x", model="m", protocol="p")
        again = s.run_trial(case, exp, "x", model="m", protocol="p")
        self.assertNotEqual(first.classification, DUPLICATE_TRIAL)
        self.assertEqual(again.classification, DUPLICATE_TRIAL)
        self.assertEqual(len(s.trials), 1)
        self.assertEqual(len(s.quarantine), 1)

    def test_resume_exact_and_replay_agrees(self):
        from eval_assurance.dualpath import DualPathSession
        case, exp = self._c01()
        s = DualPathSession(self.workdir / "r")
        s.run_trial(case, exp, "x", model="m", protocol="p1")
        s.run_trial(case, exp, "y", model="m", protocol="p2")
        s.save()
        s2 = DualPathSession(self.workdir / "r")
        self.assertTrue(s2.load())
        self.assertEqual(set(s2.trials), set(s.trials))
        rp = s2.replay(case, exp, "m", "p1")
        self.assertTrue(rp["matches_recorded"])

    def test_tampered_artifact_detected(self):
        from eval_assurance.dualpath import (MISSING_EVIDENCE,
                                             DualPathSession)
        case, exp = self._c01()
        s = DualPathSession(self.workdir / "t")
        s.run_trial(case, exp, "x", model="m", protocol="p")
        art = next((s.workdir / "artifacts").iterdir())
        art.write_text("tampered", encoding="utf-8")
        problems = s.verify()
        self.assertTrue(problems)
        tid = next(iter(s.trials))
        self.assertEqual(s.trials[tid]["classification"],
                         MISSING_EVIDENCE)

    def test_missing_evidence_distinct_from_empty(self):
        from eval_assurance.dualpath import (EMPTY_OUTPUT, MISSING,
                                             MISSING_EVIDENCE,
                                             DualPathSession,
                                             evaluate_dual)
        case, exp = self._c01()
        s = DualPathSession(self.workdir / "m")
        self.assertEqual(
            s.run_trial(case, exp, "", model="m", protocol="e")
            .classification, EMPTY_OUTPUT)
        self.assertEqual(
            s.run_trial(case, exp, MISSING, model="m", protocol="g")
            .classification, MISSING_EVIDENCE)


if __name__ == "__main__":
    unittest.main()
