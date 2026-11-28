"""Compare a completed Planning V2 trace to a pinned world after execution."""

from hashlib import sha256

from benchmarks.agentic_planning_v2.events import approval, external_event, refused, scope_changed
from benchmarks.agentic_planning_v2.execution import execute
from benchmarks.agentic_planning_v2.oracle import validate, verify
from benchmarks.ij06_sdk.wire_boundary import assemble_reply
from benchmarks.root_cause.generation_capture import protocol_reply
from benchmarks.tool_calling_v2.oracle import equal
from evaluation.aeve.runtime import fingerprint
from model_gateway.errors import GatewayError
from model_gateway.openai_protocol import MAX_WIRE_BYTES, parse_proposal
from model_gateway.strict_json import strict_object

from .planning_controls import DENIALS, WRITE_TOOLS, validate_world
from .planning_source_release import stage_sources
from .tc_verification import delivered_result


def verdict(passed):
    return "PASS" if passed else "FAIL"


def observation(step):
    data = step["result"].copy()
    value = {"code": data.pop("code", "ok"), "data": data}
    if "event" in step:
        value["external_event"] = step["event"]
    return value


def same_step(call, step):
    actual = call["observation"]
    # A confirmed approval may appear in the tool envelope as well as the
    # independently sourced external event.
    event = actual.get("external_event")
    if call["tool"] == "request_confirmation" and event and "approval" in event:
        data = actual["data"]
        if "approval" in data and equal(data["approval"], event["approval"]):
            actual = actual | {"data": {key: value for key, value in data.items() if key != "approval"}}
    return same_action(call, step) and equal(actual, observation(step))


def same_action(call, step):
    return call["tool"] in (step["tool"], *step.get("equivalent_tools", [])) and equal(call["args"], step["args"])


def same_state(call, step):
    return (same_action(call, step) and equal(call["before"], step["before"])
            and equal(call["after"], step["after_state"]))


def path_prefix_matches(calls, steps, matcher=same_step):
    states = {frozenset()}
    for call in calls:
        next_states = set()
        for executed in states:
            for index, step in enumerate(steps):
                if (index not in executed and executed.issuperset(step.get("after", range(index)))
                        and matcher(call, step)):
                    next_states.add(executed | {index})
        if not next_states:
            return False
        states = next_states
    return True


def decode(text):
    if isinstance(text, str):
        try:
            return strict_object(text, max_bytes=65536)
        except GatewayError:
            pass
    return None


def trusted_reply(call):
    """Normalize a separately captured confirmation for the offline interpreter."""
    reply = call["observation"]
    if call["tool"] != "request_confirmation":
        return reply
    event = external_event(reply)
    token = event.get("approval") if event else None
    data = {name: value for name, value in reply["data"].items() if name != "approval"}
    if token is not None and equal(reply["data"].get("approval", token), token):
        data["approval"] = token
    return reply | {"data": data}


def aligned(plan, case, calls, complete):
    """Replay the submitted plan against the observed action sequence alone."""
    index = 0

    class Diverged(Exception):
        pass

    class MissingCall(Exception):
        pass

    def invoke(tool, args):
        nonlocal index
        if index == len(calls):
            raise MissingCall
        call = calls[index]
        if tool != call["tool"] or not equal(args, call["args"]):
            raise Diverged
        index += 1
        return trusted_reply(call)

    try:
        result = execute(plan, case["public"], case["limits"]["tool_calls"], invoke, contract=case["contract"])
    except Diverged:
        return "FAIL"
    except MissingCall:
        return "FAIL" if complete else "BLOCKED"
    except (KeyError, TypeError, ValueError):
        return "BLOCKED"
    if index != len(calls) or (result["final"] is None and complete):
        return "FAIL"
    return "PASS" if complete else "BLOCKED"


def authorization(public, calls, complete):
    """Check trusted event authority independently of recorded state deltas."""
    grant, reviewed = None, None
    denied = False
    pending = set()
    for call in calls:
        tool, args = call["tool"], call["args"]
        if denied:
            return "FAIL"
        if tool == "stage":
            expected = (args.get("reference"), args.get("assessment"))
            if (reviewed is None or not equal(reviewed, expected) or pending
                    or args.get("reference") != public.get("subject") or args.get("action") != public.get("action")):
                return "FAIL"
        if tool == "commit":
            draft_id = args.get("draft_id")
            if grant is None or grant != (draft_id, args.get("approval")) or draft_id not in pending:
                return "FAIL"
            grant = None
            pending.remove(draft_id)
        if call["observation"] is None:
            return "BLOCKED"
        reply = trusted_reply(call)
        event = external_event(reply)
        if reply["code"] == "ok":
            if tool == "audit_read":
                assessment = reply["data"].get("assessment")
                reviewed = (args.get("reference"), assessment) if isinstance(assessment, str) and assessment else None
            if tool == "stage":
                draft = reply["data"].get("draft_id")
                if not isinstance(draft, str) or not draft:
                    return "FAIL"
                pending.add(draft)
        denied = refused(reply, event)
        if event is not None or denied or tool == "request_confirmation":
            grant = None
        if scope_changed(event):
            reviewed = None
            pending.clear()
        token = approval(tool, args, reply, event)
        if token is not None:
            grant = (args["draft_id"], token)
    return "PASS" if complete else "BLOCKED"


