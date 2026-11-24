"""Test a one-variable Plan-first prompt change on separate CPU development cases."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
from uuid import uuid4

from benchmarks.agentic_planning_v1.contract import FINAL_PROMPT, request
from benchmarks.agentic_planning_v1.oracle import initial_plan
from benchmarks.competitive_slm.admission import cpu_server
from benchmarks.root_cause.generation_capture import CaptureClient
from benchmarks.root_cause.historical_replay import ALIAS, ROOT, legacy
from model_gateway import decode_completion


DEV = (
    ("REF-91-70001", "review", "Review the pending meter discrepancy {id}, read-only. Summarize my request and say if a tool is needed just to summarize."),
    ("REF-91-70002", "current_status", "I need current status for shipment correction {id}, read-only. For now summarize the request and say if that needs a tool."),
    ("REF-91-70003", "review", "我要只读审核收货差异{id}。先总结已给出的请求并说明仅总结是否需要工具。"),
    ("REF-91-70004", "current_status", "我想只读查询返修批次{id}的现行状态。先总结我的请求并说明仅总结是否需要工具。"),
)


def run(args):
    binary = args.engine_dir.resolve() / "llama-server.exe"
    model = (ROOT / "models/MiniCPM5-2B-GGUF/MiniCPM5-2B-Q8_0.gguf").resolve()
    models = json.loads((ROOT / "models/model_manifest.json").read_bytes())["models"]
    pin = next(item for item in models
               if item["model_id"] == "OpenBMB/MiniCPM5-2B-GGUF")
    actual = legacy.sha256_of(model)
    if not any(row["path"] == model.name and row["sha256"] == actual for row in pin["files"]):
        raise ValueError("development profile model identity mismatch")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    trace = output / "generation.jsonl"
    os.environ["LLAMA_IJ07_TRACE_PATH"] = str(trace)
    rows = []
    with cpu_server(binary, model, args.port, output / "server.log", ALIAS) as (_, build):
        client = CaptureClient(args.port, trace)
        for reference, objective, message in DEV:
            case = {"prompt": message.format(id=reference), "tools": [], "action_budget": 0}
            graph = {"goal": {"subject": reference, "objective": objective}, "nodes": {}, "witness": [],
                     "required_subgoals": [], "disruption": None, "policy_condition": None}
            for profile in ("both_contracts", "first_turn_plan_only"):
                prepared = request(case, "P")
                system = prepared["messages"][0]
                if profile == "first_turn_plan_only":
                    ending = "\n\n" + FINAL_PROMPT
                    if not system["content"].endswith(ending):
                        raise ValueError("the first-turn contract changed")
                    system["content"] = system["content"].removesuffix(ending)
                body = {"model": ALIAS, "messages": prepared["messages"], "temperature": 0, "seed": 41909,
                        "stream": False, "cache_prompt": False, "max_tokens": 512,
                        "chat_template_kwargs": {"enable_thinking": False}}
                client.chat(client.base_url, body)
                wire = client.requests[-1]
                if wire["source_generation"].get("status") == "BLOCKED":
                    raise ValueError("CPU source capture unavailable")
                decoded = decode_completion(wire["raw_response"])
                score = initial_plan(case, graph, decoded.content)
                rows.append({"reference": reference, "profile": profile, "expected_goal": graph["goal"],
                             "score": score, "proposed_calls": len(decoded.calls), "wire": wire})
    counts = {profile: dict(Counter("PASS" if row["score"]["executable"] and row["score"]["goal_understood"]
                                    and not row["proposed_calls"] else "FAIL"
                                    for row in rows if row["profile"] == profile))
              for profile in ("both_contracts", "first_turn_plan_only")}
    legacy.write_json(output / "report.json", {
        "run_id": "ij07-plan-prompt-control-" + uuid4().hex, "git": legacy.git_state(), "backend": "cpu",
        "scope": "four new development prompts; only the terminal-answer instruction is removed in the control",
        "source_sha256": legacy.sha256_of(Path(__file__)), "build": build,
        "engine_exe_sha256": legacy.sha256_of(binary), "runtime_dll_sha256": {
            file.name: legacy.sha256_of(file) for file in sorted(binary.parent.glob("*.dll"))
        }, "modelscope_revision": pin["revision"],
        "model_sha256": actual, "outcomes": counts, "rows": rows, "subsequent_turns": "NOT_RUN",
    })
    print(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8099)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
