"""N03-B1 taxonomy contract tests (IJ-NANO-1.3S order 6.1).

Positive: the committed taxonomy validates; its digest is recorded.
Negative controls: every structural mutation the validator exists to catch
(missing primitive, extra field, batch drift, vocabulary violation,
isolation-label corruption, duplicate capability) must fail the validator.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TAXONOMY = ROOT / "evaluation" / "ij_nano" / "n03" / "taxonomy.json"
VALIDATOR = ROOT / "scripts" / "ij_nano" / "n03" / "validate_taxonomy.py"

sys.path.insert(0, str(ROOT / "scripts" / "ij_nano" / "n03"))
import validate_taxonomy as vt  # noqa: E402


def run_validator(doc: dict | None = None) -> list[str]:
    if doc is None:
        r = subprocess.run([sys.executable, "-I", str(VALIDATOR)],
                           capture_output=True, text=True, cwd=ROOT)
        return [] if r.returncode == 0 else [r.stderr]
    return vt._errors(doc, {})


class TestTaxonomyPositive(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(TAXONOMY.read_text(encoding="utf-8"))

    def test_committed_taxonomy_valid(self):
        self.assertEqual(run_validator(), [])

    def test_all_32_primitives_with_all_batches(self):
        self.assertEqual(len(self.doc["primitives"]), 32)
        for pid, p in self.doc["primitives"].items():
            self.assertEqual(p["batch"], vt.BATCH_OF[pid], pid)

    def test_diagnostic_isolation_examples_present(self):
        # order 6.1: supplying tool identity must not be reported as
        # autonomous tool selection - both selection primitives carry the
        # explicit diagnostic_isolation label
        for pid in ("C07", "C08"):
            self.assertEqual(
                self.doc["primitives"][pid]["capability_isolation"]["label"],
                "diagnostic_isolation", pid)

    def test_digest_stable_and_recorded(self):
        # freeze record: the mission state pins the taxonomy sha256; changing
        # the taxonomy requires updating this pin in the same commit (an
        # explicit identity change, never silent)
        digest = hashlib.sha256(TAXONOMY.read_bytes()).hexdigest()
        state = json.loads((ROOT / "MISSION_STATE_IJNANO_N03_PROGRESSIVE.json")
                           .read_text(encoding="utf-8"))
        self.assertEqual(state["taxonomy"]["sha256"], digest)
        self.assertEqual(state["gates"]["N03_TAXONOMY_CONTRACTS_FROZEN"],
                         "GRANTED")


class TestTaxonomyNegativeControls(unittest.TestCase):
    """Each mutation below is a defect class; the validator must catch it."""

    def setUp(self):
        self.base = json.loads(TAXONOMY.read_text(encoding="utf-8"))

    def _err(self, doc):
        errs = vt._errors(doc, {})
        self.assertTrue(errs, "validator missed the injected defect")
        return errs

    def test_missing_primitive_detected(self):
        del self.base["primitives"]["C17"]
        self._err(self.base)

    def test_extra_field_detected(self):
        self.base["primitives"]["C01"]["cognitive_description_note"] = None
        self._err(self.base)

    def test_batch_drift_detected(self):
        self.base["primitives"]["C09"]["batch"] = "A"
        self._err(self.base)

    def test_unknown_protocol_detected(self):
        self.base["primitives"]["C01"]["applicable_protocols"].append(
            "telepathy")
        self._err(self.base)

    def test_isolation_label_corruption_detected(self):
        self.base["primitives"]["C08"]["capability_isolation"]["label"] = \
            "fully_autonomous_tool_selection"
        self._err(self.base)

    def test_duplicate_capability_detected(self):
        self.base["primitives"]["C06"]["capability"] = \
            self.base["primitives"]["C05"]["capability"]
        self._err(self.base)

    def test_witness_depletion_detected(self):
        self.base["primitives"]["C22"]["correct_witnesses"] = ["only one"]
        self._err(self.base)

    def test_missing_required_field_detected(self):
        del self.base["primitives"]["C31"]["independent_ground_truth"]
        self._err(self.base)


if __name__ == "__main__":
    unittest.main()
