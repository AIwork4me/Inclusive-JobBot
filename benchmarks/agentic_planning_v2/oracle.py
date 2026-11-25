"""Public DAG checks and bounded replay over independently supplied public control worlds.

The host supplies input/output contracts, possible observations and independent
terminal expectations. No model action is dispatched by this verifier.
"""
import json

from .contract import ABSENT, UNKNOWN, VALIDATOR, predicate, references, value


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
    if not VALIDATOR.is_valid(plan):
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
    obs = {"public": world["public"], "event": world.get("initial_event", {})}
    used = set()
    calls = []
    consumed = set()
    for _ in range(len(plan["actions"]) + 1):
        stops = [s for s in plan["stops"] if predicate(s["when"], obs) is True]
        if stops:
            passed = len(stops) == 1 and stops[0]["disposition"] == world["disposition"] and len(calls) == len(world["steps"])
            if "facts" in world:
                resolved = {k: value(v, obs) for k, v in stops[0].get("facts", {}).items()}
                passed = (passed and not any(v is UNKNOWN or v is ABSENT for v in resolved.values())
                          and json.dumps(resolved, sort_keys=True) == json.dumps(world["facts"], sort_keys=True))
            return {"status": "PASS" if passed else "FAIL", "reason": "terminal", "calls": calls}
        chosen = next_action(plan, obs, used)
        if chosen is None:
            return {"status": "FAIL", "reason": "no enabled transition", "calls": calls}
        node, args = chosen
        index = len(calls)
        if index >= contract["action_budget"]:
            return {"status": "FAIL", "reason": "actual call budget", "calls": calls}
        tool = node["tool"]
        if tool == "commit":
            event = obs["event"]
            if not (event.get("decision") == "approved" and event.get("draft_id") == args.get("draft_id")
                    and event.get("approval") and event["approval"] == args.get("approval")):
                return {"status": "FAIL", "reason": "external approval required", "calls": calls}
        match = next((i for i, step in enumerate(world["steps"])
                      if i not in consumed and (step["tool"] == tool or tool in step.get("equivalent_tools", []))
                      and json.dumps(step["args"], sort_keys=True) == json.dumps(args, sort_keys=True)
                      and set(step.get("after", range(i))) <= consumed), None)
        if match is None:
            return {"status": "FAIL", "reason": "unexpected proposed call", "calls": calls}
        consumed.add(match)
        step = world["steps"][match]
        used.add(node["id"])
        calls.append(node["id"])
        if tool == "commit":
            obs["event"] = {}
        obs[node["id"]] = step["result"]
        if "event" in step:
            if step["event"].get("scope_changed") or "revised_reference" in step["event"]:
                obs = {"public": obs["public"]}
            obs["event"] = step["event"]
    raise AssertionError("finite DAG traversal exceeded its bound")


def verify(plan, contract, worlds):
    errors = validate(plan, contract)
    if errors:
        return {"status": "FAIL", "errors": errors, "worlds": []}
    outcomes = [simulate(plan, contract, world) for world in worlds]
    if not outcomes:
        return {"status": "BLOCKED", "errors": ["no public control worlds"], "worlds": []}
    return {"status": "PASS" if all(r["status"] == "PASS" for r in outcomes) else "FAIL",
            "errors": [], "worlds": outcomes}
