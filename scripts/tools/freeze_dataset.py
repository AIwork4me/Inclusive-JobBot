#!/usr/bin/env python3
"""Freeze a benchmark dataset by recording the SHA256 of every file in it.

A dataset is frozen by writing ``<name>.manifest.json`` next to it. Runners
refuse to start when the on-disk files no longer match the manifest, so a
result can always be tied to the exact inputs it was produced with.

Usage:
    python scripts/tools/freeze_dataset.py benchmarks/engine_qualification/workload.json
    python scripts/tools/freeze_dataset.py --check benchmarks/engine_qualification/workload.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys


def sha256_of(path: pathlib.Path) -> str:
  digest = hashlib.sha256()
  with path.open("rb") as handle:
    for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
      digest.update(block)
  return digest.hexdigest()


def files_of(target: pathlib.Path) -> list[pathlib.Path]:
  if target.is_file():
    return [target]
  return sorted(p for p in target.rglob("*") if p.is_file() and not p.name.endswith(".manifest.json"))


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  parser.add_argument("dataset", help="dataset file or directory")
  parser.add_argument("--check", action="store_true", help="verify only; do not write")
  parser.add_argument("--frozen-note", default="", help="note recorded in a new manifest")
  args = parser.parse_args()

  target = pathlib.Path(args.dataset).resolve()
  if target.is_file():
    manifest_path = target.with_name(target.name + ".manifest.json")
    relative_to = target.parent
  else:
    manifest_path = target / "dataset.manifest.json"
    relative_to = target
  files = files_of(target)
  entries = [
      {
          "path": p.relative_to(relative_to).as_posix(),
          "size": p.stat().st_size,
          "sha256": sha256_of(p),
      }
      for p in files
  ]

  if args.check:
    if not manifest_path.exists():
      print(f"FAIL: no manifest at {manifest_path}")
      return 1
    frozen = {item["path"]: item["sha256"] for item in json.loads(manifest_path.read_text(encoding="utf-8"))["files"]}
    mismatches = [item["path"] for item in entries if frozen.get(item["path"]) != item["sha256"]]
    missing = sorted(set(frozen) - {item["path"] for item in entries})
    for path in mismatches + missing:
      print(f"FAIL: {path} does not match the frozen manifest")
    print(f"{'FAIL' if mismatches or missing else 'PASS'}: {len(entries)} file(s) checked against {manifest_path.name}")
    return 1 if mismatches or missing else 0

  manifest = {
      "schema_version": 1,
      "frozen_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
      "dataset": target.name,
      "file_count": len(entries),
      "case_count": None,
      "note": args.frozen_note,
      "files": entries,
  }
  for path in files:
    if path.suffix == ".json":
      try:
        data = json.loads(path.read_text(encoding="utf-8"))
      except json.JSONDecodeError:
        continue
      if isinstance(data, dict):
        counts = {
            key: len(value)
            for key, value in data.items()
            if isinstance(value, list) and value and all(isinstance(item, dict) for item in value)
        }
        if counts:
          manifest["case_count"] = sum(counts.values())
          manifest["case_count_by_section"] = counts
  manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
  print(f"frozen: {len(entries)} file(s), {manifest['case_count']} case(s) -> {manifest_path}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
