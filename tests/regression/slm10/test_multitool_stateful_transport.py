"""Scripted loopback software controls. These fixtures carry no model or GPU evidence."""

import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

import pytest

from benchmarks.root_cause.generation_capture import CaptureClient
from benchmarks.slm10.multitool_stateful import SQLiteSandbox


ENTITY = "room-blue"
DRAFT = "fixture-draft"
TEXT = "The accessible rehearsal room opens at 10:00."


@contextmanager
def scripted_provider(replies):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            index = len(requests)
            requests.append(body)
            message = replies[index](body) if index < len(replies) else {"content": "unexpected request"}
            raw = json.dumps({"id": f"mock-cmpl-{index}", "model": "software-fixture", "created": 1,
                              "object": "chat.completion", "choices": [{"message": {"role": "assistant", **message},
                                  "index": 0, "finish_reason": "tool_calls" if "tool_calls" in message else "stop"}],
                              "usage": {"prompt_tokens": 90, "completion_tokens": 10, "total_tokens": 100}}).encode()
            media = "application/json"
            if body.get("stream"):
                from benchmarks.slm10.tc_execution import adapted_sse

                media, raw = adapted_sse(media, raw, {"request": json.dumps(body)})
            self.send_response(200)
            self.send_header("Content-Type", media)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        worker = Thread(target=server.serve_forever, kwargs={"poll_interval": .05}, daemon=True)
        worker.start()
        try:
            yield CaptureClient(server.server_address[1]), requests
        finally:
            server.shutdown()
            worker.join()


def proposal(tool, **arguments):
    return {"content": None, "tool_calls": [{"id": "fixture-" + tool, "type": "function", "function": {
        "name": tool, "arguments": json.dumps(arguments),
    }}]}


@pytest.mark.parametrize("track", ["direct_acting_first", "sdk_acting_first"])
@pytest.mark.parametrize("scenario", ["approved", "declined", "revoked", "forged"])
def test_matched_public_paths_persist_only_fresh_host_approved_commit(tmp_path, track, scenario):
    from benchmarks.slm10.multitool_stateful_transport import HostDecision, StatefulService, public_case
    from benchmarks.slm10.planning_matched_executor import execute_trial

    kwargs = {}
    if track.startswith("sdk_"):
        sdk_bin = pytest.importorskip("google.antigravity.bin")
        harness = Path(sdk_bin.__file__).with_name("localharness.exe")
        if not harness.is_file():
            pytest.skip("Antigravity Windows harness is unavailable")
        kwargs = {"target": tmp_path / "sdk", "harness": harness}
    database = tmp_path / "control.sqlite"
    store = SQLiteSandbox(database, session_id="fixture-session", initial_scope={ENTITY})
    reviews = []

    def decide(review):
        reviews.append(review)
        return HostDecision("fixture-event", scenario != "declined")

    def commit(request):
        observation = json.loads(request["messages"][-1]["content"])
        if scenario == "revoked":
            store.update_scope({ENTITY})
        return proposal("commit", draft_id=DRAFT, approval=observation["external_event"]["approval"])

    service = StatefulService(store, reference=ENTITY, draft_id=DRAFT, text=TEXT, decide=decide)
    script = [lambda body: proposal("stage", reference=ENTITY, text=TEXT),
              lambda body: proposal("read_draft", draft_id=DRAFT)]
    if scenario == "forged":
        script.append(lambda body: proposal("commit", draft_id=DRAFT, approval="invented-by-model"))
    else:
        script.append(lambda body: proposal("request_confirmation", draft_id=DRAFT))
    if scenario in ("approved", "revoked"):
        script.append(commit)
    if scenario != "forged":
        script.append(lambda body: {"content": json.dumps({"outcome": scenario})})

    with scripted_provider(script) as (client, requests):
        trace = asyncio.run(execute_trial(client, "software-fixture", public_case(ENTITY, TEXT), service,
                                          "software-fixture-trial", track, seed=42, **kwargs))
    assert len(requests) == len(script), trace["failure"]
    assert trace["complete"] == (scenario != "forged"), trace["failure"]
    assert all(event.get("native_evidence", {}).get("status") == "NOT_RUN"
               for event in trace["wire"] if event.get("provider_request_id"))
    state = SQLiteSandbox(database, session_id="fixture-session").snapshot()
    target = {"entity_id": ENTITY, "draft_id": DRAFT, "draft_version": 1, "scope_version": 1}
    assert state["drafts"] == [target | {"text": TEXT}]
    assert state["releases"] == ([target | {"event_id": "fixture-event", "text": TEXT}] if scenario == "approved" else [])
    assert len(state["decisions"]) == len(reviews) == (0 if scenario == "forged" else 1)
    if reviews:
        assert reviews[0].text == TEXT and reviews[0].draft_version == 1
        assert state["decisions"] == [target | {"event_id": "fixture-event",
                                          "decision": "DENIED" if scenario == "declined" else "APPROVED"}]
    if scenario == "revoked":
        assert state["scope_version"] == 2
        assert trace["calls"][-1]["observation"] == {"code": "permission_denied", "data": {}}
    if scenario == "forged":
        assert "trusted external grant" in trace["failure"]["message"] or track.startswith("sdk_")


def test_confirmation_with_scope_change_during_host_review_never_issues_grant(tmp_path):
    from benchmarks.slm10.multitool_stateful_transport import HostDecision, StatefulService

    store = SQLiteSandbox(tmp_path / "control.sqlite", session_id="test-session", initial_scope={ENTITY})

    def stale(_):
        store.update_scope({ENTITY})
        return HostDecision("stale-event", True)

    service = StatefulService(store, reference=ENTITY, draft_id=DRAFT, text=TEXT, decide=stale)
    assert service.execute("stage", {"reference": ENTITY, "text": TEXT})["code"] == "ok"
    assert service.execute("read_draft", {"draft_id": DRAFT})["data"]["text"] == TEXT
    assert service.execute("request_confirmation", {"draft_id": DRAFT}) == {"code": "permission_denied", "data": {}}
    assert store.snapshot()["decisions"] == store.snapshot()["releases"] == []


def test_requires_persisted_readback_and_consumes_the_exact_grant_once(tmp_path):
    from benchmarks.slm10.multitool_stateful_transport import HostDecision, StatefulService

    store = SQLiteSandbox(tmp_path / "control.sqlite", session_id="test-session", initial_scope={ENTITY})
    reviews = []

    def decide(review):
        reviews.append(review)
        return HostDecision("fresh-review", True)

    service = StatefulService(store, reference=ENTITY, draft_id=DRAFT, text=TEXT, decide=decide)
    assert service.execute("stage", {"reference": ENTITY, "text": TEXT})["code"] == "ok"
    assert service.execute("request_confirmation", {"draft_id": DRAFT})["code"] == "permission_denied"
    assert reviews == []
    assert service.execute("read_draft", {"draft_id": DRAFT})["data"]["text"] == TEXT
    approval = service.execute("request_confirmation", {"draft_id": DRAFT})["external_event"]["approval"]
    exact = {"draft_id": DRAFT, "approval": approval}
    assert service.execute("commit", exact)["code"] == "ok"
    assert service.execute("commit", exact)["code"] == "permission_denied"
    assert len(store.snapshot()["releases"]) == 1
