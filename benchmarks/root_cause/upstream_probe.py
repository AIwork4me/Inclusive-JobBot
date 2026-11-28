"""Compare a digest-pinned upstream Windows build against historical diagnostic cases."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
from uuid import uuid4

from benchmarks.root_cause.historical_replay import ALIAS, ROOT, gpu_server, legacy, run_case
from benchmarks.tool_calling.runner.run_parser_fixtures import eos_token_id
from benchmarks.tool_calling_v2 import rescore
from benchmarks.tool_calling_v2.parser.assessment import validators_for
from benchmarks.tool_calling_v2.parser.fixtures import build
from benchmarks.tool_calling_v2.parser.run_wire import trial
from scripts.tools.verify_ij06_evidence import verify_gpu


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--archive-identity", type=Path, required=True)
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8094, choices=range(1024, 65536), metavar="PORT")
    args = parser.parse_args()
    release = rescore.read_json(args.archive_identity)
    if args.archive.name != release["asset"] or legacy.sha256_of(args.archive) != release["sha256"]:
        parser.error("upstream release archive digest mismatch")
    base = args.engine_dir.resolve(strict=True)
    binary = base / "llama-server.exe"
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    model = (ROOT / "models/MiniCPM5-2B-GGUF/MiniCPM5-2B-Q8_0.gguf").resolve()
    historical = legacy.DATASET_DIR / legacy.DATASETS["test"]
    audit = rescore.read_json(ROOT / "evidence/IJ07/baseline_manifest.json")
    selected = set(audit["recalculated"]["vulkan"]["v1_pass_with_empty_ticket_tags"]) | {"tc-seq-0043"}
    fixture_data = build(include_lexical=True)
    validators = validators_for(fixture_data["tools"])
    result = {
        "run_id": "ij07-upstream-" + uuid4().hex, "git": legacy.git_state(), "started_utc": legacy.utc_now(),
        "engine": {**release, "exe_sha256": legacy.sha256_of(binary),
                   "dll_sha256": {dll.name: legacy.sha256_of(dll) for dll in sorted(base.glob("*.dll"))}},
        "model_sha256": legacy.sha256_of(model), "dataset_sha256": legacy.sha256_of(historical),
        "fixture_version": fixture_data["version"], "historical": [], "parser_fixtures": [],
    }
    env = dict(os.environ)
    env.pop("LLAMA_IJ07_TRACE_PATH", None)
    with gpu_server(binary, model, "vulkan", env, output, args.port, "upstream", False,
                    build_prefix=f'{release["tag"]}-{release["commit"][:8]}') as (client, launch):
        result["launch"] = launch
        eos = eos_token_id(client.base_url)
        for fixture in fixture_data["fixtures"]:
            row = trial(client.base_url, ALIAS, fixture_data["tools"], fixture, eos, validators)
            result["parser_fixtures"].append(row)
        for case in rescore.json_lines(historical):
            if case["id"] in selected:
                sample = run_case(case, client)
                sample["run_id"] = result["run_id"]
                sample["rescored_v2"] = rescore.rescore(case, sample)
                result["historical"].append(sample)
                print(case["id"], sample["rescored_v2"]["status"], flush=True)
    launch_file = output / "launch.json"
    legacy.write_json(launch_file, {**launch, "status": "PASS"})
    result["physical_gpu"] = "PASS" if verify_gpu(
        {"gpu_launch": launch_file, "gpu_counters": output / launch["counter_file"]}, "vulkan",
    ) else "FAIL"
    result["summary"] = {
        "fixtures": dict(Counter(row["status"] for row in result["parser_fixtures"])),
        "historical_v2": dict(Counter(row["rescored_v2"]["status"] for row in result["historical"])),
    }
    result["finished_utc"] = legacy.utc_now()
    legacy.write_json(output / "report.json", result)
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
