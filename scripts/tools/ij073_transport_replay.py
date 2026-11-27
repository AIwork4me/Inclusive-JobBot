"""Verify the four archived V2 transport attempts and their one-field contrast."""
from copy import deepcopy
import json
from pathlib import Path

from benchmarks.agentic_planning_v2.runner import evaluate_raw
from scripts.tools.ij073_baseline import digest, read, records


def audit():
    runs = {}
    inputs = {}
    summary = []
    for name in ("initial", "public"):
        root = Path("evidence/IJ073/transport") / name
        run = read(root / "transport.json")
        counter_path = root / run["launch"]["counter_file"]
        if digest(counter_path) != run["gpu_samples_sha256"]:
            raise ValueError("counter file differs")
        samples = [r for r in records(counter_path) if r["kind"] == "gpu_engine"
                   and r["instance"].startswith(f"pid_{run['launch']['pid']}_")]
        trace = {r["completion_id"]: r for r in records(root / run["launch"]["trace_file"])}
        if not samples or not any(s["utilization"] > 0 for s in samples):
            raise ValueError("missing active process GPU samples")
        runs[name] = run
        for trial in run["trials"]:
            capture = trial["capture"]
            body = deepcopy(capture["request"])
            visible = json.loads(body["messages"][1]["content"])
            initial = visible.pop(name)
            if initial != run["world"]["public"]:
                raise ValueError("public facts differ")
            body["messages"][1]["content"] = visible
            inputs[name, trial["mode"]] = body
            source = capture["source_generation"]
            if capture["http_status"] != 200 or capture["render_status"] != 200 or source.get("truncated") is not False:
                raise ValueError("incomplete physical response")
            response = json.loads(capture["raw_response"])
            if trace[response["id"]] != source:
                raise ValueError("source capture differs")
            if bool(source["generation_settings"]["grammar"]) != (trial["mode"] == "constrained"):
                raise ValueError("sampler treatment differs")
            content = response["choices"][0]["message"]["content"]
            contract = {"goal": visible["goal"], "public_fields": list(initial), "event_fields": visible["external_event_fields"],
                        "tools": visible["tools"], "action_budget": visible["limits"]["tool_calls"]}
            scored = evaluate_raw(content, contract, [run["world"]])
            if scored != trial["evaluation"]:
                raise ValueError("offline result differs")
            summary.append({"binding": name, "mode": trial["mode"], "plan": scored, "run_id": run["run_id"],
                            "active_pid_engine_samples": sum(s["utilization"] > 0 for s in samples),
                            "pid_engine_samples": len(samples), "prompt_tokens": len(source["prompt_token_ids"]),
                            "generated_tokens": len(source["sampled_token_ids"])})
    if runs["initial"]["identity"] != runs["public"]["identity"] or runs["initial"]["case_sha256"] != runs["public"]["case_sha256"]:
        raise ValueError("paired identities differ")
    for mode in ("native", "constrained"):
        if inputs["initial", mode] != inputs["public", mode]:
            raise ValueError("request differs outside the binding name")
    return {"scope": "one synthetic zero-tool case, Qwen3-14B Q8_0 on Radeon Vulkan, paired development probes", "rows": summary}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
