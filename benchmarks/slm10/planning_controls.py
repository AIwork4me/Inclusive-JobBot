"""Validate independently supplied synthetic worlds with the existing Planning V2 machinery."""

from collections import Counter
from copy import deepcopy
import re
import unicodedata

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from benchmarks.agentic_planning_v2.events import scope_changed
from benchmarks.agentic_planning_v2.oracle import verify
from benchmarks.agentic_planning_v2.safety import reconcile
from benchmarks.agentic_planning_v2.types import input_schema, matches
from benchmarks.tool_calling_v2.oracle import equal
from evaluation.aeve.runtime import fingerprint

LEVELS = tuple(f"L{i}" for i in range(8))
LIMITS = {"tool_calls", "model_requests", "retries", "peak_context_tokens"}
PUBLIC_FIELDS = {"case_id", "level", "language", "task", "public", "contract", "limits"}
AUTH_FIELDS = {"source", "scope_changed", "approval", "draft_id", "decision"}
WRITE_TOOLS = {"stage", "commit"}
DENIALS = {"permission_denied", "approval_declined"}
DISPOSITIONS = {"completed", "understood", "clarify", "escalate"}
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")


def normalized_task(task):
    return " ".join(unicodedata.normalize("NFKC", task).casefold().split())


def names(items):
    return (isinstance(items, list) and all(isinstance(item, str) and NAME.fullmatch(item) for item in items)
            and len(items) == len(set(items)))


def validate_schema(schema):
    pending = [schema]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            for key in ("$ref", "$dynamicRef", "$recursiveRef"):
                if key in item and (not isinstance(item[key], str) or not item[key].startswith("#")):
                    raise ValueError("only local JSON Schema references are permitted in Planning tool contracts")
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        raise ValueError("invalid public tool input schema") from error


def validate_public(row, historical):
    if not isinstance(row, dict) or row.keys() != PUBLIC_FIELDS:
        raise ValueError("invalid public case fields")
    case_id, level, task = row["case_id"], row["level"], row["task"]
    if (level not in LEVELS or not isinstance(case_id, str)
            or not re.fullmatch(rf"SLM-AP2-{level}-[A-Za-z0-9_-]{{1,64}}", case_id)
            or row["language"] not in ("en", "zh", "mixed") or not isinstance(task, str) or not task.strip()):
        raise ValueError("invalid independent Planning case identity or language")
    if normalized_task(task) in historical:
        raise ValueError("historical Planning task cannot be imported")
    limits, contract = row["limits"], row["contract"]
    if (not isinstance(limits, dict) or limits.keys() != LIMITS
            or any(type(n) is not int or n < 0 for n in limits.values())
            or limits["model_requests"] < 1 or limits["peak_context_tokens"] < 1):
        raise ValueError("invalid Planning budget")
    contract_fields = {"goal", "tools", "public_fields", "event_fields", "action_budget"}
    if (not isinstance(contract, dict) or not contract_fields <= contract.keys()
            or contract.keys() - contract_fields - {"goal_options"}
            or not isinstance(contract["goal"], str) or not NAME.fullmatch(contract["goal"])
            or not names(contract["public_fields"]) or not names(contract["event_fields"])
            or not isinstance(row["public"], dict) or not row["public"].keys() <= set(contract["public_fields"])
            or "approval" in contract["public_fields"] or type(contract["action_budget"]) is not int
            or contract["action_budget"] != limits["tool_calls"] or not isinstance(contract["tools"], dict)):
        raise ValueError("invalid public Planning V2 contract")
    if "goal_options" in contract and (not names(contract["goal_options"]) or len(contract["goal_options"]) < 2
                                      or contract["goal"] not in contract["goal_options"]):
        raise ValueError("invalid public goal choices")
    if level == "L0" and limits["tool_calls"] != 0:
        raise ValueError("L0 requires a zero-tool budget")
    for tool, spec in contract["tools"].items():
        if (not isinstance(tool, str) or not NAME.fullmatch(tool) or not isinstance(spec, dict)
                or not {"inputs", "outputs"} <= spec.keys()
                or spec.keys() - {"inputs", "outputs", "input_schema", "description"}
                or not names(spec["inputs"]) or not names(spec["outputs"])):
            raise ValueError("invalid public tool contract")
        if "input_schema" in spec:
            validate_schema(spec["input_schema"])


