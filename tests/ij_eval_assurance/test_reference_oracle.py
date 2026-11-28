"""EA03 — independent reference oracle regression (N03 Batch A dev corpus).

Consumes the PINNED dataset snapshot committed at
``evidence/IJEVAL/EA03_N03/pinned/`` (raw-file digests match the IJ-NANO
handoff package manifest @ d23de5a) — never the mutable sibling worktree.

Historical note: the first qualification run (commit 3ec4c28) established
133 VALID / 27 NOT_ESTABLISHED with a structurally weaker oracle. The v2
oracle performs full-field independent semantic derivation (GT-D01..D05);
the corrected qualification of the SAME pinned data is 160/160 VALID with
597/597 mutations detected. The historical 133/27 run remains immutable
evidence in git history and in reconciliation_dev160.json; these tests
pin the CORRECTED derivation, which is recomputed here — never tuned to
a headline number.
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

PINNED = ROOT / "evidence" / "IJEVAL" / "EA03_N03" / "pinned"


def load_dev():
    pub = [json.loads(l) for l in
           (PINNED / "n03_cases.public.jsonl").read_text(
               encoding="utf-8").splitlines() if l.strip()]
    exp = {json.loads(l)["case_id"]: json.loads(l) for l in
           (PINNED / "n03_dev_expectations.jsonl").read_text(
               encoding="utf-8").splitlines() if l.strip()}
    dev = [c for c in pub if c["split"] == "development"
           and c["primitive"] in {f"C0{i}" for i in range(1, 9)}]
    return dev, exp


@unittest.skipUnless((PINNED / "n03_cases.public.jsonl").exists(),
                     "pinned Batch A snapshot not present")
class TestGroundTruthQualification(unittest.TestCase):
    def run_oracle(self):
        from eval_assurance.reference.oracle import validate_ground_truth
        dev, exp = load_dev()
        self.assertEqual(len(dev), 160)
        return [validate_ground_truth(c, exp.get(c["case_id"])) for c in dev]

    def test_corrected_qualification_numbers(self):
        results = self.run_oracle()
        counts = {"VALID": 0, "INVALID": 0, "AMBIGUOUS": 0,
                  "NOT_ESTABLISHED": 0}
        for r in results:
            counts[r.verdict.value] += 1
        self.assertEqual(counts["VALID"], 160)
        self.assertEqual(counts["INVALID"], 0)
        self.assertEqual(counts["AMBIGUOUS"], 0)
        self.assertEqual(counts["NOT_ESTABLISHED"], 0)

    def test_all_primitives_fully_recomputable_20_20(self):
        from eval_assurance.reference.oracle import validate_ground_truth
        dev, exp = load_dev()
        for prim in ("C01", "C02", "C03", "C04", "C05", "C06", "C07",
                     "C08"):
            cases = [c for c in dev if c["primitive"] == prim]
            verdicts = [validate_ground_truth(c, exp.get(c["case_id"]))
                        .verdict.value for c in cases]
            self.assertEqual(verdicts.count("VALID"), 20, prim)

    def test_oracle_imports_no_ij_nano_code(self):
        import inspect
        from eval_assurance.reference import interpreter, oracle
        for mod in (oracle, interpreter):
            src = inspect.getsource(mod)
            for banned in ("from evaluation", "import evaluation",
                           "from n02r", "import n02r", "from benchmarks",
                           "import benchmarks"):
                self.assertNotIn(banned, src)


@unittest.skipUnless((PINNED / "n03_cases.public.jsonl").exists(),
                     "pinned Batch A snapshot not present")
class TestGTDDefectProbes(unittest.TestCase):
    """The GT-D01..GT-D05 source-level concerns as permanent regressions:
    each was an escape vector in the pre-repair oracle and must stay
    detected."""

    @classmethod
    def setUpClass(cls):
        cls.dev, cls.exp = load_dev()
        cls.by_id = {c["case_id"]: c for c in cls.dev}

    def v(self, case, expectation):
        from eval_assurance.reference.oracle import validate_ground_truth
        return validate_ground_truth(case, expectation).verdict.value

    def case(self, cid):
        return copy.deepcopy(self.by_id[cid]), \
            copy.deepcopy(self.exp[cid])

    # GT-D01: a wrong but syntactically valid canonical code must not
    # obtain VALID; partial validation must not be promoted to VALID.
    def test_gtd01_c02_field_mutations(self):
        c, e = self.case("n03-C02-project-d00")
        for fld, val in (("action", "submit"), ("object", "audit_trail"),
                         ("completion_criterion", "visible_in_system"),
                         ("deadline", "2030-01-01")):
            m = copy.deepcopy(e)
            m["expected"][fld] = val
            self.assertNotEqual(
                self.v(c, m), "VALID",
                f"mutated {fld} still validates (GT-D01)")
        m = copy.deepcopy(e)
        m["expected"]["unknown_flags"]["deadline"] = True
        self.assertNotEqual(self.v(c, m), "VALID", "flag flip (GT-D01)")
        m = copy.deepcopy(e)
        del m["expected"]["action"]
        self.assertNotEqual(self.v(c, m), "VALID", "missing field")
        m = copy.deepcopy(e)
        m["expected"]["priority"] = "high"
        self.assertNotEqual(self.v(c, m), "VALID", "extra field")
        c2 = copy.deepcopy(c)
        c2["public_payload"]["message"] = "Please migrate it by 2026-12-11."
        self.assertEqual(self.v(c2, e), "NOT_ESTABLISHED",
                         "partial validation must be NOT_ESTABLISHED")

    # GT-D02: constraints are parsed from the PUBLIC instruction; a
    # coupled corruption of stored constraints+ids cannot validate.
    def test_gtd02_c04_coupled_mutation(self):
        c, e = self.case("n03-C04-retail-d00")
        m = copy.deepcopy(e)
        m["expected"]["constraints"] = [["price<=", 200]]
        m["expected"]["ids"] = ["SKU-001", "SKU-002"]
        m["alternatives"] = ["ties in unspecified keys may differ"]
        self.assertEqual(self.v(c, m), "INVALID",
                         "coupled corruption must be INVALID (GT-D02)")
        cz, ez = self.case("n03-C04-retail-d01")
        mz = copy.deepcopy(ez)
        mz["expected"]["constraints"] = [["stock>", 0]]
        mz["expected"]["ids"] = sorted(
            i["id"] for i in cz["public_payload"]["items"]
            if i.get("stock", 0) > 0)
        mz["expected"]["order"] = None
        self.assertEqual(self.v(cz, mz), "INVALID",
                         "zh coupled corruption must be INVALID")
        c2, e2 = self.case("n03-C04-retail-d02")
        m2 = copy.deepcopy(e2)
        m2["expected"]["ids"] = list(reversed(m2["expected"]["ids"]))
        self.assertNotEqual(self.v(c2, m2), "VALID",
                            "declared sort sequence reversed")

    # GT-D03: recording/ISO/audit inclusion AND exclusion; undeclared
    # ties are AMBIGUOUS, never automatically VALID.
    def test_gtd03_c06_counterexamples(self):
        from eval_assurance.reference.oracle import validate_ground_truth

        def run(instr, options, choice, alternatives=(), need=None):
            case = {"case_id": "probe", "primitive": "C06",
                    "public_payload": {"instruction": instr,
                                       "options": options}}
            exp = {"case_id": "probe",
                   "expected": {"choice": choice,
                                "construction": {"need": need or {}}},
                   "alternatives": list(alternatives)}
            return validate_ground_truth(case, exp).verdict.value

        plans = [
            {"id": "P-CHEAP-NOREC", "price": 10, "seats": 10,
             "recording": False},
            {"id": "P-COSTLY-REC", "price": 99, "seats": 10,
             "recording": True},
        ]
        req = "Choose the cheapest plan offering at least 5 seats WITH " \
              "recording included. Emit exactly one plan id."
        self.assertEqual(run(req, plans, "P-CHEAP-NOREC",
                             need={"seats": 5, "recording": True}),
                         "INVALID",
                         "cheapest lacking recording must not validate")
        self.assertEqual(run(req, plans, "P-COSTLY-REC",
                             need={"seats": 5, "recording": True}),
                         "VALID")
        excl = "Choose the cheapest plan offering at least 5 seats " \
               "WITHOUT recording. Emit exactly one plan id."
        self.assertEqual(run(excl, plans, "P-COSTLY-REC",
                             need={"seats": 5, "recording": False}),
                         "INVALID")
        self.assertEqual(run(excl, plans, "P-CHEAP-NOREC",
                             need={"seats": 5, "recording": False}),
                         "VALID")
        tie = plans + [{"id": "P-TIE-REC", "price": 99, "seats": 10,
                        "recording": True}]
        self.assertEqual(run(req, tie, "P-COSTLY-REC",
                             need={"seats": 5, "recording": True}),
                         "AMBIGUOUS", "undeclared tie must be AMBIGUOUS")
        self.assertEqual(run(req, tie, "P-COSTLY-REC",
                             alternatives=("tie: P-COSTLY-REC or P-TIE-REC",),
                             need={"seats": 5, "recording": True}),
                         "VALID", "declared tie validates")
        zh = "选择提供至少5个席位且含录制的最便宜方案。只输出一个方案编号。"
        self.assertEqual(run(zh, plans, "P-CHEAP-NOREC",
                             need={"seats": 5, "recording": True}),
                         "INVALID", "zh 含录制 must filter")
        zh2 = "选择提供至少5个席位且不含录制的最便宜方案。只输出一个方案编号。"
        self.assertEqual(run(zh2, plans, "P-COSTLY-REC",
                             need={"seats": 5, "recording": False}),
                         "INVALID", "zh 不含录制 must filter")
        sups = [
            {"id": "S-NOISO", "price": 10, "iso": False, "audit": True},
            {"id": "S-BOTH", "price": 50, "iso": True, "audit": True},
            {"id": "S-NOAUDIT", "price": 20, "iso": True, "audit": False},
        ]
        self.assertEqual(run("Choose the cheapest supplier that passed "
                             "an audit. Emit exactly one supplier id.",
                             sups, "S-BOTH", need={"audit": True}),
                         "INVALID", "iso absent from instruction: no filter")
        self.assertEqual(run("Choose the cheapest supplier WITHOUT ISO "
                             "certification. Emit exactly one supplier id.",
                             sups, "S-BOTH", need={"iso": False}),
                         "INVALID", "negated iso must filter")

    # GT-D04: registry/required tags contradicting the PUBLIC objective
    # or descriptions are detected even when internally consistent.
    def test_gtd04_c08_hidden_construction(self):
        c, e = self.case("n03-C08-biztools-d00")
        m = copy.deepcopy(e)
        victim = "meeting_notifier"
        m["expected"]["tool_id"] = victim
        m["expected"]["construction"]["registry_tags"][victim] = \
            ["email", "send"]
        self.assertEqual(
            self.v(c, m), "INVALID",
            "coupled registry+answer mutation must be INVALID (GT-D04)")
        m = copy.deepcopy(e)
        m["expected"]["construction"]["required_tags"] = ["calendar", "post"]
        self.assertEqual(self.v(c, m), "INVALID",
                         "required tags contradicting the objective")
        m = copy.deepcopy(e)
        m["expected"]["construction"]["registry_tags"]["ghost"] = \
            ["email", "send"]
        self.assertEqual(self.v(c, m), "INVALID",
                         "registry references a tool absent publicly")
        m = copy.deepcopy(e)
        del m["expected"]["construction"]["registry_tags"]["email_sender"]
        self.assertEqual(self.v(c, m), "INVALID",
                         "public tool missing from registry")

    # GT-D05: formfill/formatting independently established; sequence
    # equality is not set equality.
    def test_gtd05_c03_recovered_cases(self):
        c, e = self.case("n03-C03-formfill-d00")
        self.assertEqual(self.v(c, e), "VALID",
                         "formfill independently established (GT-D05)")
        m = copy.deepcopy(e)
        m["expected"]["value"] = "+31-10-555999"
        self.assertEqual(self.v(c, m), "INVALID")
        m = copy.deepcopy(e)
        m["expected"]["field"] = "delivery_city"
        self.assertEqual(self.v(c, m), "INVALID")
        cf, ef = self.case("n03-C03-formatting-d02")
        self.assertEqual(self.v(cf, ef), "VALID",
                         "not_in_stock_upper independently established")
        c4, e4 = self.case("n03-C03-formatting-d00")
        m4 = copy.deepcopy(e4)
        m4["expected"]["lines"] = list(reversed(m4["expected"]["lines"]))
        self.assertEqual(self.v(c4, m4), "AMBIGUOUS",
                         "order-only difference: not silently VALID")


@unittest.skipUnless((PINNED / "n03_cases.public.jsonl").exists(),
                     "pinned Batch A snapshot not present")
class TestMutationTargetsRegression(unittest.TestCase):
    """The pinned mutation_targets.md comparator mutations (M-C0xa/b),
    represented in the permanent regression corpus via the response
    evaluation path (production comparator analogue) and the GT path."""

    @classmethod
    def setUpClass(cls):
        cls.dev, cls.exp = load_dev()

    def first(self, prim):
        for c in self.dev:
            if c["primitive"] == prim:
                return c, self.exp[c["case_id"]]
        raise AssertionError(prim)

    def eval(self, prim, raw):
        from eval_assurance.reference.oracle import evaluate_response
        c, e = self.first(prim)
        return evaluate_response(c, e, raw).verdict.value

    # M-C02a: unknown_flags ignored -> inconsistent flag claim
    def test_mc02a_unknown_flags_matter(self):
        c, e = self.first("C02")
        from eval_assurance.reference.oracle import validate_ground_truth
        truth = validate_ground_truth(c, e).recomputed
        resp = copy.deepcopy(truth)
        resp["deadline"] = None
        resp["unknown_flags"]["deadline"] = False   # inconsistent claim
        self.assertEqual(self.eval("C02", json.dumps(resp)),
                         "INCORRECT")

    # M-C02b: deadline comparison skipping ISO normalization
    def test_mc02b_deadline_exact(self):
        c, e = self.first("C02")
        from eval_assurance.reference.oracle import validate_ground_truth
        truth = validate_ground_truth(c, e).recomputed
        if truth["deadline"] is None:
            self.skipTest("no deadline surface in this case")
        resp = copy.deepcopy(truth)
        resp["deadline"] = truth["deadline"].replace("-", "/")
        self.assertEqual(self.eval("C02", json.dumps(resp)),
                         "INCORRECT")

    # M-C03a: line-set replaced by substring presence
    def test_mc03a_substring_not_sufficient(self):
        c, e = self.first("C03")
        from eval_assurance.reference.oracle import validate_ground_truth
        truth = validate_ground_truth(c, e).recomputed
        if isinstance(truth, dict):
            self.skipTest("formfill case")
        raw = " ".join(x[:3] for x in truth)
        self.assertEqual(self.eval("C03", raw), "INCORRECT")

    # M-C03b: whitespace tolerance without case accidents
    def test_mc03b_whitespace_tolerated(self):
        self.assertEqual(
            self.eval("C03", "  headlamp  \n\nmap case\n   trail jacket\n"),
            "CORRECT")

    # M-C03b': enumeration markers are contract violations
    def test_mc03b_markers_rejected(self):
        self.assertEqual(self.eval("C03", "- headlamp\n- map case"),
                         "INCORRECT")

    # M-C04a: subset check (extra ids escape)
    def test_mc04a_extra_id_rejected(self):
        c, e = self.first("C04")
        from eval_assurance.reference.oracle import validate_ground_truth
        truth = validate_ground_truth(c, e).recomputed
        extra = ", ".join(list(truth) + ["SKU-999"])
        self.assertEqual(self.eval("C04", extra), "INCORRECT")

    # M-C04b: declared sort order ignored
    def test_mc04b_sort_enforced(self):
        c, e = self.first("C04")
        from eval_assurance.reference.oracle import validate_ground_truth
        truth = validate_ground_truth(c, e).recomputed
        if not ((e.get("expected") or {}).get("order")):
            self.skipTest("first C04 case declares no sort")
        raw = ", ".join(reversed(truth))
        self.assertEqual(self.eval("C04", raw), "INCORRECT")

    # M-C05a: predicate boundary flipped at the threshold
    def test_mc05a_boundary(self):
        from eval_assurance.reference.oracle import validate_ground_truth
        c, e = self.first("C05")
        r = validate_ground_truth(c, e)
        self.assertEqual(r.verdict.value, "VALID")
        limit = (r.recomputed or {}).get("limit")
        if limit is None:
            self.skipTest("fulfillment family first case")
        c2 = copy.deepcopy(c)
        c2["public_payload"]["facts"] = \
            f"Purchase was {limit} days ago on the standard plan."
        self.assertEqual(validate_ground_truth(c2, e).recomputed[
            "decision"], True, "days == limit is within (at most)")

    # M-C06a: cheapest-qualifying replaced by cheapest-overall
    def test_mc06a_cheapest_overall_rejected(self):
        c, e = self.first("C06")
        from eval_assurance.reference.oracle import validate_ground_truth
        truth = validate_ground_truth(c, e).recomputed
        target = truth["choice"] if isinstance(truth, dict) else truth
        cheapest = min(c["public_payload"]["options"],
                       key=lambda o: o["price"])["id"]
        if cheapest == target:
            self.skipTest("cheapest overall already qualifies here")
        self.assertEqual(self.eval("C06", cheapest), "INCORRECT")

    # M-C06b: hard-constraint filter dropped for one attribute
    def test_mc06b_filter_dropped_rejected(self):
        from eval_assurance.reference.oracle import validate_ground_truth
        for c in self.dev:
            if c["primitive"] != "C06":
                continue
            e = self.exp[c["case_id"]]
            need = e["expected"]["construction"]["need"]
            if "recording" not in need or not need["recording"]:
                continue
            no_rec = [o for o in c["public_payload"]["options"]
                      if not o.get("recording")]
            if not no_rec:
                continue
            m = copy.deepcopy(e)
            m["expected"]["choice"] = min(
                no_rec, key=lambda o: o["price"])["id"]
            self.assertEqual(
                validate_ground_truth(c, m).verdict.value, "INVALID",
                "cheapest non-recording plan must be rejected")
            return
        self.skipTest("no recording-filtered case in corpus")

    # M-C07a: paraphrase normalization accepting swapped tokens
    def test_mc07a_no_paraphrase_acceptance(self):
        c, e = self.first("C07")
        from eval_assurance.reference.oracle import validate_ground_truth
        truth = validate_ground_truth(c, e).recomputed
        swapped = "_".join(reversed(truth.split("_")))
        self.assertEqual(self.eval("C07", swapped), "INCORRECT")

    # M-C08a: candidate-list membership check dropped
    def test_mc08a_hallucinated_id_rejected(self):
        self.assertEqual(self.eval("C08", "ghost_tool"), "INCORRECT")

    # M-C08b: capability-superset uniqueness dropped (GT path)
    def test_mc08b_uniqueness_enforced(self):
        from eval_assurance.reference.oracle import validate_ground_truth
        c, e = self.first("C08")
        con = e["expected"]["construction"]
        m = copy.deepcopy(e)
        m["expected"]["construction"]["registry_tags"] = {
            tid: sorted(set(con["required_tags"]))
            for tid in con["registry_tags"]}
        self.assertEqual(validate_ground_truth(c, m).verdict.value,
                         "INVALID",
                         "registry contradicting descriptions detected")


@unittest.skipUnless((PINNED / "n03_cases.public.jsonl").exists(),
                     "pinned Batch A snapshot not present")
class TestResponseEvaluationContract(unittest.TestCase):
    """Obligation B contract points that must never regress."""

    @classmethod
    def setUpClass(cls):
        cls.dev, cls.exp = load_dev()

    def first(self, prim):
        for c in self.dev:
            if c["primitive"] == prim:
                return c, self.exp[c["case_id"]]
        raise AssertionError(prim)

    def test_empty_output_is_its_own_class(self):
        from eval_assurance.reference.oracle import evaluate_response
        for prim in ("C01", "C02", "C03", "C04", "C05", "C06", "C07",
                     "C08"):
            c, e = self.first(prim)
            self.assertEqual(evaluate_response(c, e, "   \n").verdict.value,
                             "EMPTY_OUTPUT", prim)

    def test_software_error_never_model_failure(self):
        from eval_assurance.reference.oracle import evaluate_response
        c, e = self.first("C05")

        class Boom:
            def __getattr__(self, k):
                raise RuntimeError("exploded")
        bc = dict(c)
        bc["public_payload"] = Boom()
        self.assertEqual(evaluate_response(bc, e, "TRUE").verdict.value,
                         "NOT_EVALUABLE")

    def test_unestablished_truth_refuses_evaluation(self):
        from eval_assurance.reference.oracle import evaluate_response
        c, e = self.first("C02")
        c2 = copy.deepcopy(c)
        c2["public_payload"]["message"] = "Please handle it soon."
        r = evaluate_response(c2, e, json.dumps(e["expected"]))
        self.assertEqual(r.verdict.value, "NOT_EVALUABLE",
                         "no established truth -> NOT_EVALUABLE")

    def test_positive_negative_witnesses(self):
        from eval_assurance.reference.oracle import (evaluate_response,
                                                     validate_ground_truth)
        for prim in ("C01", "C02", "C03", "C04", "C05", "C06", "C07",
                     "C08"):
            c, e = self.first(prim)
            truth = validate_ground_truth(c, e).recomputed
            if prim == "C01":
                pos = truth
            elif prim == "C02":
                pos = json.dumps(truth)
            elif prim == "C03":
                pos = json.dumps(truth) if isinstance(truth, dict) \
                    else "\n".join(truth)
            elif prim == "C04":
                pos = ", ".join(truth)
            elif prim == "C05":
                pos = "TRUE" if truth["decision"] else "FALSE"
            else:
                pos = truth["choice"] if isinstance(truth, dict) else truth
            self.assertEqual(evaluate_response(c, e, pos).verdict.value,
                             "CORRECT", prim)
            self.assertIn(
                evaluate_response(c, e, "definitely not valid output")
                .verdict.value, ("INCORRECT", "NOT_EVALUABLE"), prim)


if __name__ == "__main__":
    unittest.main()
