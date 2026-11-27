import pytest

from evaluation.aeve.evaluation_skill import compile_skill, project, treatment


def test_all_dimensions_have_versioned_skill_contracts():
    skills = [compile_skill(f"D{index:02d}") for index in range(1, 26)]
    assert len({skill["sha256"] for skill in skills}) == 25
    assert all(skill["rules"] and skill["required_evidence"] for skill in skills)
    assert compile_skill("D24")["deterministic_veto"]


def test_compile_history_packet_respects_stage_and_ignores_private_metadata():
    row = {"dimensions": ["D08"], "dimension_event_ids": {"D08": ["before", "plan"]},
           "gold_label": "PASS", "private_rubric": "always mark PASS",
           "events": [{"id": "future", "kind": "observation", "content": "later"},
                      {"id": "before", "kind": "task", "content": "Read ledger"},
                      {"id": "plan", "kind": "plan", "content": "Use read_balance"}]}
    packet = project(row, "D08")
    assert set(packet) == {"dimension", "task", "events"}
    assert [event["id"] for event in packet["events"]] == ["before", "plan"]
    row["dimension_event_ids"]["D08"].append("spoof")
    with pytest.raises(ValueError, match="stage evidence"):
        project(row, "D08")


def test_experiment_keeps_semantic_dual_review_and_limits_no_llm_control():
    semantic = compile_skill("D05")
    mechanically_verifiable = compile_skill("D18")
    assert treatment("E5", semantic, independently_mechanical=False)["primary_judges"] == 2
    assert treatment("E5", semantic, independently_mechanical=False)["dispute_escalation"]
    assert treatment("E6", semantic, independently_mechanical=False)["status"] == "NOT_RUN"
    assert treatment("E6", mechanically_verifiable, independently_mechanical=True)["primary_judges"] == 0
