"""N03-B2/B3 + D01/D02 dataset regression tests (IJ-NANO-1.3S).

Covers: build determinism against the committed roster digests, roster-derived
slot accounting (Batch A scope + engine negatives), verification report
invariants, public-artifact leakage, protected-confirmation exclusion from
git, and taxonomy conformance evidence.
"""
from __future__ import annotations

import json
import pathlib
import random
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "ij_nano" / "n03"))

BASE = ROOT / "evaluation" / "ij_nano" / "n03"
EVID = ROOT / "evidence" / "IJNANO" / "N03" / "dataset"


def _load_jsonl(p: pathlib.Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]


class TestBuildDeterminism(unittest.TestCase):
    def test_dev_roster_reproduces_committed_digest(self):
        """Regenerating the development roster from the committed seed must
        reproduce the committed public digest bit-for-bit."""
        from evaluation.ij_nano.n03.dataset import (DEV_SEED,
                                                FAMILIES_BY_PRIMITIVE)
        from evaluation.ij_nano.n03.dataset.core import roster_digest
        cases = []
        for prim in sorted(FAMILIES_BY_PRIMITIVE):
            for fam in FAMILIES_BY_PRIMITIVE[prim]:
                if fam.split != "development":
                    continue
                for seq in range(10):
                    lang = "en" if seq % 2 == 0 else "zh"
                    rng = random.Random(f"{DEV_SEED}:{fam.family_id}:{seq}")
                    cases.append(fam.emit(rng, lang, seq))
        manifest = json.loads((EVID / "build_manifest.json")
                              .read_text(encoding="utf-8"))
        # public digest covers dev+conf; compare the dev half via the
        # dev-only expectation digest instead
        from evaluation.ij_nano.n03.dataset.core import expected_digest
        self.assertEqual(expected_digest(cases),
                         manifest["dev_expectations_digest"])

    def test_build_manifest_counts(self):
        m = json.loads((EVID / "build_manifest.json")
                       .read_text(encoding="utf-8"))
        self.assertEqual(m["dev_cases"], 640)
        self.assertEqual(m["confirmation_cases"], 320)
        for k, want in (("development:en", 320), ("development:zh", 320),
                        ("confirmation:en", 160), ("confirmation:zh", 160)):
            self.assertEqual(m["counts"].get(k), want, k)


class TestSlotAccounting(unittest.TestCase):
    def test_batch_a_manifest_consistency(self):
        import slot_accounting as sa
        roster = _load_jsonl(BASE / "dataset" / "public" /
                             "n03_cases.public.jsonl")
        registry = json.loads((BASE / "model_registry.json")
                              .read_text(encoding="utf-8"))
        manifest, errors = sa.account(roster, registry)
        self.assertEqual(errors, [])
        self.assertEqual(manifest["primitives_built"], 32)
        self.assertTrue(manifest["complete"])       # full 960-case roster
        t = manifest["totals"]
        self.assertEqual((t["dev_cases"], t["conf_cases"],
                          t["dev_slots"], t["conf_slots"],
                          t["primary_slots"]),
                         (640, 320, 1920, 960, 2880))
        for b in "ABCD":
            self.assertEqual(manifest["per_batch"][b]["primitives"], 8, b)
        # committed manifest matches fresh accounting
        committed = json.loads((EVID / "slot_manifest.json")
                               .read_text(encoding="utf-8"))
        self.assertEqual(committed["totals"], t)

    def test_engine_rejects_duplicate_ids(self):
        import slot_accounting as sa
        roster = _load_jsonl(BASE / "dataset" / "public" /
                             "n03_cases.public.jsonl")
        registry = json.loads((BASE / "model_registry.json")
                              .read_text(encoding="utf-8"))
        roster.append(dict(roster[0]))             # duplicate id
        _, errors = sa.account(roster, registry)
        self.assertTrue(any("duplicate" in e for e in errors))

    def test_engine_rejects_misclassified_split(self):
        import slot_accounting as sa
        roster = _load_jsonl(BASE / "dataset" / "public" /
                             "n03_cases.public.jsonl")
        registry = json.loads((BASE / "model_registry.json")
                              .read_text(encoding="utf-8"))
        roster[0]["split"] = "validation"          # invalid split
        _, errors = sa.account(roster, registry)
        self.assertTrue(any("misclassified" in e for e in errors))

    def test_engine_rejects_wrong_case_count(self):
        import slot_accounting as sa
        roster = _load_jsonl(BASE / "dataset" / "public" /
                             "n03_cases.public.jsonl")
        registry = json.loads((BASE / "model_registry.json")
                              .read_text(encoding="utf-8"))
        dropped = [r for r in roster if r["case_id"] !=
                   "n03-C01-helpdesk-d00"]          # one dev case removed
        manifest, errors = sa.account(dropped, registry)
        self.assertTrue(any("dev cases !=" in e for e in errors))


