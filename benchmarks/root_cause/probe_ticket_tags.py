"""Repeat empty-tag cases while changing one input constraint or weight precision."""

import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
from uuid import uuid4

from benchmarks.competitive_slm.admission import cpu_server
from benchmarks.root_cause.generation_capture import CaptureClient
from benchmarks.root_cause.historical_replay import ALIAS, ROOT, legacy, run_case
from benchmarks.tool_calling_v2 import rescore


def evaluate_variant(cases, client, label, report):
    rows = []
    for case in cases:
        stimulus = deepcopy(case)
        if label == "minimum_two_tags":
            schema = next(tool["function"]["parameters"] for tool in stimulus["tools"]
                          if tool["function"]["name"] == "create_ticket")
            schema["properties"]["tags"]["minItems"] = 2
        row = run_case(stimulus, client)
        row["run_id"] = report["run_id"]
        checked = rescore.rescore(case, row)
        tags = [item["arguments"].get("tags") for step in row["steps"] for item in step.get("tool_calls", [])
                if item["name"] == "create_ticket" and isinstance(item.get("arguments"), dict)]
        rows.append({"variant": label, "case_id": case["id"], "observed_ticket_tags": tags,
                     "v2": checked, "original_style": row})
        print(label, case["id"], checked["status"], flush=True)
    return rows


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--engine-dir", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--port", default=8097, type=int, choices=range(1024, 65536), metavar="PORT")
    args = cli.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    binary = args.engine_dir.resolve() / "llama-server.exe"
    trace = output / "generation.jsonl"
    env_var = "LLAMA_IJ07_TRACE_PATH"
    old = os.environ.get(env_var)
    os.environ[env_var] = str(trace)
    historical = legacy.DATASET_DIR / legacy.DATASETS["test"]
    audit = rescore.read_json(ROOT / "evidence/IJ07/baseline_manifest.json")
    ids = set(audit["recalculated"]["vulkan"]["v1_pass_with_empty_ticket_tags"])
    cases = [case for case in rescore.json_lines(historical) if case["id"] in ids]
    gguf = next(m for m in rescore.read_json(ROOT / "models/model_manifest.json")["models"]
                if m["model_id"] == "OpenBMB/MiniCPM5-2B-GGUF")
    report = {
        "run_id": "ij07-tags-" + uuid4().hex, "git": legacy.git_state(), "started_utc": legacy.utc_now(),
        "backend": "cpu", "source_sha256": legacy.sha256_of(Path(__file__)),
        "engine_exe_sha256": legacy.sha256_of(binary), "runtime_dll_sha256": {
            file.name: legacy.sha256_of(file) for file in sorted(binary.parent.glob("*.dll"))
        }, "modelscope_revision": gguf["revision"], "dataset_sha256": legacy.sha256_of(historical),
        "variants": {},
    }
    try:
        for precision, variants in (("Q8_0", ("baseline", "minimum_two_tags")), ("F16", ("f16_reference",))):
            filename = f"MiniCPM5-2B-{precision}.gguf"
            model = (ROOT / gguf["local_dir"] / filename).resolve()
            actual = legacy.sha256_of(model)
            if not any(row["path"] == filename and row["sha256"] == actual for row in gguf["files"]):
                cli.error("model digest differs from ModelScope manifest")
            with cpu_server(binary, model, args.port, output / f"{precision}.log", ALIAS) as (link, build):
                client = CaptureClient(args.port, trace)
                for label in variants:
                    rows = evaluate_variant(cases, client, label, report)
                    report["variants"][label] = {
                        "model_sha256": actual, "build": build, "rows": rows,
                        "v2_status": dict(Counter(row["v2"]["status"] for row in rows)),
                        "empty_api_tags": sum([] in row["observed_ticket_tags"] for row in rows),
                    }
                    legacy.write_json(output / "report.json", report)
    finally:
        if old is None:
            os.environ.pop(env_var, None)
        else:
            os.environ[env_var] = old
    report["finished_utc"] = legacy.utc_now()
    legacy.write_json(output / "report.json", report)


if __name__ == "__main__":
    main()
