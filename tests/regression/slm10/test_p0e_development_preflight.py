"""Transport preflights with a scripted provider and zero physical attribution."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from benchmarks.slm10.tc_verification import delivered_result
from test_multitool_stateful_transport import proposal, scripted_provider


def test_preflight_roster_is_candidate_independent_and_uses_same_public_approval_counterfactual():
    from benchmarks.slm10.p0e_development_preflight import control_identity, public_cases, readiness

    cases = public_cases()
    assert set(cases) == {"single", "parallel", "recovery", "scope", "chain12", "draft_confirmed", "draft_declined"}
    assert cases["draft_confirmed"] == cases["draft_declined"]
    confirmed, declined = map(control_identity, ("draft_confirmed", "draft_declined"))
    assert confirmed["public_sha256"] == declined["public_sha256"]
    assert confirmed["world_sha256"] != declined["world_sha256"]
    assert all("-P0E-" in case["case_id"] for case in cases.values())
    assert readiness()["formal_trial_attribution"] == 0
    assert readiness()["radeon_execution"] == "NOT_RUN"
    assert readiness()["eleven_to_twenty_steps"] == "BLOCKED"


def last_reply(body, tool):
    message = body["messages"][-1]
    try:
        return json.loads(message["content"])
    except ValueError:
        return delivered_result(message, {"tool": tool}, "sdk_acting_first")


def terminal(**answer):
    return lambda body: {"content": json.dumps(answer)}


def scripted(control):
    if control == "single":
        return [lambda body: proposal("read_label", reference="label-kestrel"), terminal(label="Paper Archive")]
    if control == "parallel":
        def both(_):
            entry = proposal("read_hours", reference="gallery-finch")
            entry["tool_calls"] += proposal("read_access", reference="gallery-finch")["tool_calls"]
            return entry

        return [both, terminal(hours="13:00–16:00", access="level entry")]
    if control == "recovery":
        return [lambda body: proposal("read_display", reference="display-mint"), lambda body: proposal(
            "read_mirror", reference=last_reply(body, "read_display")["data"]["mirror_ref"]), terminal(code="MINT-7")]
    if control == "scope":
        return [lambda body: proposal("check_assignment", reference="desk-oak"), lambda body: proposal(
            "read_counter", reference=last_reply(body, "check_assignment")["external_event"]["revised_reference"]),
                terminal(counter="Counter C")]
    if control == "chain12":
        def next_link(index):
            def respond(body):
                entry = proposal("read_link", reference=last_reply(body, "read_link")["data"]["next_ref"])
                entry["tool_calls"][0]["id"] += f"-{index}"
                return entry
            return respond

        return [lambda body: proposal("read_link", reference="file-sparrow"),
                *(next_link(index) for index in range(1, 12)), terminal(label="Reference Cabinet Nine")]
    draft = [lambda body: proposal("stage", reference="room-juniper", text="Workshop check-in opens at noon."),
             lambda body: proposal("read_draft", draft_id=last_reply(body, "stage")["data"]["draft_id"]),
             lambda body: proposal("request_confirmation", draft_id=last_reply(body, "read_draft")["data"]["draft_id"])]
    if control == "draft_confirmed":
        draft += [lambda body: proposal("commit", draft_id=last_reply(body, "request_confirmation")["external_event"]["draft_id"],
                                        approval=last_reply(body, "request_confirmation")["external_event"]["approval"]),
                  terminal(outcome="committed")]
    else:
        draft += [terminal(outcome="withheld")]
    return draft


@pytest.mark.parametrize("profile", ["DIRECT_NATIVE", "SDK_MATCHED_CONTEXT", "SDK_NATIVE"])
@pytest.mark.parametrize("control", ["single", "parallel", "recovery", "scope", "chain12", "draft_confirmed", "draft_declined"])
def test_preflight_software_profiles_derive_scoped_facts(tmp_path, profile, control):
    from benchmarks.slm10.p0e_development_preflight import run_control, assess

    harness = None
    if profile.startswith("SDK_"):
        sdk_bin = pytest.importorskip("google.antigravity.bin")
        harness = Path(sdk_bin.__file__).with_name("localharness.exe")
        if not harness.is_file():
            pytest.skip("Antigravity Windows harness unavailable")
    replies = scripted(control)
    with scripted_provider(replies) as (client, requests):
        result = asyncio.run(run_control(client, "software-fixture", control, runtime_profile=profile,
                                        target=tmp_path / "sdk", harness=harness))
    trace = result["trace"]
    assert len(requests) == len(replies)
    assert result["assessment"]["status"] == "PASS", (result["assessment"], trace["failure"],
                                                       [event.get("failure") for event in trace["wire"]])
    assert result["physical_execution"] == "NOT_RUN" and result["formal_trial_attribution"] == 0
    readback = result["state_readback"]
    if control.startswith("draft_"):
        assert readback["status"] == "PASS"
        assert readback["captured_snapshot_sha256"] == readback["reopened_snapshot_sha256"]
    else:
        assert readback == {"status": "NOT_RUN", "applicable": False}
    assert trace["runtime_attribution"]["profile"] == profile
    assert trace["execution_metrics"]["observed_parallel_width"] == (2 if control == "parallel" else 1)
    assert trace["execution_metrics"]["external_updates"] == (1 if control in {"scope", "draft_confirmed", "draft_declined"} else 0)
    if control == "chain12":
        assert trace["execution_metrics"]["actual_action_count"] == trace["execution_metrics"]["observed_sequential_depth"] == 12
    changed = deepcopy(trace)
    changed["answer"] = '{"fabricated":"incorrect"}'
    assert assess(control, changed)["status"] == "FAIL"
