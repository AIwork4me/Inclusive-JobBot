import asyncio
from collections import Counter
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Thread
from types import SimpleNamespace

import pytest

from benchmarks.slm10 import online_compensation as run
from benchmarks.slm10 import online_compensation_score as score
from evaluation.aeve.runtime import canonical, fingerprint


CORRECT = '{"reference":"BX-81","units":17,"state":"found"}'
FENCED = f'```json\n{CORRECT}\n```'
WRONG = '{"reference":"OTHER","units":17,"state":"found"}'


def fake_attempt(answer, *, stop="stop", attested=True, failure=None):
    return {"answer": answer, "failure": failure, "sdk_wall_ms": 17,
            "wire": [{"status": "PASS", "http_status": 200, "validated_calls": 0,
                      "provider_request_id": "synthetic", "response_capture_complete": True,
                      "validated_finish_reason": stop, "provider_stop_reason": stop,
                      "parsed_response": [{"message": {"content": answer}}],
                      "native_evidence": {"status": "PASS" if attested else "BLOCKED"},
                      "wall_ms": 5, "usage": {"prompt_tokens": 8, "completion_tokens": 4}}]}


def exercise(arm, *answers):
    calls = []

    def invoke(profile, attempt):
        calls.append((profile, attempt))
        return answers[attempt]

    return run.apply_arm(arm, invoke), calls


def test_schedule_counterbalances_all_arms_and_keeps_seeds_paired():
    roster = run.schedule()
    assert len(roster) == 96
    assert set(Counter(row["case_id"] for row in roster).values()) == {8}
    assert set(Counter((row["seed"], row["arm"], index % 4)
                       for index, row in enumerate(roster)).values()) == {3}
    assert all(len({(row["case_id"], row["seed"]) for row in roster[i:i + 4]}) == 1
               for i in range(0, len(roster), 4))


def test_host_extracts_only_terminal_complete_value_and_keeps_raw_attempt():
    capture, calls = exercise("HOST_NORMALIZED", fake_attempt(FENCED))
    assert capture["delivered"] == CORRECT
    assert capture["attempts"][0]["answer"] == FENCED
    assert len(calls) == 1
    assert capture["host_normalization_ms"] >= 0


@pytest.mark.parametrize("answer", [FENCED + "\nextra", f'```json\n{{"x":1,"x":2}}\n```'])
def test_host_preserves_ambiguous_raw_values(answer):
    capture, _ = exercise("HOST_NORMALIZED", fake_attempt(answer))
    assert capture["delivered"] == answer


def test_retry_is_schema_triggered_single_bounded_attempt():
    capture, calls = exercise("RETRY_ASSISTED", fake_attempt(FENCED), fake_attempt(CORRECT))
    assert calls == [("original", 0), ("retry", 1)]
    assert capture["delivered"] == CORRECT
    assert [item["answer"] for item in capture["attempts"]] == [FENCED, CORRECT]
    wrong, calls = exercise("RETRY_ASSISTED", fake_attempt(WRONG))
    assert len(calls) == 1
    assert wrong["delivered"] == WRONG
    invalid, calls = exercise("RETRY_ASSISTED", fake_attempt(FENCED), fake_attempt("{}"))
    assert len(calls) == 2
    assert invalid["delivered"] == "{}"


@pytest.mark.parametrize("first", [fake_attempt(FENCED, stop="length"),
                                   fake_attempt(FENCED, failure="transport")])
def test_unvalidated_terminal_never_normalizes_or_retries(first):
    for arm in ("HOST_NORMALIZED", "RETRY_ASSISTED"):
        capture, calls = exercise(arm, first)
        assert capture["delivered"] is None
        assert len(calls) == 1


def test_schema_request_contains_only_public_shape_and_retry_only_fixed_prompt():
    original = {"model": "test", "messages": [{"role": "user", "content": "public facts"}], "stream": True}
    base = run.request_body(original, "test", 11731, "original", "public facts")
    constrained = run.request_body(original, "test", 11731, "grammar", "public facts")
    assert base == {k: v for k, v in constrained.items() if k != "response_format"}
    properties = constrained["response_format"]["json_schema"]["schema"]["properties"]
    assert properties["reference"] == {"type": ["string", "null"]}
    assert properties["units"] == {"type": ["integer", "null"]}
    assert "const" not in json.dumps(properties)
    assert run.prompt_text("public facts", "retry") == "public facts\n\n" + run.RETRY_PROMPT
    with pytest.raises(ValueError):
        run.request_body(original | {"tools": [{"type": "function"}]}, "test", 11731, "original", "public facts")


def test_runtime_does_not_import_scoring_module():
    command = ('import sys; import benchmarks.slm10.online_compensation; '
               'assert "benchmarks.slm10.online_compensation_score" not in sys.modules')
    root = Path(run.__file__).parents[2]
    environment = {**os.environ, "PYTHONPATH": str(root / "src")}
    subprocess.run([sys.executable, "-c", command], check=True, cwd=root, env=environment, timeout=30)


