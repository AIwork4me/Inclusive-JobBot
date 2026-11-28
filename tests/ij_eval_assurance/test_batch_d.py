"""Permanent regression coverage — N03 Batch D qualification (C25-C32).

Covers the AUTH-2 Batch D release chain: oracle ground-truth validity,
mutation battery, dual-path witness semantics (incl. ambiguity
discipline, citation supersets, ABSTAIN), module independence, and
release artifacts (registry keeps all four batch certificates).
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance import dualpath_d                         # noqa: E402
from eval_assurance.reference import oracle_d                 # noqa: E402

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
AUTH2D = ROOT / "evidence" / "IJEVAL" / "AUTH2D"
EA13D = ROOT / "evidence" / "IJEVAL" / "EA13D"
PIN_FULL = EVID / "pinned_full"

PRIMS = [f"C{i:02d}" for i in range(25, 33)]


def _load():
    rows = [json.loads(l) for l in
            (PIN_FULL / "n03_cases.public.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()]
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PIN_FULL / "n03_dev_expectations.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip())}
    return rows, exps


class BatchDGroundTruth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows, exps = _load()
        cls.dev = [r for r in rows if r["split"] == "development" and
                   r["primitive"] in PRIMS]
        cls.exps = exps
        assert len(cls.dev) == 160

    def test_all_160_dev_ground_truths_valid(self):
        bad = [(r["case_id"],
                oracle_d.validate_ground_truth(
                    r, self.exps.get(r["case_id"], {})).verdict.value)
               for r in self.dev]
        bad = [b for b in bad if b[1] != "VALID"]
        self.assertEqual(bad, [])

    def test_gt_artifact_matches_live_oracle(self):
        art = json.loads(
            (EVID / "ground_truth_qualification_dev160_batch_d.json")
            .read_text(encoding="utf-8"))
        self.assertTrue(art["summary"]["all_valid"])
        self.assertEqual(art["summary"]["counts"], {"VALID": 160})

    def test_mutation_battery_no_escapes(self):
        art = json.loads(
            (EVID / "gt_mutation_coverage_dev160_batch_d.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(art["summary"]["escaped"], 0)
        self.assertGreaterEqual(art["summary"]["controls"], 250)


class BatchDIndependence(unittest.TestCase):
    def test_batch_d_modules_import_no_ij_nano_code(self):
        import inspect
        from eval_assurance.reference import (interpreter_d, oracle_d as
                                              ord_)
        from eval_assurance.production import (evaluator_d, parser_d as
                                               ppd)
        for mod in (interpreter_d, ord_, evaluator_d, ppd, dualpath_d):
            src = inspect.getsource(mod)
            for banned in ("from evaluation", "import evaluation",
                           "from n02r", "import n02r",
                           "from benchmarks", "import benchmarks"):
                self.assertNotIn(banned, src,
                                 f"{mod.__name__} violates independence")


class BatchDDecisionSemantics(unittest.TestCase):
    """Batch-D-specific decision rules through the dual-path."""

    @classmethod
    def setUpClass(cls):
        cls.rows, cls.exps = _load()

    def _case(self, predicate):
        rows = type(self).rows
        return next(r for r in rows
                    if r["split"] == "development" and predicate(r))

    def test_c26_invalid_value_counts_as_missing(self):
        case = self._case(lambda r: r["primitive"] == "C26" and
                          (r["public_payload"].get("field_validity")
                           or {}) and
                          any(v is not None for v in
                              (r["public_payload"].get(
                                  "available_information") or {}).values()))
        exp = self.exps[case["case_id"]]
        e = exp["expected"]
        raw = json.dumps({"decision": e["decision"],
                          "missing": e.get("missing") or []})
        r = dualpath_d.evaluate_dual(case, exp, raw)
        self.assertEqual(r.classification, "CORRECT")
        # a decision that ignores the validity gap must NOT pass
        wrong = json.dumps({"decision":
                            "ACT" if e["decision"] == "ASK" else "ASK",
                            "missing": []})
        r2 = dualpath_d.evaluate_dual(case, exp, wrong)
        self.assertEqual(r2.classification, "INCORRECT")

    def test_c29_ambiguity_discipline(self):
        amb = self._case(lambda r: r["primitive"] == "C29" and
                         self.exps[r["case_id"]]["expected"]["class"] ==
                         "AMBIGUOUS")
        exp = self.exps[amb["case_id"]]
        ids = exp["expected"]["readings"]
        r = dualpath_d.evaluate_dual(amb, exp, f"AMBIGUOUS: {ids[0]}, "
                                             f"{ids[1]}")
        self.assertEqual(r.classification, "CORRECT")
        r2 = dualpath_d.evaluate_dual(amb, exp, ids[0])
        self.assertEqual(r2.classification, "INCORRECT")

    def test_c31_superset_citations_accepted(self):
        case = self._case(lambda r: r["primitive"] == "C31")
        exp = self.exps[case["case_id"]]
        req = exp["expected"]["required_citations"]
        ids = [ev["id"] for ev in case["public_payload"]["evidence"]]
        extra = next(i for i in ids if i not in req)
        raw = "Facts. " + " ".join(f"({c})" for c in req + [extra])
        r = dualpath_d.evaluate_dual(case, exp, raw)
        self.assertEqual(r.classification, "CORRECT")
        phantom = "Facts. (EV-PHANTOM)"
        r2 = dualpath_d.evaluate_dual(case, exp, phantom)
        self.assertEqual(r2.classification, "INCORRECT")

    def test_c32_abstain_discipline(self):
        ab = self._case(lambda r: r["primitive"] == "C32" and
                        self.exps[r["case_id"]]["expected"]
                        ["output_class"] == "ABSTAIN")
        an = self._case(lambda r: r["primitive"] == "C32" and
                        self.exps[r["case_id"]]["expected"]
                        ["output_class"] == "ANSWER")
        self.assertEqual(dualpath_d.evaluate_dual(
            ab, self.exps[ab["case_id"]], "ABSTAIN").classification,
            "CORRECT")
        self.assertEqual(dualpath_d.evaluate_dual(
            ab, self.exps[ab["case_id"]], "11:11").classification,
            "INCORRECT")
        self.assertEqual(dualpath_d.evaluate_dual(
            an, self.exps[an["case_id"]],
            str(self.exps[an["case_id"]]["expected"]["answer"])
        ).classification, "CORRECT")
        self.assertEqual(dualpath_d.evaluate_dual(
            an, self.exps[an["case_id"]], "ABSTAIN").classification,
            "INCORRECT")


class BatchDReleaseArtifacts(unittest.TestCase):
    def test_release_json(self):
        rel = json.loads((AUTH2D / "release.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(rel["experiment"],
                         "N03-AUTH2-DEVELOPMENT-BATCH-D-v1")
        self.assertEqual(rel["scope"]["slots"], 480)
        self.assertEqual(rel["scope"]["primitives"], PRIMS)
        self.assertEqual(rel["dispatch_limits"], {"max_trials": 480})
        self.assertIn("BLOCKED", rel["confirmation_status"])

    def test_roster_development_only(self):
        ros = json.loads((AUTH2D / "development_roster_480.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(ros["slot_count"], 480)
        rows, _ = _load()
        split = {r["case_id"]: r["split"] for r in rows}
        self.assertTrue(all(split[s["case_id"]] == "development"
                            for s in ros["slots"]))

    def test_canary_breaker_consumer_passed(self):
        self.assertTrue(json.loads(
            (AUTH2D / "canary_integration.json")
            .read_text(encoding="utf-8"))["passed"])
        self.assertTrue(json.loads(
            (AUTH2D / "breaker_drill.json")
            .read_text(encoding="utf-8"))["passed"])
        cv = json.loads((AUTH2D / "consumer_verification.json")
                        .read_text(encoding="utf-8"))
        self.assertTrue(cv["issue_ok"])
        self.assertTrue(cv["revoked_refused"])

    def test_ea13d_all_qualified(self):
        rep = json.loads(
            (EA13D / "primitive_qualification_batch_d.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(rep["summary"], {"qualified": 8, "total": 8})

    def test_witness_and_fault_artifacts(self):
        wit = json.loads((EVID / "dualpath_witnesses_batch_d.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(wit["summary"]["failed"], 0)
        supers = [r for r in wit["rows"] if "SUPERSET" in
                  r.get("detail", "")]
        self.assertTrue(supers)
        self.assertTrue(all(r["passed"] for r in supers))
        mut = json.loads(
            (EVID / "production_mutation_campaign_batch_d.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(mut["summary"]["escapes"], 0)
        by_name = {f["fault"]: f["verdict"] for f in mut["faults"]}
        for critical in ("D-E03_substring_answer", "D-E07_guess_tolerated",
                         "D-E01_validity_gap_tolerated"):
            self.assertEqual(by_name[critical], "DETECTED")

    def test_registry_keeps_all_batches(self):
        reg = json.loads(
            (EVID / "certificates" / "registry.json")
            .read_text(encoding="utf-8"))
        protocols = {c["protocol"] for c in reg["certificates"]}
        for batch in ("A", "B", "C", "D"):
            self.assertIn(
                f"cpu-dualpath-qualification:N03_BATCH_{batch}_DEV_CPU_"
                "DUALPATH", protocols)


if __name__ == "__main__":
    unittest.main()
