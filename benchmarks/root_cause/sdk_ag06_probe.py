"""Repeat the unchanged Antigravity AG-06 case against real Radeon inference."""

import argparse
import asyncio
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

from benchmarks.ij06_sdk.qualify import execute_case, harness_package, write_evidence
from benchmarks.root_cause.historical_replay import ALIAS, ROOT, engine_runtime, gpu_server, legacy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("vulkan", "rocm"), required=True)
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8094, choices=range(1024, 65536), metavar="PORT")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    model = (ROOT / "models/MiniCPM5-2B-GGUF/MiniCPM5-2B-Q8_0.gguf").resolve()
    harness = Path(harness_package.__file__).with_name("localharness.exe")
    binary, engine, env = engine_runtime(args.engine_dir.resolve(), args.backend)
    report = {
        "run_id": "ij07-ag06-" + uuid4().hex, "git": legacy.git_state(), "engine": engine,
        "model_sha256": legacy.sha256_of(model), "backend": args.backend,
        "sdk_version": version("google-antigravity"), "harness_sha256": legacy.sha256_of(harness),
        "started_utc": legacy.utc_now(), "repetitions": [],
        "AG-11": {"status": "BLOCKED", "reason": "complete process-tree egress evidence unavailable"},
    }
    with gpu_server(binary, model, args.backend, env, out, args.port, "sdk", False) as (client, launch):
        report["launch"] = launch
        for index in range(1, 4):
            result = asyncio.run(execute_case(client.base_url, ALIAS, out / f"trial-{index}", harness, "AG-06"))
            report["repetitions"].append({"trial": index, **result})
            write_evidence(out / "report.json", report)
            print(args.backend, "AG-06", index, result["status"], flush=True)
    report["finished_utc"] = legacy.utc_now()
    write_evidence(out / "report.json", report)


if __name__ == "__main__":
    main()
