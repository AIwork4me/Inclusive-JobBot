from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue, wire_boundary
from benchmarks.slm10.lfm3_ha_admission import admission_route, equivalent, intervention, numeric_row


class LoRANumericEvidenceTests(unittest.TestCase):
    def test_equal_and_reproducible_difference(self):
        base = [(0, -0.2), (1, -2.0)]
        self.assertTrue(equivalent(base, [(0, -0.200001), (1, -2.0)]))
        self.assertFalse(equivalent(base, [(1, -2.0), (0, -0.2)]))
        self.assertFalse(intervention(base, [(0, -0.20001), (1, -2.0)]))
        self.assertTrue(intervention(base, [(1, -0.3), (0, -2.0)]))
        self.assertFalse(intervention(base, [(20, -0.1), (21, -2.0)]))

    def test_native_numeric_row_refuses_incomplete_or_nonfinite_data(self):
        row = {"id": 0, "top_logprobs": [{"id": i, "logprob": -1.0 - i} for i in range(32)]}
        self.assertEqual(numeric_row({"completion_probabilities": [row]})[1][0], 1)
        for bad in ([], [row, row], [dict(row, id=80)],
                    [dict(row, top_logprobs=[{"id": 0, "logprob": float("nan")}] * 32)]):
            with self.assertRaises(ValueError):
                numeric_row({"completion_probabilities": bad})

    def test_guard_denies_wrong_model_and_weight_overrides(self):
        allowed = b'{"model":"lfm3-ha","messages":[]}'
        self.assertEqual(admission_route(allowed), allowed)
        for raw in (b'{"model":"another"}', b'{}', b'{"model":"lfm3-ha","lora":[{"id":99,"scale":1}]}',
                    b'{"model":"lfm3-ha","lora":[{"id":0,"scale":0}]}',
                    b'{"model":"lfm3-ha","model":"another"}', b'{"model":"lfm3-ha","lora":[]}'):
            with self.assertRaises(ValueError):
                admission_route(raw)

    def test_fixed_sdk_route_rejects_cross_session_and_aborted_routes(self):
        forwarded = []
        terminal = (b'{"choices":[{"index":0,"finish_reason":"stop",'
                    b'"message":{"role":"assistant","content":"Synthetic"}}]}')

        class ScriptedProvider(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                forwarded.append(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(terminal)))
                self.end_headers()
                self.wfile.write(terminal)

        payload = b'{"model":"lfm3-ha","messages":[]}'
        opener = build_opener(ProxyHandler({}))

        def send(url):
            return opener.open(Request(url + "/chat/completions", data=payload), timeout=4)

        with ThreadingHTTPServer(("127.0.0.1", 0), ScriptedProvider) as upstream:
            thread = Thread(target=upstream.serve_forever)
            thread.start()
            try:
                origin = f"http://127.0.0.1:{upstream.server_port}"
                with (wire_boundary(origin, ApprovalQueue(), [], trial_id="session-one",
                                    adapt_request=admission_route) as first,
                      wire_boundary(origin, ApprovalQueue(), [], trial_id="session-two",
                                    adapt_request=admission_route) as second):
                    with send(second.url) as reply:
                        self.assertEqual(reply.status, 200)
                    cross_session = f"http://{urlsplit(second.url).netloc}{urlsplit(first.url).path}"
                    with self.assertRaises(HTTPError) as rejected:
                        send(cross_session)
                    self.assertEqual(rejected.exception.code, 404)
                    first.abort()
                    with self.assertRaises(HTTPError) as stale:
                        send(first.url)
                    self.assertEqual(stale.exception.code, 502)
            finally:
                upstream.shutdown()
                thread.join()
        self.assertEqual(forwarded, [payload])