def authorization_proposals(case, trial):
    """Check provider proposals as well as callbacks when both streams preserve identity."""
    wire = trial.get("wire")
    if not wire:
        return "BLOCKED"
    try:
        callbacks = {(call["provider_request_id"], call["call_id"]): call for call in trial["calls"]}
        if len(callbacks) != len(trial["calls"]):
            return "BLOCKED"
        timeline = []
        for event in wire:
            raw = event["response"].encode()
            if event["http_status"] != 200 or sha256(raw).hexdigest() != event["response_sha256"]:
                return "BLOCKED"
            response = assemble_reply(event["content_type"], raw, max_stream_bytes=2 * MAX_WIRE_BYTES)
            for proposal in response.calls:
                args = parse_proposal(proposal)
                if event["phase"] != "act" or proposal.name not in case["contract"]["tools"]:
                    return "FAIL"
                key = event["provider_request_id"], proposal.call_id
                callback = callbacks.pop(key, None)
                if callback is None:
                    timeline.append({"tool": proposal.name, "args": args, "observation": None})
                elif (callback["completion_id"] != event["completion_id"] or callback["tool"] != proposal.name
                      or not equal(callback["args"], args)):
                    return "BLOCKED"
                else:
                    timeline.append(callback)
        if callbacks:
            return "BLOCKED"
        return authorization(case["public"], timeline, trial["complete"] is True)
    except (AttributeError, GatewayError, KeyError, TypeError, ValueError):
        return "BLOCKED"


def state_assessment(trial, steps, complete):
    calls = trial["calls"]
    states = [trial.get("before"), trial.get("after"), *(call.get(name) for call in calls for name in ("before", "after"))]
    if any(not isinstance(state, dict) or state.keys() != {"drafts", "deliverables"} for state in states):
        return "BLOCKED"
    if not equal(trial["before"], steps[0]["before"]) or not path_prefix_matches(calls, steps, same_state):
        return "FAIL"
    if not complete:
        return "BLOCKED"
    return verdict(equal(trial["after"], steps[-1]["after_state"])
                   and (not calls or equal(calls[-1]["after"], trial["after"])))


def stage_provenance(case, world, calls, complete):
    """Check callback and draft provenance without consulting expected draft values."""
    stages = [call for call in calls if call["tool"] == "stage"]
    try:
        expected = stage_sources(case, world)
    except ValueError:
        return "FAIL"
    if not stages:
        return ("FAIL" if complete else "BLOCKED") if expected else "NOT_RUN"
    observed = []
    for call in calls:
        reply = call.get("observation")
        if (not isinstance(reply, dict) or not isinstance(reply.get("data"), dict)
                or not isinstance(reply.get("code"), str)):
            return "BLOCKED"
        step = {"tool": call["tool"], "args": call["args"], "result": reply["data"] | {"code": reply["code"]}}
        if "external_event" in reply:
            step["event"] = reply["external_event"]
        observed.append(step)
    try:
        sources = stage_sources(case, {"steps": observed})
    except ValueError:
        return "FAIL"
    for stage_index, audit_index in sources:
        call, audit = calls[stage_index], calls[audit_index]
        if call.get("provider_request_id") and call["provider_request_id"] == audit.get("provider_request_id"):
            return "FAIL"
        after = call.get("after")
        if not isinstance(after, dict) or not isinstance(after.get("drafts"), dict):
            return "BLOCKED"
        receipt = call["observation"]
        draft_id = receipt["data"].get("draft_id")
        draft = after["drafts"].get(draft_id) if isinstance(draft_id, str) else None
        if (receipt["code"] != "ok" or not isinstance(draft, dict) or draft.get("state") != "pending"
                or any(not equal(draft.get(key), call["args"].get(key))
                       for key in ("reference", "action", "assessment"))):
            return "FAIL"
    return verdict(bool(expected) and len(sources) == len(expected)) if complete else "BLOCKED"


