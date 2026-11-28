"""Permanent regression coverage — Batch A requalification (48H-B-006).

The drill revocation stays durable (never un-revoked); the recovery
is a separate requalified certificate + fresh authoritative
generation + new scope-bound authorization; drills are isolated and
never modify the real registry.
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
AUTH2RQ = ROOT / "evidence" / "IJEVAL" / "AUTH2A_RQ"


class BatchARequalification(unittest.TestCase):
    def test_release_artifacts(self):
        rel = json.loads((AUTH2RQ / "release.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(rel["closes_blocker"], "48H-B-006")
        self.assertEqual(rel["experiment"],
                         "N03-AUTH2-DEVELOPMENT-BATCH-A-v2-RQ")
        self.assertEqual(rel["scope"]["slots"], 480)
        self.assertEqual(rel["authorization_checksum"],
                         json.loads((AUTH2RQ /
                                     "execution_authorization.json")
                                    .read_text(encoding="utf-8"))
                         ["authorization"]["checksum"])

    def test_fresh_gates_passed_live(self):
        gates = json.loads((AUTH2RQ / "fresh_gates.json")
                           .read_text(encoding="utf-8"))["gates"]
        self.assertTrue(gates["passed"])
        self.assertEqual(gates["gt_total"], 160)
        self.assertEqual(gates["gt_invalid"], [])
        self.assertEqual(gates["witness_failed"], [])
        self.assertEqual(gates["production_fault_escapes"], [])

    def test_canary_breaker_consumer(self):
        self.assertTrue(json.loads(
            (AUTH2RQ / "canary_integration.json")
            .read_text(encoding="utf-8"))["passed"])
        self.assertTrue(json.loads(
            (AUTH2RQ / "breaker_drill.json")
            .read_text(encoding="utf-8"))["passed"])
        cv = json.loads((AUTH2RQ / "consumer_verification.json")
                        .read_text(encoding="utf-8"))
        self.assertTrue(cv["issue_ok"])
        self.assertTrue(cv["revoked_refused"])
        self.assertTrue(cv["real_registry_untouched_by_drill"])

    def test_revoked_cert_stays_revoked(self):
        reg = json.loads(
            (EVID / "certificates" / "registry.json")
            .read_text(encoding="utf-8"))
        revoked = {r["certificate_id"] for r in reg["revocations"]}
        self.assertIn("512efb617a9cb4c8", revoked)
        # the requalified certificate is a NEW id, separately registered
        rq = [c for c in reg["certificates"]
              if c["protocol"].endswith("_RQ")]
        self.assertEqual(len(rq), 1)
        self.assertNotEqual(rq[0]["certificate_id"],
                            "512efb617a9cb4c8")

    def test_requalified_registration_references_only_valid_certs(self):
        rel = json.loads((AUTH2RQ / "release.json")
                         .read_text(encoding="utf-8"))
        self.assertNotIn("512efb617a9cb4c8", rel["certificate_ids"])
        reg = json.loads(
            (EVID / "certificates" / "registry.json")
            .read_text(encoding="utf-8"))
        rq_id = next(c["certificate_id"] for c in reg["certificates"]
                     if c["protocol"].endswith("_RQ"))
        self.assertIn(rq_id, rel["certificate_ids"])


if __name__ == "__main__":
    unittest.main()
