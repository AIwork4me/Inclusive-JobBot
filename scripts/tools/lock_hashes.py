#!/usr/bin/env python3
"""Add SHA256 hashes to requirements.lock and cross-check them with pypi.org.

The project installs Python packages from a PyPI mirror on networks where
`files.pythonhosted.org` is unreliable. A mirror is not trusted on its own, so
this tool:

1. downloads the exact pinned files into a scratch directory;
2. computes the SHA256 of each file;
3. compares it with the digest that the official `pypi.org` metadata API
   publishes for that exact filename;
4. rewrites ``requirements.lock`` with ``--hash=`` entries, so
   ``pip install --require-hashes`` can be used afterwards.

If the official API cannot be reached or any digest differs, the lock file is
left untouched and the exit status is non-zero.

Usage:
    python scripts/tools/lock_hashes.py [--index-url URL] [--lock requirements.lock]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys
import time
import urllib.parse
import urllib.request

DEFAULT_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"
PYPI_JSON = "https://pypi.org/pypi/{name}/{version}/json"


def sha256_of(path: pathlib.Path) -> str:
  digest = hashlib.sha256()
  with path.open("rb") as handle:
    for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
      digest.update(block)
  return digest.hexdigest()


def parse_lock(text: str) -> list[tuple[str, str]]:
  pins = []
  for line in text.splitlines():
    line = line.split("#", 1)[0].strip()
    if "==" in line:
      name, version = line.split("==", 1)
      name = name.split()[0].strip()
      pins.append((name, version.strip()))
  return pins


def official_digest(name: str, version: str, filename: str) -> str | None:
  url = PYPI_JSON.format(name=urllib.parse.quote(name, safe=""), version=urllib.parse.quote(version, safe=""))
  request = urllib.request.Request(url, headers={"User-Agent": "inclusive-jobbot"})
  last_error: OSError | None = None
  for attempt in range(3):
    try:
      with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)
      break
    except OSError as error:
      last_error = error
      time.sleep(2 * (attempt + 1))
  else:
    raise last_error

  for entry in data.get("urls", []):
    if entry.get("filename") == filename:
      return (entry.get("digests") or {}).get("sha256")
  return None


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  parser.add_argument("--lock", default="requirements.lock")
  parser.add_argument("--index-url", default=DEFAULT_INDEX)
  parser.add_argument("--download-dir", default=".runtime/lock-wheels")
  parser.add_argument("--evidence", default="evidence/M0/lock_hash_crosscheck.json")
  parser.add_argument("--skip-download", action="store_true", help="reuse the files already in --download-dir")
  args = parser.parse_args()

  lock_path = pathlib.Path(args.lock)
  original = lock_path.read_text(encoding="utf-8")
  pins = parse_lock(original)
  download_dir = pathlib.Path(args.download_dir)
  if args.skip_download:
    print(f"reusing the files already present in {args.download_dir}")
  else:
    if download_dir.exists():
      for stale in download_dir.iterdir():
        stale.unlink()
    subprocess.run(
        [
            sys.executable, "-m", "pip", "download", "--disable-pip-version-check", "--no-deps",
            "-q", "-d", str(download_dir), "-i", args.index_url, "-r", str(lock_path),
        ],
        check=True,
    )
  download_dir.mkdir(parents=True, exist_ok=True)

  results = []
  failures = 0
  hashes: dict[str, str] = {}
  downloaded: list[tuple[str, str, pathlib.Path, str]] = []
  for name, version in pins:
    prefix = name.replace("-", "_").lower()
    wanted = f"{prefix}-{version.lower()}"
    candidates = [p for p in download_dir.iterdir() if p.name.lower().startswith(wanted)]
    if not candidates:
      results.append({"name": name, "version": version, "status": "FAIL", "reason": "no file was downloaded"})
      failures += 1
      continue
    downloaded.append((name, version, candidates[0], sha256_of(candidates[0])))

  # The official metadata lookups are slow on this network; run them together.
  with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    pending = {pool.submit(official_digest, name, version, file.name): item for item in downloaded for (name, version, file, _) in [item]}
    for future in concurrent.futures.as_completed(pending):
      name, version, file, local = pending[future]
      try:
        official = future.result()
      except OSError as error:
        results.append({"name": name, "version": version, "status": "BLOCKED", "reason": f"pypi.org unreachable: {error}"})
        failures += 1
        continue
      matches = official is not None and official == local
      if not matches:
        failures += 1
      results.append(
          {
              "name": name,
              "version": version,
              "file": file.name,
              "sha256_local": local,
              "sha256_pypi_org": official,
              "status": "PASS" if matches else "FAIL",
          }
      )
      if matches:
        hashes[f"{name}=={version}"] = local
  results.sort(key=lambda item: item["name"].lower())

  status = "PASS" if failures == 0 else "FAIL"
  evidence = {
      "schema_version": 1,
      "run_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
      "tool": "scripts/tools/lock_hashes.py",
      "index_url": args.index_url,
      "official_metadata": "https://pypi.org/pypi/<name>/<version>/json",
      "status": status,
      "package_count": len(pins),
      "pass_count": sum(1 for r in results if r["status"] == "PASS"),
      "packages": results,
  }
  evidence_path = pathlib.Path(args.evidence)
  evidence_path.parent.mkdir(parents=True, exist_ok=True)
  evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

  if status != "PASS":
    print(f"{status}: {failures} of {len(pins)} pins could not be cross-checked; {args.lock} left unchanged")
    return 1

  lines = []
  for line in original.splitlines():
    stripped = line.split("#", 1)[0].strip()
    if "==" in stripped and "--hash" not in line:
      pin_name, pin_version = stripped.split("==", 1)
      key = f"{pin_name.split()[0].strip()}=={pin_version.split()[0]}"
      if key in hashes:
        line = f"{key} --hash=sha256:{hashes[key]}"
    lines.append(line)
  lock_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
  # Read the file back: reporting success is not enough, the hashes must be there.
  written = sum(1 for line in lock_path.read_text(encoding="utf-8").splitlines() if "--hash=sha256:" in line)
  if written != len(hashes):
    print(f"FAIL: {len(hashes)} pins were cross-checked but only {written} hashes are in {args.lock}")
    return 1
  print(f"{status}: {len(hashes)}/{len(pins)} pins cross-checked with pypi.org; {written} hashes written to {args.lock}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
