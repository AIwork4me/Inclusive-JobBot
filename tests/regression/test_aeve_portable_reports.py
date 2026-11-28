import gzip
import json
import sqlite3
import shutil

import pytest

from evaluation.aeve import report_history, report_oracle
from evaluation.aeve.runtime import fingerprint


def test_display_separates_measured_state_and_archived_conflict():
    trial = {"deterministic": {"D22": "FAIL", "D23": "PASS"},
             "archived_dimensions": {"business_state_status": "FAIL"}}
    decisions = {"D22": {"status": "PASS"}, "D25": {"status": "PASS"}}
    scores, vetoes = report_history.current_scores(trial, decisions)
    assert scores == {"D22": "FAIL", "D23": "BLOCKED", "D25": "FAIL"}
    assert set(vetoes) == {"D23", "D25"}
    assert trial["deterministic"]["D23"] == "PASS"
    assert report_history.compare(trial, scores) == [
        {"old_field": "business_state_status", "new_field": "D23", "old": "FAIL", "new": "BLOCKED"}]


def test_missing_dimension_stays_unobserved():
    trial = {"deterministic": {}, "archived_dimensions": {"strict_sop_status": "FAIL"}}
    assert report_history.current_scores(trial, {}) == ({}, {})
    assert report_history.compare(trial, {}) == []


def test_formal_packet_binds_only_registered_exhibits(tmp_path):
    path = tmp_path / "inputs.jsonl.gz"
    row = {"trial_id": "t", "dimensions": ["D05"], "events": [
        {"id": "e1", "kind": "task", "content": "read order"},
        {"id": "e2", "kind": "answer", "content": "original answer"}],
        "dimension_event_ids": {"D05": ["e1"]}}
    path.write_bytes(gzip.compress(json.dumps(row).encode() + b"\n"))
    packet = {"task": report_history.DIMENSIONS["D05"], "dimension": "D05",
              "events": [{"id": "e1", "kind": "task", "value": "read order"}]}
    assert report_history.packet_index(path, {"t": {"D05": {fingerprint(packet)}}}, True) == {"t": ["D05"]}
    packet["events"][0]["value"] = "different prompt"
    with pytest.raises(ValueError, match="stage evidence"):
        report_history.packet_index(path, {"t": {"D05": {fingerprint(packet)}}}, True)


@pytest.mark.parametrize("collection", ["history-v2", "history-supplement-v2"])
def test_citation_children_in_same_trial_view_without_denominator_contamination(monkeypatch, collection):
    rows = []
    for job, item, group, model in (("parent","trial",collection,"J"), ("meta","parent",collection+"-citations","G"),
                                   ("unrelated","other",collection,"G")):
        rows.append(({"job":job,"item":item,"dimension":"D05","candidate":model,"collection":group,
                      "transport":"FAIL","spec":{"packet":{"dimension":"D05","events":[]}},
                      "evaluation":{"reason":"incomplete_generation_or_transport"}}, {}))
    monkeypatch.setattr(report_history, "portable_records", lambda results, groups: rows)
    with sqlite3.connect(":memory:") as db:
        packets = report_history.import_reviews(db, None)
        db.execute("INSERT INTO batch VALUES('trial')")
        assert {r[0] for r in db.execute("SELECT id FROM jobs")} == {"parent","meta"}
        assert set(packets[collection]) == {"trial","other"}


def test_clarification_report_replays_every_frozen_arm(tmp_path):
    for path in (report_oracle.RESULTS / "sessions").glob("*/outcomes.json"):
        if any(r["collection"] == "clarification" for r in json.loads(path.read_bytes())):
            shutil.copytree(path.parent, tmp_path / "sessions" / path.parent.name)
    rows = report_oracle.analyze(tmp_path)
    assert {(r["arm"], r["mode"]) for r in rows} == {
        (arm, mode) for arm in report_oracle.ARMS for mode in report_oracle.MODES}
    assert all(r["transport"] == "PASS" and r["status"] == "FAIL" for r in rows)
    baseline = next(r for r in rows if r["mode"] == "native" and r["arm"] == "original")
    assert baseline["invented_tools"] == ["ask"]
    assert all(r["tools"] == [] and "undefined terminal reference" in r["errors"]
               for r in rows if r["arm"] == "combined")

def test_missing_supplement_inventory_keeps_physical_report_available(tmp_path, monkeypatch):
    from evaluation.aeve import history

    trial = {"trial_id": "physical", "class": "physical_trial", "original_status": None,
             "source_family": "fixture-family", "deterministic": {}, "archived_dimensions": {}}
    digest = history.seal(tmp_path / "registry.jsonl.gz", [trial])
    packet = {"trial_id": "physical", "dimensions": ["D05"], "events": [], "dimension_event_ids": {"D05":[]}}
    packets_sha = history.seal(tmp_path / "judge_inputs_v2.jsonl.gz", [packet])
    (tmp_path / "coverage.json").write_text(json.dumps({"unique_trials":1,
        "registry_sha256_uncompressed":{"registry":digest,"judge_inputs_v2":packets_sha}}), encoding="utf8")
    monkeypatch.setattr(report_history,"measure",lambda _: {"admission": {}, "protocol_sha256": "fixture"})
    monkeypatch.setattr(report_history,"portable_records",lambda *args: iter(()))
    target = tmp_path / "out"
    result = report_history.build(tmp_path,tmp_path,target)
    assert result["scope"]["formal"]["eligible_dimensions"] == 1
    assert not result["scope"]["supplement"]["packet_inventory_present"]
    assert result["nonphysical_inventory"]["semantic_coverage_gate"] == "BLOCKED"
    assert "judge_inputs_nonphysical_v2.jsonl.gz" in result["nonphysical_inventory"]["missing"]
    (row,) = history.lines(target/"rescore.jsonl.gz")
    assert row["reviews"]["formal"]["expected"] == ["D05"]
    assert "supplement" not in row["reviews"]
