"""Collect source-side generation and HTTP evidence from a private loopback server."""

import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from benchmarks.tool_calling_v2.parser.run_wire import raw_stream, split_sse
from model_gateway.errors import GatewayError
from model_gateway.openai_protocol import MAX_CALLS, decode_completion
from model_gateway.streaming import StreamAssembler


MAX_BODY = 4 * 1024 * 1024


class CaptureError(ValueError):
    pass


def protocol_reply(raw, stream):
    if not stream:
        return json.loads(raw)
    events = split_sse(raw)
    decoded = [json.loads(event) for event in events if event != b"[DONE]"]
    if len(decoded) == 1 and decoded[0].get("error"):
        return decoded[0]
    if not events or events[-1] != b"[DONE]" or events.count(b"[DONE]") != 1:
        raise CaptureError("SSE did not terminate exactly once")
    ids = {event.get("id") for event in decoded}
    if len(ids) != 1 or None in ids:
        raise CaptureError("SSE completion identity missing or changed")
    reply = raw_stream(events)
    if not reply.get("error") and not reply["choices"][0].get("finish_reason"):
        raise CaptureError("SSE missing terminal choice")
    reply.update(id=next(iter(ids)), timings=next(
        (event["timings"] for event in reversed(decoded) if "timings" in event), None,
    ))
    return reply


def correlate(rows, reply, stream):
    if len(rows) != 1:
        raise CaptureError(f"expected one source trace, read {len(rows)}")
    trace = rows[0]
    if not trace.get("completion_id") or trace.get("stream") is not stream:
        raise CaptureError("source identity or stream mode missing")
    if reply.get("id") and trace["completion_id"] != reply["id"]:
        raise CaptureError("source/wire completion identity mismatch")
    for field, usage_field in (("prompt_token_ids", "prompt_tokens"), ("sampled_token_ids", "completion_tokens")):
        ids = trace[field]
        expected = (reply.get("usage") or {}).get(usage_field)
        if not isinstance(ids, list) or any(type(token) is not int for token in ids):
            raise CaptureError("invalid source token list")
        if expected is not None and len(ids) != expected:
            raise CaptureError(f"{field} token count differs from usage")
    for field in ("sampled_bytes_hex", "pre_parser_bytes_hex"):
        bytes.fromhex(trace[field])
    return trace


def check_gateway(raw, stream, *, max_nonstream_calls=MAX_CALLS):
    try:
        if stream:
            gate = StreamAssembler()
            for event in split_sse(raw):
                gate.feed(event)
            gate.finish()
        else:
            decode_completion(raw, max_calls=max_nonstream_calls)
    except (GatewayError, ValueError) as exc:
        return {"status": "FAIL", "error": str(exc)}
    return {"status": "PASS"}


class CaptureClient:
    def __init__(self, port, trace_path=None, *, max_nonstream_calls=MAX_CALLS):
        self.base_url = f"http://127.0.0.1:{port}"
        self.max_nonstream_calls = max_nonstream_calls
        self.trace_path = Path(trace_path) if trace_path else None
        self.position = self.trace_path.stat().st_size if self.trace_path and self.trace_path.exists() else 0
        self.opener = build_opener(ProxyHandler({}))
        self.requests = []

    def post(self, path, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(self.base_url + path, data=data, headers={"Content-Type": "application/json"})
        try:
            response = self.opener.open(request, timeout=180)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY:
                raise CaptureError("HTTP body exceeded capture limit")
            return response.code, response.headers.get_content_type(), raw

    def read_trace(self):
        if self.trace_path is None or not self.trace_path.exists():
            return []
        with self.trace_path.open("rb") as handle:
            handle.seek(self.position)
            data = handle.read()
            self.position = handle.tell()
        if data and not data.endswith(b"\n"):
            raise CaptureError("source trace ended mid-record")
        return [json.loads(line) for line in data.splitlines()]

    def chat(self, base_url, body):
        if base_url != self.base_url:
            raise CaptureError("capture only accepts its configured loopback server")
        request = {**body, "verbose": True, "return_tokens": True}
        render_status, _, render = self.post("/apply-template", request)
        started = time.perf_counter()
        status, content_type, raw = self.post("/v1/chat/completions", request)
        wall_ms = round((time.perf_counter() - started) * 1000)
        stream = bool(request.get("stream"))
        try:
            reply = protocol_reply(raw, stream and status == 200)
        except (ValueError, KeyError, TypeError) as exc:
            reply = {"error": {"message": str(exc)}}
        rows = self.read_trace()
        try:
            source = correlate(rows, reply, stream)
        except (ValueError, KeyError, TypeError) as exc:
            source = {"status": "BLOCKED", "reason": str(exc), "unmatched_rows": rows}
        self.requests.append({
            "request": request, "render_status": render_status, "render_response": render.decode("utf-8"),
            "http_status": status, "content_type": content_type,
            "raw_response": raw.decode("utf-8"), "source_generation": source,
            "gateway_protocol": (check_gateway(raw, stream, max_nonstream_calls=self.max_nonstream_calls)
                                 if status == 200 else {"status": "NOT_RUN"}),
            "wall_ms": wall_ms,
        })
        if "error" not in reply and status == 200:
            return {**reply, "wall_ms": wall_ms}
        rejected = reply.get("error")
        parser_rejected = isinstance(rejected, dict) and (
            rejected.get("message") == "The model produced output that does not match the expected peg-native format"
        )
        return {"error": f"HTTP {status}" if status != 200 else "incomplete protocol response",
                "retryable": not parser_rejected and (status >= 500 or status == 429),
                "parser_rejected": parser_rejected, "wall_ms": wall_ms}
