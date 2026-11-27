"""Independent software witnesses for the SQLite write boundary."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
import json
import sqlite3
from threading import Barrier

import pytest


def open_sandbox(path, session="session-east", scope=None):
    from benchmarks.slm10.multitool_stateful import SQLiteSandbox

    return SQLiteSandbox(path, session_id=session, initial_scope=scope)


TARGET = {"entity_id": "room-blue", "draft_id": "reservation-1", "draft_version": 1}
TEXT = "Reserve the accessible rehearsal room for the afternoon."
NEW_TEXT = "Reserve the accessible rehearsal room for the evening."


def call(sandbox, name, **args):
    return sandbox.invoke(name, json.dumps(args))


def stage(sandbox, *, entity_id="room-blue", draft_id="reservation-1"):
    return call(sandbox, "create_draft", entity_id=entity_id, draft_id=draft_id, text=TEXT)


@pytest.fixture
def sandbox(tmp_path):
    return open_sandbox(tmp_path / "software.sqlite", scope={"room-blue", "room-green"})


def review(sandbox, *, event="review-1", approved=True, target=TARGET):
    record = sandbox.review_draft(**target)
    assert record is not None
    assert sandbox.record_decision(record, event_id=event, approved=approved)


def test_authorized_draft_is_durable_without_publishing(tmp_path):
    db = tmp_path / "software.sqlite"
    writer = open_sandbox(db, scope={"room-blue"})
    assert stage(writer) == {"code": "drafted", "data": TARGET | {"scope_version": 1}}

    reopened = open_sandbox(db)
    snapshot = reopened.snapshot()
    assert snapshot["drafts"] == [TARGET | {"text": TEXT, "scope_version": 1}]
    assert snapshot["releases"] == snapshot["decisions"] == []
    assert call(reopened, "read_draft", **TARGET) == {
        "code": "ok", "data": TARGET | {"text": TEXT, "scope_version": 1},
    }


@pytest.mark.parametrize("tool,args", [
    ("create_draft", '{"entity_id":"room-blue","draft_id":"reservation-1","text":"a","text":"b"}'),
    ("create_draft", '{"entity_id":"room-blue","draft_id":"reservation-1","text":"  "}'),
    ("commit_draft", '{"entity_id":"room-blue","draft_id":"reservation-1","draft_version":true}'),
    ("record_decision", '{"entity_id":"room-blue","draft_id":"reservation-1","approved":true}'),
    ("update_scope", '{"scope":["outside"]}'),
    ("commit_draft", '{"entity_id":"room-blue","draft_id":"reservation-1","draft_version":1,"approved":true}'),
    ("commit_draft", '{"entity_id":"room-blue","draft_id":"reservation-1","draft_version":1,"session_id":"session-east"}'),
])
def test_model_cannot_forge_authority_or_bypass_argument_contract(sandbox, tool, args):
    stage(sandbox)
    assert sandbox.invoke(tool, args) == {"code": "invalid_call", "data": {}}
    state = sandbox.snapshot()
    assert state["scope"] == ["room-blue", "room-green"]
    assert len(state["drafts"]) == 1
    assert state["releases"] == state["decisions"] == []
    assert state["audit"][-1]["outcome"] == "INVALID_CALL"


def test_model_cannot_stage_an_entity_outside_the_host_grant(sandbox):
    assert stage(sandbox, entity_id="room-purple")["code"] == "permission_denied"
    assert sandbox.snapshot()["drafts"] == []


def test_commit_without_trusted_external_confirmation_fails_closed(sandbox):
    stage(sandbox)
    assert sandbox.review_draft(**TARGET).text == TEXT
    assert call(sandbox, "commit_draft", **TARGET) == {"code": "permission_denied", "data": {}}
    assert sandbox.snapshot()["releases"] == []
    assert sandbox.snapshot()["audit"][-1]["outcome"] == "APPROVAL_REQUIRED"


def test_explicit_denial_is_persisted_and_cannot_be_replaced(sandbox):
    stage(sandbox)
    review(sandbox, approved=False)
    record = sandbox.review_draft(**TARGET)
    assert not sandbox.record_decision(record, event_id="review-2", approved=True)
    assert call(sandbox, "commit_draft", **TARGET)["code"] == "permission_denied"
    state = sandbox.snapshot()
    assert state["decisions"] == [TARGET | {"event_id": "review-1", "decision": "DENIED", "scope_version": 1}]
    assert state["releases"] == []
    assert state["audit"][-1]["outcome"] == "APPROVAL_DENIED"


def test_approved_commit_is_durable_and_idempotent_across_reopen(tmp_path):
    db = tmp_path / "software.sqlite"
    sandbox = open_sandbox(db, scope={"room-blue"})
    stage(sandbox)
    review(sandbox)
    first = call(sandbox, "commit_draft", **TARGET)
    assert first == {"code": "committed", "data": TARGET | {"scope_version": 1}}

    reopened = open_sandbox(db)
    assert call(reopened, "commit_draft", **TARGET) == first
    state = reopened.snapshot()
    assert state["releases"] == [TARGET | {"text": TEXT, "event_id": "review-1", "scope_version": 1}]
    assert state["decisions"] == [TARGET | {"event_id": "review-1", "decision": "APPROVED", "scope_version": 1}]
    assert [(row["event"], row["outcome"]) for row in state["audit"]] == [
        ("create_draft", "DRAFTED"), ("external_decision", "APPROVED"),
        ("commit_draft", "COMMITTED"), ("commit_draft", "REPLAYED"),
    ]
    committed = state["audit"][-2]
    assert {key: committed[key] for key in TARGET} == TARGET
    assert committed["scope_version"] == 1 and committed["event_id"] == "review-1"
    with closing(sqlite3.connect(db)) as observer:
        assert observer.execute("SELECT session_id, entity_id, draft_id, draft_version, scope_version, event_id, text "
                                "FROM releases").fetchall() == [
            ("session-east", "room-blue", "reservation-1", 1, 1, "review-1", TEXT),
        ]
    assert call(reopened, "revise_draft", **TARGET, text=NEW_TEXT)["code"] == "permission_denied"


def test_external_decision_requires_exact_review_and_unique_event(sandbox):
    stage(sandbox)
    record = sandbox.review_draft(**TARGET)
    assert not sandbox.record_decision(replace(record, text="Different text"), event_id="review-1", approved=True)
    assert not sandbox.record_decision(record, event_id="review-1", approved="true")
    assert sandbox.record_decision(record, event_id="review-1", approved=True)
    assert sandbox.record_decision(record, event_id="review-1", approved=True)
    assert not sandbox.record_decision(record, event_id="review-1", approved=False)

    stage(sandbox, entity_id="room-green", draft_id="reservation-2")
    other = TARGET | {"entity_id": "room-green", "draft_id": "reservation-2"}
    assert not sandbox.record_decision(sandbox.review_draft(**other), event_id="review-1", approved=True)
    assert call(sandbox, "commit_draft", **other)["code"] == "permission_denied"
    assert call(sandbox, "commit_draft", **(TARGET | {"entity_id": "room-green"}))["code"] == "permission_denied"
    assert len(sandbox.snapshot()["decisions"]) == 1


def test_approval_cannot_transfer_to_revised_draft(sandbox):
    stage(sandbox)
    review(sandbox)
    old = sandbox.review_draft(**TARGET)
    current = TARGET | {"draft_version": 2}
    assert call(sandbox, "revise_draft", **TARGET, text=NEW_TEXT) == {
        "code": "drafted", "data": current | {"scope_version": 1},
    }
    assert not sandbox.record_decision(old, event_id="stale-review", approved=True)
    assert call(sandbox, "commit_draft", **TARGET)["code"] == "permission_denied"
    assert call(sandbox, "commit_draft", **current)["code"] == "permission_denied"
    review(sandbox, event="review-2", target=current)
    assert call(sandbox, "commit_draft", **current)["code"] == "committed"
    assert sandbox.snapshot()["releases"] == [
        current | {"text": NEW_TEXT, "event_id": "review-2", "scope_version": 1},
    ]


def test_scope_update_invalidates_approval_even_for_retained_entity(sandbox):
    stage(sandbox)
    review(sandbox)
    record = sandbox.review_draft(**TARGET)
    assert sandbox.update_scope({"room-blue"}) == 2
    assert sandbox.review_draft(**TARGET) is None
    assert not sandbox.record_decision(record, event_id="stale-review", approved=True)
    assert call(sandbox, "commit_draft", **TARGET)["code"] == "permission_denied"
    assert call(sandbox, "read_draft", **TARGET)["code"] == "permission_denied"
    current = TARGET | {"draft_version": 2}
    assert call(sandbox, "revise_draft", **TARGET, text=NEW_TEXT)["data"] == current | {"scope_version": 2}
    review(sandbox, event="review-2", target=current)
    assert call(sandbox, "commit_draft", **current)["code"] == "committed"
    assert sandbox.snapshot()["releases"] == [
        current | {"text": NEW_TEXT, "event_id": "review-2", "scope_version": 2},
    ]


def test_scope_revocation_blocks_draft_revision_and_receipt_replay(sandbox):
    stage(sandbox)
    review(sandbox)
    assert call(sandbox, "commit_draft", **TARGET)["code"] == "committed"
    assert sandbox.update_scope(set()) == 2
    assert call(sandbox, "commit_draft", **TARGET)["code"] == "permission_denied"
    assert call(sandbox, "revise_draft", **TARGET, text=NEW_TEXT)["code"] == "permission_denied"
    assert stage(sandbox, draft_id="reservation-2")["code"] == "permission_denied"
    assert len(sandbox.snapshot()["releases"]) == 1


def test_sessions_isolate_identical_draft_and_entity_ids(tmp_path):
    db = tmp_path / "software.sqlite"
    east = open_sandbox(db, scope={"room-blue"})
    west = open_sandbox(db, "session-west", {"room-blue"})
    stage(east)
    review(east)
    east_record = east.review_draft(**TARGET)
    assert call(west, "read_draft", **TARGET)["code"] == "permission_denied"
    assert west.snapshot()["drafts"] == []
    stage(west)
    assert not west.record_decision(east_record, event_id="review-2", approved=True)
    west_record = west.review_draft(**TARGET)
    assert not west.record_decision(west_record, event_id="review-1", approved=True)
    assert call(west, "commit_draft", **TARGET)["code"] == "permission_denied"
    assert call(east, "commit_draft", **TARGET)["code"] == "committed"
    assert west.snapshot()["releases"] == west.snapshot()["decisions"] == []
    review(west, event="review-2")
    assert call(west, "commit_draft", **TARGET)["code"] == "committed"
    assert east.snapshot()["releases"][0]["event_id"] == "review-1"
    assert west.snapshot()["releases"][0]["event_id"] == "review-2"
    with pytest.raises(ValueError, match="scope"):
        open_sandbox(db, scope={"room-green"})


def test_review_from_another_database_cannot_authorize_an_identical_session(tmp_path):
    old = open_sandbox(tmp_path / "old.sqlite", scope={"room-blue", "room-green"})
    new = open_sandbox(tmp_path / "new.sqlite", scope={"room-blue"})
    stage(old)
    stage(new)
    assert not new.record_decision(old.review_draft(**TARGET), event_id="review-1", approved=True)
    assert call(new, "commit_draft", **TARGET)["code"] == "permission_denied"


def test_concurrent_commit_has_one_mutation_and_one_receipt(tmp_path):
    db = tmp_path / "software.sqlite"
    first = open_sandbox(db, scope={"room-blue"})
    second = open_sandbox(db)
    stage(first)
    review(first)
    start = Barrier(2, timeout=5)

    def commit(instance):
        start.wait()
        return call(instance, "commit_draft", **TARGET)

    with ThreadPoolExecutor(max_workers=2) as workers:
        receipts = list(workers.map(commit, (first, second)))
    assert receipts == [{"code": "committed", "data": TARGET | {"scope_version": 1}}] * 2
    state = first.snapshot()
    assert len(state["releases"]) == 1
    assert [row["outcome"] for row in state["audit"][-2:]] == ["COMMITTED", "REPLAYED"]


def test_sqlite_failure_after_release_insert_rolls_back_and_allows_retry(tmp_path):
    db = tmp_path / "software.sqlite"
    sandbox = open_sandbox(db, scope={"room-blue"})
    stage(sandbox)
    review(sandbox)
    with closing(sqlite3.connect(db)) as fault:
        fault.execute("""CREATE TRIGGER inject_audit_failure BEFORE INSERT ON audit
                          WHEN NEW.outcome = 'COMMITTED'
                          BEGIN SELECT RAISE(ABORT, 'synthetic after-insert failure'); END""")
        assert call(sandbox, "commit_draft", **TARGET) == {"code": "transaction_failed", "data": {}}
        assert fault.execute("SELECT * FROM releases").fetchall() == []
        snapshot = open_sandbox(db).snapshot()
        assert snapshot["releases"] == []
        assert [row["outcome"] for row in snapshot["audit"]] == ["DRAFTED", "APPROVED", "ROLLED_BACK"]
        assert snapshot["decisions"][0]["event_id"] == "review-1"
        fault.execute("DROP TRIGGER inject_audit_failure")
    assert call(sandbox, "commit_draft", **TARGET)["code"] == "committed"
    assert len(sandbox.snapshot()["releases"]) == 1
