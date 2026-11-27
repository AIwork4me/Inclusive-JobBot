"""Local protocol boundary for tools exposed to the Antigravity SDK."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import socket
from threading import Lock, Thread
import time
from traceback import extract_tb
from urllib.parse import urlsplit
from uuid import uuid4

from model_gateway import GatewayError, StreamAssembler, decode_completion
from model_gateway.openai_protocol import MAX_WIRE_BYTES
from model_gateway.strict_json import strict_object

MAX_BODY = 1 << 20


def _canonical(value):
    if isinstance(value, Decimal):
        return ("decimal", value)
    if type(value) is float:
        return ("decimal", Decimal(str(value)))
    if type(value) is dict:
        return ("object", sorted((k, _canonical(v)) for k, v in value.items()))
    if type(value) is list:
        return ("array", [_canonical(v) for v in value])
    return (type(value).__name__, value)


class ApprovalQueue:
    """Match a typed SDK callback to one pending wire proposal by exact value."""

    def __init__(self):
        self._lock = Lock()
        self._pending = []
        self._seen = set()
        self._closed = False

    def publish(self, calls):
        with self._lock:
            if self._closed:
                raise ValueError("Wire approval queue is closed")
            self._pending = []
            pending = [(call, _canonical(strict_object(call.arguments_raw))) for call in calls]
            ids = {call.call_id for call, _ in pending}
            if len(ids) != len(pending) or ids.intersection(self._seen):
                raise ValueError("Duplicate wire call ID")
            self._seen.update(ids)
            self._pending = pending

    def claim(self, name, arguments):
        with self._lock:
            if self._closed:
                raise ValueError("Wire approval queue is closed")
            wanted = _canonical(arguments)
            matches = [
                index for index, (call, bound) in enumerate(self._pending)
                if call.name == name and bound == wanted
            ]
            if len(matches) != 1:
                raise ValueError("SDK callback does not match one validated wire proposal")
            return self._pending.pop(matches[0])[0]

    def close(self):
        with self._lock:
            self._closed = True
            self._pending = []


def assemble_reply(content_type, body, *, max_stream_bytes=MAX_WIRE_BYTES):
    if not content_type.startswith("text/event-stream"):
        return decode_completion(body)
    assembler = StreamAssembler(max_stream_bytes=max_stream_bytes)
    for frame in body.replace(b"\r\n", b"\n").split(b"\n\n"):
        data = [line[5:].removeprefix(b" ") for line in frame.split(b"\n") if line.startswith(b"data:")]
        if data:
            assembler.feed(b"\n".join(data))
        elif frame and not all(line.startswith(b":") for line in frame.splitlines()):
            raise ValueError("Invalid SSE frame")
    return assembler.finish()


class _Server(ThreadingHTTPServer):
    daemon_threads = True


@dataclass(frozen=True)
class WireEndpoint:
    url: str
    abort: Callable[[], None]


@contextmanager
def wire_boundary(upstream, approvals, events, *, transient_first=False, transient_all=False,
                  request_started=None, trial_id=None, observe=None, max_stream_bytes=MAX_WIRE_BYTES,
                  adapt_request=None, adapt_response=None):
    """Verify each complete tool batch before releasing the response to the SDK.

    SSE frames are retained and forwarded unchanged once the terminal frame is
    checked. Buffering adds delay and this adapter cannot measure SDK TTFT.
    """
    target = urlsplit(upstream)
    if target.scheme != "http" or target.hostname != "127.0.0.1" or target.path or not target.port:
        raise ValueError("Expected a literal managed loopback origin")
    if trial_id is None and (observe is not None or adapt_request is not None or adapt_response is not None):
        raise ValueError("wire observation and adaptation require a trial identity")
    route = "/" + secrets.token_urlsafe(24) + "/v1"
    turn_lock = Lock()
    upstream_lock = Lock()
    active = None
    aborted = False

    def abort():
        nonlocal aborted
        with upstream_lock:
            aborted = True
            approvals.close()
            if active is not None and active.sock is not None:
                try:
                    active.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def reply(self, status, content_type, body):
            try:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except ConnectionError:
                pass

        def do_POST(self):
            nonlocal active
            if self.path != route + "/chat/completions":
                self.reply(404, "application/json", b'{"error":{"message":"Unknown model route"}}')
                return
            with turn_lock:
                connection = None
                event = {"status": "NOT_RUN"}
                if trial_id is not None:
                    event.update(trial_id=trial_id, sdk_request_id=uuid4().hex)
                events.append(event)
                started = time.perf_counter()
                try:
                    approvals.publish([])
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= MAX_BODY:
                        raise ValueError("Invalid body size")
                    self.connection.settimeout(15)
                    body = self.rfile.read(size)
                    event["request"] = body.decode("utf-8")
                    if request_started:
                        request_started.set()
                    if transient_all or (transient_first and len(events) == 1):
                        event.update(status="PASS", http_status=429, synthetic_fault=True)
                        self.reply(429, "application/json", b'{"error":{"message":"Synthetic retry qualification fault"}}')
                        return
                    if adapt_request is not None:
                        body = adapt_request(body)
                        if not isinstance(body, bytes) or not 0 < len(body) <= MAX_BODY:
                            raise ValueError("Invalid adapted body size")
                    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=60)
                    with upstream_lock:
                        if aborted:
                            raise ConnectionAbortedError()
                        active = connection
                        if trial_id is not None:
                            event.update(provider_request_id=uuid4().hex, provider_request=body.decode("utf-8"),
                                         provider_request_sha256=sha256(body).hexdigest())
                        connection.request("POST", "/v1/chat/completions", body, {"Content-Type": "application/json"})
                    upstream_response = connection.getresponse()
                    content_type = upstream_response.getheader("Content-Type", "application/json")
                    content_encoding = upstream_response.getheader("Content-Encoding")
                    if trial_id is not None:
                        event.update(http_status=upstream_response.status, content_type=content_type,
                                     content_encoding=content_encoding,
                                     content_length=upstream_response.getheader("Content-Length"))
                    response = upstream_response.read(MAX_BODY + 1)
                    if trial_id is not None:
                        event.update(response_bytes=len(response), response_sha256=sha256(response).hexdigest(),
                                     response_capture_complete=len(response) <= MAX_BODY)
                        try:
                            event["response"] = response.decode("utf-8")
                        except UnicodeDecodeError:
                            event["private_response_hex"] = response.hex()
                        if observe is not None:
                            observe(event)
                    if len(response) > MAX_BODY or content_encoding:
                        raise ValueError("Unsupported model response size or encoding")
                    event.update(response=response.decode("utf-8"), http_status=upstream_response.status,
                                 content_type=content_type)
                    if upstream_response.status == 200:
                        result = assemble_reply(content_type, response, max_stream_bytes=max_stream_bytes)
                        if adapt_response is not None:
                            content_type, response = adapt_response(content_type, response, event)
                            if not isinstance(response, bytes) or len(response) > MAX_BODY:
                                raise ValueError("Invalid SDK response adaptation")
                            event.update(sdk_response=response.decode("utf-8"), sdk_content_type=content_type)
                        with upstream_lock:
                            if aborted:
                                raise ConnectionAbortedError()
                            approvals.publish(result.calls)
                            event.update(status="PASS", validated_calls=len(result.calls))
                            if trial_id is not None:
                                event.update(parsed_tool_call_ids=[call.call_id for call in result.calls],
                                             validated_finish_reason=result.finish_reason)
                    self.reply(upstream_response.status, content_type, response)
                except (ValueError, OSError, GatewayError, http.client.HTTPException) as error:
                    event.update(status="FAIL", error_type=type(error).__name__,
                                 error_code="CANCELLED" if aborted else getattr(error, "code", None))
                    if trial_id is not None:
                        frame = extract_tb(error.__traceback__)[-1]
                        event["failure"] = {
                            "type": f"{type(error).__module__}.{type(error).__qualname__}",
                            "message": str(error), "file": Path(frame.filename).name,
                            "function": frame.name, "line": frame.lineno,
                        }
                    self.reply(502, "application/json", b'{"error":{"message":"Model protocol validation failed"}}')
                finally:
                    with upstream_lock:
                        if connection:
                            connection.close()
                        active = None
                    event["wall_ms"] = round((time.perf_counter() - started) * 1000, 2)

    server = _Server(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield WireEndpoint(f"http://127.0.0.1:{server.server_address[1]}{route}", abort)
    finally:
        abort()
        server.shutdown()
        server.server_close()
        thread.join()
