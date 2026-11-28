"""Permanent regression coverage — HF native harness verifier
qualification framework (48H-B-003 EAE side)."""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance.qualification import hf_verifiers as hv  # noqa: E402


def _chain(steps):
    prev = None
    for s in steps:
        s["state_digest"] = hv._digest_obj({"prev": prev,
                                            "state": s["state"]})
        prev = s["state_digest"]
    return steps


def _evidence(answer="42", rule="exact_match", expected="42"):
    trace = _chain([
        {"state": {"cwd": "/sandbox", "files": {"data.csv": "1,2"}}},
        {"state": {"cwd": "/sandbox", "files": {"data.csv": "1,2"},
                   "answer": answer}},
    ])
    return {
        "task_id": "smol-0001",
        "trace": trace,
        "claimed_verdict": True,
        "verifier": {"rule": rule, "answer_field": "answer",
                     "expected": expected},
        "network_policy": "deny-all",
        "resource_bounds": {"max_memory_mb": 2048, "cpu_seconds": 60},
        "protected_access": [],
    }


class PinValidation(unittest.TestCase):
    _PIN = {
        "task_id": "smol-0001",
        "dataset_revision": "abc123",
        "environment_image_digest": "a" * 64,
        "verifier_digest": "b" * 64,
        "reference_solution_digest": "c" * 64,
        "sampling_policy": "one attempt, temperature 0.8",
        "max_agent_steps": 30,
        "token_limits": {"context": 65536},
        "context_config": {"thinking": True},
        "timeout_s": 600,
        "training_overlap": "UNCERTAIN",
        "overlap_note": "selection rule cannot prove disjointness",
    }

    def test_complete_pin_valid(self):
        self.assertTrue(hv.validate_verifier_pin(self._PIN)["valid"])

    def test_missing_field_rejected(self):
        pin = {k: v for k, v in self._PIN.items()
               if k != "verifier_digest"}
        r = hv.validate_verifier_pin(pin)
        self.assertFalse(r["valid"])
        self.assertIn("missing pin field: verifier_digest", r["problems"])

    def test_uncertain_overlap_requires_note(self):
        pin = dict(self._PIN, overlap_note="")
        self.assertFalse(hv.validate_verifier_pin(pin)["valid"])

    def test_bad_digest_rejected(self):
        pin = dict(self._PIN, verifier_digest="not-a-digest")
        self.assertFalse(hv.validate_verifier_pin(pin)["valid"])


class SandboxEvidence(unittest.TestCase):
    def test_valid_evidence_passes(self):
        r = hv.verify_sandbox_evidence(_evidence())
        self.assertTrue(r["valid"], r["problems"])
        self.assertIs(r["recomputed_verdict"], True)

    def test_wrong_claimed_verdict_detected(self):
        ev = _evidence()
        ev["claimed_verdict"] = False
        r = hv.verify_sandbox_evidence(ev)
        self.assertFalse(r["valid"])

    def test_host_path_leak_detected(self):
        ev = _evidence()
        ev["trace"] = _chain([
            {"state": {"cmd": "cat C:/Users/secret/data.csv"}}])
        r = hv.verify_sandbox_evidence(ev)
        self.assertFalse(r["valid"])
        self.assertTrue(any("host filesystem" in p
                            for p in r["problems"]))

    def test_protected_access_detected(self):
        ev = _evidence()
        ev["protected_access"] = ["hidden_tests"]
        r = hv.verify_sandbox_evidence(ev)
        self.assertFalse(r["valid"])
        self.assertTrue(any("hidden_tests" in p for p in r["problems"]))

    def test_mid_trace_tamper_breaks_chain(self):
        ev = _evidence()
        ev["trace"][0]["state"]["injected"] = True   # no re-chain
        r = hv.verify_sandbox_evidence(ev)
        self.assertFalse(r["valid"])
        self.assertTrue(any("chain broken" in p for p in r["problems"]))


class MutationBattery(unittest.TestCase):
    def test_answer_flip_flips_verdict(self):
        r = hv.mutation_battery(_evidence())
        self.assertTrue(r["passed"], r["controls"])
        by = {c["control"]: c["passed"] for c in r["controls"]}
        self.assertTrue(by["answer_flip_flips_verdict"])
        self.assertTrue(by["mid_trace_tamper_rejected"])

    def test_numeric_match_tolerance(self):
        ev = _evidence(answer="41.999", rule="numeric_match",
                       expected="42")
        ev["verifier"]["tolerance"] = 0.01
        r = hv.verify_sandbox_evidence(ev)
        self.assertTrue(r["valid"], r["problems"])
        ev2 = _evidence(answer="41.9", rule="numeric_match",
                        expected="42")
        ev2["verifier"]["tolerance"] = 0.01
        r2 = hv.verify_sandbox_evidence(ev2)
        self.assertFalse(r2["valid"])


class FailClosed(unittest.TestCase):
    def test_no_assets_blocks(self):
        r = hv.qualify_verifier_suite([], [], [])
        self.assertEqual(r["verdict"], "BLOCKED_PENDING_ASSETS")

    def test_full_suite_qualifies_on_synthetic_assets(self):
        pin = {
            "task_id": "smol-0001", "dataset_revision": "r1",
            "environment_image_digest": "a" * 64,
            "verifier_digest": "b" * 64,
            "reference_solution_digest": "c" * 64,
            "sampling_policy": "one attempt",
            "max_agent_steps": 30, "token_limits": {"context": 65536},
            "context_config": {}, "timeout_s": 600,
            "training_overlap": "NONE",
        }
        r = hv.qualify_verifier_suite(
            [pin], [_evidence()],
            [{"class": "LOCAL_REPRODUCTION",
              "differences_documented": True}])
        self.assertEqual(r["verdict"], "QUALIFIED", r)
        r2 = hv.qualify_verifier_suite(
            [pin], [_evidence()],
            [{"class": "NOT_A_CLASS"}])
        self.assertEqual(r2["verdict"], "NOT_QUALIFIED")


if __name__ == "__main__":
    unittest.main()
