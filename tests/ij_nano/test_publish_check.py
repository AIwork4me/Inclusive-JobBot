"""Synthetic scanner control for the fail-closed publication check
(mission order IJ-NANO-1.2 section 10).

The publication decision must come from the ACTUAL FINDING COUNT in the
scanner output, never from the exit code alone. These controls use only
synthetic, documentation-example strings (the classic AWS docs example
key) - no real personal information is introduced anywhere.
"""
import importlib.util
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
CHECK = REPO / "scripts" / "tools" / "publish_check.py"
SCANNER = REPO / "scripts" / "tools" / "scan_sensitive.py"

# Synthetic, documentation-example strings (never real credentials).
# Assembled at runtime from fragments so the repository copy contains no
# literal credential-shaped string that the scanner itself would flag.
SYNTHETIC_AWS_EXAMPLE_KEY = "AKIA" + "IOSFODNN7" + "EXAMPLE"


def _load_check():
    spec = importlib.util.spec_from_file_location("publish_check", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFailClosedDecision(unittest.TestCase):
    """Unit controls over the decision core: output text decides."""

    def setUp(self):
        self.pc = _load_check()

    def test_clean_output_allows(self):
        ok, msg = self.pc.evaluate_output(
            "scanned 3 file(s): 0 finding(s)\n", "", 0)
        self.assertTrue(ok, msg)

    def test_findings_block_regardless_of_exit_code(self):
        # THE regression this gate exists for: exit code 0 WITH findings
        # (observed on some hosts) must still block.
        out = ("docs/x.md:4: credential-shaped string (aws_access_key)\n"
               "scanned 12 file(s): 1 finding(s)\n")
        for code in (0, 1):
            with self.subTest(exit_code=code):
                ok, _ = self.pc.evaluate_output(out, "", code)
                self.assertFalse(ok)

    def test_missing_summary_blocks(self):
        ok, _ = self.pc.evaluate_output("everything looks fine, trust me\n", "", 0)
        self.assertFalse(ok)

    def test_empty_output_blocks(self):
        ok, _ = self.pc.evaluate_output("", "", 0)
        self.assertFalse(ok)

    def test_count_parity_mismatch_blocks(self):
        # summary says 0 findings but a finding line is present
        ok, _ = self.pc.evaluate_output(
            "a.txt:1: credential-shaped string (aws_access_key)\n"
            "scanned 2 file(s): 0 finding(s)\n", "", 0)
        self.assertFalse(ok)

    def test_nonzero_exit_with_zero_findings_blocks(self):
        ok, _ = self.pc.evaluate_output("scanned 2 file(s): 0 finding(s)\n",
                                        "", 3)
        self.assertFalse(ok)


class TestEndToEndSyntheticControl(unittest.TestCase):
    """Full pipeline: a synthetic credential-shaped file must BLOCK the
    publication check through the real scanner."""

    def test_synthetic_finding_blocks_publication(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="ij_nano_pubchk_"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "scripts" / "tools").mkdir(parents=True)
        shutil.copy(SCANNER, tmp / "scripts" / "tools" / "scan_sensitive.py")
        # no .git -> the scanner scans the working tree (pre-first-commit
        # path), so a plain file is scanned without any git machinery
        (tmp / "synthetic_control.txt").write_text(
            f"aws_access_key = {SYNTHETIC_AWS_EXAMPLE_KEY}\n",
            encoding="utf-8")
        pc = _load_check()
        ok, msg = pc.publish_check(tmp, staged=False)
        self.assertFalse(ok, "synthetic finding must block publication")
        self.assertIn("finding", msg)

    def test_clean_tree_allows(self):
        pc = _load_check()
        ok, msg = pc.publish_check(REPO, staged=False)
        self.assertTrue(ok, msg)

    def test_cli_exit_codes(self):
        ok_code = subprocess.run(
            [sys.executable, "-I", str(CHECK), "--root", str(REPO)],
            capture_output=True, text=True)
        self.assertEqual(ok_code.returncode, 0, ok_code.stdout)


if __name__ == "__main__":
    unittest.main()
