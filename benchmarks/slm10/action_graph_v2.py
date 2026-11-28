"""Source-linked action-instance matching for independent workflow suites."""

from collections import Counter
from hashlib import sha256

from jsonschema import Draft202012Validator

from benchmarks.tool_calling_v2.oracle import decode_object, equal
from evaluation.aeve.runtime import canonical


def block(reason):
    return {"status": "BLOCKED", "reason": reason, "mapped": []}


def replay(graph, evidence):
    """Match a complete capture to a bounded executable graph with typed evidence."""
    if not isinstance(evidence, dict) or not isinstance(evidence.get("calls"), list):
        return block("MISSING_TRACE")
    calls = evidence["calls"]
    if not evidence.get("complete"):
        return block("INCOMPLETE_TRACE")
    nodes = {node["action_id"]: node for node in graph["actions"]}
    if len(nodes) != len(graph["actions"]) or len(nodes) > 20:
        raise ValueError("graph identity or size differs from the verifier contract")
    edges = {name: set(node["depends_on"]) for name, node in nodes.items()}
    if any(name in deps or deps - nodes.keys() for name, deps in edges.items()):
        raise ValueError("invalid action dependencies")
    waiting = set(nodes)
    while waiting:
        ready = {name for name in waiting if not waiting.intersection(edges[name])}
        if not ready:
            raise ValueError("dependency graph contains a cycle")
        waiting -= ready
    if len(calls) > 24:
        return {"status": "FAIL", "reason": "EXECUTION_BUDGET", "mapped": []}
    required = {"call_id", "completion_id", "turn", "tool", "arguments_raw", "observation", "observation_sources"}
    if any(required - call.keys() for call in calls):
        return block("MISSING_ACTION_PROVENANCE")
    if any(type(call["turn"]) is not int or call["turn"] < 0
           or not isinstance(call["observation_sources"], dict) for call in calls):
        return block("MALFORMED_ACTION_PROVENANCE")
    if any(not isinstance(call[k], str) or not call[k] for k in ("call_id", "completion_id") for call in calls):
        return block("MALFORMED_ACTION_IDENTITY")
    if len({call["call_id"] for call in calls}) != len(calls):
        return {"status": "FAIL", "reason": "REUSED_CALL_ID", "mapped": []}
    if Counter(call["tool"] for call in calls) != Counter(node["tool"] for node in nodes.values()):
        return {"status": "FAIL", "reason": "ACTION_MULTIPLICITY", "mapped": []}
    ordered = sorted(calls, key=lambda call: call["turn"])
    raw_arguments = {}
    for call in ordered:
        try:
            args = decode_object(call["arguments_raw"])
        except ValueError:
            return {"status": "FAIL", "reason": "ARGUMENT_JSON", "mapped": []}
        if not Draft202012Validator(graph["schemas"][call["tool"]]).is_valid(args):
            return {"status": "FAIL", "reason": "ARGUMENT_SCHEMA", "mapped": []}
        raw_arguments[call["call_id"]] = args

    work = 0
    visited = set()

    def match(index, bindings):
        nonlocal work
        work += 1
        if work > 20000:
            return None
        if index == len(ordered):
            return bindings
        key = index, tuple(sorted((name, value["call_id"]) for name, value in bindings.items()))
        if key in visited:
            return None
        visited.add(key)
        call = ordered[index]
        for name, node in nodes.items():
            if name in bindings or call["tool"] != node["tool"] or edges[name] - bindings.keys():
                continue
            if any(bindings[parent]["turn"] >= call["turn"] for parent in edges[name]):
                continue
            if not equal(raw_arguments[call["call_id"]], node["arguments"]) or not equal(
                    call["observation"], node["observation"]):
                continue
            links = {}
            for argument, spec in node.get("input_sources", {}).items():
                parent, observation_key = spec
                if parent not in edges[name]:
                    raise ValueError("input source is not an explicit dependency")
                original = bindings[parent]
                if observation_key not in original["observation"] or not equal(
                        original["observation"][observation_key], node["arguments"].get(argument)):
                    break
                links[argument] = {"action_id": parent, "call_id": original["call_id"], "key": observation_key}
            else:
                if call["observation_sources"] == links:
                    result = match(index + 1, bindings | {name: call})
                    if result is not None:
                        return result
        return None

    bindings = match(0, {})
    if bindings is None:
        if work > 20000:
            return block("AMBIGUOUS_WITHIN_SEARCH_BOUND")
        return {"status": "FAIL", "reason": "NO_PROVEN_GRAPH_EMBEDDING", "mapped": []}
    return {"status": "PASS", "reason": "SCOPED_ACTION_GRAPH_MATCH",
            "mapped": [{"action_id": name, "call_id": call["call_id"], "completion_id": call["completion_id"],
                        "arguments_sha256": sha256(canonical(nodes[name]["arguments"])).hexdigest(),
                        "arguments_raw_sha256": sha256(call["arguments_raw"].encode()).hexdigest(),
                        "observation_sha256": sha256(canonical(call["observation"])).hexdigest(),
                        "observation_sources": call["observation_sources"], "depends_on": nodes[name]["depends_on"]}
                       for name, call in bindings.items()]}
