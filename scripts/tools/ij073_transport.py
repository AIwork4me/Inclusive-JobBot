"""Run one preregistered local V2 transport diagnostic in each generation mode."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import uuid

from benchmarks.agentic_planning_v2.runner import evaluate_raw, plan_request
from benchmarks.competitive_slm.tc_v2_candidate import server_environment, verify_launch, verify_runtime
from benchmarks.root_cause.historical_replay import gpu_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("model", "engine", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--port", type=int, default=18743)
    args = parser.parse_args()
    if subprocess.check_output(["git", "status", "--porcelain"]).strip():
        raise ValueError("diagnostic source tree is dirty")
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    engine, model = args.engine.resolve(), args.model.resolve()
    identity = verify_runtime("J", model, engine)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    task = "The date range for the review of DEMO is missing. Ask for the dates. Return subject and reason date_range_required."
    public = {"subject": "DEMO"}
    limits = {"tool_calls": 0, "model_requests": 1, "retries": 0, "peak_context_tokens": 8192}
    contract = {"goal": "clarify_dates", "public_fields": ["subject"], "event_fields": [], "tools": {}, "action_budget": 0}
    world = {"public": public, "steps": [], "disposition": "clarify", "facts": {"subject": "DEMO", "reason": "date_range_required"}}
    run = {"scope": "two single-attempt development transport diagnostics", "source": source, "identity": identity,
           "run_id": "ij073-wire-" + uuid.uuid4().hex, "sdk_installed": version("google-antigravity"), "sdk_used": False,
           "case_sha256": hashlib.sha256(json.dumps([task, contract, world], sort_keys=True).encode()).hexdigest(),
           "world": world, "trials": []}
    output = args.output / "transport.json"
    with gpu_server(engine / "llama-server.exe", model, "vulkan", server_environment(), args.output, args.port,
                    "transport", True, alias="ij07-candidate-j") as (client, launch):
        verify_launch(launch, identity)
        run["launch"] = launch
        for mode in ("native", "constrained"):
            body = plan_request("ij07-candidate-j", task, public, contract, limits, mode == "constrained")
            body.update(temperature=0, seed=41909, max_tokens=512, stream=False, cache_prompt=False,
                        chat_template_kwargs={"enable_thinking": False})
            response = client.chat(client.base_url, body)
            capture = client.requests[-1]
            raw = response.get("choices", [{}])[0].get("message", {}).get("content")
            scored = evaluate_raw(raw, contract, [world]) if isinstance(raw, str) else {"status": "NOT_RUN"}
            run["trials"].append({"mode": mode, "capture": capture, "evaluation": scored})
            output.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf8")
    run["gpu_samples_sha256"] = hashlib.sha256((args.output / launch["counter_file"]).read_bytes()).hexdigest()
    output.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf8")


if __name__ == "__main__":
    main()
