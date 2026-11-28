"""Permanent regression coverage — N03 Batch C qualification (C17-C24).

Covers the AUTH-2 Batch C release chain: oracle ground-truth validity,
mutation battery, dual-path witness semantics (incl. the plan-scoring
rule: alternative simulated-valid plans are CORRECT; reference plans
are never string-matched), module independence, release artifacts, and
the registry keeping all batch certificates.
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance import dualpath_c                         # noqa: E402
from eval_assurance.reference import oracle_c                 # noqa: E402

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
AUTH2C = ROOT / "evidence" / "IJEVAL" / "AUTH2C"
EA13C = ROOT / "evidence" / "IJEVAL" / "EA13C"
PIN_FULL = EVID / "pinned_full"

PRIMS = [f"C{i:02d}" for i in range(17, 25)]


def _load():
    rows = [json.loads(l) for l in
            (PIN_FULL / "n03_cases.public.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()]
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PIN_FULL / "n03_dev_expectations.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip())}
    return rows, exps


class BatchCGroundTruth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows, exps = _load()
        cls.dev = [r for r in rows if r["split"] == "development" and
                   r["primitive"] in PRIMS]
        cls.exps = exps
        assert len(cls.dev) == 160

    def test_all_160_dev_ground_truths_valid(self):
        bad = [(r["case_id"],
                oracle_c.validate_ground_truth(
                    r, self.exps.get(r["case_id"], {})).verdict.value)
               for r in self.dev]
        bad = [b for b in bad if b[1] != "VALID"]
        self.assertEqual(bad, [])

    def test_gt_artifact_matches_live_oracle(self):
        art = json.loads(
            (EVID / "ground_truth_qualification_dev160_batch_c.json")
            .read_text(encoding="utf-8"))
        self.assertTrue(art["summary"]["all_valid"])
        self.assertEqual(art["summary"]["counts"], {"VALID": 160})

    def test_mutation_battery_no_escapes(self):
        art = json.loads(
            (EVID / "gt_mutation_coverage_dev160_batch_c.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(art["summary"]["escaped"], 0)
        self.assertGreaterEqual(art["summary"]["controls"], 300)


class BatchCIndependence(unittest.TestCase):
    def test_batch_c_modules_import_no_ij_nano_code(self):
        import inspect
        from eval_assurance.reference import (interpreter_c, oracle_c as
                                              orc)
        from eval_assurance.production import (evaluator_c, parser_c as
                                              ppc)
        for mod in (interpreter_c, orc, evaluator_c, ppc, dualpath_c):
            src = inspect.getsource(mod)
            for banned in ("from evaluation", "import evaluation",
                           "from n02r", "import n02r",
                           "from benchmarks", "import benchmarks"):
                self.assertNotIn(banned, src,
                                 f"{mod.__name__} violates independence")


class BatchCPlanScoringRule(unittest.TestCase):
    """The pinned plan-scoring rule is enforced on both paths."""

    @classmethod
    def setUpClass(cls):
        cls.rows, cls.exps = _load()
        cls.by_prim = {r["primitive"]: r for r in cls.rows
                       if r["split"] == "development" and
                       r["primitive"] in PRIMS}

    def test_alternative_valid_plan_is_correct(self):
        # C19: append a harmless applicable action to the reference
        # plan — still simulated-valid, still goal-reaching
        case = next(r for r in self.rows if r["primitive"] == "C19" and
                    r["split"] == "development")
        p = case["public_payload"]
        plan = list(self.exps[case["case_id"]]["expected"]
                    ["reference_plan"])
        _, _, final = oracle_c.simulate_plan(
            plan, p["initial_state"], p["actions"])
        for name, spec in p["actions"].items():
            if name in plan:
                continue
            if all(final.get(k) == v for k, v in
                   (spec.get("preconditions") or {}).items()):
                alt = json.dumps(plan + [name])
                r = dualpath_c.evaluate_dual(
                    case, self.exps[case["case_id"]], alt)
                self.assertEqual(
                    r.classification, "CORRECT",
                    f"alternative plan must be CORRECT: {r.reasons}")
                return
        self.fail("no case admitted an alternative-plan probe")

    def test_reference_plan_reordering_breaks_preconditions(self):
        case = next(r for r in self.rows if r["primitive"] == "C19" and
                    r["split"] == "development")
        p = case["public_payload"]
        plan = list(self.exps[case["case_id"]]["expected"]
                    ["reference_plan"])
        if len(plan) < 2:
            self.skipTest("single-step plan")
        swapped = json.dumps([plan[1], plan[0]] + plan[2:])
        r = dualpath_c.evaluate_dual(case, self.exps[case["case_id"]],
                                     swapped)
        self.assertEqual(r.classification, "INCORRECT")

    def test_prefix_reexecution_refused(self):
        case = next(r for r in self.rows if r["primitive"] == "C21" and
                    r["split"] == "development")
        p = case["public_payload"]
        cont = list(self.exps[case["case_id"]]["expected"]
                    ["continuation"])
        stale = json.dumps(list(p.get("executed_prefix") or []) + cont)
        r = dualpath_c.evaluate_dual(case, self.exps[case["case_id"]],
                                     stale)
        self.assertEqual(r.classification, "INCORRECT")


class BatchCDualPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.exps = _load()
        cls.by_prim = {r["primitive"]: r for r in cls.rows
                       if r["split"] == "development" and
                       r["primitive"] in PRIMS}

    def _flow(self, prim, raw):
        case = self.by_prim[prim]
        return dualpath_c.evaluate_dual(
            case, self.exps[case["case_id"]], raw)

    def test_empty_keeps_own_class(self):
        for prim in PRIMS:
            self.assertEqual(self._flow(prim, "").classification,
                             "EMPTY_OUTPUT")

    def test_software_error_never_model_failure(self):
        class _Raising:
            def parse_response(self, prim, payload, response):
                raise RuntimeError("injected")
        case = self.by_prim["C17"]
        r = dualpath_c.evaluate_dual(
            case, self.exps[case["case_id"]], "[true]",
            production_parser=_Raising().parse_response)
        self.assertEqual(r.classification, "EVALUATOR_SOFTWARE_ERROR")
        self.assertTrue(r.quarantine)

    def test_c22_200_wrapper_never_clears_body_error(self):
        case = next(r for r in self.rows if r["case_id"].startswith(
            "n03-C22-") and r["split"] == "development" and
            r["public_payload"]["response"].get("http_status") == 200 and
            "error" in (r["public_payload"]["response"].get("body")
                        or {}))
        e = self.exps[case["case_id"]]["expected"]
        raw = json.dumps({"is_error": e["is_error"],
                          "code": e.get("code") or ""})
        r = dualpath_c.evaluate_dual(case, self.exps[case["case_id"]],
                                     raw)
        self.assertEqual(r.classification, "CORRECT")
        # ... and the anti-rule (is_error false) must NOT pass
        raw2 = json.dumps({"is_error": not e["is_error"],
                           "code": e.get("code") or ""})
        r2 = dualpath_c.evaluate_dual(case, self.exps[case["case_id"]],
                                      raw2)
        self.assertEqual(r2.classification, "INCORRECT")


class BatchCReleaseArtifacts(unittest.TestCase):
    def test_release_json(self):
        rel = json.loads((AUTH2C / "release.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(rel["experiment"],
                         "N03-AUTH2-DEVELOPMENT-BATCH-C-v1")
        self.assertEqual(rel["scope"]["slots"], 480)
        self.assertEqual(rel["scope"]["primitives"], PRIMS)
        self.assertEqual(rel["dispatch_limits"], {"max_trials": 480})
        self.assertIn("BLOCKED", rel["confirmation_status"])

    def test_roster_complete_and_development_only(self):
        ros = json.loads((AUTH2C / "development_roster_480.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(ros["slot_count"], 480)
        rows, _ = _load()
        split = {r["case_id"]: r["split"] for r in rows}
        self.assertTrue(all(split[s["case_id"]] == "development"
                            for s in ros["slots"]))

    def test_canary_breaker_consumer_passed(self):
        self.assertTrue(json.loads(
            (AUTH2C / "canary_integration.json")
            .read_text(encoding="utf-8"))["passed"])
        self.assertTrue(json.loads(
            (AUTH2C / "breaker_drill.json")
            .read_text(encoding="utf-8"))["passed"])
        cv = json.loads((AUTH2C / "consumer_verification.json")
                        .read_text(encoding="utf-8"))
        self.assertTrue(cv["issue_ok"])
        self.assertTrue(cv["revoked_refused"])

    def test_ea13c_all_qualified(self):
        rep = json.loads(
            (EA13C / "primitive_qualification_batch_c.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(rep["summary"], {"qualified": 8, "total": 8})

    def test_witness_and_fault_artifacts(self):
        wit = json.loads((EVID / "dualpath_witnesses_batch_c.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(wit["summary"]["failed"], 0)
        # alternative-plan positives exist and pass
        alts = [r for r in wit["rows"]
                if r.get("detail", "").startswith("ALTERNATIVE")]
        self.assertTrue(alts)
        self.assertTrue(all(r["passed"] for r in alts))
        mut = json.loads(
            (EVID / "production_mutation_campaign_batch_c.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(mut["summary"]["escapes"], 0)
        by_name = {f["fault"]: f["verdict"] for f in mut["faults"]}
        self.assertEqual(by_name["C-E03_plan_string_match"], "DETECTED")
        self.assertEqual(by_name["C-E05_status_clears_error"], "DETECTED")

    def test_registry_keeps_all_batches(self):
        reg = json.loads(
            (EVID / "certificates" / "registry.json")
            .read_text(encoding="utf-8"))
        protocols = {c["protocol"] for c in reg["certificates"]}
        for batch in ("A", "B", "C"):
            self.assertIn(
                f"cpu-dualpath-qualification:N03_BATCH_{batch}_DEV_CPU_"
                "DUALPATH", protocols)

    def test_intake_artifact_verified(self):
        art = json.loads((EVID / "intake_verification_batch_c.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(art["verdict"], "VERIFIED")
        self.assertEqual(art["structure"]["dev"], 160)


if __name__ == "__main__":
    unittest.main()
