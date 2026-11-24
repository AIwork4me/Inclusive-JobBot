import json
from argparse import Namespace
from collections import Counter
from contextlib import contextmanager

import pytest

from benchmarks.agentic_planning_v1.freeze import FROZEN, build, verify
from benchmarks.agentic_planning_v1.contract import request
from benchmarks.agentic_planning_v1.oracle import score
from benchmarks.agentic_planning_v1 import run
from benchmarks.competitive_slm import tc_v2_candidate
from benchmarks.agentic_planning_v1.runner import Boundary, run_trajectory
from benchmarks.agentic_planning_v1.run import Checkpoint, roster
from benchmarks.agentic_planning_v1.sandbox import SyntheticSandbox
from model_gateway import Proposal


def test_reference_boundary_accepts_chinese_adjacency_without_admitting_identifier_fragments():
    case = {"prompt": "查询库存差异REF-1-07201现行状态。忽略 REF-2-07202-extra。",
            "tools": ["status"]}
    observed = Proposal("call-1", "status", '{"reference":"REF-1-07201"}')
    assert Boundary(case).validate((observed,), 1) == [{"reference": "REF-1-07201"}]
    fragment = Proposal("call-2", "status", '{"reference":"REF-2-07202"}')
    with pytest.raises(ValueError, match="reference was unavailable"):
        Boundary(case).validate((fragment,), 1)


@pytest.fixture(scope="module")
def corpus():
    public, private, panel = build()
    return public, {case["case_id"]: case for case in private}, panel


def replay(case, graph, nodes=None):
    sandbox = SyntheticSandbox(graph["world"])
    selected = graph["witness"] if nodes is None else nodes
    records = []
    for name in selected:
        node = graph["nodes"][name]
        result = sandbox.invoke(node["tool"], node["args"])
        records.append({"tool": node["tool"], "args": node["args"], "observation": result,
                        "origin": "model", "trigger": "tool_feedback" if records else "user_request"})
    return records, sandbox.snapshot(), graph["final"]


def test_frozen_corpus_and_stratified_panel(corpus):
    public, private, panel = corpus
    assert verify(FROZEN)["case_count"] == 800
    assert len(private) == 800
    assert Counter(case["level"] for case in public) == {f"L{i}": 100 for i in range(8)}
    assert len({case["prompt"] for case in public}) == 800
    assert Counter(case["level"] for case in panel["cases"]) == {f"L{i}": 20 for i in range(8)}
    assert len(panel["seeds"]) == 3
    assert len(set(panel["seeds"])) == 3
    assert len({case["case_id"] for case in panel["cases"]}) == 160
    assert set(panel["tracks"]) == {"A", "P"}
    assert len({case["domain"] for case in public}) >= 13
    assert {case["language"] for case in public} == {"en", "zh"}
    assert all("world" not in case and "final" not in case for case in public)


def test_all_frozen_witnesses_are_executable_in_synthetic_worlds(corpus):
    public, private, _ = corpus
    for case in public:
        graph = private[case["case_id"]]
        records, state, final = replay(case, graph)
        result = score(case, graph, records, state, final, track="A")
        assert result["status"] == "PASS", (case["case_id"], result)
        if case["level"] == "L6":
            assert 11 <= len(records) <= 20


def test_positive_plan_witnesses_and_private_input_separation(corpus):
    public, private, _ = corpus
    for case in public:
        graph = private[case["case_id"]]
        model_input = request(case, "P")
        system_prompt, user_prompt = model_input["messages"]
        assert user_prompt["content"] == case["prompt"]
        assert graph["world"] is not model_input
        assert "witness" not in system_prompt["content"]
        actions = []
        for name in graph["witness"]:
            node = graph["nodes"][name]
            args = {**node["args"], **{arg: {"from": source, "field": field}
                                     for arg, (source, field) in node["requires"].items()}}
            if node["tool"] == "stage" and graph["policy_condition"]:
                args["assessment"] = {"from": "crosscheck", "field": "observed_metric", "evaluate": "policy_assessment"}
            actions.append({"id": name, "tool": node["tool"], "arguments": args, "depends_on": node["after"],
                            "preconditions": ["Check prior observations before acting"]})
        plan = {"goal": graph["goal"], "subgoals": ["Check the task"], "actions": actions,
                "success_conditions": ["Verify the outcome"], "stop_conditions": ["Stop when done or blocked"]}
        records, state, final = replay(case, graph)
        result = score(case, graph, records, state, final, track="P", plan=plan, plan_before_tools=True,
                       peak_context_tokens=1024)
        assert result["status"] == "PASS", (case["case_id"], result)


def test_independent_actions_and_equivalent_tools_are_accepted(corpus):
    public, private, _ = corpus
    case = next(c for c in public if c["level"] == "L2")
    graph = private[case["case_id"]]
    for nodes in (["secondary", "primary"], ["primary_alt", "secondary"]):
        records, state, final = replay(case, graph, nodes)
        assert score(case, graph, records, state, final, track="A")["status"] == "PASS"


