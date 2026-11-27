"""Model-facing V2 planning boundary and offline public control evaluator.

Only an explicitly supplied public contract reaches the request builder. Each
world used for control evaluation is owned by the caller and is never appended
to the prompt. No business handler runs at this boundary.
"""
from copy import deepcopy
import json

from benchmarks.tool_calling_v2.oracle import decode_object
from .contract import SCHEMA, TYPED_SCHEMA, typed
from .oracle import verify


def plan_request(model, task, public, contract, limits, constrained=False, *, goal_track="provided", clarify=False,
                 dynamic_tools=False, zero_actions=False, specialize_arguments=False):
    visible = {"task": task, "public": public, "goal": contract["goal"], "tools": contract["tools"],
               "external_event_fields": contract["event_fields"], "limits": limits,
               "schema": json.loads((TYPED_SCHEMA if typed(contract) else SCHEMA).read_bytes())}
    if goal_track == "inferred":
        del visible["goal"]
        if "goal_options" in contract:
            options = contract["goal_options"]
            if len(set(options)) < 2 or contract["goal"] not in options:
                raise ValueError("the public goal vocabulary must cover multiple objectives")
            visible["goal_options"] = sorted(set(options))
    elif goal_track != "provided":
        raise ValueError("unknown goal track")
    schema = visible["schema"]
    if dynamic_tools:
        names = sorted(contract["tools"])
        if names:
            schema["$defs"]["action"]["properties"]["tool"] = {"enum": names}
        else:
            # The empty public vocabulary permits precisely one action list.
            schema["properties"]["actions"] = {"const": []}
    if specialize_arguments:
        if not dynamic_tools:
            raise ValueError("tool-specific argument keys require a dynamic tool vocabulary")
        if names:
            branches = []
            for name in names:
                action = deepcopy(schema["$defs"]["action"])
                action["properties"]["tool"] = {"const": name}
                keys = list(contract["tools"][name]["inputs"])
                action["properties"]["arguments"] = {"type": "object", "required": keys, "additionalProperties": False,
                                                     "properties": {k: {"$ref": "#/$defs/term"} for k in keys}}
                branches.append(action)
            schema["$defs"]["action"] = {"oneOf": branches}
    if zero_actions and limits["tool_calls"] == 0:
        schema["properties"]["actions"] = {"type": "array", "items": {"$ref": "#/$defs/action"}, "maxItems": 0}
    body = {"model": model, "messages": [
        {"role": "system", "content": (
            "Return a version-2 conditional plan as one JSON object. Use only the public task and tool contracts. "
            "Nodes run at most once. The first ready node in declaration order runs. depends_on requires all "
            "dependencies to have executed. observes declares optional observation sources. Conditions use "
            "three-valued logic. A guard enables an action only when true. first selects the first available "
            "field in order. A scope revision invalidates prior observations. A commit requires an external "
            "approval for the exact draft. Stops are evaluated before each call and must resolve uniquely. "
            "Supply the requested final facts as expressions on each applicable stop.")},
        {"role": "user", "content": json.dumps(visible, ensure_ascii=False, sort_keys=True)}]}
    if clarify:
        body["messages"][0]["content"] += (
            " Express a request for missing information using a clarify stop. "
            "Clarifying can terminate immediately with an empty actions array.")
    if constrained:
        body["response_format"] = {"type": "json_schema", "json_schema": {
            "name": "conditional_plan_v2", "strict": True, "schema": visible["schema"]}}
    return body


def evaluate_raw(raw, contract, public_worlds):
    try:
        plan = decode_object(raw)
    except ValueError as error:
        return {"status": "FAIL", "errors": [str(error)], "worlds": []}
    return verify(plan, contract, public_worlds)
