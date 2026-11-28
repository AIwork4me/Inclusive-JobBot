"""Translate interventions to AST, then compare necessary public effects before/after."""
import json
from collections import Counter
from pathlib import Path

from benchmarks.agentic_planning_v2.reachability import missing_effects
from scripts.tools.ij073_baseline import VALIDITY, read, records


def requirements(case):
    tools, prompt = case["tools"], case["prompt"]
    if "audit_read" in tools:
        groups = [{"lookup"}, {"audit_read"}]
        if "draft_id" in prompt:
            groups.extend([{"stage"}, {"verify_draft"}])
        if "audit_ref" in prompt:
            groups.extend([{"commit"}, {"verify_delivery"}])
        return groups
    if "read_record" in tools and "status" in prompt:
        return [{"lookup"}, {"archive"}]
    if "check_policy" in tools:
        return [{"lookup"}, {"check_policy"}]
    groups = []
    if "status" in prompt:
        groups.append({"status", "status_mirror"})
    if "classification" in prompt:
        groups.append({"archive"})
    return groups


def run():
    directory = Path("benchmarks/agentic_planning_v1/datasets")
    cases = {r["case_id"]: r for r in records(directory / "holdout.jsonl")}
    plans = {r["case_id"]: r["initial_plan"] for r in read(VALIDITY / "planning-plan-controls.json.gz")["trials"]}
    # These ASTs encode the two published experimental treatments. The
    # verifier receives only an AST, never a mutation label or a case ID.
    treatments = {"disable_first_action": False, "require_denied_approval": {
        "op": "eq", "left": {"from": "event", "field": "decision"}, "right": "declined"}}
    rows = []
    for trial in read(VALIDITY / "planning-precondition-controls.json")["trials"]:
        case_id = trial["case_id"]
        groups = requirements(cases[case_id])
        actions = [{**node, "when": True} for node in plans[case_id]["actions"]]
        before = missing_effects(actions, groups, {})
        target, = (node for node in actions if node["id"] == trial["action_id"])
        target["when"] = treatments[trial["mutation"]]
        after = missing_effects(actions, groups, {})
        rows.append({"case_id": case_id, "mutation": trial["mutation"], "action_id": target["id"],
                     "baseline_missing": before, "mutated_missing": after, "old_control": trial["status"],
                     "clean_baseline_transition": not before and bool(after),
                     "additional_missing": [group for group in after if group not in before],
                     "causal_rejection": "PASS" if any(group not in before for group in after) else "FAIL"})
    return {"scope": "necessary public effect reachability; non-intervened prose guards relaxed to true",
            "counts": dict(Counter(r["mutation"]+"/"+r["causal_rejection"] for r in rows)), "trials": rows}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
