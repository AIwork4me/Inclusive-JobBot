"""Offline necessary condition: can the archived initial graph emit the observed calls?

Precondition prose is deliberately relaxed. Success is an upper bound, while an
unmatched prefix is evidence that executing these declared nodes cannot explain
the observed path without replanning. Only prior observations can bind values.
"""
import re

MISSING = object()


def argument(value, observations, policy):
    if not isinstance(value, dict):
        return value
    obs = observations.get(value["from"], {})
    key = value["field"]
    if key.startswith("external_event."):
        return obs.get("external_event", {}).get(key.split(".", 1)[1], MISSING)
    result = obs.get("data", {}).get(key, MISSING)
    if "evaluate" not in value:
        return result
    threshold = re.search(r"(at most|at least|最多|至少)\s*(\d+)", policy)
    if type(result) is not int or value["evaluate"] != "policy_assessment" or not threshold:
        return MISSING
    upper = threshold[1] in ("at most", "最多")
    meets = result <= int(threshold[2]) if upper else result >= int(threshold[2])
    return "meets_policy" if meets else "outside_policy"


def match_prefix(actions, calls, policy):
    # Keep every possible binding when equivalent nodes can produce one call.
    states = [{}]
    for index, call in enumerate(calls):
        successors = []
        for observed in states:
            for node in actions:
                if (node["id"] in observed or node["tool"] != call["tool"]
                        or not observed.keys() >= set(node["depends_on"])):
                    continue
                args = {k: argument(v, observed, policy) for k, v in node["arguments"].items()}
                if args == call["args"]:
                    successors.append({**observed, node["id"]: call["observation"]})
        if not successors:
            return index
        states = successors
    return len(calls)
