"""Exercise the offline assessment of actual Planning V2 trajectories."""

from copy import deepcopy

from evaluation.aeve.runtime import canonical, fingerprint

from benchmarks.slm10.planning_matched_assessment import assess_trial
from benchmarks.slm10.planning_public_authoring import public_cases
from benchmarks.slm10.planning_source_controls import build_control


def fixture(level, world_id):
    case = next(row for row in public_cases() if row["level"] == level)
    proof = build_control(case)
    world = next(row for row in proof["worlds"] if row["world_id"] == world_id)
    calls = []
    for step in world["steps"]:
        data = step["result"].copy()
        observation = {"code": data.pop("code", "ok"), "data": data}
        if "event" in step:
            observation["external_event"] = step["event"]
        calls.append({"tool": step["tool"], "args": step["args"], "observation": observation,
                      "before": step.get("before", {}), "after": step.get("after_state", {})})
    trial = {"case_id": case["case_id"], "public_sha256": fingerprint(case), "track": "direct_plan_first",
             "plan_raw": canonical(proof["witness"]).decode(), "answer": canonical(world["facts"]).decode(),
             "calls": calls, "complete": True, "before": calls[0]["before"], "after": calls[-1]["after"]}
    return case, proof, world, trial


def test_legal_alternative_order_remains_eligible_for_scoped_replay():
    case, proof, world, trial = fixture("L2", "primary")
    trial["calls"].reverse()
    result = assess_trial(case, proof, world["world_id"], trial)
    assert result["software_dimensions"]["actual_call_path"] == "PASS"
    assert result["software_dimensions"]["final_facts"] == "PASS"
    assert result["formal_dimensions"]["D25"] == "BLOCKED"


def test_terminal_fact_cannot_make_stale_scope_path_pass():
    case, proof, world, trial = fixture("L5", "scope_revision")
    mutated = deepcopy(trial)
    mutated["calls"][-1]["args"]["reference"] = case["public"]["reference"]
    result = assess_trial(case, proof, world["world_id"], mutated)
    assert result["software_dimensions"]["final_facts"] == "PASS"
    assert result["software_dimensions"]["actual_call_path"] == "FAIL"
    assert result["software_dimensions"]["observed_workflow"] == "FAIL"


def test_alternate_business_route_is_a_condition_not_an_execution_fault():
    case, proof, world, trial = fixture("L4", "alternate_source")
    verdicts = assess_trial(case, proof, world["world_id"], trial)["software_dimensions"]
    assert verdicts["conditional_route"] == "PASS"
    assert verdicts["recovery_response"] == "NOT_RUN"
