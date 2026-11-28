#!/usr/bin/env python3
"""Fail-closed publication check around the sensitive-data scanner.

Mission order IJ-NANO-1.2 section 10: the scanner has been observed to
exit 0 even while reporting findings on some hosts, so the publication
decision must be made from the ACTUAL FINDING COUNT in the scanner
output, never from the exit code alone.

Fail-closed rules - publication is BLOCKED (exit 1) when any of these
holds:
- the scanner cannot be executed or times out;
- the scanner's summary line ("scanned N file(s): M finding(s)") is
  missing or unparseable;
- the reported finding count M is not zero;
- non-summary output lines disagree with the parsed count (count-parity
  guard against summary corruption);
- the exit code is non-zero while the parsed count is zero (unknown
  scanner state).

Usage:
    python scripts/tools/publish_check.py [--staged] [--root DIR]
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

_TIMEOUT_S = 600


def evaluate_output(stdout: str, stderr: str, code: int) -> tuple[bool, str]:
    """Decide from scanner output text alone (unit-testable core)."""
    out = (stdout + "\n" + stderr).strip()
    if not out:
        return False, "fail-closed: scanner produced no output"
    lines = [ln for ln in out.splitlines() if ln.strip()]
    # summary lines look like "... scanned 12 file(s): 3 finding(s)"
    summary_lines = [ln for ln in lines if re.search(
        r"scanned \d+ file\(s\): \d+ finding\(s\)", ln)]
    if not summary_lines:
        return False, "fail-closed: scanner summary line missing/unparseable"
    m = re.search(r"scanned (\d+) file\(s\): (\d+) finding\(s\)",
                  summary_lines[-1])
    files_scanned, findings = int(m.group(1)), int(m.group(2))
    finding_lines = [ln for ln in lines if ln not in summary_lines]
    parity = len(finding_lines)
    if findings != parity:
        return False, (f"fail-closed: finding-count parity mismatch "
                       f"(summary says {findings}, {parity} finding line(s) "
                       f"in output)")
    if findings > 0:
        return False, (f"BLOCKED: {findings} finding(s) across "
                       f"{files_scanned} scanned file(s) - resolve before "
                       f"publishing")
    if code != 0:
        return False, (f"fail-closed: scanner exit code {code} with zero "
                       f"parsed findings - unknown scanner state")
    return True, (f"publication check PASS: 0 findings across "
                  f"{files_scanned} scanned file(s)")


def run_scanner(scanner: pathlib.Path, root: pathlib.Path,
                staged: bool) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-I", str(scanner), "--root", str(root)]
    if staged:
        cmd.append("--staged")
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=_TIMEOUT_S)


def publish_check(root: pathlib.Path, staged: bool = False) -> tuple[bool, str]:
    scanner = root / "scripts" / "tools" / "scan_sensitive.py"
    if not scanner.exists():
        return False, f"fail-closed: scanner not found at {scanner}"
    try:
        proc = run_scanner(scanner, root, staged)
    except subprocess.TimeoutExpired:
        return False, "fail-closed: scanner timed out"
    except OSError as exc:
        return False, f"fail-closed: scanner could not be executed: {exc}"
    return evaluate_output(proc.stdout, proc.stderr, proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--staged", action="store_true",
                        help="check only staged files")
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    allowed, message = publish_check(root, args.staged)
    print(message)
    if not allowed:
        print("Details: run python scripts/tools/scan_sensitive.py"
              + (" --staged" if args.staged else ""))
    return 0 if allowed else 1


if __name__ == "__main__":
    sys.exit(main())
