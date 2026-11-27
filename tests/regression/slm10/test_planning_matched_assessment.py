"""Exercise the offline assessment of actual Planning V2 trajectories."""

from copy import deepcopy
from hashlib import sha256

import pytest

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
    assert result["software_dimensions"]["plan_validity"] == "PASS"
    assert result["software_dimensions"]["plan_executability"] == "PASS"
    assert result["software_dimensions"]["plan_to_execution_alignment"] == "FAIL"
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


def test_actual_scope_response_does_not_establish_an_explicit_replan():
    case, proof, world, trial = fixture("L5", "revised_primary_unavailable")
    results = assess_trial(case, proof, world["world_id"], trial)
    software = results["software_dimensions"]
    assert software["scope_revision_response"] == "PASS"
    assert software["recovery_response"] == "PASS"
    assert software["plan_to_execution_alignment"] == "PASS"
    assert software["dynamic_replanning"] == "BLOCKED"
    assert "dynamic_replanning" in results["evidence_gaps"]
    assert results["formal_dimensions"]["D12"] == "BLOCKED"


def test_state_and_authorization_are_assessed_independently():
    case, proof, world, trial = fixture("L7", "approved")
    valid = assess_trial(case, proof, world["world_id"], trial)["software_dimensions"]
    assert valid["authorization_trace"] == "PASS"
    assert valid["persisted_state"] == "PASS"

    wrong_state = deepcopy(trial)
    wrong_state["calls"][-1]["after"]["deliverables"] = {}
    wrong_state["after"] = wrong_state["calls"][-1]["after"]
    scored = assess_trial(case, proof, world["world_id"], wrong_state)["software_dimensions"]
    assert scored["authorization_trace"] == "PASS"
    assert scored["persisted_state"] == "FAIL"
    assert scored["actual_call_path"] == "PASS"

    unauthorized = deepcopy(trial)
    unauthorized["calls"][2]["observation"].pop("external_event")
    scored = assess_trial(case, proof, world["world_id"], unauthorized)["software_dimensions"]
    assert scored["authorization_trace"] == "FAIL"
    assert scored["persisted_state"] == "PASS"
    assert scored["actual_call_path"] == "FAIL"

    wrong_audit = deepcopy(trial)
    wrong_audit["calls"][0]["args"]["reference"] += "-WRONG"
    scored = assess_trial(case, proof, world["world_id"], wrong_audit)["software_dimensions"]
    assert scored["authorization_trace"] == "FAIL"


def test_invalid_plan_goal_is_separate_from_structural_validity():
    case = next(row for row in public_cases() if row["level"] == "L0" and row["public"])
    proof = build_control(case)
    incorrect = proof["witness"] | {"goal": "request_reference"}
    trial = {"case_id": case["case_id"], "public_sha256": fingerprint(case), "track": "direct_plan_first",
             "plan_raw": canonical(incorrect).decode(), "answer": canonical(proof["worlds"][0]["facts"]).decode(),
             "calls": [], "complete": True, "before": {}, "after": {}}
    scored = assess_trial(case, proof, proof["worlds"][0]["world_id"], trial)["software_dimensions"]
    assert scored["goal_inference"] == "FAIL"
    assert scored["plan_validity"] == "PASS"
    assert scored["plan_executability"] == "FAIL"
    assert scored["business_facts"] == "PASS"


def test_trace_binding_is_distinct_from_software_scoring_and_a_formal_credential():
    case, proof, world, trial = fixture("L1", "primary")
    unbound = assess_trial(case, proof, world["world_id"], trial)
    assert unbound["world_binding"] == "BLOCKED"
    assert unbound["software_dimensions"]["strict_e2e_necessary_conditions"] == "PASS"
    assert unbound["formal_dimensions"]["D25"] == "BLOCKED"
    assert "D25" in unbound["credential_gaps"]
    trial.update(world_id=world["world_id"], world_sha256=fingerprint(world))
    assert assess_trial(case, proof, world["world_id"], trial)["world_binding"] == "PASS"
    trial["world_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="world digest"):
        assess_trial(case, proof, world["world_id"], trial)


def test_authorization_scores_observed_rejected_commit_proposal_separately_from_callbacks():
    case, proof, world, trial = fixture("L7", "declined")
    draft_id = trial["calls"][-1]["args"]["draft_id"]
    proposed_calls = [*trial["calls"], {"tool": "commit", "args": {"draft_id": draft_id, "approval": "invalid"}}]
    wire = []
    for index, call in enumerate(proposed_calls):
        call.update(call_id=f"call-{index}", provider_request_id=f"request-{index}", completion_id=f"completion-{index}")
        message = {"role": "assistant", "content": None, "tool_calls": [{"type": "function", "id": call["call_id"],
                   "function": {"name": call["tool"], "arguments": canonical(call["args"]).decode()}}]}
        raw = canonical({"id": call["completion_id"], "object": "chat.completion",
                         "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls"}]})
        wire.append({"phase": "act", "provider_request_id": call["provider_request_id"],
                     "http_status": 200, "content_type": "application/json", "response": raw.decode(),
                     "response_sha256": sha256(raw).hexdigest(), "completion_id": call["completion_id"]})
    trial.update(wire=wire, complete=False, answer=None)
    scored = assess_trial(case, proof, world["world_id"], trial)["software_dimensions"]
    assert scored["authorization_trace"] == "BLOCKED"
    assert scored["authorization_proposals"] == "FAIL"
    assert scored["strict_e2e_necessary_conditions"] == "FAIL"


def test_l6_stage_provenance_in_the_actual_assessment_path():
    case, proof, world, trial = fixture("L6", "reviewed_draft")
    dimensions = assess_trial(case, proof, world["world_id"], trial)["software_dimensions"]
    assert dimensions["stage_provenance"] == "PASS"

    overridden = deepcopy(trial)
    stage = overridden["calls"][-1]
    stage["args"]["assessment"] = "unobserved assessment"
    stage["after"]["drafts"][stage["observation"]["data"]["draft_id"]]["assessment"] = "unobserved assessment"
    assert assess_trial(case, proof, world["world_id"], overridden)["software_dimensions"]["stage_provenance"] == "FAIL"

    different_draft = deepcopy(trial)
    stage = different_draft["calls"][-1]
    stage["after"]["drafts"][stage["observation"]["data"]["draft_id"]]["reference"] = "unrelated subject"
    assert assess_trial(case, proof, world["world_id"], different_draft)["software_dimensions"]["stage_provenance"] == "FAIL"
