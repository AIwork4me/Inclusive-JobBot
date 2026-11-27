import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread
from types import SimpleNamespace

import pytest

from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue
from benchmarks.slm10.sdk_adapter_development import (
    RequestBoundary, assess, load_plan, read_cases, require_synthetic_read_only, sdk_trial, verify_request_audits,
)
from benchmarks.slm10.sdk_adapters import load_profiles
from benchmarks.slm10.tc_v3 import CONFIG, PARAMETERS, TOOLS
from evaluation.aeve.runtime import canonical, fingerprint
from model_gateway.base import Proposal
from model_gateway.strict_json import strict_object


def test_holdout_plan_is_frozen_disjoint_and_balanced():
    plan, cases = load_plan()
    assert plan["candidate"] == "B"
    assert plan["treatment"] == "compact_result_codec"
    assert len(cases) == 12
    public = [case["public"] for case in cases]
    assert len({(case["family"], case["language"]) for case in public}) == 12
    full = read_cases("development-public.jsonl") + read_cases("holdout-public.jsonl")
    for field in ("case_id", "prompt"):
        assert not ({case[field] for case in full} & {case[field] for case in public})
    for case in cases:
        require_synthetic_read_only(case["public"], case["world"])
        assert len(case["arm_order"]) == 2 and set(case["arm_order"]) == {"reference", "treatment"}


def test_read_only_gate_rejects_write_tools_and_live_approval():
    _, cases = load_plan()
    public, world = cases[0]["public"], cases[0]["world"]
    with pytest.raises(ValueError, match="read-only"):
        require_synthetic_read_only(public | {"tools": ["commit_release"]}, world)
    with pytest.raises(ValueError, match="read-only"):
        require_synthetic_read_only(public, world | {"external_approval": "confirmed"})


def fixture(component="compact_result_codec"):
    _, cases = load_plan()
    case = next(case for case in cases if case["public"]["family"] == "single")
    profiles = load_profiles()
    public, world = case["public"], case["world"]
    calls = []

    def execute(proposal, turn, event):
        arguments = strict_object(proposal.arguments_raw)
        result = world["records"][proposal.name][arguments["reference"]]
        calls.append({key: event[key] for key in ("trial_id", "provider_request_id", "completion_id")} | {
            "call_id": proposal.call_id, "tool": proposal.name, "arguments_raw": proposal.arguments_raw,
            "decision": "EXECUTED", "result": result, "turn": turn,
        })
        return result

    service = SimpleNamespace(allowed_tools=set(public["tools"]), calls=calls, execute=execute)
    queue, wire = ApprovalQueue(), []
    boundary = RequestBoundary(profiles[component], public, service, queue, wire, "test-trial", lambda: None,
                               {"stream": False, "seed": case["seed"]}, public_tools(public))
    return case, service, queue, wire, boundary


def public_tools(public):
    return [{"type": "function", "function": {"name": name, "description": TOOLS[name], "parameters": PARAMETERS}}
            for name in public["tools"]]


def sdk_request(public, history=()):
    return canonical({"tools": public_tools(public), "stream": True, "messages": [
        {"role": "system", "content": CONFIG["system"] + "\n- Format your responses in github-style markdown.\n"},
        {"role": "user", "content": public["prompt"]},
        *history,
    ]})


def test_request_adapter_rejects_sdk_tool_scope_drift():
    case, _, _, wire, boundary = fixture()
    public = case["public"]
    payload = json.loads(sdk_request(public))
    payload["tools"] = []
    wire.append({"sdk_request_id": "sdk-one"})
    with pytest.raises(ValueError, match="tool"):
        boundary.adapt(canonical(payload))