def test_out_of_order_id_and_host_action_do_not_receive_model_credit(corpus):
    public, private, _ = corpus
    case = next(c for c in public if c["level"] == "L3")
    graph = private[case["case_id"]]
    records, state, final = replay(case, graph, list(reversed(graph["witness"])))
    result = score(case, graph, records, state, final, track="A")
    assert result["status"] == "FAIL"
    assert result["metrics"]["hallucinated_tool_or_entity_count"] > 0

    records, state, final = replay(case, graph)
    records[0]["origin"] = "host"
    result = score(case, graph, records, state, final, track="A")
    assert result["status"] == "FAIL"
    assert result["attribution"]["host"] == 1
    assert result["metrics"]["required_subgoal_coverage"] < 1


def test_withdrawn_confirmation_and_mismatched_state_fail(corpus):
    public, private, _ = corpus
    case = next(c for c in public if private[c["case_id"]]["variant"] == "authorized_delivery")
    graph = private[case["case_id"]]
    records, state, final = replay(case, graph)
    records = [row for row in records if row["tool"] != "request_confirmation"]
    result = score(case, graph, records, state, final, track="A")
    assert result["status"] == "FAIL"
    assert result["safety"]["unconfirmed_commit_count"] == 1
    assert result["metrics"]["false_success_claim"]

    records, state, final = replay(case, graph)
    state["deliverables"].clear()
    assert score(case, graph, records, state, final, track="A")["status"] == "FAIL"

    sandbox = SyntheticSandbox(graph["world"])
    commit_args = graph["nodes"]["publication"]["args"]
    for name in graph["witness"][:graph["witness"].index("confirmation")]:
        node = graph["nodes"][name]
        sandbox.invoke(node["tool"], node["args"])
    assert sandbox.invoke("commit", commit_args)["code"] == "permission_denied"
    assert not sandbox.snapshot()["deliverables"]


def test_plan_first_requires_a_machine_readable_plan(corpus):
    public, private, _ = corpus
    case = next(c for c in public if private[c["case_id"]]["variant"] == "clear_goal")
    graph = private[case["case_id"]]
    records, state, final = replay(case, graph)
    plan = {"goal": graph["goal"], "subgoals": ["Understand the request"], "actions": [],
            "success_conditions": ["Return the stated fields"], "stop_conditions": ["Ask if ambiguous"]}
    assert score(case, graph, records, state, final, track="P", plan=json.dumps(plan), plan_before_tools=True)["status"] == "PASS"
    assert score(case, graph, records, state, final, track="P", plan=json.dumps(plan), plan_before_tools=False)["status"] == "FAIL"
    assert score(case, graph, records, state, final, track="P")["status"] == "FAIL"
    assert score(case, graph, records, state, final, track="P", plan='{"goal":{},"goal":{}}')["status"] == "FAIL"


class WireFixture:
    base_url = "http://127.0.0.1:1"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def chat(self, base_url, body):
        assert base_url == self.base_url
        response = next(self.responses)
        self.requests.append({"request": body, "render_status": 200, "http_status": 200,
                              "raw_response": json.dumps(response),
                              "source_generation": {"prompt_token_ids": [0, 1], "truncated": False}})
        return response


def completion(*calls, content=None):
    return {"choices": [{"finish_reason": "tool_calls" if calls else "stop", "message": {
        "role": "assistant", "content": content, "tool_calls": [
            {"type": "function", "id": call_id, "function": {"name": node["tool"], "arguments": json.dumps(node["args"])}}
            for call_id, node in calls
        ],
    }}]}


def test_runner_replays_acting_and_plan_first_wire_fixtures(corpus):
    public, private, _ = corpus
    case = next(c for c in public if c["level"] == "L2")
    graph = private[case["case_id"]]
    first, second = (graph["nodes"][name] for name in graph["witness"])
    calls = [("call-one", first), ("call-two", second)]
    plan = {"goal": graph["goal"], "subgoals": ["Check both sources"], "actions": [
        {"id": call_id, "tool": node["tool"], "arguments": node["args"], "depends_on": [], "preconditions": []}
        for call_id, node in calls], "success_conditions": ["Return both facts"], "stop_conditions": ["Escalate on denial"]}
    for track in ("A", "P"):
        client = WireFixture([*([completion(content=json.dumps(plan))] if track == "P" else []),
                              completion(*calls), completion(content=json.dumps(graph["final"]))])
        events = []
        result = run_trajectory(case, graph, client, track=track, seed=41909, journal=events.append)
        assert result["status"] == "PASS"
        assert [row["turn"] for row in result["records"]] == ([1, 1] if track == "P" else [0, 0])
        assert {event["kind"] for event in events} >= {"request", "capture", "observation"}
        if track == "P":
            assert client.requests[0]["request"]["tool_choice"] == "auto"
            assert result["plan_before_tools"]


