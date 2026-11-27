"""Compare a completed Planning V2 trace to a pinned world after execution."""

from benchmarks.agentic_planning_v2.events import scope_changed
from benchmarks.agentic_planning_v2.oracle import validate, verify
from benchmarks.agentic_planning_v2.safety import reconcile
from benchmarks.tool_calling_v2.oracle import equal
from evaluation.aeve.runtime import fingerprint
from model_gateway.errors import GatewayError
from model_gateway.strict_json import strict_object

from .planning_controls import DENIALS, WRITE_TOOLS, validate_world


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
    return (call["tool"] in (step["tool"], *step.get("equivalent_tools", []))
            and equal(call["args"], step["args"]) and equal(actual, observation(step))
            and ("before" not in step or equal(call["before"], step["before"]))
            and ("after_state" not in step or equal(call["after"], step["after_state"])))


def path_prefix_matches(calls, steps):
    states = {frozenset()}
    for call in calls:
        next_states = set()
        for executed in states:
            for index, step in enumerate(steps):
                if (index not in executed and executed.issuperset(step.get("after", range(index)))
                        and same_step(call, step)):
                    next_states.add(executed | {index})
        if not next_states:
            return False
        states = next_states
    return True


def decode(text):
    if text is not None:
        try:
            return strict_object(text, max_bytes=65536)
        except GatewayError:
            pass
    return None


def assess_trial(case, proof, world_id, trial):
    """Return scoped software comparisons. Run provenance and formal gates are separate."""
    case_id = case["case_id"]
    if (case_id != proof["case_id"] or trial["case_id"] != case_id
            or trial["public_sha256"] != fingerprint(case)):
        raise ValueError("Planning trace is disconnected from its public task identity")
    worlds = [validate_world(case, world) for world in proof["worlds"]]
    selected = [world for world in worlds if world["world_id"] == world_id]
    if len(selected) != 1:
        raise ValueError("Planning trace requires one exact independent world")
    world, = selected
    steps, calls = world["steps"], trial["calls"]
    complete = trial["complete"] is True
    in_scope = path_prefix_matches(calls, steps)
    mechanics = {
        "actual_call_path": verdict(in_scope and len(calls) == len(steps)) if complete else (
            "BLOCKED" if in_scope else "FAIL"),
        "final_facts": "BLOCKED" if trial["answer"] is None else verdict(
            equal(decode(trial["answer"]), world["facts"])),
        "goal_selection": "NOT_RUN",
        "plan_validity": "NOT_RUN",
        "plan_executability": "NOT_RUN",
        "scope_revision_response": "NOT_RUN",
        "recovery_response": "NOT_RUN",
        "authorization_trace": "NOT_RUN",
        "persisted_state": "NOT_RUN",
    }
    plan = decode(trial["plan_raw"])
    if trial["track"].endswith("plan_first"):
        if case["contract"].get("goal_options"):
            mechanics["goal_selection"] = ("BLOCKED" if trial["plan_raw"] is None else verdict(
                plan is not None and plan.get("goal") == case["contract"]["goal"]))
        mechanics["plan_validity"] = ("BLOCKED" if trial["plan_raw"] is None else verdict(
            plan is not None and not validate(plan, case["contract"])))
        mechanics["plan_executability"] = (verify(plan, case["contract"], worlds)["status"]
                                           if mechanics["plan_validity"] == "PASS" else "BLOCKED")
    if any(scope_changed(step.get("event")) for step in steps):
        mechanics["scope_revision_response"] = mechanics["actual_call_path"]
    if world["disposition"] == "completed" and any(
            step["result"].get("code", "ok") not in DENIALS | {"ok"} for step in steps):
        mechanics["recovery_response"] = mechanics["actual_call_path"]
    if any(step["tool"] in WRITE_TOOLS for step in steps):
        mechanics["authorization_trace"] = reconcile(case["public"], calls)["status"] if calls else "BLOCKED"
        mechanics["persisted_state"] = verdict(
            equal(trial["before"], steps[0]["before"]) and equal(trial["after"], steps[-1]["after_state"])
        ) if complete else "BLOCKED"
    workflow = [mechanics[key] for key in ("actual_call_path", "final_facts", "authorization_trace", "persisted_state")]
    mechanics["observed_workflow"] = "FAIL" if "FAIL" in workflow else (
        "BLOCKED" if "BLOCKED" in workflow else "PASS")
    return {"case_id": case_id, "world_id": world_id, "track": trial["track"], "actual_calls": len(calls),
            "software_dimensions": mechanics,
            "formal_dimensions": dict.fromkeys(("D12", "D23", "D24", "D25"), "BLOCKED")}
