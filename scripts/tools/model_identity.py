#!/usr/bin/env python3
"""Verify local MiniCPM5-2B artifacts against ModelScope metadata.

Every file is compared with the SHA256 and size that ModelScope publishes for a
pinned repository revision. The result is written twice:

* ``models/model_manifest.json`` - the stable description scripts install from.
* ``evidence/IJ0/model_identity.json`` - the verification record for one run.

The ModelScope listing is archived as ``modelscope_listing.json`` next to the
evidence; pass it back with ``--listing`` to repeat the comparison without
network access. Exit status is non-zero when any file is missing, has the
wrong size or has the wrong digest.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys
import urllib.request

MODELSCOPE_FILES_API = (
    "https://modelscope.cn/api/v1/models/{model_id}/repo/files"
    "?Revision={revision}&Recursive=true"
)
MODELSCOPE_MODEL_API = "https://modelscope.cn/api/v1/models/{model_id}"

# Revisions are the ModelScope head commits observed on 2026-11-24.
PINNED = (
    ("gguf-inference", "OpenBMB/MiniCPM5-2B-GGUF", "8cc1178b0a5cee98872ca3f2f88d49b3d3fa6f59"),
    ("bf16-reference", "OpenBMB/MiniCPM5-2B", "4e7a94716d4526da493d68962f475390e852954b"),
)


def sha256_of(path: pathlib.Path) -> str:
  digest = hashlib.sha256()
  with path.open("rb") as handle:
    for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
      digest.update(block)
  return digest.hexdigest()


def fetch_json(url: str) -> dict:
  request = urllib.request.Request(url, headers={"User-Agent": "inclusive-jobbot"})
  with urllib.request.urlopen(request, timeout=60) as response:
    return json.load(response)


def remote_listing(model_id: str, revision: str, cached: dict) -> tuple[list[dict], str | None]:
  """Returns (files, license) from the archived listing or from ModelScope."""
  archived = cached.get(model_id)
  if archived is not None:
    return archived["files"], archived.get("license")
  listing = fetch_json(MODELSCOPE_FILES_API.format(model_id=model_id, revision=revision))
  if listing.get("Code") != 200:
    raise RuntimeError(f"ModelScope listing failed for {model_id}: {listing.get('Message')}")
  files = [
      {"Path": f["Path"], "Size": f["Size"], "Sha256": f["Sha256"], "CommittedDate": f["CommittedDate"]}
      for f in listing["Data"]["Files"]
  ]
  detail = fetch_json(MODELSCOPE_MODEL_API.format(model_id=model_id)).get("Data") or {}
  return files, detail.get("License")


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  parser.add_argument("--root", default=".", help="repository root")
  parser.add_argument("--models-dir", default="models")
  parser.add_argument("--evidence", default="evidence/IJ0/model_identity.json")
  parser.add_argument("--listing", help="archived ModelScope listing to use instead of the API")
  args = parser.parse_args()

  root = pathlib.Path(args.root).resolve()
  models_dir = root / args.models_dir
  evidence_path = root / args.evidence
  evidence_path.parent.mkdir(parents=True, exist_ok=True)
  archive_path = evidence_path.parent / "modelscope_listing.json"
  cached = json.loads(pathlib.Path(args.listing).read_text(encoding="utf-8")) if args.listing else {}
  now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

  manifest = {
      "schema_version": 1,
      "generated_utc": now,
      "source_policy": {
          "allowed_hosts": ["modelscope.cn"],
          "huggingface_fallback": False,
          "weights_committed_to_git": False,
      },
      "models": [],
  }
  record = {
      "schema_version": 1,
      "run_time_utc": now,
      "verifier": "scripts/tools/model_identity.py",
      "listing_source": "archived" if args.listing else "ModelScope API at pinned revision",
      "models": [],
  }
  archived_listing: dict[str, dict] = {}
  failures = 0

  for role, model_id, revision in PINNED:
    remote, license_name = remote_listing(model_id, revision, cached)
    remote.sort(key=lambda item: item["Path"])
    archived_listing[model_id] = {"revision": revision, "license": license_name, "files": remote}
    local_dir = models_dir / model_id.split("/")[1]

    manifest["models"].append(
        {
            "role": role,
            "model_id": model_id,
            "source_url": f"https://modelscope.cn/models/{model_id}",
            "revision": revision,
            "license": license_name,
            "license_statement": (
                "Model card: this repository and MiniCPM model weights are released "
                "under the Apache-2.0 License."
            ),
            "local_dir": local_dir.relative_to(root).as_posix(),
            "files": [
                {"path": item["Path"], "size": item["Size"], "sha256": item["Sha256"]}
                for item in remote
            ],
        }
    )

    files_record = []
    for item in remote:
      local = local_dir / item["Path"]
      outcome = {
          "path": item["Path"],
          "expected_size": item["Size"],
          "expected_sha256": item["Sha256"],
          "committed_at": dt.datetime.fromtimestamp(
              item["CommittedDate"], dt.timezone.utc
          ).isoformat(timespec="seconds"),
      }
      if not local.is_file():
        outcome.update(status="FAIL", reason="missing")
      else:
        actual_size = local.stat().st_size
        actual_sha256 = sha256_of(local)
        matches = actual_size == item["Size"] and actual_sha256 == item["Sha256"]
        outcome.update(
            actual_size=actual_size,
            actual_sha256=actual_sha256,
            status="PASS" if matches else "FAIL",
        )
        if not matches:
          outcome["reason"] = "size or sha256 mismatch"
      if outcome["status"] != "PASS":
        failures += 1
      files_record.append(outcome)
      print(f"{outcome['status']}  {model_id}/{item['Path']}")

    expected_paths = {item["Path"] for item in remote}
    extra = sorted(
        p.relative_to(local_dir).as_posix()
        for p in local_dir.rglob("*")
        if p.is_file()
        and p.relative_to(local_dir).as_posix() not in expected_paths
        and not any(part.startswith(".") for part in p.relative_to(local_dir).parts)
    )
    for path in extra:
      print(f"UNEXPECTED  {model_id}/{path}")
      failures += 1

    record["models"].append(
        {
            "role": role,
            "model_id": model_id,
            "revision": revision,
            "license": license_name,
            "local_dir": local_dir.relative_to(root).as_posix(),
            "file_count": len(files_record),
            "pass_count": sum(1 for f in files_record if f["status"] == "PASS"),
            "unexpected_local_files": extra,
            "files": files_record,
        }
    )

  record["status"] = "PASS" if failures == 0 else "FAIL"
  record["fail_count"] = failures
  archive_path.write_text(json.dumps(archived_listing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
  (root / "models" / "model_manifest.json").write_text(
      json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
  )
  evidence_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
  print(f"overall: {record['status']} ({failures} failing file(s))")
  return 0 if failures == 0 else 1


if __name__ == "__main__":
  sys.exit(main())
