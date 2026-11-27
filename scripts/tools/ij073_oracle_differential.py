"""Cross-check public control replay, executable graphs and independent trace/state grading."""
import argparse
from collections import Counter
from pathlib import Path

from benchmarks.agentic_planning_v1.sandbox import SyntheticSandbox
from benchmarks.agentic_planning_v2.execution import execute
from benchmarks.agentic_planning_v2.oracle import verify
from benchmarks.agentic_planning_v2.safety import reconcile
from benchmarks.agentic_planning_v2.trace import assess
from benchmarks.atlas_validity.planning_intent_witness import REFERENCE
from scripts.tools.ij073_baseline import VALIDITY, read, records
from scripts.tools.ij073_oracle_event_matrix import audit as event_matrix

OUT = Path("evidence/IJ073/oracle/differential_closure.json")


def audit():
    base = Path("benchmarks/agentic_planning_v1")
    cases, graphs = ({r["case_id"]: r for r in records(base / group / "holdout.jsonl")}
                     for group in ("datasets", "task_graphs"))
    archived = read(Path("evidence/IJ073/oracle/executable_witness.json"))
    validations = []
    for row in archived["rows"]:
        key = row["case_id"]
        spec = archived["plans"][row["plan_and_contract_sha256"]]
        contract = {**spec["contract"], "action_budget": row["budget"]}
        public = {"subject": REFERENCE.search(cases[key]["prompt"])[0]}
        plan = spec["plan"]
        sandbox = SyntheticSandbox(graphs[key]["world"])
        before = sandbox.snapshot()
        ledger = []

        def invoke(tool, args):
            start = sandbox.snapshot()
            reply = sandbox.invoke(tool, args)
            ledger.append({"tool": tool, "args": args, "observation": reply, "before": start, "after": sandbox.snapshot()})
            return reply

        actual = execute(plan, public, row["budget"], invoke, contract=contract)
        world = {"public": public, **row["final"], "steps": []}
        for cell in row["records"]:
            reply = cell["observation"]
            step = {"tool": cell["tool"], "args": cell["args"], "result": {**reply["data"], "code": reply["code"]}}
            if "external_event" in reply:
                step["event"] = reply["external_event"]
            world["steps"].append(step)
        tested = verify(plan, contract, [world])
        trace = assess(cases[key], graphs[key], {"before_state": before, "after_state": sandbox.snapshot(),
                       "records": actual["records"], "final_raw": actual["final"]})
        safety = reconcile(public, ledger)
        ok = (tested["status"] == "PASS" and actual["final"] == row["final"] and actual["records"] == row["records"]
              and trace["final_and_state"] == "PASS" and not trace["trace_errors"] and not trace["authorization_errors"]
              and safety["status"] == "PASS")
        validations.append({"case_id": key, "simulated": tested["status"], "sandbox_calls": len(ledger),
                            "trace": trace["trace_replay"], "safety": safety["status"], "terminal": trace["final_and_state"],
                            "differential": "PASS" if ok else "FAIL"})
    aligned = read(Path("evidence/IJ073/oracle/legacy_alignment.json"))
    originals = {r["case_id"]: r for r in read(VALIDITY / "planning-plan-controls.json.gz")["trials"]}
    discrepancies = []
    for r in aligned["rows"]:
        if r["original"] != "PASS" or r["trace_representability"] != "FAIL":
            continue
        old = originals[r["case_id"]]
        prefix = r["matched_prefix"]
        tool = old["calls"][prefix]["tool"]
        nodes = [n["id"] for n in old["initial_plan"]["actions"] if n["tool"] == tool]
        prior = [c["tool"] for c in old["calls"][:prefix]]
        if nodes and len(nodes) > prior.count(tool):
            raise ValueError("mismatch needs a binding-level investigation")
        discrepancies.append({"case_id": r["case_id"], "first_divergent_call": prefix + 1, "required_tool": tool,
                              "available_node_ids": nodes, "used_prior": prior.count(tool),
                              "trigger": old["calls"][prefix-1]["observation"],
                              "reason": "all matching nodes consumed" if nodes else "required tool absent from graph"})
    if len(validations) != 800 or len(discrepancies) != 235:
        raise ValueError("unexpected frozen cohort")
    return {"scope": "offline synthetic frozen worlds, not arbitrary-world completeness",
            "baseline": "88786ed8f01e9faf37ae458e66a6d9e953daba44",
            "differential_counts": dict(Counter(r["differential"] for r in validations)),
            "legacy_divergence_by_tool": dict(Counter(r["required_tool"] for r in discrepancies)),
            "independent_event_controls": event_matrix(),
            "legacy_discrepancies": discrepancies, "rows": validations}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = audit()
    from scripts.tools.ij073_verify import encoded
    expected = encoded(data)
    if args.write:
        OUT.write_bytes(expected)
    elif OUT.read_bytes() != expected:
        raise SystemExit("differential evidence mismatch")
    print(data["differential_counts"], data["legacy_divergence_by_tool"])
