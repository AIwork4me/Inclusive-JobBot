import gzip
import json
from pathlib import Path

from evaluation.aeve.adjudication import assess
from evaluation.aeve.controller import connect, judge_job
from evaluation.aeve.intake import seed_history
from evaluation.aeve.runtime import canonical


def test_stage_visibility_and_family_routing(tmp_path):
    db = connect(tmp_path)
    target = tmp_path/"input.jsonl"
    target.write_bytes(canonical({"projection_version":2,"trial_id":"a"*64,"source_sha256":"b"*64,"source_family":"Qwen","events":[
        {"id":"t","kind":"task","content":"Read status"},{"id":"p","kind":"plan","content":"Read once"},
        {"id":"o","kind":"observation","content":"private future value"}],
        "dimensions":["D08"],"dimension_event_ids":{"D08":["t","p"]}})+b"\n")
    seed_history(db,target,admitted=["J","G","F","B"])
    rows = list(db.execute("SELECT candidate,spec FROM jobs ORDER BY candidate"))
    assert [r["candidate"] for r in rows] == ["F","G"]
    for row in rows:
        spec = json.loads(gzip.decompress(row["spec"]))
        assert [e["id"] for e in spec["packet"]["events"]] == ["t","p"]
        assert "private future value" not in spec["body"]["messages"][1]["content"]
    db.close()


def test_unqualified_history_cannot_promote_an_unsupported_citation(tmp_path):
    db = connect(tmp_path)
    registry = tmp_path/"registry.jsonl"
    registry.write_bytes(canonical({"trial_id":"trial","source_family":"MiniCPM","deterministic":{}})+b"\n")
    packet = {"dimension":"D05","task":"Is the claim correct?","events":[{"id":"e1","kind":"answer","value":"blue"}]}
    answer = {"verdict":"PASS","reason_summary":"The claim matches.","evidence_refs":["e1"]}
    for model in ("J","G"):
        judge_job(db,"history-v2","trial",model,packet)
    db.execute("UPDATE jobs SET status='RECORDED',result=?", (json.dumps(answer),))
    def result():
        return assess(db,registry,enqueue=True,collection="history-v2",admitted=["J","G","F"])["trial","D05"]
    assert result()["status"] == "BLOCKED"
    assert db.execute("SELECT count(*) FROM jobs WHERE collection='history-v2-citations'").fetchone()[0] == 2
    bad = {**answer,"evidence_refs":["judge-assertion"]}
    db.execute("UPDATE jobs SET status='RECORDED',result=? WHERE collection='history-v2-citations'", (json.dumps(bad),))
    denied = result()
    assert denied["status"] == "BLOCKED" and len(denied["invalid"]) == 2
    assert db.execute("SELECT candidate FROM jobs WHERE collection='history-v2-dispute'").fetchone()[0] == "F"
    registry.write_bytes(canonical({"trial_id":"trial","source_family":"MiniCPM","deterministic":{"D05":"FAIL"}})+b"\n")
    assert result()["status"] == "FAIL"
    db.close()


def test_missing_business_fact_cannot_be_granted_by_two_model_votes(tmp_path):
    db = connect(tmp_path)
    registry = tmp_path/"registry.jsonl"
    registry.write_bytes(canonical({"trial_id":"x","source_family":"MiniCPM","deterministic":{}})+b"\n")
    packet = {"dimension":"D23","task":"Is the change persisted?","events":[{"id":"e","kind":"answer","value":"done"}]}
    for reviewer in ("J","G"):
        judge_job(db,"history-v2","x",reviewer,packet)
    answer = json.dumps({"verdict":"PASS","reason_summary":"Recorded.","evidence_refs":["e"]})
    db.execute("UPDATE jobs SET status='RECORDED',result=?",(answer,))
    options = dict(enqueue=True,collection="history-v2",admitted=["J","G","F"])
    assess(db,registry,**options)
    db.execute("UPDATE jobs SET status='RECORDED',result=? WHERE collection='history-v2-citations'",(answer,))
    decision = assess(db,registry,**options)["x","D23"]
    assert decision["status"] == "BLOCKED" and "fact unavailable" in decision["reason"]
    db.close()
