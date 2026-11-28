import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest

sdk = pytest.importorskip("google.antigravity")
from google.antigravity import bin as sdk_bin

from benchmarks.slm10.ha11_sdk import TYPED, execute_sdk, matched_provider_controls


def test_shared_provider_limit_keeps_original_sdk_tool_choice():
    raw = '{"stream":true,"stream_options":{"include_usage":true},"tool_choice":"none","max_completion_tokens":65535}'
    effective = matched_provider_controls(raw, {"stream": False, "tool_choice": "auto", "seed": 7107,
                                                "max_completion_tokens": 768, "cache_prompt": False})
    assert effective == {"stream": False, "tool_choice": "none", "seed": 7107,
                         "max_completion_tokens": 768, "cache_prompt": False}


@pytest.mark.skipif(not Path(sdk_bin.__file__).with_name("localharness.exe").is_file(),
                    reason="requires pinned Windows SDK harness")
def test_real_sdk_binding_keeps_call_id_after_config_copy(tmp_path):
    requests, executions = [], []
    tool = {"type": "function", "function": {"name": "check_layout", "description": "Read layout.",
            "parameters": {"type": "object", "properties": {"page": {"type": "integer"}},
                           "required": ["page"]}}}

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(request)
            first = len(requests) == 1
            message = {"role": "assistant", "content": None if first else "Done"}
            if first:
                message["tool_calls"] = [{"type": "function", "id": "call_layout",
                                          "function": {"name": "check_layout", "arguments": '{"page":7}'}}]
            data = {"id": f"probe-{len(requests)}", "model": "synthetic", "object": "chat.completion", "created": 1,
                    "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if first else "stop"}]}
            reply = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

    def execute(proposal, turn, _wire):
        executions.append((proposal.call_id, turn, json.loads(proposal.arguments_raw)))
        return {"status": "ready"}

    with ThreadingHTTPServer(("127.0.0.1", 0), Provider) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            client = SimpleNamespace(base_url=f"http://127.0.0.1:{server.server_port}", trace_path=None)
            result = asyncio.run(execute_sdk(
                client, "synthetic", [tool], {"check_layout"}, execute, "Read layout page 7.", "Use supplied tools.",
                "scripted-sdk", tmp_path, Path(sdk_bin.__file__).with_name("localharness.exe"),
                profile=TYPED, model_budget=4, tool_budget=4, token_budget=768, provider_controls={"stream": False},
            ))
        finally:
            server.shutdown()
            thread.join()

    assert result["failure"] is None
    assert result["answer"] == "Done"
    assert executions == [("call_layout", 0, {"page": 7})]
    assert [row["tool_phase"] for row in result["wire"]] == ["ACT", "REPLAN"]
    assert [body["tool_choice"] for body in requests] == ["auto", "auto"]
    binding, = [row["binding"] for row in result["callbacks"]]
    assert binding["integer_conversions"] == (("page",),)
    assert binding["proposal"]["call_id"] == "call_layout"
