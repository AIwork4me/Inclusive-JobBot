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


def test_observed_review_profile_requires_a_prior_turn_for_drafts(tmp_path):
    case = next(case for case in load_freeze().active.values() if case.world["draft_ids"])
    reference = case.world["draft_ids"][0]
    read = json.dumps({"record_id": reference})
    draft = json.dumps({"record_id": reference, "reason": "route_review"})
    legacy = Scenario(case, tmp_path / "legacy.sqlite3")
    assert legacy.call("early", "create_hold_draft", draft)["status"] == "drafted"

    revised = Scenario(case, tmp_path / "revised.sqlite3", require_observed_draft=True)
    assert revised.call("early", "create_hold_draft", draft, turn=0) == {"error": "POLICY_DENIED"}
    assert revised.call("read", "read_review", read, turn=1)["draft_permission"] is True
    assert revised.call("same-turn", "create_hold_draft", draft, turn=1) == {"error": "POLICY_DENIED"}
    assert revised.snapshot()["review_drafts"] == {}
    assert revised.call("next-turn", "create_hold_draft", draft, turn=2)["status"] == "drafted"
    assert set(revised.snapshot()["review_drafts"]) == {reference}


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


def test_candidate_profile_changes_only_model_on_the_wire():
    case = load_freeze().controls["DIAG-NO-TOOL-EN"]
    normal = WireFixture([{"content": '{"status":"ready"}'}])
    candidate = WireFixture([{"content": '{"status":"ready"}'}])
    default_result = run_case(case, normal, None, seed=48707)
    candidate_result = run_case(case, candidate, None, seed=48707, alias="ij07-candidate-b")
    assert default_result["status"] == candidate_result["status"] == "PASS"
    default_request = default_result["requests"][0]["request"]
    candidate_request = candidate_result["requests"][0]["request"]
    assert default_request["model"] == run.ALIAS
    assert candidate_request == {**default_request, "model": "ij07-candidate-b"}


@pytest.mark.parametrize("candidate_id", ("D", "H"))
def test_strict_candidate_uses_shared_multitool_budget_and_pinned_template(candidate_id, tmp_path, monkeypatch):
    verified = {"candidate": candidate_id, "template": {"sha256": "strict-embedded"}, "engine": {"exe_sha256": "exe"},
                "budgets": {"model_turns": 7, "completion_tokens_per_turn": 768, "context_tokens": 8192}}
    path = tmp_path / "pinned-Q8_0.gguf"
    path.touch()
    monkeypatch.setattr(run.tc_v2_candidate, "verify_runtime",
                        lambda code, model, engine: verified if (code, model, engine) == (candidate_id, path, tmp_path) else None)
    monkeypatch.setattr(run.tc_v2_candidate, "server_environment", lambda: {"fixture": "1"})
    args = SimpleNamespace(candidate=candidate_id, backend="vulkan", engine_dir=tmp_path, model=path, runtime_root=None)
    binary, model, identity, env = run.resolve_runtime(args)
    assert (binary, model, env) == (tmp_path / "llama-server.exe", path, {"fixture": "1"})
    assert identity["model_alias"] == f"ij07-candidate-{candidate_id.lower()}"
    assert identity["expected_template_sha256"] == "strict-embedded"
    assert "budgets" not in identity and "budgets" in verified
    with pytest.raises(ValueError, match="Vulkan"):
        run.resolve_runtime(SimpleNamespace(**{**vars(args), "backend": "rocm"}))


def test_wire_plan_selects_exact_frozen_repeat_population():
    freeze = load_freeze()
    panel = plan(freeze, "repeat", [], first_seed=987)
    assert len(panel) == 300 and len({row["key"] for row in panel}) == 300
    assert {row["case_id"] for row in panel} == set(freeze.panel["case_ids"])
    assert {row["seed"] for row in panel} == set(freeze.panel["seeds"])
    with pytest.raises(ValueError, match="outside"):
        plan(freeze, "primary", ["DIAG-NO-TOOL-EN"], first_seed=987)


def test_strict_launcher_handoff_reuses_decoder_and_checks_live_pin(tmp_path, monkeypatch):
    freeze = load_freeze()
    case = freeze.controls["DIAG-NO-TOOL-EN"]
    wire = WireFixture([{"content": '{"status":"ready"}'}])
    started = []
    checked = []

    @contextmanager
    def synthetic_server(_binary, _model, backend, _env, _output, _port, _tag, observe, *, alias, max_nonstream_calls):
        started.append((backend, observe, alias, max_nonstream_calls))
        yield wire, {"backend": backend, "gpu": {}, "build": "fixture", "args": [],
                     "template_sha256": "fixture", "layers_offloaded": 1, "layers_total": 1}

    monkeypatch.setattr(run.historical_replay, "gpu_server", synthetic_server)
    monkeypatch.setattr(run.tc_v2_candidate, "verify_launch", lambda launch, config: checked.append(config["candidate"]))
    monkeypatch.setattr(run.qualify, "pid_counter_proof", lambda *_: {"status": "BLOCKED"})
    roster = plan(freeze, "controls", [case.case_id], first_seed=42)
    config = {"candidate": "B", "model_alias": "ij07-candidate-b", "panel": "controls", "scope": "diagnostic",
              "roster": roster, "expected_template_sha256": "fixture"}
    args = SimpleNamespace(backend="vulkan", resume=False, port=18718, batch_size=None)
    summary = run.execute_locked(args, config, {case.case_id: case}, tmp_path, None, None, {})
    assert started == [("vulkan", True, "ij07-candidate-b", run.LIMITS["max_proposals"])]
    assert checked == ["B"] and summary["candidate"] == "B"
    assert summary["physical_evidence_status"] == "BLOCKED"
    assert wire.requests[0]["request"]["model"] == "ij07-candidate-b"


def test_checkpoint_resume_binds_evidence_and_preserves_interruptions(tmp_path, monkeypatch):
    freeze = load_freeze()
    case = freeze.controls["DIAG-NO-TOOL-EN"]
    blocked = True
    launches = []

    @contextmanager
    def synthetic_server(_binary, _model, backend, _env, _output, _port, _tag, observe, *, alias, max_nonstream_calls):
        assert observe
        assert alias == run.ALIAS
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

def test_multitool_stream_mode_reaches_real_runner_decoder():
    case = load_freeze().controls["DIAG-NO-TOOL-EN"]

    class SSEFixture(WireFixture):
        def chat(self, url, request):
            reply = super().chat(url, request)
            content = reply["choices"][0]["message"]["content"]
            choice = {"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": "stop"}
            self.requests[-1]["raw_response"] = f"data: {json.dumps({'choices': [choice]})}\n\ndata: [DONE]\n\n"
            return reply

    result = run_case(case, SSEFixture([{"content": '{"status":"ready"}'}]), None, seed=66007, stream=True)
    assert result["status"] == "PASS"
    assert result["requests"][0]["request"]["stream_options"] == {"include_usage": True}
