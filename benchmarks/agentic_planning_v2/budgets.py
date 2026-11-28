"""Resource accounting for trusted runner telemetry, independently per dimension."""
def assess_budgets(plan, limits, *, calls, model_requests=None, retries=None, peak_context_tokens=None):
    measured = {"tool_calls": calls, "model_requests": model_requests, "retries": retries,
                "peak_context_tokens": peak_context_tokens}
    result = {}
    for dimension, observed in measured.items():
        limit = limits.get(dimension)
        if observed is None or limit is None:
            status = "NOT_RUN"
        elif type(observed) is not int or type(limit) is not int or min(observed, limit) < 0:
            status = "FAIL"
        else:
            status = "PASS" if observed <= limit else "FAIL"
        result[dimension] = {"used": observed, "limit": limit, "status": status}
    return {"graph_nodes": len(plan["actions"]),
            "conditional_nodes": sum(node["when"] is not True for node in plan["actions"]),
            "dimensions": result}
