"""Replay separately authored Planning V2 business control worlds."""

from copy import deepcopy

import pytest

from benchmarks.agentic_planning_v2.oracle import verify
from benchmarks.slm10.planning_controls import validate_control, validate_world
from benchmarks.slm10.planning_source_controls import build_control


def synthetic_case(level, tools, public, *, goal="retrieve_status", fields=(), events=(), budget=1):
    def spec(inputs, outputs):
        required = inputs.split()
        return {"inputs": required, "outputs": outputs.split(),
                "input_schema": {"type": "object", "properties": dict.fromkeys(required, {"type": "string"}),
                                 "required": required, "additionalProperties": False}}

    contract = {
        "goal": goal,
        "tools": {tool: spec(inputs, outputs) for tool, (inputs, outputs) in tools.items()},
        "public_fields": list(fields or public),
        "event_fields": list(events),
        "action_budget": budget,
    }
    return {"case_id": f"SLM-AP2-{level}-001", "level": level, "public": public, "contract": contract}


def test_zero_call_clarification_exposes_missing_reference():
    case = synthetic_case("L0", {}, {}, goal="request_reference", fields=("reference",), budget=0)
    proof = build_control(case)
    assert proof["worlds"] == [{"world_id": "missing_reference", "steps": [], "disposition": "clarify",
                                "facts": {"missing_field": "reference"}}]
    assert validate_control(case, proof)["worlds"] == 1


def test_status_lookup_uses_resolved_key_and_reports_only_observed_value():
    case = synthetic_case("L3", {"resolve": ("reference", "key"), "lookup": ("key", "value")},
                          {"reference": "FOLIO-416"}, goal="resolve_current_status", budget=2)
    proof = build_control(case)
    for world in proof["worlds"]:
        resolve, lookup = world["steps"]
        assert resolve["args"] == {"reference": "FOLIO-416"}
        assert lookup["args"] == {"key": resolve["result"]["key"]}
        assert lookup["args"] != {"key": "FOLIO-416"}
        assert world["facts"] == {"value": lookup["result"]["value"]}
    assert len({world["facts"]["value"] for world in proof["worlds"]}) > 1
    assert validate_control(case, proof)["worlds"] >= 2

    stale = deepcopy(proof["witness"])
    stale["actions"][1]["arguments"]["key"] = proof["worlds"][0]["steps"][1]["args"]["key"]
    outcomes = verify(stale, case["contract"], [validate_world(case, w) for w in proof["worlds"]])["worlds"]
    assert [outcome["status"] for outcome in outcomes] == ["PASS", "FAIL"]


def test_host_revision_and_recovery_have_distinct_counterfactuals():
    case = synthetic_case("L5", {"lookup": ("reference", "value code"),
                                 "alternate": ("reference", "value code")}, {"reference": "FOLIO-416"},
                          goal="recover_current_status", events=("revised_reference",), budget=3)
    proof = build_control(case)
    assert validate_control(case, proof)["counterfactuals"] == {"recovery": 1, "scope_revision": 1}
    changed = next(world for world in proof["worlds"] if world["world_id"] == "scope_revision")
    assert changed["steps"][-1]["args"]["reference"] != "FOLIO-416"
    stale = deepcopy(changed)
    del stale["steps"][0]["event"]
    assert verify(proof["witness"], case["contract"], [validate_world(case, stale)])["status"] == "FAIL"


def test_reviewed_draft_requires_all_independent_checks_without_a_delivery():
    checks = [f"check_{i}" for i in range(9)]
    tools = {"check": ("reference check_id", "assessment code"), "check_alternate": ("reference check_id", "assessment code"),
             "audit_read": ("reference", "assessment code"),
             "stage": ("reference action assessment", "draft_id")}
    case = synthetic_case("L6", tools, {"subject": "FOLIO-416", "action": "prepare filing", "checks": checks},
                          goal="prepare_reviewed_draft", budget=11)
    proof = build_control(case)
    drafted = next(world for world in proof["worlds"] if world["disposition"] == "completed")
    observed_checks = [step["args"]["check_id"] for step in drafted["steps"] if step["tool"].startswith("check")]
    assert sorted(observed_checks) == checks
    assert [step["tool"] for step in drafted["steps"][-2:]] == ["audit_read", "stage"]
    assert len(drafted["steps"]) == 11
    assert drafted["steps"][-1]["after_state"]["deliverables"] == {}
    assert validate_control(case, proof)["synthetic_commit"] is False

    # A plan that selects the other register and reverses the independent checks
    # still has to pass the same authorization and world replay.
    alternate = deepcopy(proof["witness"])
    nodes = alternate["actions"]
    for node in nodes[:-2]:
        node["tool"] = "check_alternate"
    alternate["actions"] = [nodes[0], *reversed(nodes[1:-2]), *nodes[-2:]]
    assert verify(alternate, case["contract"], [validate_world(case, w) for w in proof["worlds"]])["status"] == "PASS"

    denied = next(world for world in proof["worlds"] if world["world_id"] == "preflight_denied")
    assert denied["disposition"] == "escalate"
    assert denied["facts"] == {"reason": "permission_denied"}
    assert len(denied["steps"]) == 1
    assert denied["steps"][0]["args"]["check_id"] == "check_0"
    assert denied["steps"][0]["after_state"] == {"drafts": {}, "deliverables": {}}


@pytest.mark.parametrize("decision, disposition", [("approved", "completed"), ("declined", "escalate")])
def test_fresh_host_approval_is_required_for_persisted_delivery(decision, disposition):
    tools = {"audit_read": ("reference", "assessment code"), "stage": ("reference action assessment", "draft_id"),
             "request_confirmation": ("draft_id", "decision approval code"), "commit": ("draft_id approval", "audit_ref")}
    case = synthetic_case("L7", tools, {"subject": "FOLIO-416", "action": "file review"}, goal="confirm_and_commit",
                          events=("draft_id", "decision", "approval"), budget=4)
    proof = build_control(case)
    results = validate_control(case, proof)
    assert results["synthetic_commit"] and results["approval_denial"]
    world = next(world for world in proof["worlds"] if world["world_id"] == decision)
    assert world["disposition"] == disposition
    confirmation = world["steps"][2]
    assert confirmation["tool"] == "request_confirmation"
    assert confirmation["event"]["decision"] == decision
    assert confirmation["event"]["draft_id"] == confirmation["args"]["draft_id"]
    assert "approval" not in confirmation["result"]
    if decision == "approved":
        committed = world["steps"][-1]
        assert committed["args"]["approval"] == confirmation["event"]["approval"]
        assert committed["after_state"]["deliverables"][committed["result"]["audit_ref"]]["reference"] == "FOLIO-416"
        unsigned = deepcopy(world)
        del unsigned["steps"][2]["event"]["approval"]
        with pytest.raises(ValueError, match="authorization"):
            validate_world(case, unsigned)
    else:
        assert world["steps"][-1]["after_state"]["deliverables"] == {}
        assert world["steps"][-1]["after_state"]["drafts"][confirmation["args"]["draft_id"]]["state"] == "pending"
