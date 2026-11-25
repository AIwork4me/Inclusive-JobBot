"""Conservative may-reach analysis for mandatory effects in a public contract.

Unknown observations may enable an action. A commit must be reachable in an
approved external state. Infeasibility in this relaxation proves a missing
effect. Feasibility alone does not establish a correct plan.
"""
from .contract import UNKNOWN, predicate


def missing_effects(actions, required, public):
    reachable = set()
    tools = set()
    for _ in range(len(actions)):
        previous = len(reachable)
        for node in actions:
            if node["id"] in reachable or not set(node["depends_on"]) <= reachable:
                continue
            known = {"public": public}
            if node["tool"] == "commit":
                # Only project the known decision. Other fields (including
                # the token) are unknown until a real external grant arrives.
                known["event"] = {"decision": "approved"}
            # With a partial observation, absence is unknown, including exists.
            if may_hold(node["when"], known) is False:
                continue
            reachable.add(node["id"])
            tools.add(node["tool"])
        if len(reachable) == previous:
            break
    return [sorted(group) for group in required if not tools.intersection(group)]


def may_hold(expr, partial):
    """Evaluate on partial objects, using UNKNOWN for unassigned fields."""
    if type(expr) is bool:
        return expr
    op = expr["op"]
    if op in ("and", "or"):
        values = [may_hold(x, partial) for x in expr["args"]]
        decisive = op == "or"
        return decisive if decisive in values else UNKNOWN if UNKNOWN in values else not decisive
    if op == "not":
        result = may_hold(expr["arg"], partial)
        return UNKNOWN if result is UNKNOWN else not result
    if op == "exists":
        key = expr["ref"]
        return True if key["field"] in partial.get(key["from"], {}) else UNKNOWN
    for term in (expr["left"], expr["right"]):
        if isinstance(term, dict) and ("from" not in term or term["field"] not in partial.get(term["from"], {})):
            return UNKNOWN
    return predicate(expr, partial)
