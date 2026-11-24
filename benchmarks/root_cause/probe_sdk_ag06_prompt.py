"""Compare AG-06's frozen prompt to an explicit tool-result field instruction."""

import argparse
import asyncio
from collections import Counter
from importlib.metadata import version
import json
from pathlib import Path
from uuid import uuid4

from benchmarks.competitive_slm.admission import cpu_server
from benchmarks.ij06_sdk import qualify
from benchmarks.root_cause.historical_replay import ALIAS, ROOT, legacy


def run(args):
    binary = args.engine_dir.resolve() / "llama-server.exe"
    model = (ROOT / "models/MiniCPM5-2B-GGUF/MiniCPM5-2B-Q8_0.gguf").resolve()
    models = json.loads((ROOT / "models/model_manifest.json").read_bytes())["models"]
    pin = next(row for row in models if row["model_id"] == "OpenBMB/MiniCPM5-2B-GGUF")
    model_sha = legacy.sha256_of(model)
    if not any(row["path"] == model.name and row["sha256"] == model_sha for row in pin["files"]):
        raise ValueError("AG-06 control model differs from the ModelScope pin")
    harness = Path(qualify.harness_package.__file__).with_name("localharness.exe").resolve()
    output = args.output.resolve()
    original = qualify.CASE_SPECS["AG-06"]
    output.mkdir(parents=True, exist_ok=False)
    instruction = (" The tool response carries the status string in its result field. "
                   "Use only that field's string value for finish.status.")
    rows = []
    try:
        with cpu_server(binary, model, args.port, output / "server.log", ALIAS) as (client, build):
            for index in range(1, 4):
                for profile in ("frozen", "result_field_instruction"):
                    active_prompt = original[0] + instruction if profile == "result_field_instruction" else original[0]
                    qualify.CASE_SPECS["AG-06"] = (active_prompt, original[1])
                    observed = asyncio.run(qualify.execute_case(
                        client.base_url, ALIAS, output / f"{profile}-{index}", harness, "AG-06"
                    ))
                    rows.append({"profile": profile, "trial": index, "prompt": active_prompt, **observed})
                    print(profile, index, observed["status"], flush=True)
    finally:
        qualify.CASE_SPECS["AG-06"] = original
    outcomes = {
        profile: dict(Counter(row["status"] for row in rows if row["profile"] == profile))
        for profile in ("frozen", "result_field_instruction")
    }
    qualify.write_evidence(output / "report.json", {
        "run_id": "ij07-ag06-prompt-control-" + uuid4().hex, "git": legacy.git_state(),
        "backend": "cpu", "scope": "real local SDK, only the user prompt changes", "build": build,
        "source_sha256": legacy.sha256_of(Path(__file__)), "engine_exe_sha256": legacy.sha256_of(binary),
        "runtime_dll_sha256": {file.name: legacy.sha256_of(file) for file in sorted(binary.parent.glob("*.dll"))},
        "model_sha256": model_sha, "modelscope_revision": pin["revision"], "harness_sha256": legacy.sha256_of(harness),
        "sdk_version": version("google-antigravity"), "outcomes": outcomes, "trials": rows,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8098)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
