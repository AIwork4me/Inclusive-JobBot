#!/usr/bin/env python3
"""IJ-NANO N02 driver: holds the host-wide physical-GPU lease for the whole
session and runs, per candidate: the frozen IJ-SDK admission smoke (server +
10 case families) then the IJ-NANO protocol probe. Writes a session record.

Usage:
    python -I benchmarks/ij_nano/n02_session.py --weights-root <dir> \
        --candidates S1,S2,S3d,R1,R2
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks" / "root_cause"))
import gpu_lease  # noqa: E402  (existing host-wide protocol, reused as-is)

CANDIDATES = {
    "S1": ("models/MiniCPM5-2B-GGUF/MiniCPM5-2B-Q8_0.gguf", "minicpm5-2b"),
    "S2": ("models/ij_sdk/LFM3-1.7B-GGUF/LFM3-1.7B-Q8_0.gguf", "lfm3-1.7b"),
    "S3d": ("models/ij_sdk/Qwen3.5-2B-GGUF/Qwen3.5-2B-Q8_0.gguf", "qwen3.5-2b"),
    "R1": ("models/ij_sdk/Qwen3-8B-GGUF/Qwen3-8B-Q8_0.gguf", "qwen3-8b"),
    "R2": ("models/ij_sdk/Qwen3-14B-GGUF/Qwen3-14B-Q8_0.gguf", "qwen3-14b"),
}


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(ROOT))
    return {"exit": p.returncode, "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-800:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights-root", required=True)
    ap.add_argument("--candidates", default="S1,S2,S3d,R1,R2")
    ap.add_argument("--backend", default="vulkan")
    ap.add_argument("--skip-admission", action="store_true",
                    help="run only the protocol probe (admission evidence already sealed)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    weights_root = pathlib.Path(args.weights_root).resolve()

    session = {"schema_version": 1, "mission": "IJ-NANO-1.0", "phase": "N02",
               "lease_protocol": "benchmarks/root_cause/gpu_lease.py physical_gpu() (host-wide named mutex)",
               "backend": args.backend, "started_utc": utc(), "candidates": {}}

    with gpu_lease.physical_gpu():
        session["lease_acquired_utc"] = utc()
        print(f"[lease ACQUIRED {utc()}] host-wide physical GPU session", flush=True)
        for cid in [c.strip() for c in args.candidates.split(",") if c.strip()]:
            rel, alias = CANDIDATES[cid]
            model = (weights_root / rel).resolve()
            if not model.is_file():
                session["candidates"][cid] = {"status": "MISSING_MODEL", "path": rel}
                print(f"[{cid}] MISSING {rel}", flush=True)
                continue
            adm_out = f"evidence/IJNANO/N02/admission/{cid}.json"
            probe_out = f"evidence/IJNANO/N02/protocol/{cid}.json"
            if args.skip_admission:
                adm = {"exit": 0, "stdout_tail": "skipped (--skip-admission; existing evidence preserved)",
                       "stderr_tail": ""}
                print(f"[{cid}] admission skipped", flush=True)
            else:
                print(f"[{cid}] admission smoke ({alias}) ...", flush=True)
                adm = run([sys.executable, "-I", "benchmarks/ij_sdk/admission_smoke.py",
                           "--candidate", cid, "--model", str(model), "--alias", alias,
                           "--backend", args.backend, "--output", adm_out])
                print(f"[{cid}] admission exit={adm['exit']}", flush=True)
            print(f"[{cid}] protocol probe ...", flush=True)
            probe = run([sys.executable, "-I", "benchmarks/ij_nano/n02_protocol_probe.py",
                         "--candidate", cid, "--model", str(model), "--alias", alias,
                         "--backend", args.backend, "--port", "8093", "--output", probe_out])
            print(f"[{cid}] probe exit={probe['exit']}", flush=True)
            session["candidates"][cid] = {
                "model_repo_relative_path": rel, "alias": alias,
                "admission": {"exit": adm["exit"], "output": adm_out},
                "protocol_probe": {"exit": probe["exit"], "output": probe_out},
                "status": "DONE" if (adm["exit"] == 0 and probe["exit"] == 0) else "CHECK",
            }
        session["lease_released_utc"] = utc()
        print(f"[lease RELEASED {utc()}]", flush=True)

    out = ROOT / "evidence/IJNANO/N02/session_record.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(session, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"session record -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