def validate_world(case, world):
    contract = case["contract"]
    if (not isinstance(world, dict) or world.keys() != {"world_id", "steps", "disposition", "facts"}
            or not isinstance(world["world_id"], str) or not NAME.fullmatch(world["world_id"])
            or not isinstance(world["disposition"], str) or world["disposition"] not in DISPOSITIONS
            or not isinstance(world["facts"], dict)
            or not isinstance(world["steps"], list) or len(world["steps"]) > contract["action_budget"]):
        raise ValueError("invalid independent world, terminal facts or step budget")
    tool_specs = contract["tools"]
    has_state = any(isinstance(step, dict) and (step.get("tool") in ("stage", "commit")
                    or {"before", "after_state"} & step.keys()) for step in world["steps"])
    ledger = []
    for index, step in enumerate(world["steps"]):
        if (not isinstance(step, dict) or not {"tool", "args", "result"} <= step.keys()
                or step.keys() - {"tool", "args", "result", "event", "after", "equivalent_tools", "before", "after_state"}
                or not isinstance(step["tool"], str) or step["tool"] not in tool_specs
                or not isinstance(step["result"], dict)
                or not isinstance(step["args"], dict)):
            raise ValueError("invalid independent world step")
        tool = step["tool"]
        result = step["result"]
        if ("code" in result and not isinstance(result["code"], str)) or "external_event" in result:
            raise ValueError("untrusted event or malformed tool result")
        alternatives = step.get("equivalent_tools", [])
        if (not names(alternatives) or tool in alternatives or set(alternatives) & WRITE_TOOLS
                or (tool in WRITE_TOOLS and alternatives)):
            raise ValueError("invalid equivalent independent world tools")
        for name in (tool, *alternatives):
            spec = tool_specs.get(name)
            if (spec is None or step["args"].keys() != set(spec["inputs"])
                    or not matches(step["args"], input_schema(name, spec))
                    or result.keys() - {"code"} - set(spec["outputs"])):
                raise ValueError("independent world exceeds the public tool contract")
        after = step.get("after", list(range(index)))
        if (not isinstance(after, list) or any(type(prereq) is not int or not 0 <= prereq < index for prereq in after)
                or len(after) != len(set(after))):
            raise ValueError("invalid independent world dependencies")
        event = step.get("event")
        if "event" in step and (not isinstance(event, dict) or event.get("source") != "synthetic_external_user"
                                or event.keys() - {"source", "scope_changed"} - set(contract["event_fields"])):
            raise ValueError("world event requires a trusted host event and declared fields")
        if "approval" in result:
            raise ValueError("synthetic approval tokens must come from the independent host event")
        if event and "approval" in event and (tool != "request_confirmation" or event.get("decision") != "approved"
                                              or event.get("draft_id") != step["args"].get("draft_id")
                                              or not isinstance(event["approval"], str) or not event["approval"]):
            raise ValueError("synthetic approval token requires confirmation of the exact draft")
        if has_state:
            ledger.append(write_record(step, event))
    if has_state and reconcile(case["public"], ledger)["status"] != "PASS":
        raise ValueError("independent world fails synthetic authorization or state reconciliation")
    return world | {"public": case["public"]}


def write_record(step, event):
    states = (step.get("before"), step.get("after_state"))
    if any(not isinstance(state, dict) or state.keys() != {"drafts", "deliverables"}
           or any(not isinstance(items, dict) for items in state.values()) for state in states):
        raise ValueError("synthetic write worlds require trusted per-call state snapshots")
    data = dict(step["result"])
    observed = {"code": data.pop("code", "ok"), "data": data}
    if event is not None:
        observed["external_event"] = event
        if step["tool"] == "request_confirmation" and "approval" in event:
            data.setdefault("approval", event["approval"])
    return {"tool": step["tool"], "args": step["args"], "observation": observed,
            "before": states[0], "after": states[1]}


