"""Bind a backend adapter to one local llama.cpp origin and model alias."""

from __future__ import annotations

import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .base import Completion
from .capabilities import BackendCapabilities
from .errors import ErrorCode, GatewayError
from .openai_protocol import MAX_WIRE_BYTES, decode_completion
from .streaming import StreamAssembler


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LlamaCppBackend:
    capabilities = BackendCapabilities(
        tool_calls=True, streaming=True, reasoning_separation=True, native_cancellation=False,
    )

    def __init__(self, origin: str, model: str, *, timeout: float = 30):
        address = urlsplit(origin)
        if (address.scheme != "http" or address.hostname not in {"127.0.0.1", "::1"}
                or not address.port or address.username is not None or address.path
                or address.query or address.fragment):
            raise ValueError("expected an explicit loopback HTTP origin")
        if not isinstance(model, str) or not model or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("expected one model alias and a finite positive socket timeout")
        self._url = origin + "/v1/chat/completions"
        self._model = model
        self._timeout = timeout
        self._http = build_opener(ProxyHandler({}), _NoRedirect())

    def complete(self, request: dict) -> Completion:
        if request.get("model", self._model) != self._model:
            raise GatewayError(ErrorCode.MODEL_ERROR, "request model differs from the configured model")
        stream = request.get("stream", False)
        if type(stream) is not bool:
            raise GatewayError(ErrorCode.PROTOCOL_ERROR, "stream must be a Boolean")
        try:
            raw = json.dumps({**request, "model": self._model}, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError):
            raise GatewayError(ErrorCode.PROTOCOL_ERROR, "invalid model request JSON") from None
        headers = {"Content-Type": "application/json",
                   "Accept": "text/event-stream" if stream else "application/json"}
        request = Request(self._url, data=raw, headers=headers, method="POST")
        try:
            with self._http.open(request, timeout=self._timeout) as response:
                media_type = response.headers.get_content_type()
                expected = "text/event-stream" if stream else "application/json"
                if media_type != expected:
                    raise GatewayError(ErrorCode.PROTOCOL_ERROR, "unexpected model response media type")
                body = response.read(MAX_WIRE_BYTES + 1)
                if len(body) > MAX_WIRE_BYTES:
                    raise GatewayError(ErrorCode.PROTOCOL_ERROR, "model response exceeds byte limit")
                if stream:
                    assembler = StreamAssembler()
                    for event in body.replace(b"\r\n", b"\n").split(b"\n\n"):
                        fields = [line[5:].removeprefix(b" ") for line in event.split(b"\n")
                                  if line.startswith(b"data:")]
                        if fields:
                            assembler.feed(b"\n".join(fields))
                    return assembler.finish()
                return decode_completion(body)
        except HTTPError as error:
            with error:
                if error.code == 500:
                    try:
                        info = json.loads(error.read(8192)).get("error")
                    except (UnicodeError, ValueError, OSError, AttributeError):
                        info = None
                    if isinstance(info, dict) and info.get("message") == (
                        "The model produced output that does not match the expected peg-native format"
                    ):
                        raise GatewayError(ErrorCode.PARSER_ERROR, "native tool parser rejected model output") from None
            raise GatewayError(ErrorCode.MODEL_ERROR, f"local inference returned HTTP {error.code}") from None
        except (TimeoutError, URLError) as error:
            if isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError):
                raise GatewayError(ErrorCode.TIMEOUT, "local model socket timed out") from None
            raise GatewayError(ErrorCode.MODEL_ERROR, "local model connection failed") from None
        except OSError:
            raise GatewayError(ErrorCode.MODEL_ERROR, "local model connection failed") from None
