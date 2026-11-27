from dataclasses import dataclass
from decimal import Decimal
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue, assemble_reply, wire_boundary
from audit import write_evidence
from model_gateway import GatewayError
from model_gateway.openai_protocol import MAX_WIRE_BYTES


@dataclass
class Call:
    call_id: str
    name: str
    arguments_raw: str


def test_only_validated_wire_arguments_can_be_claimed_once():
    queue = ApprovalQueue()
    call = Call("x", "lookup", '{"id":"PO-1"}')
    queue.publish([call])
    with pytest.raises(ValueError):
        queue.claim("lookup", {"id": "PO-2"})
    assert queue.claim("lookup", {"id": "PO-1"}) == call
    with pytest.raises(ValueError):
        queue.claim("lookup", {"id": "PO-1"})


def test_argument_type_change_and_ambiguous_callback_rejected():
    queue = ApprovalQueue()
    first = Call("x", "lookup", '{"count":1}')
    second = Call("y", "lookup", '{"count":1}')
    queue.publish([first])
    with pytest.raises(ValueError):
        queue.claim("lookup", {"count": True})
    with pytest.raises(ValueError, match="Duplicate"):
        queue.publish([first])
    queue = ApprovalQueue()
    queue.publish([first, second])
    with pytest.raises(ValueError):
        queue.claim("lookup", {"count": 1})


def test_expiring_turn_and_invalid_arguments_do_not_leave_permits():
    queue = ApprovalQueue()
    call = Call("x", "lookup", '{"id":"PO-1"}')
    queue.publish([call])
    queue.publish([])
    with pytest.raises(ValueError):
        queue.claim("lookup", {"id": "PO-1"})
    with pytest.raises(ValueError):
        queue.publish([Call("y", "lookup", '{"id":"PO-1","id":"PO-2"}')])
    with pytest.raises(ValueError):
        queue.claim("lookup", {"id": "PO-1"})


def test_cancellation_closes_approval_queue():
    queue = ApprovalQueue()
    call = Call("x", "lookup", '{"id":"PO-1"}')
    queue.publish([call])
    queue.close()
    with pytest.raises(ValueError, match="closed"):
        queue.claim("lookup", {"id": "PO-1"})
    with pytest.raises(ValueError, match="closed"):
        queue.publish([call])


def test_checkpoint_preserves_exact_decimal(tmp_path):
    output = tmp_path / "checkpoint.json"
    value = Decimal("123456789.123456789123456789")
    write_evidence(output, {"audit": {"elapsed": value}})
    loaded = json.loads(output.read_text(encoding="utf-8"), parse_float=Decimal)
    assert loaded["audit"]["elapsed"] == value


def test_wire_capture_keeps_rejected_upstream_response_and_failure_location():
    raw = b'data: {"choices":[]}\n\n'

    class EncodedReply(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Encoding", "identity")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    with HTTPServer(("127.0.0.1", 0), EncodedReply) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        events = []
        try:
            with wire_boundary(f"http://127.0.0.1:{server.server_port}", ApprovalQueue(), events,
                               trial_id="diagnostic-control") as endpoint:
                with pytest.raises(HTTPError) as failure:
                    urlopen(Request(endpoint.url + "/chat/completions", data=b"{}"), timeout=5)
            assert failure.value.code == 502
        finally:
            server.shutdown()
            thread.join()
    event, = events
    assert event["trial_id"] == "diagnostic-control"
    assert event["sdk_request_id"] != event["provider_request_id"]
    assert event["response"] == raw.decode()
    assert event["content_encoding"] == "identity"
    assert event["response_bytes"] == len(raw)
    assert event["failure"]["type"] == "builtins.ValueError"
    assert event["failure"]["function"] == "do_POST"
    assert event["status"] == "FAIL"


def test_qualified_sdk_stream_budget_preserves_frame_and_termination_checks():
    def frame(delta, finish=None):
        return b"data: " + json.dumps({
            "id": "same", "model": "local", "choices": [
                {"index": 0, "delta": delta, "finish_reason": finish},
            ],
        }).encode() + b"\n\n"

    piece = frame({"content": "x" * 1024})
    body = piece * 500 + frame({}, "stop") + b"data: [DONE]\n\n"
    with pytest.raises(GatewayError, match="stream byte limit"):
        assemble_reply("text/event-stream", body)
    assert assemble_reply("text/event-stream", body, max_stream_bytes=2 * MAX_WIRE_BYTES).finish_reason == "stop"
    with pytest.raises(GatewayError, match="stream did not terminate"):
        assemble_reply("text/event-stream", body.removesuffix(b"data: [DONE]\n\n"),
                       max_stream_bytes=2 * MAX_WIRE_BYTES)
    with pytest.raises(GatewayError):
        assemble_reply("text/event-stream", frame({"content": "x" * MAX_WIRE_BYTES}),
                       max_stream_bytes=2 * MAX_WIRE_BYTES)