def negative_controls(plan, contract, world):
    counts = Counter()
    for index, step in enumerate(world["steps"]):
        event = step.get("event")
        if scope_changed(event):
            changed = [value for key, value in event.items() if key not in AUTH_FIELDS
                       and not any(equal(value, before) for before in world["public"].values())]
            if not changed or not any(equal(value, arg) for value in changed
                                      for later in world["steps"][index + 1:] for arg in later["args"].values()):
                raise ValueError("scope revision has no verified action on its new value")
            counterfactual = deepcopy(world)
            del counterfactual["steps"][index]["event"]
            if verify(plan, contract, [counterfactual])["status"] != "FAIL":
                raise ValueError("V2 witness accepts a stale scope")
            counts["scope_revision"] += 1
        code = step["result"].get("code", "ok")
        if (code not in DENIALS | {"ok"} and index < len(world["steps"]) - 1
                and world["disposition"] == "completed" and not scope_changed(event)):
            counterfactual = deepcopy(world)
            counterfactual["steps"][index]["result"]["code"] = "ok"
            if verify(plan, contract, [counterfactual])["status"] != "FAIL":
                raise ValueError("V2 witness recovery does not depend on the observed disruption")
            counts["recovery"] += 1
    return counts


def level_features(level, worlds, counterfactuals):
    longest = max(len(world["steps"]) for world in worlds)
    steps = [step for world in worlds for step in world["steps"]]
    denied = any(world["disposition"] == "escalate" and any(
        step["result"].get("code") in DENIALS or (step.get("event") or {}).get("decision") == "declined"
        for step in world["steps"]) for world in worlds)
    approval_denial = any(world["disposition"] == "escalate"
                          and any(step["tool"] == "stage" for step in world["steps"])
                          and any(step["tool"] == "request_confirmation"
                                  and (event := step.get("event", {})).get("decision") == "declined"
                                  and event.get("draft_id") == step["args"].get("draft_id")
                                  for step in world["steps"]) for world in worlds)
    committed = any(step["tool"] == "commit" and step["result"].get("code", "ok") == "ok" for step in steps)
    requirements = {
        "L0": longest == 0,
        "L1": longest == 1,
        "L2": longest == 2 and any(len(world["steps"]) == 2 and world["steps"][1].get("after") == [] for world in worlds),
        "L3": any(any(
            equal(arg, old) for previous in step.get("after", range(i))
            for field, old in world["steps"][previous]["result"].items() if field != "code"
            for arg in step["args"].values())
            for world in worlds for i, step in enumerate(world["steps"])),
        "L4": longest >= 2,
        "L5": bool(counterfactuals or denied),
        "L6": 11 <= longest <= 20 and any(step["tool"] == "stage" for step in steps) and not committed,
        "L7": bool(steps) or all(world["disposition"] == "clarify" for world in worlds),
    }
    if not requirements[level]:
        raise ValueError(f"independent V2 worlds do not substantiate the {level} workload")
    return {"synthetic_commit": committed, "approval_denial": approval_denial}


def validate_control(case, proof):
    if (not isinstance(proof, dict) or proof.keys() != {"case_id", "variant", "witness", "worlds"}
            or proof["case_id"] != case["case_id"] or not isinstance(proof["variant"], str)
            or not NAME.fullmatch(proof["variant"]) or not isinstance(proof["worlds"], list) or not proof["worlds"]):
        raise ValueError("missing or mismatched independent V2 world proof")
    worlds = [validate_world(case, world) for world in proof["worlds"]]
    if len({world["world_id"] for world in worlds}) != len(worlds):
        raise ValueError("repeated independent world identity")
    replay = verify(proof["witness"], case["contract"], worlds)
    if replay["status"] != "PASS":
        raise ValueError("independent V2 witness does not meet the frozen worlds")
    stats = Counter()
    for world in worlds:
        stats.update(negative_controls(proof["witness"], case["contract"], world))
    routes = {fingerprint([(step["tool"], step["args"]) for step in world["steps"]]) for world in worlds}
    return {"variant": proof["variant"], "worlds": len(worlds), "distinct_routes": len(routes),
            "counterfactuals": dict(stats), **level_features(case["level"], worlds, stats)}