def test_compact_uses_only_claimed_callback_receipts_and_binds_real_provider_ids():
    case, service, queue, wire, boundary = fixture()
    public, node = case["public"], case["oracle"]["nodes"][0]
    call = Proposal("call-one", node["tool"], canonical(node["arguments"]).decode())
    queue.publish([call])
    wire.append({"sdk_request_id": "sdk-one", "status": "PASS", "trial_id": "test-trial",
                 "provider_request_id": "provider-one", "completion_id": "completion-one",
                 "parsed_tool_call_ids": [call.call_id], "http_status": 200})
    result = boundary.callback(call.name, node["arguments"]["reference"])
    assert len(service.calls) == 1
    assert json.loads(result) == node["result"]

    proposal = {"role": "assistant", "tool_calls": [{"id": call.call_id, "type": "function",
                "function": {"name": call.name, "arguments": call.arguments_raw}}]}
    wrapper = ("Created At: 1\nCompleted At: 2\nTool response for " + call.name
               + ":\n```json\n" + json.dumps({"result": result}) + "\n```")
    tool = {"role": "tool", "name": call.name, "tool_call_id": call.call_id, "content": wrapper}
    wire.append({"sdk_request_id": "sdk-two", "trial_id": "test-trial", "status": "PASS"})
    output = boundary.adapt(sdk_request(public, (proposal, tool)))
    wire[-1].update(provider_request_id="provider-two", provider_request_sha256=fingerprint(json.loads(output)),
                    provider_request=output.decode())
    audit, = verify_request_audits(wire[1:])
    assert audit["provider_request_id"] == "provider-two"
    assert audit["callback_sources"] == (("provider-one", "completion-one", "call-one"),)
    assert json.loads(output)["messages"][-1]["content"] == result


def test_existing_approval_path_rejects_unlinked_callback():
    case, service, queue, _, boundary = fixture()
    node = case["oracle"]["nodes"][0]
    queue.publish([Proposal("call-one", node["tool"], canonical(node["arguments"]).decode())])
    with pytest.raises(ValueError, match="provenance"):
        boundary.callback(node["tool"], node["arguments"]["reference"])
    assert service.calls == []


@pytest.mark.skipif(sys.platform != "win32", reason="fixture uses the pinned Windows SDK harness")
@pytest.mark.parametrize("component", ["reference", "prompt_compiler", "compact_result_codec", "action_state"])
def test_real_sdk_request_profiles_with_scripted_loopback_provider(tmp_path, component):
    pytest.importorskip("google.antigravity")
    from google.antigravity import bin as sdk_bin

    _, cases = load_plan()
    case = cases[0]
    oracle = case["oracle"]
    node = oracle["nodes"][0]
    profiles = load_profiles()
    requests = []
    alias = "scripted-adapter-provider"
    tool_call = {"id": "call-source", "type": "function", "function": {
        "name": node["tool"], "arguments": canonical(node["arguments"]).decode(),
    }}

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            turn = len(requests)
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            message = {"tool_calls": [tool_call]} if turn == 0 else {"content": canonical(oracle["answer"]).decode()}
            raw = canonical({"id": f"fixture-{turn}", "object": "chat.completion", "created": 1, "model": alias,
                             "choices": [{"index": 0, "message": {"role": "assistant", **message},
                                          "finish_reason": "tool_calls" if turn == 0 else "stop"}]})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    with ThreadingHTTPServer(("127.0.0.1", 0), Provider) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            client = SimpleNamespace(base_url=f"http://127.0.0.1:{server.server_port}", trace_path=None)
            harness = Path(sdk_bin.__file__).with_name("localharness.exe")
            capture = asyncio.run(sdk_trial(client, alias, case["public"], case["world"], f"fixture-{component}",
                                            tmp_path, harness, case["seed"], profiles[component]))
        finally:
            server.shutdown()
            thread.join()

    assert capture["failure"] is None
    assert len(requests) == 2 and len(capture["calls"]) == 1
    assert all(event["native_evidence"]["status"] == "NOT_RUN" for event in capture["wire"])
    score = assess(capture, oracle, profiles)
    assert score["business_completion"] == "PASS"
    assert score["profile_application"] == ("NOT_RUN" if component == "reference" else "PASS")
    assert score["structured_output_observer"] == "PASS"
    assert score["native_source"] == "NOT_RUN"
    assert score["terminal_observer"]["decision"] == "ALLOW_FINAL"
    assert capture["host_protected_callbacks"] == []
    tool = next(message for message in requests[-1]["messages"] if message["role"] == "tool")
    if component == "compact_result_codec":
        assert json.loads(tool["content"]) == node["result"]
    else:
        assert tool["content"].startswith("Created At: ")
