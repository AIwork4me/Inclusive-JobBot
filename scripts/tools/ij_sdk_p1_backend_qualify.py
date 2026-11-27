#!/usr/bin/env python3
"""IJ-SDK-1.0 P1: frozen backend qualification protocol on gfx1100 (Python runner).

Per backend arm (cpu is always the reference arm; backends never share a
qualification cell):

    1. managed server start via start_llama_server.ps1 (refuses silent CPU
       fallback, records the offload line per decision D-010),
    2. GPU counter sampler bound to the real server PID (GPU arms only),
    3. probe (first real inference) via check_llama_server.ps1 -Probe,
    4. the 9-check API surface check (streaming/non-streaming parity),
    5. the native tool-calling smoke suite,
    6. managed stop.

A GPU arm passes only with the full D-010 proof: the server's own offload
line (N > 0) AND sampled counter rows showing engine activity for the
server process.

Every child script's output is redirected to files, never to a pipe the
server could inherit (decision D-011; observed live twice during P1).

Usage:
    python -I scripts/tools/ij_sdk_p1_backend_qualify.py \
        --backends cpu,vulkan,rocm --model q4 \
        --output evidence/IJSDK/P1/backend_qualification.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PS = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")
ENGINE_EXE_SHA256 = "38c5affb81c9a8f88f5538c7d11bc445e13bc46a2c6eda05694b8b31a8d45995"


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clock() -> str:
    return dt.datetime.now().strftime("%H:%M:%S")


class Log:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a", encoding="utf-8")

    def write(self, text: str) -> None:
        line = f"[{clock()}] {text}"
        self.handle.write(line + "\n")
        self.handle.flush()
        print(line, flush=True)

    def close(self) -> None:
        self.handle.close()


def run_ps(script: Path, args: list[str], out_base: Path, timeout: int = 1200) -> dict:
    """Run a PowerShell script with output redirected to files (never pipes)."""
    out_path = out_base.with_suffix(".out")
    err_path = out_base.with_suffix(".err")
    with out_path.open("wb") as out_f, err_path.open("wb") as err_f:
        proc = subprocess.run(
            [PS, "-NoProfile", "-ExecutionPolicy", "RemoteSigned", "-File", str(script)] + args,
            stdout=out_f, stderr=err_f,
            cwd=str(ROOT), timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    out = out_path.read_text(encoding="utf-8", errors="replace") if out_path.exists() else ""
    err = err_path.read_text(encoding="utf-8", errors="replace") if err_path.exists() else ""
    return {"exit_code": proc.returncode, "stdout": out, "stderr": err}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backends", default="cpu,vulkan,rocm")
    parser.add_argument("--model", default="q4", choices=["q4", "q8", "f16"])
    parser.add_argument("--context", type=int, default=8192)
    parser.add_argument("--output", default="evidence/IJSDK/P1/backend_qualification.json")
    parser.add_argument("--work-dir", default=".runtime/ijsdk_p1")
    args = parser.parse_args()

    backends = [b.strip() for b in args.backends.split(",") if b.strip()]
    work_dir = ROOT / args.work_dir
    work_dir.mkdir(parents=True, exist_ok=True)
    log = Log(work_dir / "qualify_run.log")
    log.write(f"P1 backend qualification start: backends={backends} model={args.model}")

    manifest = read_json(ROOT / "models" / "model_manifest.json")
    gguf_model = next(m for m in manifest["models"] if m["role"] == "gguf-inference")
    suffix = {"q4": "Q4_K_M", "q8": "Q8_0", "f16": "F16"}[args.model]
    gguf_file = next(f for f in gguf_model["files"] if f["path"].endswith(f"MiniCPM5-2B-{suffix}.gguf"))

    python_exe = ROOT / ".venv" / "Scripts" / "python.exe"
    arms = []

    for backend in backends:
        arm: dict = {
            "backend": backend,
            "model_alias": args.model,
            "model_path": f"{gguf_model['local_dir']}/{gguf_file['path']}",
            "model_sha256": gguf_file["sha256"],
            "started_utc": now_utc(),
        }
        log.write(f"[start-{backend}] managed start")
        start = run_ps(
            ROOT / "scripts" / "windows" / "start_llama_server.ps1",
            ["-Backend", backend, "-Model", args.model, "-ContextLength", str(args.context)],
            work_dir / f"start_{backend}",
        )
        if start["stdout"].strip():
            log.write(f"[start-{backend}] {start['stdout'].strip().splitlines()[-1]}")

        state_path = ROOT / ".runtime" / "llama-server" / "server.json"
        if start["exit_code"] != 0 or not state_path.exists():
            arm.update(status="BLOCKED", reason=f"managed start failed (exit {start['exit_code']}); see {args.work_dir}/start_{backend}.out")
            arm["finished_utc"] = now_utc()
            arms.append(arm)
            continue

        state = read_json(state_path)
        arm["server"] = {
            "port": state.get("port"),
            "backend_reported": state.get("backend"),
            "layers_offloaded": state.get("layers_offloaded"),
            "layers_total": state.get("layers_total"),
            "offload_log_line": state.get("offload_log_line"),
            "startup_seconds": state.get("startup_seconds"),
            "allocation_log_lines": state.get("allocation_log_lines"),
            "server_log": state.get("logs", {}).get("main"),
        }
        server_pid = state.get("pid")
        port = state.get("port")

        counter_path = None
        stop_file = None
        sampler = None
        if backend != "cpu":
            counter_path = work_dir / f"counters_{backend}.jsonl"
            stop_file = work_dir / f"stop-sampler-{backend}"
            if stop_file.exists():
                stop_file.unlink()
            sampler_log = (work_dir / f"sampler_{backend}").with_suffix(".log")
            sampler = subprocess.Popen(
                [PS, "-NoProfile", "-ExecutionPolicy", "RemoteSigned", "-File",
                 str(ROOT / "scripts" / "windows" / "sample_gpu_counters.ps1"),
                 "-TargetProcessId", str(server_pid),
                 "-OutputPath", str(counter_path), "-StopFile", str(stop_file),
                 "-MaxSeconds", "900"],
                stdout=sampler_log.open("wb"), stderr=subprocess.DEVNULL,
                cwd=str(ROOT), creationflags=subprocess.CREATE_NO_WINDOW,
            )
            ready = Path(f"{stop_file}.ready")
            deadline = time.time() + 120
            while not ready.exists() and time.time() < deadline:
                time.sleep(0.5)
            arm["counter_sampler_ready"] = ready.exists()
            log.write(f"[sampler-{backend}] ready={ready.exists()}")

        log.write(f"[probe-{backend}] first real inference")
        probe = run_ps(ROOT / "scripts" / "windows" / "check_llama_server.ps1", ["-Probe"],
                       work_dir / f"probe_{backend}")
        arm["probe_exit"] = probe["exit_code"]

        log.write(f"[api-{backend}] 9-check API surface")
        api_out = work_dir / f"api_check_{backend}.json"
        try:
            api = subprocess.run(
                [str(python_exe), "-I", str(ROOT / "scripts" / "tools" / "llama_server_api_check.py"),
                 "--base-url", f"http://127.0.0.1:{port}", "--output", str(api_out)],
                cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
            )
            arm["api_check_exit"] = api.returncode
            if api.stdout.strip():
                log.write(f"[api-{backend}] {api.stdout.strip().splitlines()[-1][:200]}")
        except subprocess.TimeoutExpired:
            arm["api_check_exit"] = 124
        arm["api_check_evidence"] = f"{args.work_dir}/api_check_{backend}.json"

        log.write(f"[smoke-{backend}] native tool-calling smoke suite")
        smoke_out = work_dir / f"tool_smoke_{backend}.json"
        try:
            smoke = subprocess.run(
                [str(python_exe), "-I", str(ROOT / "scripts" / "tools" / "tool_calling_smoke.py"),
                 "--base-url", f"http://127.0.0.1:{port}", "--output", str(smoke_out)],
                cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
            )
            arm["tool_smoke_exit"] = smoke.returncode
            if smoke.stdout.strip():
                log.write(f"[smoke-{backend}] {smoke.stdout.strip().splitlines()[-1][:200]}")
        except subprocess.TimeoutExpired:
            arm["tool_smoke_exit"] = 124
        arm["tool_smoke_evidence"] = f"{args.work_dir}/tool_smoke_{backend}.json"

        if stop_file:
            stop_file.touch()
        log.write(f"[stop-{backend}] managed stop")
        stop = run_ps(ROOT / "scripts" / "windows" / "stop_llama_server.ps1", [],
                      work_dir / f"stop_{backend}")
        if sampler:
            try:
                sampler.wait(timeout=60)
            except subprocess.TimeoutExpired:
                sampler.kill()

        if counter_path and counter_path.exists() and counter_path.stat().st_size > 0:
            engine_rows, max_util, engine_types, max_mem = [], 0, set(), None
            for line in counter_path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = row.get("kind")
                if kind == "gpu_engine" and (row.get("utilization") or 0) > 0:
                    engine_rows.append(row)
                    max_util = max(max_util, row.get("utilization") or 0)
                    engine_types.add(row.get("engine_type") or "?")
                elif kind == "gpu_process_memory":
                    mem = row.get("dedicated_bytes")
                    if isinstance(mem, (int, float)):
                        max_mem = mem if max_mem is None else max(max_mem, mem)
            arm["gpu_counters"] = {
                "nonzero_engine_rows": len(engine_rows),
                "max_utilization": max_util,
                "engine_types": sorted(engine_types),
                "max_dedicated_memory_bytes": max_mem,
                "evidence": f"{args.work_dir}/counters_{backend}.jsonl",
            }

        arm["finished_utc"] = now_utc()
        arm["status"], arm["reason"] = "PASS", ""
        if probe["exit_code"] != 0:
            arm["status"], arm["reason"] = "FAIL", "probe failed"
        elif arm.get("api_check_exit") != 0:
            arm["status"], arm["reason"] = "FAIL", "API surface check failed"
        elif arm.get("tool_smoke_exit") != 0:
            arm["status"], arm["reason"] = "FAIL", "tool-calling smoke failed"
        if backend != "cpu":
            layers = arm["server"].get("layers_offloaded")
            if not layers or layers <= 0:
                arm["status"], arm["reason"] = "FAIL", "no GPU offload evidence (D-010)"
            elif not arm.get("gpu_counters") or arm["gpu_counters"]["nonzero_engine_rows"] == 0:
                arm["status"], arm["reason"] = "FAIL", "no GPU engine activity observed (D-010)"
        log.write(f"[arm-{backend}] status={arm['status']} {arm['reason']}")
        arms.append(arm)

    overall = "PASS" if all(a["status"] == "PASS" for a in arms) else "FAIL"
    evidence = {
        "schema_version": 1,
        "protocol": "IJ-SDK-1.0 P1 backend qualification (frozen 2026-11-27)",
        "mission": "IJ-SDK-1.0",
        "generated_utc": now_utc(),
        "engine": {
            "build": "b12359", "release": "v1.0.0",
            "commit": "b1b770d90d94cad9e9ea5b993bdbc383a522fb28",
            "exe_sha256": ENGINE_EXE_SHA256,
        },
        "gpu": {
            "architecture": "gfx1100", "device": "AMD Radeon RX 7900 XTX",
            "device_id": "0x744c", "driver": "32.0.21030.2001",
        },
        "rule": ("Backend results never mix within one experimental cell; CPU is the "
                 "reference arm; GPU arms require D-010 proof (offload line + counter "
                 "engine activity)."),
        "arms": arms,
        "overall_status": overall,
    }
    out_path = ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log.write(f"wrote {args.output} (overall: {overall})")
    log.close()
    return 0 if overall == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
