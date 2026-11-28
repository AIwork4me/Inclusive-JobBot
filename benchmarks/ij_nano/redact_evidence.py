#!/usr/bin/env python3
"""Redact local workstation paths from IJ-NANO evidence JSON files.

Replaces absolute weight-root/engine prefixes in string values with
repo-relative labels. Idempotent. Stdlib only. The local weights root is
never hardcoded here; pass it explicitly (it lives in .runtime notes,
which are untracked).

Usage: python -I benchmarks/ij_nano/redact_evidence.py --dir evidence/IJNANO --root <local weights root>
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys


def redact(obj, replacements):
    if isinstance(obj, dict):
        return {k: redact(v, replacements) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v, replacements) for v in obj]
    if isinstance(obj, str):
        for src, dst in replacements:
            if src in obj:
                obj = obj.replace(src, dst)
        return obj
    return obj


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--root", required=True,
                    help="local weights root to redact (never stored in the repository)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    root = args.root.replace("\\", "/")
    replacements = [
        (args.root + "\\", "sibling-ij-sdk-worktree/"),
        (args.root, "sibling-ij-sdk-worktree"),
        (root + "/", "sibling-ij-sdk-worktree/"),
        (root, "sibling-ij-sdk-worktree"),
    ]
    changed = 0
    for p in sorted(pathlib.Path(args.dir).rglob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        new = redact(data, replacements)
        if new != data:
            p.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"redacted: {p}")
            changed += 1
    print(f"done; {changed} file(s) modified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
