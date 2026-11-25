"""Model-facing V2 planning boundary and offline public control evaluator.

Only an explicitly supplied public contract reaches the request builder. Each
world used for control evaluation is owned by the caller and is never appended
to the prompt. No business handler runs at this boundary.
"""
import json

from benchmarks.tool_calling_v2.oracle import decode_object
from .contract import SCHEMA
from .oracle import verify


def plan_request(model, task, public, contract, limits, constrained=False):
    visible = {"task": task, "public": public, "goal": contract["goal"], "tools": contract["tools"],
               "external_event_fields": contract["event_fields"], "limits": limits,
               "schema": json.loads(SCHEMA.read_bytes())}
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
