"""Source-derived regressions for the formal historical projections."""
import json
from pathlib import Path

from evaluation.aeve.history import Inventory, classification, lines, sid
from evaluation.aeve.history_inputs import evidence_v2
from evaluation.aeve.history_scores import planning_tasks, regrade


def content(view, dimension):
    ids = set(view["dimension_event_ids"][dimension])
    return [e for e in view["events"] if e["id"] in ids]


def test_decision_time_views_hide_later_changes_and_results():
    initial = [{"role":"system","content":"Read only"}, {"role":"user","content":"Find order"}]
    later = initial + [{"role":"assistant","content":""},{"role":"tool","content":"OLD"},
                       {"role":"user","content":"Use the east site"}]
    row = {"requests":[{"request":{"messages":initial,"tools":["read"]}},
                       {"request":{"messages":later,"tools":["read"]}}],
           "plan_raw":"Find the order", "calls":[
                {"turn":0,"name":"read","arguments":{"q":"order"},"result":"OLD"},
                {"turn":1,"name":"read","arguments":{"site":"east"},"result":"NEW"}],
           "final":"NEW", "after_sqlite":{"hidden":"verdict"}, "status":"PASS"}
    view = evidence_v2("id","family",row,{},"digest")
    plan = content(view,"D09")
    action = content(view,"D14")
    trace = content(view,"D16")
    assert [e["kind"] for e in plan] == ["policy","task","tools","plan"]
    assert [e["kind"] for e in action] == ["policy","task","tools","plan","action"]
    assert [e["kind"] for e in trace][-5:] == ["action","observation","delivered_update","action","observation"]
    assert "hidden" not in json.dumps(view)
    assert "PASS" not in json.dumps(view)
    assert content(view,"D15")[-1]["content"] == "NEW"
    assert not set(view["dimensions"]) & {"D21", "D24", "D25"}


def test_no_inferred_tool_execution_or_unseen_update():
    row = {"prompt":"Read a case","plan_raw":"read and finish",
           "delivered_events":[[0,"secret"]]}
    view = evidence_v2("id", "Qwen", row, {}, "digest")
    assert {e["kind"] for e in view["events"]} == {"task", "plan"}
    assert "D13" not in view["dimensions"] and "D10" not in view["dimensions"]
    assert evidence_v2("id","Qwen",{"status":"PASS","final":"answer"},{}, "digest") is None


def test_fact_only_replay_is_scoped_to_the_original_run():
    assert sid("scorer", "case", "rocm-run") != sid("scorer", "case", "vulkan-run")


def test_parseable_wrong_final_contract_is_a_protocol_failure():
    p = next(Path("evidence/IJ07/planning/diagnostic/cases").glob("AP1-*.json"))
    row = json.loads(p.read_bytes())
    row["final_raw"] = '{"unexpected": true}'
    assert regrade(row,row["case_id"])["D20"] == "FAIL"
    row["final_raw"] = None
    assert regrade(row,row["case_id"])["D20"] == "NOT_RUN"


def test_legacy_physical_data_sources_have_adapters():
    paths = {"evidence/IJ07/model_identity/aion_tools/cpu-strict.json":"aion_tools",
             "evidence/IJ07/model_identity/aion_reference/webgpu.json":"aion_chat",
             "evidence/IJ07/competitive_slm/dev/B/result.json":"single_terminal",
             "evidence/IJ07/root_causes/ticket_tags_counterfactual/report.json.gz":"counterfactual",
             "evidence/IJ07/historical_replay/upstream_b12675/report.json":"upstream_reproduction"}
    assert {path:classification(Path(path)) for path in paths} == paths


def test_missing_plan_and_rejected_suggestion_remain_visible_without_an_execution():
    decision = {"content":"","calls":[{"tool":"ask","arguments":"{}"}]}
    row = {"track":"P","requests":[{"request":{"messages":[{"role":"system","content":"No tool"},
           {"role":"user","content":"Summarize"}]}}], "_first_decision":decision}
    view = evidence_v2("trial","family",row,{"tools":["hidden_later_tool"]},"sha")
    ids = view["dimension_event_ids"]
    assert "D19" in ids and "D13" in ids
    assert content(view,"D19")[-1]["kind"] == "initial_generation"
    assert content(view,"D13")[-1]["kind"] == "proposal"
    assert not any(e["kind"] in {"action","observation"} for e in view["events"])
    assert [e["content"] for e in view["events"] if e["kind"] == "tools"] == [[]]


def test_business_state_is_reserved_for_post_run_review():
    row = {"plan_raw":"Read only","final":"Done","before_state":{"drafts":{}},
           "after_state":{"drafts":{"d1":{"status":"staged"}}}}
    public={"prompt":"Find the report", "policy":"Read only"}
    view = evidence_v2("trial","family",row,public,"sha")
    state = content(view,"D22")[-1]
    assert state["kind"] == "persisted_state"
    assert state["content"]["observed_business_changes"] == [
        {"table":"drafts","entity":"d1","before":None,"after":{"status":"staged"}}]
    assert all(e["kind"] != "persisted_state" for e in content(view,"D09"))


def test_admission_groups_actual_continuations_but_separates_repeats():
    from evaluation.aeve.history_inputs import wire_episodes
    task = [{"role":"user","content":"Lookup"}]
    history = task + [{"role":"assistant","content":"call"},{"role":"tool","content":"42"}]
    captures = [{"request":{"messages":messages}} for messages in [task,history,task]]
    assert [[idx for idx,_ in group] for group in wire_episodes(captures)] == [[0,1],[2]]


def test_blindness_removes_source_family_and_work_directory():
    from evaluation.aeve.history_inputs import blind_content
    value = r"The SDK ran in C:\Users\<REDACTED>\Desktop\Jobbot\.runtime\qwen3-8b-job-dev-abc\work"
    redacted = blind_content(value)
    assert "qwen" not in redacted.lower() and ".runtime" not in redacted and "Desktop" not in redacted


def test_rejected_batch_preserves_proposal_but_never_synthesizes_observations():
    from evaluation.aeve.history_inputs import first_decision
    bad = [{"type":"function","id":str(i),"function":{"name":"read","arguments":"{}"}} for i in range(17)]
    response = {"choices":[{"finish_reason":"tool_calls","message":{"role":"assistant","tool_calls":bad}}]}
    cap = {"raw_response":json.dumps(response),"request":{"messages":[{"role":"user","content":"Read"}],"tools":["read"]}}
    assert len(first_decision(cap)["calls"]) == 17
    view = evidence_v2("t","f",{"requests":[cap],"calls":[]},{}, "sha")
    assert len([e for e in view["events"] if e["kind"] == "proposal"]) == 17
    assert "observation" not in {e["kind"] for e in view["events"]}