class TestVerificationReport(unittest.TestCase):
    def setUp(self):
        self.rep = json.loads((EVID / "verification_report.json")
                              .read_text(encoding="utf-8"))

    def test_pass_with_full_battery(self):
        self.assertEqual(self.rep["result"], "PASS")
        self.assertEqual(self.rep["public_cases"], 960)
        self.assertEqual(self.rep["truth_rederivations"], 960)
        self.assertEqual(self.rep["mutation_battery"]["escaped"], 0)
        self.assertEqual(self.rep["mutation_battery"]["detected"], 960)
        self.assertEqual(self.rep["problems"], [])

    def test_limitations_declared(self):
        joined = " ".join(self.rep["limitations"])
        self.assertIn("dual-implementation", joined)


class TestProtectionAndLeakage(unittest.TestCase):
    def test_no_forbidden_keys_in_public_artifacts(self):
        from evaluation.ij_nano.n03.dataset.verify import _forbidden_keys
        rows = _load_jsonl(BASE / "dataset" / "public" /
                           "n03_cases.public.jsonl")
        for r in rows:
            self.assertEqual(_forbidden_keys(r["public_payload"]), [],
                             r["case_id"])

    def test_confirmation_expectations_not_tracked_by_git(self):
        r = subprocess.run(["git", "ls-files",
                            "evaluation/ij_nano/n03/protected"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "")
        r2 = subprocess.run(
            ["git", "check-ignore", "--quiet",
             "evaluation/ij_nano/n03/protected/confirmation_seed.json"],
            cwd=ROOT)
        self.assertEqual(r2.returncode, 0, "protected seed must be ignored")

    def test_public_roster_has_no_confirmation_expectations_inline(self):
        rows = _load_jsonl(BASE / "dataset" / "public" /
                           "n03_cases.public.jsonl")
        dev_ids = {r["case_id"] for r in _load_jsonl(
            BASE / "dataset" / "expectations" /
            "n03_dev_expectations.jsonl")}
        conf_public = [r["case_id"] for r in rows
                       if r["split"] == "confirmation"]
        self.assertTrue(conf_public)
        self.assertFalse(set(conf_public) & dev_ids)

    def test_protected_manifest_is_hash_only(self):
        p = EVID / "confirmation_protected_manifest.json"
        m = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(m["case_count"], 320)
        self.assertNotIn("expected", json.dumps(m))
        self.assertEqual(len(m["expectations_sha256"]), 64)


class TestBatchAPreservation(unittest.TestCase):
    def test_batch_a_records_preserved_bit_identical(self):
        rep = json.loads((EVID / "batch_a_preservation.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(rep["batch_a_records_missing_from_full_roster"], 0)
        self.assertEqual(rep["batch_a_dev_expectations_missing"], 0)
        self.assertEqual(rep["batch_a_public_records"], 240)


class TestSchemaConformanceEvidence(unittest.TestCase):
    def test_claim_matches_engine_availability(self):
        rep = json.loads((EVID / "schema_conformance.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(rep["result"], "PASS")
        self.assertTrue(rep["taxonomy_identity_unchanged"])
        if rep["jsonschema_engine"]["available"]:
            self.assertIn("executed", rep["claim"])
        else:
            self.assertIn("NOT claimed", rep["claim"])


if __name__ == "__main__":
    unittest.main()
