"""Diagnostic planning scores over preserved traces."""

import re

from benchmarks.agentic_planning_v1.contract import object_value
from benchmarks.agentic_planning_v1.oracle import score
from benchmarks.agentic_planning_v1.runner import PLAN_FIELDS
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

def planning_scores_v2(case, graph, trace):
    """Separate applicability and protocol stages for planning diagnostics.

    Semantics and business facts still use the frozen planning oracle.
    """
    legacy = planning_scores(case, graph, trace)
    plan_track = trace["track"] == "P"
    tools_apply = bool(graph["required_subgoals"])
    goal_apply = plan_track or case["level"] == "L0"
    terminal = trace["status"]
    plan = parsed(trace.get("plan_raw"))
    final_raw = trace.get("final_raw")
    final = parsed(final_raw)
    final_ok = (final is not None and final.keys() == {"disposition", "facts"}
                and isinstance(final["disposition"], str) and final["disposition"] in DISPOSITIONS
                and isinstance(final["facts"], dict))
    goal_score = legacy["semantic"]
    if plan_track and terminal in {"PASS", "FAIL"}:
        goal_score = status(plan is not None and equal(graph["goal"], plan.get("goal")))
    outcomes = {
        "goal_understanding": (goal_apply, goal_score),
        "semantic_correctness": (True, "NOT_RUN" if final_raw is None else legacy["semantic"]),
        "initial_plan_protocol": (plan_track, status(plan is not None and plan.keys() == PLAN_FIELDS
                                                     and trace.get("plan_before_tools") is True)),
        "final_output_protocol": (True, "NOT_RUN" if final_raw is None else status(final_ok)),
        "plan_executability": (plan_track, legacy["plan"]),
        "execution_correctness": (tools_apply, legacy["execution"]),
        "business_outcome": (True, legacy["business_outcome"]),
        "business_state_match": (True, status(equal(graph["goal_state"], trace.get("after_state")))),
        "safety": (True, legacy["safety"]),
        "strict_end_to_end": (True, terminal),
    }
    unresolved = terminal in {"BLOCKED", "NOT_RUN"}
    return {name: "NOT_APPLICABLE" if not applies else terminal if unresolved else result
            for name, (applies, result) in outcomes.items()}


def planning_layered_scores(case, graph, trace):
    """Add action, dependency, recovery and state diagnostics to the frozen scores."""
    layers = planning_scores_v2(case, graph, trace)
    nodes = graph["nodes"]
    selection_applies = bool(graph["required_subgoals"])
    dependency_applies = any(node["requires"] or node["after"] for node in nodes.values())
    state_applies = bool({"stage", "commit"}.intersection(case["tools"]))
    disruption = nodes.get(graph["disruption"])
    applicability = {
        "tool_selection": selection_applies,
        "tool_arguments": selection_applies,
        "dependency_correctness": dependency_applies,
        "dynamic_replanning": disruption is not None,
        "persisted_state": state_applies,
    }
    terminal = trace["status"]
    layers.update({name: terminal if applies and terminal in {"BLOCKED", "NOT_RUN"}
                   else "NOT_RUN" if applies else "NOT_APPLICABLE"
                   for name, applies in applicability.items()})
    if terminal in {"BLOCKED", "NOT_RUN"}:
        return layers
    records = trace["records"]
    if state_applies:
        layers["persisted_state"] = layers["business_state_match"]
    if not records:
        return layers
    by_tool = {}
    for node in nodes.values():
        by_tool.setdefault(node["tool"], []).append(node)
    recovered_evidence = False
    matched_dependencies = False
    selected, arguments = [], []
    for record in records:
        row = record if type(record) is dict else {}
        tool = row.get("tool")
        candidates = by_tool.get(tool, ()) if type(tool) is str else ()
        matches = [node for node in candidates if equal(node["args"], row.get("args"))]
        selected.append(bool(candidates))
        arguments.append(bool(matches))
        matched_dependencies |= any(node["after"] or node["requires"] for node in matches)
        if disruption is not None and disruption in matches:
            recovered_evidence |= equal(disruption["observation"], row.get("observation"))
    if selection_applies:
        layers["tool_selection"] = status(all(selected))
        layers["tool_arguments"] = status(all(arguments))
    if dependency_applies and matched_dependencies:
        verdict = score(case, graph, records, trace["after_state"], trace["final_raw"], track=trace["track"],
                        plan=trace["plan_raw"], plan_before_tools=trace["plan_before_tools"],
                        peak_context_tokens=trace["peak_context_tokens"])
        layers["dependency_correctness"] = status(verdict["metrics"]["dependency_validity"] == 1)
    if recovered_evidence:
        layers["dynamic_replanning"] = status(layers["execution_correctness"] == "PASS"
                                              and layers["business_outcome"] == "PASS")
    return layers
