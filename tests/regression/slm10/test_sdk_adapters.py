import json
from decimal import Decimal
from hashlib import sha256
from threading import Event

import pytest

from benchmarks.slm10.sdk_adapters import (
    AdapterProfile, CallbackReceipt, DuplicateExecutionGuard, GuardAuthorization, RequestContext,
    Scope, TerminalContext, adapt_request, load_profiles, structured_output, termination_decision,
)
from model_gateway.errors import ErrorCode, GatewayError
from model_gateway.strict_json import strict_object


STYLE = "- Format your responses in github-style markdown.\n"
SYSTEM = "Deny all writes without human approval.\n" + STYLE + "Check cancellation.\n"
SCOPE = Scope("test-run", "test-session", "synthetic-principal", "initial-scope", "executive")
RESULT = b'{"status":"ready","score":0.1234567890123456789012345678}'
ARGS = b'{"ref":"record-1","constraints":{"country":"CN"}}'


def digest(raw):
    return sha256(raw).hexdigest()


def tool_message(result=RESULT):
    wrapper = "Created At: before\nCompleted At: after\nTool response for read_record:\n"
    wrapper += "```json\n" + json.dumps({"result": result.decode()}) + "\n```"
    return {"role": "tool", "name": "read_record", "tool_call_id": "call-a", "content": wrapper}


def source(message=None, system=SYSTEM):
    message = tool_message() if message is None else message
    return json.dumps({"tools": [{"function": {"name": "read_record"}}], "stream": True, "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": STYLE},
        {"role": "assistant", "tool_calls": [{"id": "call-a", "type": "function", "function": {
            "name": "read_record", "arguments": ARGS.decode(),
        }}]},
        message,
    ]}).encode()


def receipt(result=RESULT, *, scope=SCOPE, status="EXECUTED", call_id="call-a", arguments=ARGS):
    return CallbackReceipt(scope, "prior-request", "completion-1", call_id, "read_record", arguments, result, status)


def context(*callbacks, scope=SCOPE, system=SYSTEM):
    return RequestContext(scope, "current-request", digest(system.encode()), callbacks)


def profile(component):
    return load_profiles()[component]


@pytest.mark.parametrize("component", ["reference", "duplicate_execution_guard", "termination_policy",
                                       "structured_output_contract"])
def test_unrelated_or_off_request_arm_preserves_exact_bytes(component):
    raw = source()
    output, audit = adapt_request(profile(component), raw, context(receipt()))
    assert output is raw
    assert audit.before_sha256 == audit.after_sha256 == digest(raw)
    assert audit.message_indices == ()


def test_registry_enables_only_one_versioned_component_and_rejects_unknown_versions():
    profiles = load_profiles()
    assert len(profiles) == 7
    assert profiles["reference"] == AdapterProfile()
    with pytest.raises(ValueError, match="version"):
        AdapterProfile("prompt_compiler", "unknown")


def test_prompt_compiler_changes_only_verified_sdk_system_style_line():
    raw = source()
    output, audit = adapt_request(profile("prompt_compiler"), raw, context(receipt()))
    after, before = json.loads(output), json.loads(raw)
    before["messages"][0]["content"] = "Deny all writes without human approval.\nCheck cancellation.\n"
    assert after == before
    assert audit.message_indices == (0,)
    assert audit.provider_request_id == "current-request"
    assert audit.elapsed_ns >= 0


def test_prompt_compiler_requires_the_bound_system_message_and_an_unambiguous_style_line():
    unknown = source(system=SYSTEM + "unverified content")
    assert adapt_request(profile("prompt_compiler"), unknown, context())[0] is unknown
    ambiguous = source(system=SYSTEM + STYLE)
    assert adapt_request(profile("prompt_compiler"), ambiguous, context(system=SYSTEM + STYLE))[0] is ambiguous


def test_compact_codec_preserves_precise_and_nested_result_semantics_and_other_fields():
    raw = source()
    output, audit = adapt_request(profile("compact_result_codec"), raw, context(receipt()))
    after, before = strict_object(output), strict_object(raw)
    result = strict_object(after["messages"][3]["content"])
    assert result == {"status": "ready", "score": Decimal("0.1234567890123456789012345678")}
    before["messages"][3]["content"] = after["messages"][3]["content"]
    assert after == before
    assert audit.message_indices == (3,)
    assert audit.callback_sources == (("prior-request", "completion-1", "call-a"),)
    assert audit.after_bytes < audit.before_bytes


@pytest.mark.parametrize("invalid", [
    b'{"status":"ready","score":6}', b'{"status":"ready","status":"ready"}',
    b'{"status":"ready","score":NaN}', b'{"status":"ready","score":true}',
])
def test_compact_codec_rejects_mismatched_and_ambiguous_claimed_results(invalid):
    raw = source(tool_message(invalid))
    with pytest.raises(GatewayError):
        adapt_request(profile("compact_result_codec"), raw, context(receipt()))


