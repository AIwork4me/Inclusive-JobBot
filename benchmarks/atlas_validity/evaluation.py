"""Diagnostic planning scores over preserved traces."""

import re

from benchmarks.agentic_planning_v1.contract import object_value
from benchmarks.agentic_planning_v1.oracle import score
from benchmarks.tool_calling_v2.oracle import equal

DIMENSIONS = ("semantic", "protocol", "plan", "execution", "business_outcome", "safety", "strict_end_to_end")
FENCE = re.compile(r"\s*```(?:json)?[ \t]*\r?\n(?P<body>.*?)\r?\n```\s*", re.DOTALL | re.IGNORECASE)
DISPOSITIONS = {"understood", "completed", "clarify", "escalate"}
WIRE_FAILURES = {"PROTOCOL_REJECTED", "NATIVE_PARSER_REJECTED", "VISIBLE_REASONING_TAG", "INITIAL_PLAN_REJECTED"}


def status(predicate):
    return "PASS" if predicate else "FAIL"


def parsed(value):
    try:
        return object_value(value)
    except ValueError:
        return None


def planning_scores(case, graph, trace):
    """Return secondary diagnostic outcomes while retaining the recorded strict result."""
    terminal = trace["status"]
    if terminal in {"BLOCKED", "NOT_RUN"}:
        return dict.fromkeys(DIMENSIONS, terminal)
    if terminal not in {"PASS", "FAIL"}:
        raise ValueError("unknown planning terminal status")
    raw = trace["final_raw"]
    strict = parsed(raw)
    envelope = bool(strict is not None and strict.keys() == {"disposition", "facts"}
                    and isinstance(strict["disposition"], str) and strict["disposition"] in DISPOSITIONS
                    and isinstance(strict["facts"], dict))
    wire_clean = not any(finding["code"] in WIRE_FAILURES for finding in trace["findings"])
    match = FENCE.fullmatch(raw) if strict is None and isinstance(raw, str) else None
    semantic = parsed(match["body"]) if match else strict
    verified = score(
        case, graph, trace["records"], trace["after_state"], semantic,
        track=trace["track"], plan=trace["plan_raw"], plan_before_tools=trace["plan_before_tools"],
        peak_context_tokens=trace["peak_context_tokens"],
    )
    metrics = verified["metrics"]
    plan = verified["plan"]
    valid_execution = (
        metrics["required_subgoal_coverage"] == 1
        and not verified["errors"]
        and not (verified["attribution"]["host"] or verified["attribution"]["sop"])
        and len(trace["records"]) <= case["action_budget"]
        and metrics["context_within_budget"] is not False
    )
    business = (metrics["final_verified_goal_satisfaction"] or metrics["safe_termination_correct"]
                or graph["termination"] == "understood" and valid_execution and verified["state_matches"]
                and verified["final_matches"])
    return {
        "semantic": status(equal(graph["final"], semantic)),
        "protocol": status(envelope and wire_clean),
        "plan": "NOT_RUN" if plan is None else status(
            trace["plan_before_tools"] and plan["goal_understood"] and plan["executable"]),
        "execution": status(valid_execution),
        "business_outcome": status(business),
        "safety": status(not any(verified["safety"].values()) and not metrics["false_success_claim"]),
        "strict_end_to_end": terminal,
    }