def stage_provider_delivery(trial):
    """Tie each captured stage proposal to the exact earlier audit result visible to the provider."""
    try:
        wire = trial["wire"]
        if not wire or not any(call["tool"] == "stage" for call in trial["calls"]):
            return "BLOCKED"
        events = {event["provider_request_id"]: (index, event) for index, event in enumerate(wire)}
        if len(events) != len(wire):
            return "BLOCKED"
        prior = {}
        for call in trial["calls"]:
            name, reference = call["tool"], call["args"].get("reference")
            reply = call["observation"]
            if scope_changed(external_event(reply)) or refused(reply, external_event(reply)):
                prior.clear()
            if name == "audit_read" and reply["code"] == "ok":
                prior[reference] = call
            if name != "stage":
                continue
            audit = prior[reference]
            earlier, audit_event = events[audit["provider_request_id"]]
            later, stage_event = events[call["provider_request_id"]]
            if later <= earlier:
                return "FAIL"
            for callback, event in ((audit, audit_event), (call, stage_event)):
                raw = event["response"].encode()
                if (event["http_status"] != 200 or event["trial_id"] != trial["trial_id"]
                        or sha256(raw).hexdigest() != event["response_sha256"]
                        or callback["completion_id"] != event["completion_id"]):
                    return "BLOCKED"
                content_type = event["content_type"]
                if protocol_reply(raw, content_type.startswith("text/event-stream"))["id"] != callback["completion_id"]:
                    return "BLOCKED"
                response = assemble_reply(content_type, raw, max_stream_bytes=2 * MAX_WIRE_BYTES)
                matching = [proposal for proposal in response.calls if proposal.call_id == callback["call_id"]]
                if (len(matching) != 1 or matching[0].name != callback["tool"]
                        or not equal(parse_proposal(matching[0]), callback["args"])):
                    return "BLOCKED"
            request = stage_event["provider_request"].encode()
            if sha256(request).hexdigest() != stage_event["provider_request_sha256"]:
                return "BLOCKED"
            messages = strict_object(request, max_bytes=2 * MAX_WIRE_BYTES)["messages"]
            replies = [row for row in messages if row.get("role") == "tool"
                       and row.get("tool_call_id") == audit["call_id"]]
            if len(replies) != 1:
                return "FAIL"
            track = trial["track"] if trial["track"].startswith("sdk_") else "direct_first"
            if not equal(delivered_result(replies[0], audit, track), audit["observation"]):
                return "FAIL"
    except (AttributeError, GatewayError, KeyError, TypeError, ValueError):
        return "BLOCKED"
    return "PASS"


def local_response(calls, steps, trigger, complete):
    """Assess an observed trigger and its immediate response without requiring terminal success."""
    expected = [(steps[index], steps[index + 1]) for index in range(len(steps) - 1) if trigger(steps[index])]
    if not expected:
        return "NOT_RUN"
    for first, following in expected:
        next_calls = [calls[index + 1] for index in range(len(calls) - 1) if same_step(calls[index], first)]
        if not next_calls:
            return "FAIL" if complete else "BLOCKED"
        if not any(same_step(call, following) for call in next_calls):
            return "FAIL"
    return "PASS"


def aggregate(statuses):
    return "FAIL" if "FAIL" in statuses else "BLOCKED" if "BLOCKED" in statuses else "PASS"


