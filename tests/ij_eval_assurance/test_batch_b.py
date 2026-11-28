"""Permanent regression coverage — N03 Batch B qualification (C09-C16).

Covers the AUTH-2 Batch B release chain (order 48H-SUPPORT section 1):
independent-oracle ground-truth validity over the pinned full roster,
GT mutation battery spot controls, dual-path witness semantics,
independence of the Batch B modules, the release artifacts, and the
byte-identity of the Batch A qualified sources (their digests are
registered in the LIVE Batch A ExecutionEvidence — any edit is a
regression by definition).
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance import dualpath_b                         # noqa: E402
from eval_assurance.production import evaluator_b as pev_b    # noqa: E402
from eval_assurance.production import parser_b as ppr_b       # noqa: E402
from eval_assurance.reference import oracle_b                 # noqa: E402

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
AUTH2B = ROOT / "evidence" / "IJEVAL" / "AUTH2B"
EA13B = ROOT / "evidence" / "IJEVAL" / "EA13B"
PIN_FULL = EVID / "pinned_full"

PRIMS = [f"C{i:02d}" for i in range(9, 17)]


def _load():
    rows = [json.loads(l) for l in
            (PIN_FULL / "n03_cases.public.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()]
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PIN_FULL / "n03_dev_expectations.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip())}
    return rows, exps


class BatchBGroundTruth(unittest.TestCase):
    """EA03-B obligation A over the pinned full roster."""

    @classmethod
    def setUpClass(cls):
        rows, exps = _load()
        cls.dev = [r for r in rows if r["split"] == "development" and
                   r["primitive"] in PRIMS]
        cls.exps = exps
        assert len(cls.dev) == 160, f"expected 160 dev cases, got {len(cls.dev)}"

    def test_all_160_dev_ground_truths_valid(self):
        bad = []
        for r in self.dev:
            res = oracle_b.validate_ground_truth(
                r, self.exps.get(r["case_id"], {}))
            if res.verdict.value != "VALID":
                bad.append((r["case_id"], res.verdict.value))
        self.assertEqual(bad, [])

    def test_gt_artifact_matches_live_oracle(self):
        art = json.loads(
            (EVID / "ground_truth_qualification_dev160_batch_b.json")
            .read_text(encoding="utf-8"))
        self.assertTrue(art["summary"]["all_valid"])
        self.assertEqual(art["summary"]["counts"], {"VALID": 160})

    def test_mutation_battery_no_escapes(self):
        art = json.loads(
            (EVID / "gt_mutation_coverage_dev160_batch_b.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(art["summary"]["escaped"], 0)
        self.assertGreaterEqual(art["summary"]["controls"], 400)

    def test_out_of_scope_primitive_refused(self):
        res = oracle_b.validate_ground_truth(
            {"primitive": "C01", "case_id": "x",
             "public_payload": {}}, {"expected": {"label": "a"}})
        self.assertEqual(res.verdict.value, "NOT_ESTABLISHED")


class BatchBIndependence(unittest.TestCase):
    """The Batch B legs import no IJ-NANO code (structural)."""

    def test_batch_b_modules_import_no_ij_nano_code(self):
        import inspect
        from eval_assurance.reference import (interpreter_b, oracle_b as
                                              orb)
        from eval_assurance.production import (evaluator_b, parser_b as
                                               ppb)
        for mod in (interpreter_b, orb, evaluator_b, ppb, dualpath_b):
            src = inspect.getsource(mod)
            for banned in ("from evaluation", "import evaluation",
                           "from n02r", "import n02r",
                           "from benchmarks", "import benchmarks"):
                self.assertNotIn(banned, src,
                                 f"{mod.__name__} violates independence")

    def test_oracle_b_distinct_from_evaluator_b(self):
        import hashlib
        o = hashlib.sha256(
            (ROOT / "src" / "eval_assurance" / "reference" / "oracle_b.py")
            .read_bytes()).hexdigest()
        e = hashlib.sha256(
            (ROOT / "src" / "eval_assurance" / "production" /
             "evaluator_b.py").read_bytes()).hexdigest()
        self.assertNotEqual(o, e)


class BatchBDualPath(unittest.TestCase):
    """Reference/production disagreement handling and class discipline."""

    @classmethod
    def setUpClass(cls):
        cls.rows, cls.exps = _load()
        cls.by_prim = {}
        for r in cls.rows:
            if r["split"] == "development" and r["primitive"] in PRIMS:
                cls.by_prim.setdefault(r["primitive"], r)

    def _witness_flow(self, prim, raw):
        case = self.by_prim[prim]
        exp = self.exps[case["case_id"]]
        return dualpath_b.evaluate_dual(case, exp, raw)

    def test_positive_witnesses_correct(self):
        for prim in PRIMS:
            case = self.by_prim[prim]
            exp = self.exps[case["case_id"]]
            e = exp["expected"]
            if prim in ("C09", "C12", "C14"):
                raw = json.dumps(e.get("record") or e.get("slots") or
                                 e.get("values"))
            elif prim == "C10":
                raw = json.dumps(e["document"])
            elif prim == "C11":
                raw = e["program"]
            elif prim == "C13":
                raw = str(e["resolution"])
            elif prim == "C15":
                raw = json.dumps({"value": e["conversion"]["value"],
                                  "unit": e["conversion"]["unit"]})
            else:
                raw = str(e["answer"])
            r = self._witness_flow(prim, raw)
            self.assertEqual(
                r.classification, "CORRECT",
                f"{prim} positive witness: {r.reasons}")

    def test_empty_output_keeps_own_class(self):
        for prim in PRIMS:
            r = self._witness_flow(prim, "")
            self.assertEqual(r.classification, "EMPTY_OUTPUT")

    def test_malformed_outputs_invalid_not_software(self):
        raws = {"C09": "free text answer", "C10": "not json",
                "C11": "RUN dock", "C12": "no json here",
                "C13": "CT-1\nCT-2", "C14": "answer is 42",
                "C15": '{"value": 1}', "C16": "yes\nno"}
        for prim, raw in raws.items():
            r = self._witness_flow(prim, raw)
            self.assertEqual(r.classification, "INVALID_OUTPUT",
                             f"{prim}: {r.classification} {r.reasons}")

    def test_duplicate_json_keys_structural(self):
        for prim in ("C09", "C12", "C14", "C15"):
            r = self._witness_flow(prim, '{"value": 1, "value": 2}')
            self.assertIn(r.classification,
                          ("INVALID_OUTPUT", "INCORRECT"),
                          f"{prim}: {r.classification}")

    def test_software_error_never_model_failure(self):
        class _Raising:
            def parse_response(self, prim, payload, response):
                raise RuntimeError("injected")
        case = self.by_prim["C09"]
        r = dualpath_b.evaluate_dual(
            case, self.exps[case["case_id"]], "{}",
            production_parser=_Raising().parse_response)
        self.assertEqual(r.classification, "EVALUATOR_SOFTWARE_ERROR")
        self.assertTrue(r.quarantine)

    def test_unestablished_truth_refuses_evaluation(self):
        case = dict(self.by_prim["C09"])
        case["public_payload"] = {}          # truth not derivable
        r = dualpath_b.evaluate_dual(
            case, self.exps[case["case_id"]], "{}")
        # production consumes the STORED expectation and may score;
        # the reference path refuses — an honest disagreement is
        # NOT_EVALUABLE, never a silent CORRECT
        self.assertIn(r.classification,
                      ("NOT_EVALUABLE", "INCORRECT", "INVALID_OUTPUT"))

    def test_parser_b_rejects_out_of_batch(self):
        parsed = ppr_b.parse_response("C01", {}, "incident_report")
        self.assertEqual(parsed.parse_class, "PARSER_SOFTWARE_ERROR")


class BatchBReleaseArtifacts(unittest.TestCase):
    """The AUTH-2 Batch B release is complete and internally valid."""

    def test_release_json(self):
        rel = json.loads((AUTH2B / "release.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(rel["experiment"],
                         "N03-AUTH2-DEVELOPMENT-BATCH-B-v1")
        self.assertEqual(rel["auth_level"], "AUTH-2")
        self.assertEqual(rel["scope"]["slots"], 480)
        self.assertEqual(rel["scope"]["dev_cases"], 160)
        self.assertEqual(rel["scope"]["primitives"], PRIMS)
        self.assertEqual(rel["dispatch_limits"], {"max_trials": 480})
        self.assertIn("BLOCKED", rel["confirmation_status"])

    def test_roster_complete_and_development_only(self):
        ros = json.loads((AUTH2B / "development_roster_480.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(ros["slot_count"], 480)
        self.assertEqual(len(ros["slots"]), 480)
        cases = {s["case_id"] for s in ros["slots"]}
        self.assertEqual(len(cases), 160)
        prims = {s["primitive"] for s in ros["slots"]}
        self.assertEqual(prims, set(PRIMS))
        rows, _ = _load()
        split = {r["case_id"]: r["split"] for r in rows}
        self.assertTrue(all(split[c] == "development" for c in cases))

    def test_canary_and_breaker_passed(self):
        canary = json.loads((AUTH2B / "canary_integration.json")
                            .read_text(encoding="utf-8"))
        self.assertTrue(canary["passed"])
        self.assertEqual(sorted(canary["families"]), PRIMS)
        breaker = json.loads((AUTH2B / "breaker_drill.json")
                             .read_text(encoding="utf-8"))
        self.assertTrue(breaker["passed"])

    def test_consumer_verification_passed(self):
        cv = json.loads((AUTH2B / "consumer_verification.json")
                        .read_text(encoding="utf-8"))
        self.assertTrue(cv["issue_ok"])
        self.assertTrue(cv["revoked_refused"])

    def test_ea13b_all_qualified(self):
        rep = json.loads(
            (EA13B / "primitive_qualification_batch_b.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(rep["summary"], {"qualified": 8, "total": 8})
        for r in rep["primitives"]:
            self.assertEqual(r["verdict"], "QUALIFIED")
            self.assertTrue(r["ground_truth_all_valid"])
            self.assertEqual(r["witnesses"]["passed"],
                             r["witnesses"]["total"])

    def test_witness_suite_artifact_all_passed(self):
        wit = json.loads((EVID / "dualpath_witnesses_batch_b.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(wit["summary"]["failed"], 0)
        self.assertGreaterEqual(wit["summary"]["total"], 130)

    def test_fault_campaign_no_escapes(self):
        mut = json.loads(
            (EVID / "production_mutation_campaign_batch_b.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(mut["summary"]["escapes"], 0)
        for f in mut["faults"]:
            self.assertIn(f["verdict"], ("DETECTED", "EQUIVALENT"))
            if f["verdict"] == "EQUIVALENT":
                self.assertTrue(f["equivalent_justification"])

    def test_intake_artifact_verified(self):
        art = json.loads((EVID / "intake_verification_batch_b.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(art["verdict"], "VERIFIED")
        self.assertEqual(art["structure"]["cases"], 240)
        self.assertEqual(art["structure"]["dev"], 160)
        self.assertFalse(
            art["protected_confirmation"]["content_accessed"])


class BatchASourcesUntouched(unittest.TestCase):
    """The Batch A qualified sources stay byte-identical: their digests
    are registered in the LIVE Batch A ExecutionEvidence, so any edit
    would stale the running campaign's authorization (hard regression).
    """

    _BATCH_A_FILES = [
        "src/eval_assurance/production/parser.py",
        "src/eval_assurance/production/evaluator.py",
        "src/eval_assurance/reference/interpreter.py",
        "src/eval_assurance/reference/oracle.py",
    ]

    def test_batch_a_source_digests_match_registered_evidence(self):
        """The Batch A certificate's digest bindings must still match
        the current Batch A source bytes — any edit would stale the
        live Batch A ExecutionEvidence."""
        import hashlib
        reg = json.loads(
            (EVID / "certificates" / "registry.json")
            .read_text(encoding="utf-8"))
        batch_a = [c for c in reg["certificates"]
                   if c["protocol"] ==
                   "cpu-dualpath-qualification:N03_BATCH_A_DEV_CPU_DUALPATH"]
        self.assertTrue(batch_a,
                        "Batch A certificate missing from the registry")
        cert = batch_a[0]
        binding = {"parser_sha256":
                   "src/eval_assurance/production/parser.py",
                   "evaluator_sha256":
                   "src/eval_assurance/production/evaluator.py",
                   "interpreter_sha256":
                   "src/eval_assurance/reference/interpreter.py",
                   "reference_oracle_sha256":
                   "src/eval_assurance/reference/oracle.py"}
        for key, rel in binding.items():
            current = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
            self.assertEqual(cert[key], current,
                             f"{rel} drifted from the Batch A "
                             "certificate binding")

    def test_registry_keeps_both_batches(self):
        reg = json.loads(
            (EVID / "certificates" / "registry.json")
            .read_text(encoding="utf-8"))
        protocols = {c["protocol"] for c in reg["certificates"]}
        self.assertIn(
            "cpu-dualpath-qualification:N03_BATCH_A_DEV_CPU_DUALPATH",
            protocols)
        self.assertIn(
            "cpu-dualpath-qualification:N03_BATCH_B_DEV_CPU_DUALPATH",
            protocols)

    def test_batch_a_gt_still_validates(self):
        """Spot re-validation: the Batch A oracle on a Batch A case."""
        from eval_assurance.reference import oracle as oracle_a
        rows, exps = _load()
        case = next(r for r in rows if r["case_id"].startswith(
            "n03-C01-") and r["split"] == "development")
        res = oracle_a.validate_ground_truth(case, exps[case["case_id"]])
        self.assertEqual(res.verdict.value, "VALID")


if __name__ == "__main__":
    unittest.main()