def test_compact_codec_requires_prior_same_scope_execution_and_proposal_link():
    original = source()
    assert adapt_request(profile("compact_result_codec"), original, context())[0] is original
    stale = Scope("test-run", "test-session", "synthetic-principal", "old-scope", "executive")
    for callback in (receipt(scope=stale), receipt(status="FAILED"), receipt(call_id="missing")):
        assert adapt_request(profile("compact_result_codec"), original, context(callback))[0] is original
    with pytest.raises(GatewayError, match="arguments"):
        adapt_request(profile("compact_result_codec"), original,
                      context(receipt(arguments=b'{"ref":"different"}')))


def test_action_state_lists_only_prior_scope_current_successes_with_proof():
    raw = source()
    result, audit = adapt_request(profile("action_state"), raw, context(receipt()))
    after, before = json.loads(result), json.loads(raw)
    assert after["messages"][0]["content"].startswith(SYSTEM)
    assert "call-a" in after["messages"][0]["content"]
    assert "ready" not in after["messages"][0]["content"]
    before["messages"][0] = after["messages"][0]
    assert before == after
    assert audit.callback_sources == (("prior-request", "completion-1", "call-a"),)


def test_action_state_excludes_guard_replay_stale_scope_and_unobserved_actions():
    raw = source()
    stale = Scope("test-run", "test-session", "synthetic-principal", "old-scope", "executive")
    for callback in (receipt(status="HOST_REUSED"), receipt(scope=stale), receipt(call_id="unseen")):
        assert adapt_request(profile("action_state"), raw, context(callback))[0] is raw


def auth(call_id="call-a", **changes):
    fields = dict(scope=SCOPE, provider_request_id="prior-request" if call_id == "call-a" else "next-request",
                  call_id=call_id, tool="read_record",
                  arguments=ARGS, resource="record-1", immutable_revision="data-v1", read_only=True,
                  repeat_intent="REDUNDANT", permission="ALLOW", reuse_allowed=True)
    return GuardAuthorization(**(fields | changes))


def test_guard_returns_verified_fresh_read_and_audits_host_attribution():
    events = []
    guard = DuplicateExecutionGuard(profile("duplicate_execution_guard"), {"read_record"}, events.append)
    guard.remember(auth(), receipt())
    hit = guard.reuse(auth("call-b", provider_request_id="next-request"), lambda: None)
    assert hit is not None and hit.result == RESULT
    assert hit.audit.source_call_id == "call-a"
    assert events == [hit.audit]
    assert hit.audit.attribution == "HOST"
    assert hit.audit.call_id == "call-b" and hit.audit.provider_request_id == "next-request"
    assert not hasattr(events[0], "result")


def test_guard_reference_leaves_redundant_read_to_existing_execution_path():
    events = []
    guard = DuplicateExecutionGuard(AdapterProfile(), {"read_record"}, events.append)
    guard.remember(auth(), receipt())
    assert guard.reuse(auth("call-b"), lambda: None) is None
    assert events == []


@pytest.mark.parametrize("changes", [
    {"read_only": False}, {"reuse_allowed": False}, {"permission": "DENY"},
    {"resource": "record-2"}, {"immutable_revision": "data-v2"}, {"immutable_revision": None},
    {"repeat_intent": "REQUIRED_REPEAT"}, {"repeat_intent": "RECOVERY"},
    {"repeat_intent": "SCOPE_UPDATE"}, {"tool": "release_record"},
    {"scope": Scope("test-run", "test-session", "another-principal", "initial-scope", "executive")},
    {"scope": Scope("test-run", "another-session", "synthetic-principal", "initial-scope", "executive")},
    {"scope": Scope("test-run", "test-session", "synthetic-principal", "new-scope", "executive")},
    {"scope": Scope("test-run", "test-session", "synthetic-principal", "initial-scope", role_id="reviewer")},
])
def test_guard_negative_controls_leave_execution_to_authoritative_host_path(changes):
    events = []
    guard = DuplicateExecutionGuard(profile("duplicate_execution_guard"), {"read_record"}, events.append)
    guard.remember(auth(), receipt())
    assert guard.reuse(auth("call-b", **changes), lambda: None) is None
    assert events == []


