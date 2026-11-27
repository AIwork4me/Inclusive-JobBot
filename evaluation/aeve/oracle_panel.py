"""Public request roster for paired clarification and L0–L7 planning diagnostics."""
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.contract import request
from benchmarks.agentic_planning_v2.public_witness import build
from benchmarks.agentic_planning_v2.runner import plan_request
from .runtime import ROOT


def panel():
    # Reuse the exact input of the physical public-binding control.
    existing = json.loads((ROOT / "evidence/IJ073/transport/public/transport.json").read_bytes())
    old = existing["trials"][0]["capture"]["request"]
    visible = json.loads(old["messages"][1]["content"])
    task, public, limits = visible["task"], visible["public"], visible["limits"]
    contract = {"goal": visible["goal"], "tools": visible["tools"], "public_fields": list(public),
                "event_fields": visible["external_event_fields"], "action_budget": limits["tool_calls"]}
    for arm, changes in (("original", {}), ("clarification", {"clarify": True}),
                         ("tools", {"dynamic_tools": True}), ("zero", {"zero_actions": True}),
                         ("combined", {"clarify": True, "dynamic_tools": True, "zero_actions": True})):
        for mode in ("native", "constrained"):
            body = plan_request(old["model"], task, public, contract, limits, mode == "constrained", **changes)
            body.update({k: old[k] for k in ("temperature", "seed", "max_tokens", "stream", "cache_prompt", "chat_template_kwargs")})
            yield {"suite": "clarification", "case": "DEMO", "arm": arm, "mode": mode,
                   "track": "provided", "contract": contract, "world": existing["world"], "body": body}
    dataset = ROOT / "benchmarks/agentic_planning_v1/datasets/holdout.jsonl"
    cases = [json.loads(line) for line in dataset.read_bytes().splitlines()]
    witness = json.loads((ROOT / "evidence/IJ073/oracle/executable_witness.json").read_bytes())["rows"]
    traces = {r["case_id"]: r for r in witness}
    for level in range(8):
        for language in ("en", "zh"):
            pool = [c for c in cases if c["level"] == f"L{level}" and c["language"] == language]
            # Include explicit external denial or scope changes in the upper levels when present.
            def order(c):
                observations = [s["observation"] for s in traces[c["case_id"]]["records"]]
                special = any(s.get("code") in {"approval_declined", "permission_denied"}
                              or "revised_reference" in s.get("external_event", {}) for s in observations)
                return (not special, c["case_id"])
            case = min(pool, key=order)
            _, contract, public = build(request(case, "P"))
            contract = dict(contract, action_budget=case["action_budget"])
            limits = {"tool_calls": case["action_budget"], "model_requests": 1, "retries": 0,
                      "peak_context_tokens": min(case["context_token_budget"], 8192)}
            task = case["prompt"] + ("\n" + case["policy"] if case.get("policy") else "")
            for track in ("provided", "inferred"):
                for mode in ("native", "constrained"):
                    body = plan_request(old["model"], task, public, contract, limits, mode == "constrained",
                                        goal_track=track, clarify=True, dynamic_tools=True, zero_actions=True)
                    body.update(temperature=0, seed=41909, max_tokens=768, stream=False, cache_prompt=False,
                                chat_template_kwargs={"enable_thinking": False})
                    yield {"suite": "planning-development", "case": case["case_id"], "arm": "combined",
                           "level": level, "language": language, "mode": mode, "track": track, "contract": contract,
                           "public": public, "body": body}
