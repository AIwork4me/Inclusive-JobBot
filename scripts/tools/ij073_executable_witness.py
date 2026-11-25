"""Compile each public plan before opening its private sandbox, then execute only that graph."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.contract import request
from benchmarks.agentic_planning_v1.oracle import score
from benchmarks.agentic_planning_v1.sandbox import SyntheticSandbox
from benchmarks.agentic_planning_v2.budgets import assess_budgets
from benchmarks.agentic_planning_v2.execution import execute
from benchmarks.agentic_planning_v2.oracle import validate
from benchmarks.agentic_planning_v2.public_witness import build
from benchmarks.agentic_planning_v2.safety import reconcile
from benchmarks.tool_calling_v2.oracle import equal
from scripts.tools.ij073_baseline import VALIDITY, read, records


def audit():
    dataset = Path("benchmarks/agentic_planning_v1")
    public = list(records(dataset / "datasets/holdout.jsonl"))
    graphs = {r["case_id"]: r for r in records(dataset / "task_graphs/holdout.jsonl")}
    validated = {}
    results = []
    plans = {}
    for case in public:
        plan, contract, initial = build(request(case, "P"))
        raw = json.dumps([plan, contract], sort_keys=True)
        # Public plans refer to the subject through a binding, so the same
        # normalized contract and graph can reuse structural validation.
        if raw not in validated:
            validated[raw] = validate(plan, contract)
        identity = hashlib.sha256(raw.encode()).hexdigest()
        plans[identity] = {"plan": plan, "contract": contract}
        errors = validated[raw][:]
        graph = graphs[case["case_id"]]
        sandbox = SyntheticSandbox(graph["world"])
        ledger = []
        def invoke(tool, args):
            before = sandbox.snapshot()
            reply = sandbox.invoke(tool, args)
            ledger.append({"before": before, "after": sandbox.snapshot(), "tool": tool, "args": args, "observation": reply})
            return reply
        outcome = {"final": None, "records": [], "reason": "invalid plan"}
        if not errors:
            outcome = execute(plan, initial, case["action_budget"], invoke)
            if not equal(outcome["final"], graph["final"]):
                errors.append("terminal answer")
            if not equal(sandbox.snapshot(), graph["goal_state"]):
                errors.append("business state")
            scored = [{**record, "origin": "model", "trigger": "tool_feedback" if index else "user_request"}
                      for index, record in enumerate(outcome["records"])]
            # Frozen scorer requires the proposal role. This remains a deterministic software control.
            v1 = score(case, graph, scored, sandbox.snapshot(), outcome["final"], track="A")
            if v1["status"] != "PASS":
                errors.append("frozen action, outcome or safety check")
        safety = reconcile(initial, ledger)
        if safety["status"] != "PASS":
            errors.append("safety reconciliation")
        results.append({"safety": safety, "state_transitions": [{"before": r["before"], "after": r["after"]} for r in ledger],
                        "case_id": case["case_id"], "plan_and_contract_sha256": identity,
                        "nodes": len(plan["actions"]), "budget": case["action_budget"], "errors": errors,
                        "resources": assess_budgets(plan, {"tool_calls": case["action_budget"],
                                                  "peak_context_tokens": case["context_token_budget"]},
                                                  calls=len(outcome["records"])),
                        "status": "FAIL" if errors else "PASS", **outcome})
    by_id = {r["case_id"]: r for r in results}
    paired = []
    for group in read(VALIDITY / "planning-public-ambiguity.json")["groups"]:
        members = [by_id[r["case_id"]] for r in group["cases"]]
        ids = {r["plan_and_contract_sha256"] for r in members}
        paths = {tuple(c["tool"] for c in r["records"]) for r in members}
        paired.append({"cases": [r["case_id"] for r in members], "plans": sorted(ids), "distinct_paths": len(paths),
                       "status": "PASS" if len(ids) == 1 and len(paths) > 1 and all(r["status"] == "PASS" for r in members) else "FAIL"})
    return {"plans": plans, "public_equivalent_groups": paired, "scope": "independently executed repaired software witness, frozen V1 worlds",
            "counts": dict(Counter(r["status"] for r in results)), "rows": results}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
