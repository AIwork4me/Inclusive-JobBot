#!/usr/bin/env python3
"""IJ-SDK-1.0 P3: run every SDK arm's conformance probe against one managed
llama-server, sequentially (Python runner: D-011-safe file redirection for
the managed start/stop scripts).

Usage:
    python -I scripts/tools/ij_sdk_sdk_conformance.py --model q8 --backend vulkan
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PS = str(Path(subprocess.run(["python", "-c", "import os;print(os.environ['SystemRoot'])"], capture_output=True, text=True).stdout.strip()) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe") if False else None
import os
PS = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")

ARMS = [
    {"arm": "b1", "venv": ".venv"},
    {"arm": "b2", "venv": ".venvs/b2-openai-agents"},
    {"arm": "b3", "venv": ".venvs/b3b4-smolagents"},
    {"arm": "b4", "venv": ".venvs/b3b4-smolagents"},
    {"arm": "b5", "venv": ".venvs/b5-pydantic-ai"},
    {"arm": "b6", "venv": ".venvs/b6-langgraph"},
    {"arm": "b7", "venv": ".venvs/b7-adk"},
    {"arm": "b8", "venv": ".venvs/b8-agent-framework"},
    {"arm": "b9", "venv": ".venvs/b9-pocketflow"},
    {"arm": "o1", "venv": ".venvs/o1-dspy"},
]


def run_ps(script: Path, args: list[str], out_base: Path, timeout: int = 1200) -> int:
    with out_base.with_suffix(".out").open("wb") as out_f, out_base.with_suffix(".err").open("wb") as err_f:
        proc = subprocess.run([PS, "-NoProfile", "-ExecutionPolicy", "RemoteSigned", "-File", str(script)] + args,
                              stdout=out_f, stderr=err_f, cwd=str(ROOT), timeout=timeout,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="q8", choices=["q4", "q8", "f16"])
    parser.add_argument("--backend", default="vulkan", choices=["cpu", "vulkan", "rocm"])
    args = parser.parse_args()

    log_file = (ROOT / ".runtime" / "logs" / "ijsdk_conformance_run.log").open("a", encoding="utf-8")

    def log(text: str) -> None:
        log_file.write(text + "\n")
        log_file.flush()
        print(text, flush=True)

    log("[server] managed start")
    code = run_ps(ROOT / "scripts" / "windows" / "start_llama_server.ps1",
                  ["-Backend", args.backend, "-Model", args.model, "-ContextLength", "8192"],
                  ROOT / ".runtime" / "logs" / "conf_server_start")
    log(f"[server] start exit={code}")
    if code != 0:
        log("[server] start FAILED")
        return 2
    state = json.loads((ROOT / ".runtime" / "llama-server" / "server.json").read_text(encoding="utf-8"))
    port = state["port"]
    summary = {}
    try:
        for arm in ARMS:
            venv_python = ROOT / arm["venv"] / "Scripts" / "python.exe"
            if not venv_python.exists():
                summary[arm["arm"]] = {"status": "BLOCKED", "reason": "venv missing"}
                log(f"[{arm['arm']}] venv missing - BLOCKED")
                continue
            out = f"evidence/IJSDK/P3/conformance/{arm['arm']}.json"
            probe = subprocess.run(
                [str(venv_python), "-I", str(ROOT / "benchmarks" / "ij_sdk" / "conformance.py"),
                 "--arm", arm["arm"], "--base-url", f"http://127.0.0.1:{port}",
                 "--model", "minicpm5-2b", "--output", out],
                cwd=str(ROOT), capture_output=True, text=True, timeout=900)
            tail = (probe.stdout or probe.stderr).strip().splitlines()
            log(f"[{arm['arm']}] exit={probe.returncode} {tail[-1][:160] if tail else ''}")
            summary[arm["arm"]] = {"exit": probe.returncode}
    finally:
        log("[server] managed stop")
        run_ps(ROOT / "scripts" / "windows" / "stop_llama_server.ps1", [],
               ROOT / ".runtime" / "logs" / "conf_server_stop")
        out_path = ROOT / "evidence" / "IJSDK" / "P3" / "conformance" / "summary.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
        log(f"wrote {out_path.relative_to(ROOT)}")
    log_file.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