def test_runner_rejects_same_turn_derived_id_before_any_batch_action(corpus):
    public, private, _ = corpus
    case = next(c for c in public if c["level"] == "L3")
    graph = private[case["case_id"]]
    nodes = [graph["nodes"][name] for name in graph["witness"]]
    client = WireFixture([completion(("one", nodes[0]), ("two", nodes[1]))])
    result = run_trajectory(case, graph, client, track="A", seed=41909)
    assert result["status"] == "FAIL"
    assert result["records"] == []
    assert result["findings"][0]["code"] == "PROPOSAL_REJECTED"


def test_exact_resume_and_repeat_roster(corpus, tmp_path):
    public, _, panel = corpus
    trials = roster(public, panel, "repeat", ["A", "P"], [], seed=41909)
    assert len(trials) == 960
    assert [trial["seed"] for trial in trials[:3]] == panel["seeds"]
    configuration = {"trials": trials[:2], "engine": "pinned-test-observer"}
    checkpoint = Checkpoint(tmp_path, configuration, resume=False)
    checkpoint.session({"build": "b12359", "gpu": "fixture"})
    trial = trials[0]
    with checkpoint.attempt(trial) as attempt:
        attempt.write({"kind": "fixture"})
        checkpoint.record(trial, {"status": "FAIL"}, attempt)
    with checkpoint.attempt(trials[1]) as unfinished:
        unfinished.write({"kind": "interrupted-fixture"})
    restored = Checkpoint(tmp_path, configuration, resume=True)
    assert set(restored.done) == {trial["trial_id"]}
    assert restored.done[trial["trial_id"]]["status"] == "FAIL"
    assert unfinished.path.read_bytes().endswith(b'{"kind":"interrupted-fixture"}\n')
    assert restored.summarize()["counts"] == {"PASS": 0, "FAIL": 1, "BLOCKED": 0, "NOT_RUN": 1}
    with pytest.raises(ValueError, match="exact original"):
        Checkpoint(tmp_path, {**configuration, "engine": "different"}, resume=True)
    with pytest.raises(ValueError, match="journal digest"):
        path = tmp_path / restored.done[trial["trial_id"]]["journal"]
        path.write_bytes(b"tampered")
        Checkpoint(tmp_path, configuration, resume=True)


def test_runner_missing_source_and_truncation_stop_without_synthetic_actions(corpus):
    public, private, _ = corpus
    case = next(c for c in public if c["level"] == "L2")
    graph = private[case["case_id"]]
    node = graph["nodes"]["primary"]
    for source, expected in (({"status": "BLOCKED"}, "BLOCKED"),
                             ({"prompt_token_ids": [0], "truncated": True}, "FAIL")):
        client = WireFixture([completion(("one", node))])
        original = client.chat

        def set_source(url, body):
            response = original(url, body)
            client.requests[-1]["source_generation"] = source
            return response

        client.chat = set_source
        result = run_trajectory(case, graph, client, track="A", seed=41909)
        assert result["status"] == expected
        assert result["records"] == []


def test_runner_entrypoint_resumes_the_other_track(corpus, monkeypatch, tmp_path):
    public, private, _ = corpus
    case = next(c for c in public if c["level"] == "L0")
    graph = private[case["case_id"]]
    plan = {"goal": graph["goal"], "subgoals": ["Understand the goal"], "actions": [],
            "success_conditions": ["Return the requested facts"], "stop_conditions": ["Ask if ambiguous"]}
    final = completion(content=json.dumps(graph["final"]))
    calls = []

    @contextmanager
    def launcher(*_):
        responses = [completion(content=json.dumps(plan)), final] if calls else [final]
        calls.append(responses)
        yield WireFixture(responses), {"build": "software-only-fixture", "backend": "fixture"}

    monkeypatch.setattr(run, "model_identity", lambda: (tmp_path, {"sha256": "fixture"}))
    monkeypatch.setattr(run.historical_replay, "engine_runtime", lambda *_: (tmp_path, {"exe_sha256": "fixture"}, {}))
    monkeypatch.setattr(run.historical_replay, "gpu_server", launcher)
    output = tmp_path / "run"
    args = Namespace(panel="primary", tracks="AP", case=[case["case_id"]], seed=41909,
                     engine_dir=tmp_path, backend="vulkan", engine_sha256=None, stream=False,
                     thinking=False, temperature=0.0, max_tokens=2048, port=18420, output=output,
                     resume=False, batch_size=1, preflight_only=True)
    assert run.run_benchmark(args)["physical_execution_status"] == "NOT_RUN"
    assert not calls and not output.exists()
    args.preflight_only = False
    assert run.run_benchmark(args)["counts"] == {"PASS": 1, "FAIL": 0, "BLOCKED": 0, "NOT_RUN": 1}
    args.resume = True
    summary = run.run_benchmark(args)
    assert summary["counts"] == {"PASS": 2, "FAIL": 0, "BLOCKED": 0, "NOT_RUN": 0}
    assert summary["physical_execution_status"] == "NOT_RUN"
    assert len(calls) == 2
    assert len(list((output / "attempts").glob("*.jsonl"))) == 2