def test_guard_does_not_reuse_stale_failed_or_same_call_and_checks_cancel():
    now = [10.0]
    events = []
    guard = DuplicateExecutionGuard(profile("duplicate_execution_guard"), {"read_record"}, events.append,
                                    ttl_seconds=2, clock=lambda: now[0])
    guard.remember(auth(), receipt())
    assert guard.reuse(auth(), lambda: None) is None
    now[0] += 2
    assert guard.reuse(auth("call-b"), lambda: None) is None
    guard.remember(auth(), receipt())
    guard.remember(auth(), receipt(status="FAILED"))
    assert guard.reuse(auth("call-b"), lambda: None) is None
    guard.remember(auth(), receipt())
    cancel = Event()
    cancel.set()

    def checkpoint():
        if cancel.is_set():
            raise GatewayError(ErrorCode.CANCELLED, "cancelled")

    with pytest.raises(GatewayError, match="cancelled"):
        guard.reuse(auth("call-b"), checkpoint)
    assert events == []


def test_guard_never_returns_a_hit_if_the_audit_sink_fails():
    def broken_audit(_):
        raise OSError("audit unavailable")

    guard = DuplicateExecutionGuard(profile("duplicate_execution_guard"), {"read_record"}, broken_audit)
    guard.remember(auth(), receipt())
    with pytest.raises(OSError, match="audit"):
        guard.reuse(auth("call-b"), lambda: None)


def test_guard_invalidates_a_candidate_if_a_new_failure_arrives_during_audit():
    def invalidate(_):
        guard.remember(auth(), receipt(status="FAILED"))

    guard = DuplicateExecutionGuard(profile("duplicate_execution_guard"), {"read_record"}, invalidate)
    guard.remember(auth(), receipt())
    assert guard.reuse(auth("call-b"), lambda: None) is None


def test_archived_pilot_replay_uses_independent_reference_and_one_factor_per_arm():
    from benchmarks.slm10.sdk_adapter_qualification import archived_request_controls

    result = archived_request_controls()
    assert result["formal_trial_attribution"] == 0
    assert result["status"] == "PASS"
    assert {row["candidate"] for row in result["comparisons"]} == {"A", "B", "D"}
    assert {row["component"] for row in result["comparisons"]} == {
        "prompt_compiler", "compact_result_codec", "action_state",
    }
    for row in result["comparisons"]:
        assert row["status"] == "PASS"
        assert row["portable_source_sha256"] == row["reference_request_sha256"]


def terminal(**changes):
    fields = dict(finish_reason="stop", unresolved_calls=0, proposed_calls=0, model_calls=1, tool_calls=1,
                  max_model_calls=4, max_tool_calls=4, cancelled=False, deadline_exceeded=False,
                  authority_pending=False, workflow_complete=True, transport_complete=True)
    return TerminalContext(**(fields | changes))


def test_termination_requires_existing_complete_host_and_provider_state():
    selected = profile("termination_policy")
    assert termination_decision(selected, terminal()).decision == "ALLOW_FINAL"
    assert termination_decision(AdapterProfile(), terminal()).decision == "DEFER"
    assert termination_decision(selected, terminal(model_calls=4, tool_calls=4)).decision == "ALLOW_FINAL"
    assert termination_decision(selected, terminal(finish_reason="tool_calls", proposed_calls=1)).decision == "CONTINUE"


@pytest.mark.parametrize("changes", [
    {"cancelled": True}, {"deadline_exceeded": True}, {"authority_pending": True},
    {"workflow_complete": False}, {"transport_complete": False}, {"finish_reason": "length"},
    {"unresolved_calls": 1}, {"proposed_calls": 1}, {"model_calls": 5},
    {"finish_reason": "tool_calls", "proposed_calls": 1, "model_calls": 4},
])
def test_termination_never_turns_shortcut_or_incomplete_state_into_success(changes):
    assert termination_decision(profile("termination_policy"), terminal(**changes)).decision == "BLOCK"


SCHEMA = {"type": "object", "required": ["status"], "properties": {"status": {"const": "ready"}},
          "additionalProperties": False}


def test_output_contract_validates_exact_json_only_after_existing_terminal_authority():
    selected = profile("structured_output_contract")
    raw = b'{"status":"ready"}'
    assert structured_output(AdapterProfile(), raw, SCHEMA, terminal_allowed=True) is None
    assert structured_output(selected, raw, SCHEMA, terminal_allowed=True) == {"status": "ready"}
    with pytest.raises(GatewayError, match="terminal"):
        structured_output(selected, raw, SCHEMA, terminal_allowed=False)


@pytest.mark.parametrize("raw", [
    b'```json\n{"status":"ready"}\n```', b'{"status":"ready","status":"ready"}',
    b'{"status":"wrong"}', b'{"status":"ready","extra":true}', b'{"status": NaN}', b'[]',
])
def test_output_contract_never_repairs_or_coerces_invalid_output(raw):
    with pytest.raises(GatewayError):
        structured_output(profile("structured_output_contract"), raw, SCHEMA, terminal_allowed=True)
