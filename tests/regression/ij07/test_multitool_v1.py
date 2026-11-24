from collections import Counter
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from benchmarks.multitool_v1.dataset import FILES, ROOT, load_freeze
from benchmarks.multitool_v1.generate import generate
from benchmarks.multitool_v1.runtime import Scenario, score
from benchmarks.multitool_v1.verify import replay_reference, verify_freeze


def test_frozen_panel_and_full_fixture_replay(tmp_path):
    freeze = load_freeze()
    summary = verify_freeze(freeze, tmp_path)
    assert summary["fixture_status"] == "PASS"
    assert summary["model_status"] == "NOT_RUN"
    assert summary["case_count"] == 600
    assert summary["control_count"] == 6
    assert summary["verified"] == 606
    assert set(summary["depth_distribution"].values()) == {15}
    assert Counter(summary["repeat_languages"].values()) == {33: 2, 34: 1}


def test_model_input_omits_world_oracle_and_moderator_updates():
    freeze = load_freeze()
    case = freeze.active["MT-07-001"]
    for marker in ("required_steps", "oracle", "depends_on", "case_id", "event", "schedule"):
        assert f'"{marker}"' not in json.dumps(case.model_input())
    assert case.world["event"]["text"] not in str(case.model_input())
    assert len(case.model_input()["messages"]) == 1
    payload = case.model_input()
    payload["tools"][0]["function"]["parameters"].clear()
    assert case.model_input()["tools"][0]["function"]["parameters"]


def test_recovery_is_scoped_to_calls_and_starts_fresh():
    case = load_freeze().active["MT-06-001"]
    source = case.world["faults"][0]
    keys = {"record_id": source["record_id"]}
    first = Scenario(case)
    other = Scenario(case)
    for simulator in (first, other):
        assert simulator.call("bad", source["tool"], '{"record_id":false}') == {"error": "schema_mismatch"}
        result = simulator.call("a", source["tool"], json.dumps(keys))
        assert result == source["responses"][0]
        result = simulator.call("b", source["tool"], json.dumps(keys))
        assert result != source["responses"][0]


def test_oracle_rejects_wrong_order_invented_answer_and_evidence_loss(tmp_path):
    freeze = load_freeze()
    case = freeze.active["MT-02-001"]
    _, calls, end, _, _, _ = replay_reference(case, tmp_path)
    assert score(case, calls, end)["status"] == "PASS"
    assert score(case, list(reversed(calls)), end)["status"] == "FAIL"
    assert score(case, calls, '{"status":"complete","destination":"invented"}')["status"] == "FAIL"

    case = freeze.active["MT-08-002"]
    _, calls, end, before, after, _ = replay_reference(case, tmp_path)
    assert score(case, calls, end)["business_state_status"] == "BLOCKED"
    corrupted = deepcopy(after)
    corrupted["review_drafts"].clear()
    assert score(case, calls, end, before=before, after=corrupted)["business_state_status"] == "FAIL"


def test_parallel_alternatives_and_moderator_delivery(tmp_path):
    freeze = load_freeze()
    case = freeze.active["MT-01-001"]
    _, calls, end, *_ = replay_reference(case, tmp_path)
    reverse_parallel = list(reversed(calls))
    assert score(case, reverse_parallel, end)["status"] == "PASS"
    reverse_serial = [replace(call, turn=i) for i, call in enumerate(reverse_parallel)]
    assert score(case, reverse_serial, end)["status"] == "PASS"

    case = freeze.active["MT-07-001"]
    _, calls, end, _, _, delivery = replay_reference(case, tmp_path)
    assert score(case, calls, end, delivered_events=delivery)["status"] == "PASS"
    assert score(case, calls, end)["status"] == "FAIL"
    assert score(case, calls, end, delivered_events=[(1, "site_update")])["status"] == "FAIL"


def test_sandbox_suppresses_unauthorized_state_changes(tmp_path):
    case = load_freeze().active["MT-08-001"]
    simulator = Scenario(case, tmp_path / "access.sqlite3")
    raw = json.dumps({"record_id": case.oracle["answer"]["review_ref"], "reason": "route_review"})
    before = simulator.snapshot()
    assert "error" in simulator.call("commit", "commit_hold", raw)
    assert "error" in simulator.call("draft", "create_hold_draft", raw)
    after = simulator.snapshot()
    assert before["review_drafts"] == after["review_drafts"] == {}
    assert len(after["audit_events"]) == 1


def test_freeze_regenerates_byte_identically_and_rejects_mutation(tmp_path):
    generate(tmp_path)
    for name in (*FILES, "manifest.json"):
        assert (tmp_path / name).read_bytes() == (ROOT / name).read_bytes()
    prompt_file = tmp_path / "prompts.jsonl"
    prompt_file.write_bytes(prompt_file.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="digest mismatch"):
        load_freeze(tmp_path)
