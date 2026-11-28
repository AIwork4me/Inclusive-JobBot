"""Permanent regression coverage — adapter-scope qualification
(48H-B-002, order 48H-SUPPORT §4)."""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "evidence" / "IJEVAL" / "ADAPTER_SCOPE"


class AdapterScopeRelease(unittest.TestCase):
    def test_release(self):
        rel = json.loads((ADAPTER / "release.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(rel["experiment"],
                         "N03-AUTH2-ADAPTER-ATLAS-v1")
        self.assertEqual(rel["scope"]["slots"], 1920)
        self.assertEqual(rel["scope"]["dev_cases"], 640)
        self.assertEqual(len(rel["scope"]["models"]), 3)
        self.assertIn("BLOCKED", rel["confirmation_status"])
        self.assertIn("admission battery", rel["status"])

    def test_identity_registry_honesty(self):
        ident = json.loads((ADAPTER / "identity_registry.json")
                           .read_text(encoding="utf-8"))
        self.assertTrue(ident["base_model"]["byte_verified_on_this_host"])
        for key, a in ident["adapters"].items():
            self.assertTrue(a["manifest_anchor_complete"], key)
            # W1-W3 are manifest-anchored, NOT claimed byte-verified
            self.assertFalse(a["byte_verified_on_this_host"], key)
            self.assertTrue(a["pinned_sha256"])

    def test_canary_all_four_batch_legs(self):
        canary = json.loads((ADAPTER / "canary_integration.json")
                            .read_text(encoding="utf-8"))
        self.assertTrue(canary["passed"])
        self.assertEqual(sorted(canary["batches"]),
                         ["A", "B", "C", "D"])
        for batch, fams in canary["batches"].items():
            self.assertTrue(all(fams.values()), batch)

    def test_roster_covers_all_640_dev_cases(self):
        ros = json.loads((ADAPTER / "adapter_dev_roster_1920.json")
                         .read_text(encoding="utf-8"))
        cases = {s["case_id"] for s in ros["slots"]}
        self.assertEqual(len(cases), 640)
        prims = {s["primitive"] for s in ros["slots"]}
        self.assertEqual(len(prims), 32)
        models = {s["model"] for s in ros["slots"]}
        self.assertEqual(models,
                         {"LFM3-1.7B+W1_pi", "LFM3-1.7B+W2_opencode",
                          "LFM3-1.7B+W3_hermes"})

    def test_consumer_verification(self):
        cv = json.loads((ADAPTER / "consumer_verification.json")
                        .read_text(encoding="utf-8"))
        self.assertTrue(cv["issue_ok"])


if __name__ == "__main__":
    unittest.main()
