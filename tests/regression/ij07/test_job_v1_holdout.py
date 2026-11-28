from copy import deepcopy
from pathlib import Path

import pytest

from benchmarks.job_productivity_v1.holdout.dataset import FILES, ROOT, load
from benchmarks.job_productivity_v1.holdout.generate import generate
from benchmarks.job_productivity_v1.holdout.oracle import evaluate
from benchmarks.job_productivity_v1.holdout.verify import replay_reference, verify


def test_frozen_holdout_replays_all_cases(tmp_path):
    freeze = load()
    summary = verify(freeze, tmp_path)
    assert summary["fixture_status"] == "PASS"
    assert summary["fixture_cases"] == 600
    assert summary["measured_business_records"] == 0
    assert summary["planned_business_records"] == 3600
    assert summary["planned_repeat_records"] == 900
    assert set(summary["arm_status"].values()) == {"NOT_RUN"}


def test_pairing_and_case_material_are_separated():
    case = load().cases["JOB-DOC-001"]
    public = case.input_initial()
    assert set(public) == {"operator_message", "attachments", "shared_rules"}
    assert all(isinstance(doc["text"], str) for doc in public["attachments"])
    assert case.plan["pairing_sha256"] == case.pairing_sha256()
    original = deepcopy(case.task)
    public["attachments"].clear()
    assert case.task == original


def test_oracle_rejects_wrong_source_state_and_followup(tmp_path):
    freeze = load()
    case = next(case for case in freeze.cases.values() if case.expected["draft"] is not None)
    observation = replay_reference(case, tmp_path)
    assert evaluate(case, **observation)["status"] == "PASS"
    forged = deepcopy(observation)
    forged["after"]["review_drafts"][case.plan["case_id"]]["submitted"] = True
    assert evaluate(case, **forged)["status"] == "FAIL"
    assert evaluate(case, **{**observation, "after": None})["status"] == "BLOCKED"
    forged = deepcopy(observation)
    forged["reads"] = []
    assert evaluate(case, **forged)["status"] == "FAIL"
    forged = deepcopy(observation)
    event_id = next(key for key, event in forged["after"]["audit_events"].items() if event["status"] == "READ")
    del forged["after"]["audit_events"][event_id]
    assert evaluate(case, **forged)["status"] == "FAIL"
    case = next(case for case in freeze.cases.values() if case.task["followups"])
    observation = replay_reference(case, tmp_path)
    assert evaluate(case, **{**observation, "delivered_followups": []})["status"] == "FAIL"


def test_freeze_regeneration_and_tamper_detection(tmp_path):
    generate(tmp_path)
    for name in (*FILES, "manifest.json"):
        assert (Path(tmp_path) / name).read_bytes() == (ROOT / name).read_bytes()
    task_file = tmp_path / "tasks.jsonl"
    task_file.write_bytes(task_file.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="digest"):
        load(tmp_path)


def test_terminal_cohorts_are_separately_classified(tmp_path):
    freeze = load()
    for key, label in (("JOB-DOC-076", "correct_clarification"), ("JOB-PRD-151", "correct_refusal"),
                       ("JOB-DOC-176", "correct_escalations")):
        case = freeze.cases[key]
        result = evaluate(case, **replay_reference(case, tmp_path))
        assert result["status"] == "PASS"
        assert result[label] and result["completed"] is False
