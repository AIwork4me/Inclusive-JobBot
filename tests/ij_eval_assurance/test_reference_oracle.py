"""EA03 — independent reference oracle regression (N03 Batch A dev corpus).

Pins the ground-truth qualification of the 160 development cases at the
pinned IJ-NANO revision: 133 VALID / 27 NOT_ESTABLISHED / 0 INVALID.
Any dataset change or oracle regression that shifts these numbers fails
here. Runs only when the sibling IJNANO worktree is present."""
from __future__ import annotations

import collections
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

N03 = ROOT.parent / "IJNANO" / "evaluation" / "ij_nano" / "n03" / "dataset"


@unittest.skipUnless((N03 / "public" / "n03_cases.public.jsonl").exists(),
                     "IJNANO sibling worktree / Batch A not present")
class TestGroundTruthQualification(unittest.TestCase):
    def run_oracle(self):
        from eval_assurance.reference.oracle import validate_ground_truth
        pub = [json.loads(l) for l in (N03 / "public" /
                                       "n03_cases.public.jsonl")
               .read_text(encoding="utf-8").splitlines()]
        exp = {r["case_id"]: r for r in (
            json.loads(l) for l in (N03 / "expectations" /
                                    "n03_dev_expectations.jsonl")
            .read_text(encoding="utf-8").splitlines())}
        dev = [c for c in pub if c["split"] == "development"
               and c["primitive"] in {f"C0{i}" for i in range(1, 9)}]
        self.assertEqual(len(dev), 160)
        stats = collections.Counter()
        for c in dev:
            stats[validate_ground_truth(
                c, exp.get(c["case_id"])).verdict.value] += 1
        return stats

    def test_pinned_qualification_numbers(self):
        stats = self.run_oracle()
        self.assertEqual(stats["VALID"], 133)
        self.assertEqual(stats["INVALID"], 0)
        self.assertEqual(stats["AMBIGUOUS"], 0)
        self.assertEqual(stats["NOT_ESTABLISHED"], 27)

    def test_fully_recomputable_primitives_are_20_20(self):
        from eval_assurance.reference.oracle import validate_ground_truth
        pub = [json.loads(l) for l in (N03 / "public" /
                                       "n03_cases.public.jsonl")
               .read_text(encoding="utf-8").splitlines()]
        exp = {r["case_id"]: r for r in (
            json.loads(l) for l in (N03 / "expectations" /
                                    "n03_dev_expectations.jsonl")
            .read_text(encoding="utf-8").splitlines())}
        for prim in ("C02", "C04", "C05", "C06", "C08"):
            cases = [c for c in pub if c["split"] == "development"
                     and c["primitive"] == prim]
            verdicts = [validate_ground_truth(c, exp.get(c["case_id"])).verdict
                        .value for c in cases]
            self.assertEqual(verdicts.count("VALID"), 20, prim)

    def test_oracle_imports_no_ij_nano_code(self):
        import inspect
        from eval_assurance.reference import oracle
        src = inspect.getsource(oracle)
        for banned in ("from evaluation", "import evaluation",
                       "from n02r", "import n02r", "from benchmarks",
                       "import benchmarks"):
            self.assertNotIn(banned, src)


if __name__ == "__main__":
    unittest.main()
