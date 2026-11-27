import asyncio
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread
from types import SimpleNamespace

import pytest

from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue
from benchmarks.slm10.sdk_extension import cases
from evaluation.aeve.runtime import canonical
from model_gateway import Proposal


def example(case_id):
    return next((public, graph) for _, (public, graph) in cases() if public["case_id"] == case_id)


def event(turn, *ids, messages=()):
    return {"completion_id": f"completion-{turn}", "provider_request_id": f"request-{turn}",
            "trial_id": "software-control", "parsed_tool_call_ids": list(ids),
            "provider_request": canonical({"messages": list(messages)}).decode()}


def delivery(tool, call_id, observation):
    payload = canonical({"result": canonical(observation).decode()}).decode()
    return {"role": "tool", "name": tool, "tool_call_id": call_id,
            "content": f"Created At: t0\nCompleted At: t1\nTool response for {tool}:\n```json\n{payload}\n```"}


def test_sdk_tool_signature_preserves_nested_types_and_callback_arguments():
    pytest.importorskip("google.antigravity")
    from google.antigravity.connections.local.interactions_config_converter import callable_to_function_tool_dict
    from google.antigravity.tools.tool_runner import ToolRunner

    from benchmarks.slm10.sdk_extension_execution import ExtensionSandbox, sdk_tools

    public, graph = example("EXT-H-RESCAN")
    sandbox = ExtensionSandbox(public, graph)
    approvals = ApprovalQueue()
    proposal = Proposal("probe", "read_asset",
                        '{"filters":{"asset":"SCAN38","profile":{"max_width":2048,"channels":["red","green"],"lossless":true}}}')
    approvals.publish([proposal])
    tools = sdk_tools(public, sandbox, approvals, [event(0, "probe")])
    definition = callable_to_function_tool_dict(next(tool for tool in tools if tool.__name__ == "read_asset"))
    params = definition["parameters"]["properties"]["filters"]["properties"]["profile"]["properties"]
    assert params["lossless"]["type"] == "boolean"
    assert params["channels"]["items"]["type"] == "string"
    args = json.loads(proposal.arguments_raw)
    with pytest.raises(ValueError, match="match one validated wire proposal"):
        asyncio.run(ToolRunner(tools).execute("read_asset", filters=args["filters"] | {"profile": {
            "max_width": 2048, "channels": ["red", "green"], "lossless": 1}}))
    assert asyncio.run(ToolRunner(tools).execute("read_asset", **args)) == '{"status":"stale"}'


def test_recognized_repeats_require_verified_result_delivery():
    from benchmarks.slm10.sdk_extension_execution import ExtensionSandbox

    public, graph = example("EXT-H-RESCAN")
    args = canonical(graph["actions"][0]["arguments"]).decode()
    service = ExtensionSandbox(public, graph)
    first = event(0, "p", "same-turn")
    assert service.execute(Proposal("p", "read_asset", args), 0, [first]) == {"status": "stale"}
    assert service.execute(Proposal("same-turn", "read_asset", args), 0, [first]) == {"error": "out_of_scope"}
    wrong = event(1, "bad", messages=[delivery("read_asset", "p", {"status": "fresh"})])
    assert service.execute(Proposal("bad", "read_asset", args), 1, [first, wrong]) == {"error": "out_of_scope"}
    right = event(2, "retry", messages=[delivery("read_asset", "p", {"status": "stale"})])
    assert service.execute(Proposal("retry", "read_asset", args), 2, [first, wrong, right]) == {
        "error": "out_of_scope"
    }
    service = ExtensionSandbox(public, graph)
    first = event(0, "p")
    service.execute(Proposal("p", "read_asset", args), 0, [first])
    right = event(1, "retry", messages=[delivery("read_asset", "p", {"status": "stale"})])
    assert service.execute(Proposal("retry", "read_asset", args), 1, [first, right]) == {"status": "fresh"}


def test_grounded_follow_up_binds_exact_producer_for_same_tool_entities():
    from benchmarks.slm10.sdk_extension_execution import ExtensionSandbox

    public, graph = example("EXT-H-SEAT")
    service = ExtensionSandbox(public, graph)
    first = event(0, "seat-b", "seat-a")
    for node, call_id in zip(reversed(graph["actions"][:2]), ("seat-b", "seat-a"), strict=True):
        service.execute(Proposal(call_id, node["tool"], canonical(node["arguments"]).decode()), 0, [first])
    second = event(1, "route", messages=[delivery("show_seat", "seat-a", {"available": False}),
                                       delivery("show_seat", "seat-b", {"available": True, "route": "RT-04"})])
    assert service.execute(Proposal("route", "access_route", '{"route":"RT-04"}'), 1, [first, second]) == {
        "step_free": True
    }
    assert service.calls[-1]["observation_sources"] == {
        "route": {"action_id": "inspect-seat-b", "call_id": "seat-b", "key": "route"}
    }


