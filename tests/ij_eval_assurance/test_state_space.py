"""EA02-R EA-D03 — systematic state-combination validation as a permanent
regression battery (runs the exhaustive/pairwise harness; the expected rule
model is independently authored and never calls the validator under test)."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "ij_eval_assurance"))

import ea02r_state_space as ss  # noqa: E402


class TestStateSpace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stats = ss.run_battery()

    def test_no_escaping_invalid_combinations(self):
        self.assertEqual(self.stats["escapes"], [])

    def test_no_false_rejections(self):
        self.assertEqual(self.stats["false_rejections"], [])

    def test_every_declared_invariant_exercised(self):
        self.assertEqual(len(self.stats["rule_firing_counts"]), 24,
                         "all 24 declared invariants must fire at least once")

    def test_all_malformed_type_injections_rejected(self):
        self.assertEqual(self.stats["malformed_rejected"],
                         self.stats["malformed_injections"])

    def test_generated_counts(self):
        # 8,640 cognitive + 96 business + 216 evaluator + 360 evidence
        self.assertEqual(self.stats["generated"], 8640 + 96 + 216 + 360)
        self.assertGreater(self.stats["model_legal"], 0)
        self.assertGreater(self.stats["model_illegal"], 0)


if __name__ == "__main__":
    unittest.main()
