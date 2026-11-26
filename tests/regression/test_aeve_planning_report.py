"""Fixtures test portable diagnostic arithmetic, with no new physical GPU evidence."""
import json

import pytest

from benchmarks.agentic_planning_v1.contract import request
from benchmarks.agentic_planning_v2.public_witness import build
from evaluation.aeve import report_planning as report


@pytest.fixture(scope="module")
def roster():
    return report.frozen_panel()


def mock_response(item, spec, raw, *, finish="stop", transport="PASS"):
    outcome = report.grade(spec, raw) if transport == "PASS" else {
        "status":transport,"reason":"incomplete_generation_or_transport"}
    choice = {"message":{"content":raw},"finish_reason":finish}
    result = report.predeclared(item,spec)
    capture = {"http_status":200,"render_status":200,
               "raw_response":json.dumps({"choices":[choice],"usage":{"total_tokens":32,"completion_tokens":12}}),
               "source_generation":{"truncated":False,"prompt_token_ids":[0]*20,"sampled_token_ids":[0]*12}}
    row = {"job":result["expected_job"], "candidate":"J","spec":spec,"capture":capture,
           "transport":transport,"evaluation":outcome}
    return row, result


def witness(roster, level):
    item, spec = next((k,s) for k,s in roster.items() if s["level"] == level and s["track"] == "inferred")
    with (report.ROOT/"benchmarks/agentic_planning_v1/datasets/holdout.jsonl").open("rb") as stream:
        case = next(r for r in map(json.loads,stream) if r["case_id"]==spec["case"])
    plan, _, _ = build(request(case,"P"))
    return item,spec,plan


def test_unsealed_matrix_keeps_missing_traces_unobserved(tmp_path):
    rows = report.analyze(tmp_path)
    assert len(rows) == 64
    assert all(r["status"]=="NOT_RUN" and r["trace"]["actual_calls"] is None for r in rows)
    assert all(r["limits"]["retries"]==0 and r["limits"]["model_requests"]==1 for r in rows)
    assert len({r["case"] for r in rows}) == 16
    assert all(r["goal_field_exposed"] == (r["track"]=="provided") for r in rows)
    assert len({r["expected_job"] for r in rows})==64


@pytest.mark.parametrize("level,expected_trace",[(0,"NOT_RUN"),(7,"PASS")])
def test_replay_separates_zero_dispatch_and_successful_action_trace(roster, level, expected_trace):
    item, spec, plan = witness(roster, level)
    row, blank = mock_response(item,spec,json.dumps(plan))
    actual = report.observed(spec,row,blank,{"fixture":True})
    assert actual["status"] == actual["goal_literal_match"] == "PASS"
    assert actual["trace"]["trace_replay"] == expected_trace
    assert actual["trace"]["actual_calls"] == len(row["evaluation"]["records"])
    assert actual["trace"]["final_matches"] and actual["trace"]["state_matches"]
    assert all(v=="PASS" for v in actual["budget"].values())


def test_inferred_literal_mismatch_and_truncated_output(roster):
    item,spec,plan = witness(roster,7)
    plan["goal"] = "verified_dispatch"
    row, blank = mock_response(item,spec,json.dumps(plan))
    actual = report.observed(spec,row,blank,{"fixture":True})
    assert actual["goal_literal_match"] == "FAIL" and actual["validation_errors"] == ["incorrect public objective"]
    assert actual["trace"]["actual_calls"] is None
    row,blank = mock_response(item,spec,"{}",finish="length",transport="FAIL")
    actual = report.observed(spec,row,blank,{"fixture":True})
    assert actual["transport"]=="FAIL" and actual["goal_literal_match"]=="NOT_RUN"
    assert actual["trace"]["trace_replay"]=="NOT_RUN"


def test_offline_replay_rejects_mutated_evaluation(roster):
    item,spec,plan = witness(roster,7)
    row,blank = mock_response(item,spec,json.dumps(plan))
    row["evaluation"]["records"][0]["args"]={"fixture":"wrong"}
    with pytest.raises(ValueError,match="offline replay"):
        report.observed(spec,row,blank,{"fixture":True})
