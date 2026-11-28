"""Negative and metamorphic checks using the original planning wire and policy boundary."""

from copy import deepcopy

import pytest

from benchmarks.agentic_planning_v1.freeze import build
from benchmarks.agentic_planning_v1.oracle import score
from benchmarks.agentic_planning_v1.runner import run_trajectory
from scripts.tools.atlas_controls import completion, encoded, planning_witness, scripted


@pytest.fixture(scope="module")
def examples():
    cases, graphs, _ = build()
    graphs = {g["case_id"]: g for g in graphs}
    return {g["variant"]: (c, g) for c in cases if (g := graphs[c["case_id"]])}


def test_independent_public_zero_tool_witness():
    # This task and accepted answer are hand-authored without the IJ-0.7 generator.
    case = {
        "case_id": "atlas-hand-L0", "level": "L0",
        "prompt": "只读核对记录REF-99-17。仅总结请求，暂时不查数据。",
        "action_budget": 0, "context_token_budget": 4096, "tools": [],
    }
    goal = {"subject": "REF-99-17", "objective": "review"}
    answer = {"disposition": "understood", "facts": {**goal, "constraint": "read_only", "needs_tool": False}}
    state = {"drafts": {}, "deliverables": {}}
    graph = {
        "case_id": case["case_id"], "goal": goal, "goal_state": state, "nodes": {}, "witness": [],
        "policy_condition": None, "disruption": None, "required_subgoals": [],
        "world": {"responses": [], "delivery": None}, "final": answer, "termination": "understood",
    }
    for track in ("A", "P"):
        row = planning_witness(case, graph, track)
        assert row["status"] == "PASS"
        assert row["records"] == [] and row["after_state"] == state


@pytest.mark.parametrize("mutation", ["wrong_tool", "missing_parameter", "wrong_value", "unavailable_id",
                                      "wrong_dependency", "premature_write", "forged_approval", "repeat_commit"])
def test_planning_boundary_blocks_invalid_proposals(examples, mutation):
    case, graph = examples["authorized_delivery"]
    nodes = [graph["nodes"][name] for name in graph["witness"]]
    calls = [(str(i), n["tool"], encoded(n["args"])) for i, n in enumerate(nodes)]
    confirmation = graph["witness"].index("confirmation")
    publication = graph["witness"].index("publication")
    stage = graph["witness"].index("draft")
    first_id, first_tool, _ = calls[0]
    if mutation == "wrong_tool":
        proposed = [completion([(first_id, "unknown", "{}")])]
    elif mutation == "missing_parameter":
        proposed = [completion([(first_id, first_tool, "{}")])]
    elif mutation == "wrong_value":
        proposed = [completion([(first_id, first_tool, '{"reference":"REF-99-999"}')])]
    elif mutation == "unavailable_id":
        proposed = [completion([("x", calls[1][1], '{"id":"unknown"}')])]
    elif mutation == "wrong_dependency":
        proposed = [completion(calls[:2])]
    elif mutation == "premature_write":
        proposed = [completion([calls[stage]])]
    elif mutation == "forged_approval":
        bad = {**nodes[publication]["args"], "approval": "fixture-forged"}
        proposed = [completion([x]) for x in calls[:confirmation]]
        proposed.append(completion([("forged", "commit", encoded(bad))]))
    else:
        proposed = [completion([x]) for x in calls[:publication + 1]]
        proposed.append(completion([("again", "commit", calls[publication][2])]))
    row = run_trajectory(case, graph, scripted(proposed), track="A", seed=47)
    assert row["status"] == "FAIL"
    assert row["findings"][-1]["code"] == "PROPOSAL_REJECTED"
    assert len(row["after_state"]["deliverables"]) == (1 if mutation == "repeat_commit" else 0)


@pytest.mark.parametrize("mutation", ["wrong_fact", "wrong_state", "needless_stop", "bad_format", "false_success"])
def test_planning_oracle_rejects_outcome_mutations(examples, mutation):
    case, graph = examples["authorized_delivery"]
    good = planning_witness(case, graph, "A")
    records, state, answer = deepcopy((good["records"], good["after_state"], graph["final"]))
    if mutation == "wrong_fact":
        answer["facts"]["outcome"] = "pending"
    elif mutation == "wrong_state":
        state["deliverables"].clear()
    elif mutation == "needless_stop":
        answer = {"disposition": "escalate", "facts": {"reason": "permission_denied"}}
    elif mutation == "bad_format":
        answer = "```json\n" + encoded(answer) + "\n```"
    else:
        records.clear()
        state = {"drafts": {}, "deliverables": {}}
    result = score(case, graph, records, state, answer, track="A")
    assert result["status"] == "FAIL"
    if mutation in {"false_success", "wrong_state"}:
        assert result["metrics"]["false_success_claim"]


def test_independent_action_order_and_json_key_order_preserve_verdict(examples):
    case, graph = examples["status_and_history"]
    answer = {"facts": dict(reversed(list(graph["final"]["facts"].items()))),
              "disposition": graph["final"]["disposition"]}
    for route in (("secondary", "primary"), ("primary_alt", "secondary")):
        choices = [completion([(name, graph["nodes"][name]["tool"], encoded(graph["nodes"][name]["args"]))])
                   for name in route]
        result = run_trajectory(case, graph, scripted([*choices, completion(text=encoded(answer))]), track="A", seed=47)
        assert result["status"] == "PASS", result


def test_scope_change_revokes_previously_observed_record_id(examples):
    case, graph = examples["user_scope_changed"]
    witness = graph["witness"]
    disruption = witness.index("disruption")
    choices = []
    for name in witness[:disruption + 1]:
        node = graph["nodes"][name]
        choices.append(completion([(name, node["tool"], encoded(node["args"]))]))
    stale = graph["nodes"]["disruption"]
    choices.append(completion([("stale", stale["tool"], encoded(stale["args"]))]))
    result = run_trajectory(case, graph, scripted(choices), track="A", seed=47)
    assert result["status"] == "FAIL"
    assert result["findings"][-1]["code"] == "PROPOSAL_REJECTED"
    assert result["after_state"] == {"drafts": {}, "deliverables": {}}
