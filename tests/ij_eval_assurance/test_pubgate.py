"""EA02-R EA-D06 — publication process gate bypass tests.

Every injected failure mode must fail closed at the implemented publication
boundary: nonzero process exit, zero exit with findings, truncated output,
piped command failure, changed staged content after qualification, missing
receipt. Plus the live regression proof that a shell pipeline masks the
BLOCKED exit status (the incident that motivated the wrapper)."""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ij_eval_assurance"))

import pubgate  # noqa: E402
from pubgate import (GateFailure, parse_gate_output, run_gate,
                     staged_identity, verify_receipt)


def script_cmd(tmp: pathlib.Path, body: str) -> list[str]:
    p = tmp / "fake_check.py"
    p.write_text(body, encoding="utf-8")
    return [sys.executable, "-I", str(p)]


class TestParseGateOutput(unittest.TestCase):
    def test_pass_and_block_parsed(self):
        self.assertEqual(parse_gate_output(
            "publication check PASS: 0 findings across 3 scanned"),
            ("PASS", 0))
        self.assertEqual(parse_gate_output(
            "BLOCKED: 2 finding(s) across 3 scanned file(s) - resolve"),
            ("BLOCKED", 2))

    def test_malformed_and_truncated_fail_closed(self):
        for bad in ("", "   ", "publication check PAS",
                    "publication check PASS: 0 find",
                    "BLOCKED: finding(s)", "random output\nlines"):
            with self.assertRaises(GateFailure, msg=repr(bad)):
                parse_gate_output(bad)


class TestRunGateInjections(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmpdir = pathlib.Path(self.tmp.name)
        self.receipts = self.tmpdir / "receipts"

    def test_nonzero_exit_fail_closed(self):
        cmd = script_cmd(self.tmpdir,
                         "import sys; print('publication check PASS: 0 "
                         "findings'); sys.exit(1)")
        with self.assertRaises(GateFailure):
            run_gate(ROOT, check_cmd=cmd, receipts_dir=self.receipts)

    def test_zero_exit_with_findings_fail_closed(self):
        cmd = script_cmd(self.tmpdir,
                         "print('BLOCKED: 5 finding(s) across 9 file(s)')")
        with self.assertRaises(GateFailure):
            run_gate(ROOT, check_cmd=cmd, receipts_dir=self.receipts)

    def test_truncated_output_fail_closed(self):
        cmd = script_cmd(self.tmpdir, "print('publication check PASS: 0 fi')")
        with self.assertRaises(GateFailure):
            run_gate(ROOT, check_cmd=cmd, receipts_dir=self.receipts)

    def test_empty_output_fail_closed(self):
        cmd = script_cmd(self.tmpdir, "pass")
        with self.assertRaises(GateFailure):
            run_gate(ROOT, check_cmd=cmd, receipts_dir=self.receipts)

    def test_pass_on_real_staged_content(self):
        # nothing sensitive staged right now -> the real check must PASS and
        # write a receipt
        receipt = run_gate(ROOT, receipts_dir=self.receipts)
        self.assertTrue(receipt["passed"])
        self.assertIn("receipt_path", receipt)
        # receipt is verifiable
        rpath = ROOT / receipt["receipt_path"]
        loaded = verify_receipt(rpath)
        self.assertTrue(loaded["passed"])

    def test_changed_staged_content_during_check_fail_closed(self):
        # the "check" stages a NEW file mid-run: staged identity changes
        probe = ROOT / "ea02r_gate_probe_midrun.txt"
        cmd = script_cmd(self.tmpdir, (
            "import pathlib, subprocess, sys\n"
            f"p = pathlib.Path(r'{probe}')\n"
            "p.write_text('mid-run staging', encoding='utf-8')\n"
            "subprocess.run(['git', 'add', str(p)], check=True)\n"
            "print('publication check PASS: 0 findings')\n"))
        try:
            with self.assertRaises(GateFailure) as cm:
                run_gate(ROOT, check_cmd=cmd, receipts_dir=self.receipts)
            self.assertIn("staged content changed", str(cm.exception))
        finally:
            subprocess.run(["git", "restore", "--staged", str(probe)],
                           cwd=ROOT, capture_output=True)
            probe.unlink(missing_ok=True)

    def test_missing_receipt_fails(self):
        with self.assertRaises(GateFailure):
            verify_receipt(self.tmpdir / "does_not_exist.json")

    def test_corrupt_receipt_fails(self):
        p = self.tmpdir / "corrupt.json"
        p.write_text("{not json", encoding="utf-8")
        with self.assertRaises(GateFailure):
            verify_receipt(p)

    def test_receipt_missing_key_fails(self):
        p = self.tmpdir / "incomplete.json"
        p.write_text('{"parsed_verdict": "PASS"}', encoding="utf-8")
        with self.assertRaises(GateFailure):
            verify_receipt(p)


class TestPipeMaskingRegression(unittest.TestCase):
    """The original incident: shell pipelines hide the BLOCKED exit status.
    pubgate launches via argv (no shell), so masking is structurally
    impossible there; this test pins the motivating behavior."""

    def test_pipeline_masks_blocked_exit_status(self):
        probe = ROOT / "ea02r_gate_probe_tmp.txt"
        # scanner-detectable content: the REAL local identity resolved at
        # runtime (never hardcoded in this source file)
        import pathlib
        probe.write_text(f"local path {pathlib.Path.home()}\n",
                         encoding="utf-8")
        try:
            subprocess.run(["git", "add", str(probe)], cwd=ROOT, check=True,
                           capture_output=True)
            direct = subprocess.run(
                [sys.executable, "-I",
                 str(ROOT / "scripts/tools/publish_check.py"), "--staged"],
                cwd=ROOT, capture_output=True, text=True)
            piped = subprocess.run(
                f'"{sys.executable}" -I scripts/tools/publish_check.py '
                "--staged | tail -1",
                cwd=ROOT, shell=True, capture_output=True, text=True)
            self.assertNotEqual(direct.returncode, 0)   # genuinely BLOCKED
            self.assertEqual(piped.returncode, 0)       # pipe masks it!
            # and the wrapper, given the same blocked state, fails closed:
            with self.assertRaises(GateFailure):
                run_gate(ROOT, receipts_dir=pathlib.Path(
                    tempfile.mkdtemp()) / "receipts")
        finally:
            subprocess.run(["git", "restore", "--staged", str(probe)],
                           cwd=ROOT, capture_output=True)
            probe.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
