#!/usr/bin/env python3
"""IJ-NANO N02: fresh SHA256 verification of model weights and engine binaries.

Reads the committed identity anchor (models/ij_sdk/model_manifest.json),
resolves each recorded file against a weights root on disk, recomputes
size + SHA256 and reports agreement. Writes JSON evidence. Never modifies
anything. Stdlib only.

Usage:
    python -I benchmarks/ij_nano/verify_model_identities.py \
        --weights-root <dir containing models/> \
        --engine-root <dir containing runtime/llama-cpp/> \
        --out evidence/IJNANO/N02/identity_verification.json
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import sys


def sha256_file(path: pathlib.Path, chunk: int = 1 << 20) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
            size += len(block)
    return h.hexdigest(), size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="models/ij_sdk/model_manifest.json")
    ap.add_argument("--weights-root", required=True,
                    help="directory that contains the manifest's repo-relative paths (e.g. the sibling worktree)")
    ap.add_argument("--engine-root", default=None,
                    help="directory that contains runtime/llama-cpp/<backend>/llama-server.exe")
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-engine", action="store_true")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    repo = pathlib.Path(__file__).resolve().parents[2]
    manifest_path = repo / args.manifest
    weights_root = pathlib.Path(args.weights_root).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    report: dict = {
        "schema_version": 1,
        "mission": "IJ-NANO-1.0",
        "phase": "N02",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "identity_anchor": {
            "manifest_repo_path": args.manifest,
            "manifest_sha256": sha256_file(manifest_path)[0],
            "source": "committed at IJ-NANO base 56c6c74b (IJ-SDK P0R/P2 live-verified identities)",
        },
        "weights_root_note": "<local weights directory, path withheld from evidence>",
        "models": [],
        "engine": {"backends": []},
        "summary": {"files_checked": 0, "files_match": 0, "files_missing": 0, "files_mismatch": 0},
    }

    entries = list(manifest.get("candidates", [])) + list(manifest.get("references", []))
    for cand in entries:
        cid = cand.get("id", "?")
        for qname, frec in (cand.get("files") or {}).items():
            rel = frec.get("path")
            expect_sha = frec.get("sha256")
            expect_size = frec.get("size")
            row = {"id": cid, "quantization": qname, "repo_relative_path": rel,
                   "expected_sha256": expect_sha}
            report["summary"]["files_checked"] += 1
            disk = weights_root / rel
            if not disk.is_file():
                row["status"] = "MISSING_ON_DISK"
                report["summary"]["files_missing"] += 1
            else:
                got_sha, got_size = sha256_file(disk)
                row["size_expected"] = expect_size
                row["size_on_disk"] = got_size
                row["sha256_on_disk"] = got_sha
                if got_sha == expect_sha and (expect_size is None or got_size == expect_size):
                    row["status"] = "MATCH"
                    report["summary"]["files_match"] += 1
                else:
                    row["status"] = "MISMATCH"
                    report["summary"]["files_mismatch"] += 1
            report["models"].append(row)
            print(f"[{row['status']}] {cid} {qname} {rel}", flush=True)

    if args.engine_root and not args.skip_engine:
        engine_root = pathlib.Path(args.engine_root).resolve()
        for backend in ("cpu", "vulkan", "rocm"):
            bdir = engine_root / "runtime" / "llama-cpp" / backend
            brow = {"backend": backend, "files": []}
            exe = bdir / "llama-server.exe"
            if exe.is_file():
                sha, size = sha256_file(exe)
                brow["files"].append({"file": "llama-server.exe", "sha256": sha, "size": size})
                brow["llama_server_version_probe"] = "deferred to N02 admission run"
            for dll in sorted(bdir.glob("*.dll")):
                sha, size = sha256_file(dll)
                brow["files"].append({"file": dll.name, "sha256": sha, "size": size})
            brow["file_count"] = len(brow["files"])
            report["engine"]["backends"].append(brow)
            print(f"[engine] {backend}: {brow['file_count']} files hashed", flush=True)
        report["engine"]["identity_note"] = "official llama.cpp release v1.0.0 build b12359 (commit b1b770d9); full install SHA256s in IJ-SDK evidence/IJSDK/P1/engine_install.json"

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"evidence written: {out}")
    s = report["summary"]
    ok = s["files_mismatch"] == 0
    print(f"summary: {s}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
