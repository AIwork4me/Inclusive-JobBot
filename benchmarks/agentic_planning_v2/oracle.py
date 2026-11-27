"""Public DAG checks and bounded replay over independently supplied public control worlds.

The host supplies input/output contracts, possible observations and independent
terminal expectations. No model action is dispatched by this verifier.
"""
from benchmarks.tool_calling_v2.oracle import equal
from .types import input_schema, matches

from .contract import ABSENT, UNKNOWN, VALIDATOR, TYPED_VALIDATOR, typed, predicate, references, value


def validate(plan, contract):
    # Bound nesting and input size before recursive JSON Schema evaluation.
    todo = [(plan, 0)]
    count = 0
    while todo:
        item, depth = todo.pop()
        count += 1
        if depth > 32 or count > 8192:
            return ["plan exceeds structural limit"]
        if isinstance(item, (list, dict)):
            if len(item) > 128:
                return ["container exceeds structural limit"]
            todo.extend((child, depth + 1) for child in (item.values() if isinstance(item, dict) else item))
    validator = TYPED_VALIDATOR if typed(contract) else VALIDATOR
    if not validator.is_valid(plan):
        return ["invalid V2 schema"]
    if plan["goal"] != contract["goal"]:
        return ["incorrect public objective"]
    if set(contract["public_fields"]) & {"approval"}:
        return ["approval cannot be supplied as a public fact"]
    fields = {"public": set(contract["public_fields"]), "event": set(contract["event_fields"])}
    errors = []
    nodes = {node["id"]: node for node in plan["actions"]}
    if len(nodes) != len(plan["actions"]) or nodes.keys() & fields.keys():
        return ["duplicate or reserved action ID"]
    for name, node in nodes.items():
        spec = contract["tools"].get(node["tool"])
        if spec is None or set(node["arguments"]) != set(spec["inputs"]):
            return ["unavailable tool or invalid argument keys"]
        schema = input_schema(node["tool"], spec)
        resolved = {key: value(term, {}) for key, term in node["arguments"].items()}
        if all(v is not UNKNOWN and v is not ABSENT for v in resolved.values()) and not matches(resolved, schema):
            errors.append("tool argument type mismatch")
        for key, term in node["arguments"].items():
            if key in {"id", "peer_id", "draft_id", "approval", "audit_ref"} and (
                    not isinstance(term, dict) or not (term.keys() == {"from", "field"} or term.keys() == {"first"})):
                errors.append("identity must be bound to a known fact")
        if node["tool"] == "commit" and node["arguments"].get("approval") != {"from": "event", "field": "approval"}:
            errors.append("commit requires a trusted external grant reference")
        fields[name] = set(spec["outputs"])
    for name, node in nodes.items():
        deps = set(node["depends_on"]) | set(node.get("observes", []))
        if deps - nodes.keys():
            errors.append("undefined dependency")
        for source, field in references([node["when"], *node["arguments"].values()]):
            if field not in fields.get(source, ()) or source not in deps | {"public", "event"}:
                errors.append("unbound reference")
    for source, field in references(plan["stops"]):
        if field not in fields.get(source, ()):
            errors.append("undefined terminal reference")
    pending = set(nodes)
    while pending:
        ready = {name for name in pending if not pending.intersection(nodes[name]["depends_on"] + nodes[name].get("observes", []))}
        if not ready:
            errors.append("cyclic dependencies")
            break
        pending -= ready
    return errors


def next_action(plan, obs, used):
    for node in plan["actions"]:
        if node["id"] in used or not set(node["depends_on"]) <= obs.keys():
            continue
        if predicate(node["when"], obs) is not True:
            continue
        args = {k: value(v, obs) for k, v in node["arguments"].items()}
        if any(v is UNKNOWN or v is ABSENT for v in args.values()):
            continue
        return node, args
    return None


def simulate(plan, contract, world):
    """Replay a bounded public scenario. Only the host can publish events.

    A scope revision invalidates prior results. Every node can fire once,
    including across scope revisions. Retry and recovery require distinct nodes.
    World steps encode permitted calls with exact arguments and trusted replies.
    """
    from .execution import execute

    consumed = set()
    calls = []

    class UnexpectedCall(Exception):
        pass

    def invoke(tool, args):
        match = next((i for i, step in enumerate(world["steps"])
                      if i not in consumed and (tool == step["tool"] or tool in step.get("equivalent_tools", []))
                      and equal(args, step["args"]) and set(step.get("after", range(i))) <= consumed), None)
        if match is None:
            raise UnexpectedCall()
        consumed.add(match)
        step = world["steps"][match]
        data = dict(step["result"])
        reply = {"code": data.pop("code", "ok"), "data": data}
        if "event" in step:
            # This separate fixture field represents the host event channel.
            event = dict(step["event"])
            event.setdefault("source", "synthetic_external_user")
            if tool == "request_confirmation" and "approval" in event:
                data.setdefault("approval", event.pop("approval"))
            reply["external_event"] = event
        return reply

    try:
        result = execute(plan, world["public"], contract["action_budget"], invoke,
                         contract=contract if "tools" in contract else None, on_dispatch=calls.append)
    except UnexpectedCall:
        return {"status": "FAIL", "reason": "unexpected proposed call", "calls": calls}
    final = result["final"]
    passed = (final is not None and final["disposition"] == world["disposition"]
              and len(consumed) == len(world["steps"]) and ("facts" not in world or equal(final["facts"], world["facts"])))
    reason = {"no enabled action": "no enabled transition", "action budget exhausted": "actual call budget"}.get(
        result["reason"], result["reason"])
    return {"status": "PASS" if passed else "FAIL", "reason": reason, "calls": calls}


def verify(plan, contract, worlds):
    errors = validate(plan, contract)
    if errors:
        return {"status": "FAIL", "errors": errors, "worlds": []}
    outcomes = [simulate(plan, contract, world) for world in worlds]
    if not outcomes:
        return {"status": "BLOCKED", "errors": ["no public control worlds"], "worlds": []}
    return {"status": "PASS" if all(r["status"] == "PASS" for r in outcomes) else "FAIL",
            "errors": [], "worlds": outcomes}
