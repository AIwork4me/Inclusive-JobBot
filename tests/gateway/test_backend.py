import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from model_gateway import GatewayError
from model_gateway.llama_cpp_backend import LlamaCppBackend


@pytest.fixture
def loopback(monkeypatch):
    # This HTTP stand-in has no model, GPU, tool execution or route outside loopback.
    modes = {"reply": 200}
    requests = []
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request = self.rfile.read(int(self.headers["Content-Length"]))
            requests.append((self.path, json.loads(request)))
            response = {"choices": [{"index": 0, "message": {
                "role": "assistant", "content": "本地",
            }, "finish_reason": "stop"}]}
            self.send_response(modes["reply"])
            if modes["reply"] == 302:
                self.send_header("Location", "/unexpected")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests, modes
    finally:
        server.shutdown()
        worker.join()
        server.server_close()


def test_backend_sends_one_local_request_despite_environment_proxy(loopback):
    url, requests, _ = loopback
    result = LlamaCppBackend(url, "local").complete({"messages": [{"role": "user", "content": "hello"}]})
    assert result.content == "本地"
    assert requests == [("/v1/chat/completions", {"messages": [{"role": "user", "content": "hello"}],
                                                     "model": "local"})]


def test_redirect_does_not_change_backend_route(loopback):
    url, requests, modes = loopback
    modes["reply"] = 302
    with pytest.raises(GatewayError) as failure:
        LlamaCppBackend(url, "local").complete({"messages": []})
    assert failure.value.code == "MODEL_ERROR"
    assert len(requests) == 1


def test_per_request_model_override_rejected_before_http(loopback):
    url, requests, _ = loopback
    with pytest.raises(GatewayError) as failure:
        LlamaCppBackend(url, "local").complete({"model": "another", "messages": []})
    assert failure.value.code == "MODEL_ERROR"
    assert requests == []


@pytest.mark.parametrize("url", [
    "http://example.com:8080", "http://localhost:8080", "https://127.0.0.1:8080",
    "http://127.0.0.1", "http://127.0.0.1:8080/v1", "http://127.0.0.1:8080?alias=other",
    "http://127.0.0.1:8080#token", "http://local@127.0.0.1:8080",
])
def test_local_backend_requires_an_explicit_loopback_origin(url):
    with pytest.raises(ValueError, match="loopback"):
        LlamaCppBackend(url, "local")