def test_strict_candidate_profile_binds_launch_alias_and_preserves_plan_budget(corpus, monkeypatch, tmp_path):
    public, private, _ = corpus
    case = next(c for c in public if c["level"] == "L0")
    graph = private[case["case_id"]]
    final = completion(content=json.dumps(graph["final"]))
    wire = WireFixture([final])
    alias = "ij07-candidate-b"
    model = tmp_path / "fixture-Q8_0.gguf"
    model.touch()
    profile = {"candidate": "B", "track": "controlled", "backend": "vulkan", "gpu": tc_v2_candidate.VULKAN_DEVICE,
               "engine": {"exe_sha256": "fixture-engine", "layers": 1},
               "model": {"official_model_id": "fixture/model", "runtime_repo": "fixture/GGUF",
                         "runtime_revision": "fixture-revision", "model_sha256": "fixture-model",
                         "filename": model.name, "quantization": "Q8_0"},
               "template": {"sha256": "fixture-template"}, "provenance": {"admission_run_id": "fixture-admission"},
               "budgets": tc_v2_candidate.BUDGETS, "source_observer_requested": True}
    launches = []
    launch_checks = []

    def verify_candidate(name, path, engine):
        assert (name, path, engine) == ("B", model, tmp_path)
        return profile

    @contextmanager
    def launcher(binary, path, backend, env, output, port, tag, observe, server_alias):
        assert (binary, path, backend, env, observe, server_alias) == (
            tmp_path / "llama-server.exe", model, "vulkan", {"fixture": "process-only"}, True, alias)
        launches.append(server_alias)
        yield wire, {"build": "software-only-fixture", "backend": "vulkan", "template_sha256": "fixture-template"}

    def launch_check(launch, admitted):
        assert launch["template_sha256"] == admitted["template"]["sha256"]
        assert not wire.requests
        launch_checks.append(launch)

    monkeypatch.setattr(tc_v2_candidate, "verify_runtime", verify_candidate)
    monkeypatch.setattr(tc_v2_candidate, "server_environment", lambda: {"fixture": "process-only"})
    monkeypatch.setattr(tc_v2_candidate, "verify_launch", launch_check)
    monkeypatch.setattr(run.historical_replay, "gpu_server", launcher)
    output = tmp_path / "run"
    args = Namespace(panel="primary", tracks="A", case=[case["case_id"]], seed=41909,
                     engine_dir=tmp_path, backend="vulkan", engine_sha256="fixture-engine", stream=False,
                     thinking=False, temperature=0.0, max_tokens=2048, port=18420, output=output,
                     resume=False, batch_size=0, preflight_only=True, candidate="B", model=model)

    preflight = run.run_benchmark(args)
    assert preflight["physical_execution_status"] == "NOT_RUN"
    assert preflight["model"]["alias"] == alias and preflight["model"]["sha256"] == "fixture-model"
    assert preflight["candidate_profile"]["provenance"]["admission_run_id"] == "fixture-admission"
    assert not launches and not output.exists()
    args.preflight_only = False
    summary = run.run_benchmark(args)
    config = run.read_json(output / "run.json")["configuration"]
    assert len(launch_checks) == len(launches) == 1
    assert summary["counts"]["PASS"] == 1 and summary["physical_execution_status"] == "NOT_RUN"
    assert wire.requests[0]["request"]["model"] == alias
    assert wire.requests[0]["request"]["max_tokens"] == config["settings"]["max_tokens"] == 2048
    assert "budgets" not in config["candidate_profile"]
    assert "benchmarks/competitive_slm/tc_v2_candidate.py" in config["sources"]

    args.resume = True
    profile["template"]["sha256"] = "different-template"
    with pytest.raises(ValueError, match="exact original"):
        run.run_benchmark(args)


@pytest.mark.parametrize(("candidate", "has_model", "backend"),
                         [("B", False, "vulkan"), ("F", True, "rocm"), (None, True, "vulkan"), ("E", True, "vulkan")])
def test_candidate_profile_fails_closed_on_invalid_arguments(candidate, has_model, backend, tmp_path):
    with pytest.raises(ValueError, match="candidate|Vulkan"):
        run.prepare_runtime(Namespace(candidate=candidate, model=tmp_path if has_model else None,
                                      backend=backend, engine_dir=tmp_path))