def test_offline_score_distinguishes_syntax_facts_and_uncertainty():
    expected = {"reference": "BX-81", "units": 17, "state": "found"}
    original, _ = exercise("MODEL_NATIVE", fake_attempt(FENCED))
    result = score.assess(original, expected)
    assert [result[key] for key in ("schema", "facts", "usable")] == ["FAIL", "PASS", "FAIL"]
    host, _ = exercise("HOST_NORMALIZED", fake_attempt(FENCED))
    assert score.assess(host, expected)["usable"] == "PASS"
    unknown = {"reference": None, "units": None, "state": "unknown"}
    false_claim, _ = exercise("MODEL_NATIVE", fake_attempt(CORRECT))
    assert score.assess(false_claim, unknown)["uncertainty"] == "FAIL"
    assert score.assess(false_claim, unknown)["schema"] == "PASS"
    ambiguous, _ = exercise("MODEL_NATIVE", fake_attempt(CORRECT, attested=False))
    assert score.assess(ambiguous, expected)["usable"] == "BLOCKED"


def test_resource_replay_counts_extra_inference_and_preserves_missing_metrics():
    trial, _ = exercise("RETRY_ASSISTED", fake_attempt(FENCED), fake_attempt(CORRECT))
    assert score.resources(trial)["provider_requests"] == 2
    assert score.resources(trial)["sdk_wall_ms"] == 34
    assert score.resources(trial)["prompt_tokens"] == 16
    assert score.resources(trial)["native_decode_ms"] is None


def test_unrun_capture_keeps_full_denominator_and_rejects_wrong_plan():
    metadata = {"candidate": "D", "run_id": "test", "plan": run.plan(), "gpu_execution": "NOT_RUN"}
    result = score.replay(metadata, [])
    assert result["physical"] == "NOT_RUN"
    assert result["arms"]["MODEL_NATIVE"]["usable"]["NOT_RUN"] == 24
    with pytest.raises(ValueError, match="preregistration"):
        score.replay(metadata | {"plan": {}}, [])


@pytest.mark.skipif(sys.platform != "win32", reason="fixture uses the pinned Windows SDK harness")
def test_real_sdk_grammar_request_and_terminal_delivery_over_scripted_sse(tmp_path):
    from google.antigravity import bin as sdk_bin

    alias = "ijslm-candidate-d"
    received = []

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            shared = {"id": "fixture-completion", "object": "chat.completion.chunk", "model": alias, "created": 1}
            frames = [
                shared | {"choices": [{"index": 0, "delta": {"role": "assistant", "content": CORRECT},
                                        "finish_reason": None}]},
                shared | {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
                shared | {"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 14, "total_tokens": 21},
                          "timings": {"prompt_ms": 2.0, "predicted_ms": 8.0}},
            ]
            raw = b"".join(b"data: " + canonical(frame) + b"\n\n" for frame in frames) + b"data: [DONE]\n\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    with ThreadingHTTPServer(("127.0.0.1", 0), Provider) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            client = SimpleNamespace(base_url=f"http://127.0.0.1:{server.server_port}", trace_path=None)
            harness = Path(sdk_bin.__file__).with_name("localharness.exe")
            spec = {"case_id": "P0B-O01", "seed": 11731}
            capture = asyncio.run(run.sdk_attempt(client, alias, "fixture-0", tmp_path, harness,
                                                  run.PUBLIC[spec["case_id"]][1], spec["seed"], "grammar"))
        finally:
            server.shutdown()
            thread.join()

    assert len(received) == 1
    assert received[0]["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert received[0]["messages"] == [{"role": "system", "content": run.SYSTEM},
                                        {"role": "user", "content": run.PUBLIC[spec["case_id"]][1]}]
    assert run.terminal(capture) is True
    assert capture["answer"] == CORRECT
    assert capture["wire"][0]["native_evidence"]["status"] == "NOT_RUN"
    assert capture["wire"][0]["timings"] == {"prompt_ms": 2.0, "predicted_ms": 8.0}
    score.verified_attempt(capture, "fixture-0", spec, "grammar", "D")
    altered = deepcopy(capture)
    altered["wire"][0]["parsed_response"][0]["message"]["content"] = WRONG
    with pytest.raises(ValueError, match="projection"):
        score.verified_attempt(altered, "fixture-0", spec, "grammar", "D")
    capture["wire"][0]["response"] += "\n"
    with pytest.raises(ValueError, match="checksum"):
        score.verified_attempt(capture, "fixture-0", spec, "grammar", "D")


def test_interrupted_capture_blocks_only_reserved_slots(tmp_path):
    metadata = {"candidate": "F", "run_id": "interrupted", "plan": run.plan(), "gpu_execution": "NOT_RUN",
                "source_sha256": run.source_hashes()}
    first = run.schedule()[0]
    trial = fingerprint([metadata["run_id"], first])
    (tmp_path / "run.json").write_bytes(canonical(metadata))
    (tmp_path / trial).mkdir()
    report = score.replay(*score.read_capture(tmp_path))
    assert report["physical"] == "BLOCKED"
    assert report["arms"][first["arm"]]["usable"] == {"NOT_RUN": 23, "BLOCKED": 1, "PASS": 0, "FAIL": 0}
    (tmp_path / "run.json").write_bytes(canonical(metadata | {"source_sha256": {}}))
    with pytest.raises(ValueError, match="execution sources"):
        score.read_capture(tmp_path)
