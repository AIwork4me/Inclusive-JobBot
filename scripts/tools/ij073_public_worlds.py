"""Counterfactual software worlds authored independently of the frozen case generator."""
from copy import deepcopy
from itertools import product
import json

from benchmarks.agentic_planning_v2.runner import evaluate_raw


def review_plan():
    def pointer(source, name):
        return {"from": source, "field": name}

    risk = pointer("read", "score")
    threshold = pointer("public", "threshold")
    needs_review = {"op": "gt", "left": risk, "right": threshold}
    known = {"op": "exists", "ref": risk}
    timeout = {"op": "eq", "left": pointer("read", "code"), "right": "timeout"}
    return {"version": 2, "goal": "classify", "actions": [
        {"id": "read", "tool": "observe", "when": True, "depends_on": [], "arguments": {}},
        {"id": "recover", "tool": "backup", "when": timeout, "depends_on": ["read"], "arguments": {}},
        {"id": "review", "tool": "review", "when": needs_review, "depends_on": ["read"],
         "arguments": {"value": risk}}],
        "stops": [{"when": {"op": "exists", "ref": pointer("review", "label")}, "disposition": "completed",
                   "facts": {"class": pointer("review", "label")}},
                  {"when": {"op": "and", "args": [known, {"op": "not", "arg": needs_review}]},
                   "disposition": "completed", "facts": {"class": "routine"}},
                  {"when": {"op": "exists", "ref": pointer("recover", "missing")}, "disposition": "clarify",
                   "facts": {"reason": "measurement_required"}}]}


def run():
    contract = {"goal": "classify", "public_fields": ["threshold"], "event_fields": [], "action_budget": 2,
                "tools": {"observe": {"inputs": [], "outputs": ["score", "code"]},
                          "backup": {"inputs": [], "outputs": ["missing"]},
                          "review": {"inputs": ["value"], "outputs": ["label"]}}}
    original = review_plan()
    worlds = []
    for cutoff, measurement in product((-2, 0, 5), (None, -3, -2, 0, 1, 5, 6)):
        observed = {"code": "timeout"} if measurement is None else {"code": "ok", "score": measurement}
        steps = [{"tool": "observe", "args": {}, "result": observed}]
        if measurement is None:
            steps.append({"tool": "backup", "args": {}, "result": {"missing": True}})
            disposition, facts = "clarify", {"reason": "measurement_required"}
        elif measurement > cutoff:
            steps.append({"tool": "review", "args": {"value": measurement}, "result": {"label": "inspected"}})
            disposition, facts = "completed", {"class": "inspected"}
        else:
            disposition, facts = "completed", {"class": "routine"}
        worlds.append({"public": {"threshold": cutoff}, "steps": steps, "disposition": disposition, "facts": facts})
    cases = []

    def check(name, plan, expected):
        result = evaluate_raw(json.dumps(plan), contract, worlds)
        cases.append({"name": name, "expected": expected, "actual": result["status"],
                      "errors": result["errors"], "worlds": result["worlds"],
                      "control_status": "PASS" if result["status"] == expected else "FAIL"})

    check("declared branches", original, "PASS")
    changed = deepcopy(original)
    changed["actions"].reverse()
    check("dependency-ordered execution after list reversal", changed, "PASS")
    changed = deepcopy(original)
    changed["actions"][2]["when"]["op"] = "ge"
    check("inclusive boundary changes policy", changed, "FAIL")
    changed = deepcopy(original)
    changed["actions"][0]["depends_on"] = ["recover"]
    check("recovery cycle", changed, "FAIL")
    changed = deepcopy(original)
    changed["actions"][2]["when"] = True
    check("redundant review guard due to prior terminal test", changed, "PASS")
    changed["stops"][1]["when"] = False
    check("extra review below threshold", changed, "FAIL")
    changed = deepcopy(original)
    changed["actions"][2]["arguments"]["value"] = {"from": "public", "field": "future_score"}
    check("private future reference", changed, "FAIL")
    changed = deepcopy(original)
    changed["stops"][0]["facts"]["class"] = "routine"
    check("correct path with unsupported answer", changed, "FAIL")
    changed = deepcopy(original)
    changed["stops"].append({"when": True, "disposition": "completed", "facts": {"class": "routine"}})
    check("premature success with plausible answer", changed, "FAIL")
    return {"scope": "independently authored synthetic threshold and recovery controls; no model inference",
            "contract": contract, "public_control_worlds": worlds, "cases": cases}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