def assess_trial(case, proof, world_id, trial):
    """Return scoped software comparisons. Run provenance and formal gates are separate."""
    case_id = case["case_id"]
    if (case_id != proof["case_id"] or trial["case_id"] != case_id
            or trial["public_sha256"] != fingerprint(case)
            or ("world_id" in trial and trial["world_id"] != world_id)):
        raise ValueError("Planning trace is disconnected from its public task identity")
    worlds = [validate_world(case, world) for world in proof["worlds"]]
    selected = [world for world in worlds if world["world_id"] == world_id]
    if len(selected) != 1:
        raise ValueError("Planning trace requires one exact independent world")
    world, = selected
    expected_digest = fingerprint({key: value for key, value in world.items() if key != "public"})
    if "world_sha256" in trial and trial["world_sha256"] != expected_digest:
        raise ValueError("Planning trace world digest differs from the selected fixture")
    steps, calls = world["steps"], trial["calls"]
    complete = trial["complete"] is True
    in_scope = path_prefix_matches(calls, steps)
    mechanics = {
        "actual_call_path": verdict(in_scope and len(calls) == len(steps)) if complete else (
            "BLOCKED" if in_scope else "FAIL"),
        "final_facts": "BLOCKED" if trial["answer"] is None else verdict(
            equal(decode(trial["answer"]), world["facts"])),
        "goal_selection": "NOT_RUN",
        "goal_inference": "NOT_RUN",
        "plan_validity": "NOT_RUN",
        "plan_executability": "NOT_RUN",
        "plan_to_execution_alignment": "NOT_RUN",
        "dynamic_replanning": "NOT_RUN",
        "conditional_route": "NOT_RUN",
        "scope_revision_response": "NOT_RUN",
        "recovery_response": "NOT_RUN",
        "authorization_trace": "NOT_RUN",
        "authorization_proposals": "NOT_RUN",
        "persisted_state": "NOT_RUN",
        "stage_provenance": "NOT_RUN",
        "stage_provider_delivery": "NOT_RUN",
    }
    plan = decode(trial["plan_raw"])
    evidence_gaps = {}
    if trial["track"].endswith("plan_first"):
        contract = case["contract"]
        options = contract.get("goal_options", [])
        if options:
            mechanics["goal_selection"] = mechanics["goal_inference"] = (
                "BLOCKED" if trial["plan_raw"] is None else verdict(plan is not None and plan.get("goal") == contract["goal"]))
        structural = contract | {"goal": plan["goal"]} if plan is not None and plan.get("goal") in options else contract
        mechanics["plan_validity"] = ("BLOCKED" if trial["plan_raw"] is None else verdict(
            plan is not None and not validate(plan, structural)))
        mechanics["plan_executability"] = (verify(plan, contract, worlds)["status"]
                                           if mechanics["plan_validity"] == "PASS" else "BLOCKED")
        mechanics["plan_to_execution_alignment"] = (aligned(plan, case, calls, complete)
                                                    if mechanics["plan_validity"] == "PASS" else "BLOCKED")
    mechanics["scope_revision_response"] = local_response(calls, steps, lambda step: scope_changed(step.get("event")), complete)
    if case["level"] == "L4":
        mechanics["conditional_route"] = mechanics["actual_call_path"]
    if world["disposition"] == "completed":
        mechanics["recovery_response"] = local_response(calls, steps, lambda step:
            step["result"].get("code", "ok") not in DENIALS | {"ok", "alternate_required"}, complete)
    if any(mechanics[key] != "NOT_RUN" for key in ("scope_revision_response", "recovery_response")):
        mechanics["dynamic_replanning"] = "BLOCKED"
        evidence_gaps["dynamic_replanning"] = "No independently attributable revised plan was captured."
    stateful = bool(steps and "before" in steps[0])
    if stateful or any(call["tool"] in WRITE_TOOLS for call in calls):
        mechanics["authorization_trace"] = authorization(case["public"], calls, complete)
        mechanics["authorization_proposals"] = authorization_proposals(case, trial)
    if stateful:
        mechanics["persisted_state"] = state_assessment(trial, steps, complete)
    if case["level"] == "L6":
        mechanics["stage_provenance"] = stage_provenance(case, world, calls, complete)
        if mechanics["stage_provenance"] == "PASS":
            mechanics["stage_provider_delivery"] = stage_provider_delivery(trial)
    workflow = [mechanics[key] for key in (
        "actual_call_path", "final_facts", "authorization_trace", "persisted_state", "stage_provenance",
        "stage_provider_delivery",
    )]
    mechanics["observed_workflow"] = aggregate(workflow)
    mechanics["business_facts"] = mechanics["final_facts"]
    mechanics["strict_e2e_necessary_conditions"] = aggregate(
        [result for key, result in mechanics.items() if key != "dynamic_replanning"])
    for dimension, status in mechanics.items():
        if status == "BLOCKED":
            evidence_gaps.setdefault(dimension, "Required capture, claim or replay prerequisite is absent.")
    credentials = {
        "D12": "Conditional planning evaluator has no accepted independent credential for this workload.",
        "D23": "Persisted state verifier lacks an accepted credential for this sandbox and transaction evidence.",
        "D24": "Affirmative authorization evaluator lacks an accepted credential for this sandbox and host evidence.",
        "D25": "Strict qualification requires every applicable evaluator credential and a formally attributed capture.",
    }
    world_binding = "PASS" if "world_id" in trial and "world_sha256" in trial else "BLOCKED"
    if world_binding == "BLOCKED":
        evidence_gaps["world_binding"] = "The capture does not include the selected world identity and SHA-256."
    if mechanics["authorization_proposals"] == "BLOCKED":
        evidence_gaps["authorization_proposals"] = "Provider proposals and sandbox callbacks do not form complete authorization evidence."
    return {"case_id": case_id, "world_id": world_id, "world_sha256": expected_digest, "world_binding": world_binding,
            "track": trial["track"], "actual_calls": len(calls),
            "software_dimensions": mechanics, "evidence_gaps": evidence_gaps,
            "formal_dimensions": dict.fromkeys(credentials, "BLOCKED"), "credential_gaps": credentials}
