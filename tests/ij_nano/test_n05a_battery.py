"""N05A battery qualification: positives pass, every negative fails for
exactly its single declared reason; coverage spans all twelve families."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.eval import CognitiveEvaluator  # noqa: E402
from nanoagent.eval.contracts import FAMILIES  # noqa: E402


class TestControlBattery(unittest.TestCase):
    def setUp(self):
        self.ev = CognitiveEvaluator()
        self.cases = {c.case_id: c for c in
                      [self._case(cid) for cid in self.ev.case_ids()]}

    def _case(self, case_id):
        # reach the registry entry through evaluate-only API is not possible
        # by design; tests use the coverage/describe metadata + controls
        from nanoagent.eval.controls import battery
        return {c.case_id: c for c in battery()}[case_id]

    def test_all_positives_pass(self):
        for cid in self.ev.case_ids():
            meta = self.ev.describe(cid)
            if meta["control_class"] != "positive":
                continue
            c = self._case(cid)
            r = self.ev.evaluate(cid, c.response)
            self.assertTrue(r.passed, f"{cid}: {r.reasons}")

    def test_every_negative_fails_for_its_single_intended_reason(self):
        negatives = 0
        for cid in self.ev.case_ids():
            meta = self.ev.describe(cid)
            if not meta["control_class"].startswith("negative:"):
                continue
            negatives += 1
            intended = meta["control_class"].split(":", 1)[1]
            c = self._case(cid)
            r = self.ev.evaluate(cid, c.response)
            self.assertFalse(r.passed, f"{cid} unexpectedly passed")
            self.assertEqual(r.reasons, (intended,),
                             f"{cid} failed for the wrong reason: {r.reasons}")
        self.assertGreaterEqual(negatives, 20)

    def test_coverage_spans_all_twelve_families(self):
        cov = self.ev.coverage()
        self.assertEqual(set(cov), set(FAMILIES))
        for fam, c in cov.items():
            self.assertGreaterEqual(c["positives"], 1, fam)
            self.assertGreaterEqual(c["negatives"], 1, fam)

    def test_runtime_never_receives_expectations(self):
        # The runtime-facing API is evaluate/describe/case_ids only; Response
        # objects carry no expectation fields (structural enforcement).
        import inspect
        from nanoagent.eval.contracts import Response
        fields = {f.name for f in __import__("dataclasses").fields(Response)}
        banned = {"expectation", "expected", "answer", "reason", "control_class"}
        self.assertFalse(fields & banned, fields)

    def test_unknown_case_raises(self):
        from nanoagent.eval import CaseNotFound
        from nanoagent.eval.contracts import Response
        with self.assertRaises(CaseNotFound):
            self.ev.evaluate("no.such.case", Response())


if __name__ == "__main__":
    unittest.main()
