#!/usr/bin/env python3
"""EA02-R EA-D06 — fail-closed publication process gate.

Replaces ad-hoc ``publish_check.py | tail`` invocations (which mask the exit
status — observed live in the previous session, evidence
``evidence/IJEVAL/EA02R/red_reproduction.json`` EA_D06) with a wrapper that:

- launches the check via an argv list (no shell, no pipeline — a masked
  exit status is structurally impossible);
- captures the process exit code DIRECTLY and parses the finding count from
  the output (verdict from parsed counts, never the exit code alone);
- fails closed on missing, malformed or truncated gate output;
- binds the check to the actual staged-content identity (hash of staged
  paths+blob-shas before and after the check; a post-check change fails);
- writes an auditable receipt for every run;
- refuses to commit while BLOCKED (``commit`` subcommand).

Exit codes: 0 = PASS, 1 = BLOCKED/failed-closed, 2 = usage/other error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CHECK = [sys.executable, "-I",
                 str(ROOT / "scripts" / "tools" / "publish_check.py"),
                 "--staged"]
DEFAULT_RECEIPTS = ROOT / "evidence" / "IJEVAL" / "EA02R" / "pubgate_receipts"

_PASS_RE = re.compile(r"publication check PASS: (\d+) finding")
_BLOCK_RE = re.compile(r"BLOCKED: (\d+) finding")


class GateFailure(RuntimeError):
    """Fail-closed gate result (message explains the trigger)."""


def staged_identity(repo: pathlib.Path) -> str:
    """Content identity of the staged set: sorted (mode,path,sha) entries."""
    ls = subprocess.run(["git", "ls-files", "--cached", "-s"],
                        cwd=repo, capture_output=True, text=True, check=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                          capture_output=True, text=True, check=True)
    # only staged-for-commit changes matter: diff vs HEAD + newly added
    diff = subprocess.run(["git", "diff", "--cached", "--raw"],
                          cwd=repo, capture_output=True, text=True, check=True)
    material = "\n".join([head.stdout.strip(), ls.stdout, diff.stdout])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def parse_gate_output(text: str) -> tuple[str, int]:
    """Verdict from the parsed finding count, never the exit code alone.
    Raises GateFailure on malformed/truncated output."""
    if not isinstance(text, str) or not text.strip():
        raise GateFailure("gate output missing/empty (truncated?)")
    m = _PASS_RE.search(text)
    if m:
        return "PASS", int(m.group(1))
    m = _BLOCK_RE.search(text)
    if m:
        return "BLOCKED", int(m.group(1))
    raise GateFailure(f"gate output malformed/unparseable: {text[:120]!r}")


def run_gate(repo: pathlib.Path = ROOT, *,
             check_cmd: list[str] | None = None,
             receipts_dir: pathlib.Path | None = None,
             write_receipt: bool = True) -> dict:
    """Run the publication gate fail-closed; returns the receipt dict.
    Raises GateFailure on ANY failure condition."""
    cmd = list(check_cmd or DEFAULT_CHECK)
    receipts_dir = receipts_dir or DEFAULT_RECEIPTS
    pre_identity = staged_identity(repo)
    proc = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    stdout = proc.stdout or ""
    verdict, findings = parse_gate_output(stdout)
    post_identity = staged_identity(repo)
    receipt = {
        "schema": "ijeval.ea02r.pubgate_receipt",
        "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "check_cmd": [pathlib.Path(c).name for c in cmd],
        "process_exit_code": proc.returncode,
        "parsed_verdict": verdict,
        "parsed_findings": findings,
        "staged_identity_pre": pre_identity,
        "staged_identity_post": post_identity,
        "staged_content_changed_during_check":
            pre_identity != post_identity,
        "passed": (verdict == "PASS" and findings == 0
                   and proc.returncode == 0
                   and pre_identity == post_identity),
        "stderr_tail": (proc.stderr or "").strip()[-200:],
    }
    if verdict == "PASS" and proc.returncode != 0:
        raise GateFailure(
            f"gate process exited {proc.returncode} despite PASS output — "
            "failing closed")
    if verdict == "BLOCKED" and findings > 0:
        receipt["failure_reason"] = "scanner findings present"
    if pre_identity != post_identity:
        receipt["failure_reason"] = (receipt.get("failure_reason", "")
                                     + "; staged content changed during check")
    if write_receipt:
        receipts_dir.mkdir(parents=True, exist_ok=True)
        # colon-free stamp: Windows filenames may not contain ':'
        stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + \
            f"-{abs(hash(pre_identity)) % 100000:05d}"
        path = receipts_dir / f"receipt-{stamp}.json"
        path.write_text(json.dumps(receipt, indent=1), encoding="utf-8")
        try:
            receipt["receipt_path"] = str(path.relative_to(repo))
        except ValueError:          # receipts dir outside the repo (tests)
            receipt["receipt_path"] = str(path)
    if not receipt["passed"]:
        raise GateFailure(
            f"publication gate BLOCKED: {receipt.get('failure_reason', verdict)}"
            f" (receipt: {receipt.get('receipt_path', '<not written>')})")
    return receipt


def verify_receipt(path: pathlib.Path) -> dict:
    """Re-load and sanity-check an existing receipt (missing/corrupt -> fail)."""
    if not path.exists():
        raise GateFailure(f"gate receipt missing: {path}")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise GateFailure(f"gate receipt corrupt: {e}") from e
    for key in ("parsed_verdict", "parsed_findings", "staged_identity_pre",
                "passed"):
        if key not in receipt:
            raise GateFailure(f"gate receipt missing key {key!r}")
    return receipt


def gate_commit(repo: pathlib.Path, message: str) -> subprocess.CompletedProcess:
    """Gate, then commit only on PASS. The receipt path is printed either way."""
    try:
        receipt = run_gate(repo)
    except GateFailure as e:
        print(f"PUBGATE-BLOCKED: {e}", file=sys.stderr)
        raise SystemExit(1)
    print(f"pubgate PASS (receipt {receipt.get('receipt_path')})")
    return subprocess.run(["git", "commit", "-m", message], cwd=repo,
                          check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="run the publication gate on staged content")
    c = sub.add_parser("commit", help="gate, then commit on PASS only")
    c.add_argument("-m", "--message", required=True)
    v = sub.add_parser("verify", help="verify an existing receipt")
    v.add_argument("receipt", type=pathlib.Path)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        if args.cmd == "run":
            receipt = run_gate()
            print(json.dumps(receipt, indent=1))
            return 0
        if args.cmd == "commit":
            gate_commit(ROOT, args.message)
            return 0
        if args.cmd == "verify":
            verify_receipt(args.receipt)
            print("receipt OK")
            return 0
    except GateFailure as e:
        print(f"PUBGATE-BLOCKED: {e}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
