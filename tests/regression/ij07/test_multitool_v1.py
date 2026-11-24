from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from benchmarks.multitool_v1.dataset import FILES, ROOT, load_freeze
from benchmarks.multitool_v1.generate import generate
from benchmarks.multitool_v1 import run
from benchmarks.multitool_v1.run import plan, run_case
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


class WireFixture:
    """Supply known synthetic envelopes through the loop's real decoder."""

    base_url = "fixture"

    def __init__(self, messages, *, source_status="PASS"):
        self.messages = iter(messages)
        self.requests = []
        self.source_status = source_status

    def chat(self, _base_url, request):
        message = next(self.messages)
        reply = {"choices": [{"index": 0, "message": {"role": "assistant", **message},
                              "finish_reason": "tool_calls" if message.get("tool_calls") else "stop"}],
                 "usage": {"prompt_tokens": 12, "completion_tokens": 3}}
        self.requests.append({"request": request, "raw_response": json.dumps(reply), "http_status": 200,
                              "render_status": 200, "source_generation": {"status": self.source_status},
                              "wall_ms": 10})
        return reply


def test_wired_loop_delivers_user_update_and_scores_model_calls(tmp_path):
    case = load_freeze().active["MT-07-001"]
    _, calls, final, *_ = replay_reference(case, tmp_path)
    messages = [{"tool_calls": [{"id": call.call_id, "type": "function", "function": {
        "name": call.name, "arguments": call.arguments_raw}} for call in calls if call.turn == turn]}
                for turn in sorted({call.turn for call in calls})]
    client = WireFixture([*messages, {"content": final}])
    result = run_case(case, client, None, seed=48707)
    assert result["status"] == "PASS"
    assert result["model_calls"] == 3
    assert result["prompt_tokens"] == 36
    requests = result["requests"]
    event = case.world["event"]
    assert all(event["text"] not in item["content"] for item in requests[0]["request"]["messages"])
    assert requests[1]["request"]["messages"][-1] == {"role": "user", "content": event["text"]}
    assert result["delivered_events"] == [(0, event["id"])]
    assert all(request["request"]["seed"] == 48707 for request in requests)


def test_wired_loop_keeps_missing_observer_evidence_blocked(tmp_path):
    case = load_freeze().controls["DIAG-NO-TOOL-EN"]
    client = WireFixture([{"content": '{"status":"ready"}'}], source_status="BLOCKED")
    result = run_case(case, client, None, seed=48707)
    assert result["status"] == "BLOCKED"
    assert result["trace_status"] == "PASS"


def test_wire_plan_selects_exact_frozen_repeat_population():
    freeze = load_freeze()
    panel = plan(freeze, "repeat", [], first_seed=987)
    assert len(panel) == 300 and len({row["key"] for row in panel}) == 300
    assert {row["case_id"] for row in panel} == set(freeze.panel["case_ids"])
    assert {row["seed"] for row in panel} == set(freeze.panel["seeds"])
    with pytest.raises(ValueError, match="outside"):
        plan(freeze, "primary", ["DIAG-NO-TOOL-EN"], first_seed=987)


def test_checkpoint_resume_binds_evidence_and_preserves_interruptions(tmp_path, monkeypatch):
    freeze = load_freeze()
    case = freeze.controls["DIAG-NO-TOOL-EN"]
    blocked = True
    launches = []

    @contextmanager
    def synthetic_server(_binary, _model, backend, _env, _output, _port, _tag, observe, *, max_nonstream_calls):
        assert observe
        assert max_nonstream_calls == run.LIMITS["max_proposals"]
        launches.append(backend)
        capture = "BLOCKED" if blocked else "PASS"
        yield WireFixture([{"content": '{"status":"ready"}'}], source_status=capture), {
            "backend": backend, "gpu": {}, "build": "fixture", "args": [], "template_sha256": "fixture",
            "layers_offloaded": 1, "layers_total": 1,
        }

    monkeypatch.setattr(run.historical_replay, "gpu_server", synthetic_server)
    monkeypatch.setattr(run.qualify, "pid_counter_proof", lambda *_: {"status": "BLOCKED"})
    roster = plan(freeze, "controls", [case.case_id], first_seed=42)
    configuration = {"panel": "controls", "scope": "diagnostic", "roster": roster,
                     "expected_template_sha256": "fixture"}
    args = SimpleNamespace(backend="vulkan", resume=False, port=18718, batch_size=None)
    resume = SimpleNamespace(**{**vars(args), "resume": True})
    cases = {case.case_id: case}
    status = run.execute_locked(args, configuration, cases, tmp_path, None, None, {})
    assert status["tasks"] == {"PASS": 0, "FAIL": 0, "BLOCKED": 1, "NOT_RUN": 0}
    assert status["runtime_interruptions"] == 1

    blocked = False
    status = run.execute_locked(resume, configuration, cases, tmp_path, None, None, {})
    assert status["tasks"] == {"PASS": 1, "FAIL": 0, "BLOCKED": 0, "NOT_RUN": 0}
    assert status["physical_evidence_status"] == "BLOCKED"
    assert status["runtime_interruptions"] == 1
    assert run.execute_locked(resume, configuration, cases, tmp_path, None, None, {}) == status
    assert len(launches) == 2

    with pytest.raises(ValueError, match="original run configuration"):
        run.execute_locked(resume, {**configuration, "scope": "changed"}, cases, tmp_path, None, None, {})
    path = next((tmp_path / "cases").glob("*.json"))
    envelope = json.loads(path.read_bytes())
    envelope["row"]["final"] = "forged"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid checkpoint"):
        run.execute_locked(resume, configuration, cases, tmp_path, None, None, {})