def test_enum_mutation_is_rejected_without_running_synthetic_tool():
    from benchmarks.slm10.sdk_extension_execution import ExtensionSandbox

    public, graph = example("EXT-H-RIGHTS")
    schema = public["tools"]["read_proof"]["parameters"]
    assert schema["properties"]["proofs"]["items"]["enum"] == ["attribution", "license", "consent"]
    sandbox = ExtensionSandbox(public, graph)
    proposal = Proposal("proof", "read_proof", '{"job":"GRAPH09","proofs":["attribution","unknown"]}')
    assert sandbox.execute(proposal, 0, [event(0, "proof")]) == {"error": "call_contract"}
    assert sandbox.calls[-1]["decision"] == "DENIED"


def test_qualification_replays_all_families_and_missing_certificate_blocks(tmp_path, monkeypatch):
    from benchmarks.slm10 import sdk_extension_execution as execution

    result = execution.qualification()
    assert result["status"] == "PASS"
    assert result["physical_execution"] == "NOT_RUN"
    assert {row["case_id"] for row in result["witnesses"] if row["status"] == "PASS"} == {
        "EXT-D-CATALOG", "EXT-H-RESCAN", "EXT-H-SEAT", "EXT-H-RIGHTS", "EXT-H-LAYOUT"
    }
    missing = tmp_path / "never-written.json"
    target = tmp_path / "never-run"
    monkeypatch.setattr(execution, "require_handoff", lambda *_: pytest.fail("reached Radeon preflight"))
    with pytest.raises(ValueError, match="mechanical qualification"):
        execution.run("A", tmp_path, target, 18754, "holdout", missing)
    assert not target.exists()
    tampered = deepcopy(result)
    tampered["witnesses"].pop()
    missing.write_bytes(canonical(tampered) + b"\n")
    with pytest.raises(ValueError, match="mechanical qualification"):
        execution.run("A", tmp_path, target, 18754, "holdout", missing)


@pytest.mark.skipif(sys.platform != "win32", reason="fixture uses the pinned Windows SDK harness")
def test_real_sdk_declares_enum_and_delivers_producer_with_scripted_provider(tmp_path):
    pytest.importorskip("google.antigravity")
    from google.antigravity import bin as sdk_bin

    from benchmarks.slm10.sdk_extension_execution import _sdk_trial, score

    public, graph = example("EXT-H-RIGHTS")
    model = "fixture-provider"
    requests = []
    responses = [
        {"tool_calls": [{"id": "sdk-proof", "type": "function", "function": {
            "name": "read_proof", "arguments": '{"job":"GRAPH09","proofs":["attribution","license"]}'}}]},
        {"tool_calls": [{"id": "sdk-verify", "type": "function", "function": {
            "name": "check_release", "arguments": '{"receipt":"P-73"}'}}]},
        {"content": '{"status":"verified"}'},
    ]

    class ScriptedProvider(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            turn = len(requests)
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            payload = canonical({"id": f"scripted-{turn}", "object": "chat.completion", "created": 1, "model": model,
                                 "choices": [{"index": 0, "message": {"role": "assistant", **responses[turn]},
                                              "finish_reason": "tool_calls" if turn < 2 else "stop"}]})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    with ThreadingHTTPServer(("127.0.0.1", 0), ScriptedProvider) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            client = SimpleNamespace(base_url=f"http://127.0.0.1:{server.server_port}", trace_path=None)
            harness = Path(sdk_bin.__file__).with_name("localharness.exe")
            result = asyncio.run(_sdk_trial(client, model, public, graph, "sdk-fixture", tmp_path, harness))
        finally:
            server.shutdown()
            thread.join()

    assert result["failure"] is None
    assert result["answer"] == '{"status":"verified"}'
    assert result["calls"][1]["observation_sources"] == {
        "receipt": {"action_id": "read-proof", "call_id": "sdk-proof", "key": "receipt"}
    }
    assert all(call["decision"] == "EXECUTED" for call in result["calls"])
    declared = next(item["function"] for item in requests[0]["tools"] if item["function"]["name"] == "read_proof")
    assert declared["parameters"]["properties"]["proofs"]["items"]["enum"] == ["attribution", "license", "consent"]
    assert score(graph, result)["status"] == "BLOCKED"

    # Scripted source records exercise mechanical replay only. No model or GPU was involved.
    for wire_event in result["wire"]:
        wire_event["source_generation"] = {"completion_id": wire_event["completion_id"], "stream": False,
                                           "rendered_prompt": "software fixture", "prompt_token_ids": [1],
                                           "sampled_token_ids": [2], "sampled_bytes_hex": "61",
                                           "pre_parser_bytes_hex": "61"}
    assert score(graph, result)["status"] == "PASS"
    corrupt_sdk_answer = result | {"answer": '{"status": "verified"}'}
    assert score(graph, corrupt_sdk_answer)["reason"] == "terminal SDK answer differs from provider output"
