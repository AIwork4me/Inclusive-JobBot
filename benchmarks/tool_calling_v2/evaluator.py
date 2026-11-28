"""Evaluate observed tool workflows against an independent dependency graph."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from jsonschema import Draft202012Validator, validators

from .oracle import FinalAnswer, StateOracle, Unordered, decode_object, equal


VALIDATOR = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine_many({
        "integer": lambda _, value: type(value) is int,
        "number": lambda _, value: type(value) in (int, float, Decimal),
    }),
)


@dataclass(frozen=True)
class Ref:
    node_id: str
    path: tuple[str | int, ...]


@dataclass(frozen=True)
class Node:
    node_id: str
    tool: str
    arguments: dict
    depends_on: tuple[str, ...] = ()
    result: dict | None = None
    sop_turn: int | None = None


@dataclass(frozen=True)
class Call:
    turn: int
    call_id: str | None
    name: str
    arguments_raw: str
    result: dict | None
    kind: str = "function"


def _resolve(value, results: dict[str, dict]):
    if isinstance(value, Ref):
        result = results[value.node_id]
        for part in value.path:
            result = result[part]
        return result
    if isinstance(value, dict):
        return {key: _resolve(item, results) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, results) for item in value]
    if isinstance(value, Unordered):
        return Unordered(tuple(_resolve(item, results) for item in value.values))
    return value


@dataclass(frozen=True)
class Workflow:
    nodes: tuple[Node, ...]
    schemas: dict[str, dict]
    forbidden: frozenset[str] = frozenset()
    final: FinalAnswer = field(default_factory=FinalAnswer)
    state: StateOracle | None = None

    def __post_init__(self):
        # Authored node order must be a topological sort. A reference must read a
        # declared dependency's oracle-verified result.
        seen = {}
        for node in self.nodes:
            if node.node_id in seen or set(node.depends_on) - seen.keys():
                raise ValueError(f"invalid DAG node or dependency: {node.node_id}")
            dependencies = {name: seen[name] for name in node.depends_on if seen[name] is not None}
            _resolve(node.arguments, dependencies)
            seen[node.node_id] = node.result
        for schema in self.schemas.values():
            Draft202012Validator.check_schema(schema)


def _argument_counts(expected: dict, actual: dict) -> tuple[int, list[str]]:
    wrong = [
        key for key, value in expected.items()
        if key not in actual or not equal(value, actual[key])
    ]
    return len(expected) - len(wrong), sorted(set(wrong) | (actual.keys() - expected.keys()))


def _decimal_schema(value):
    if isinstance(value, dict):
        return {key: _decimal_schema(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decimal_schema(item) for item in value]
    if type(value) is float:
        return Decimal(str(value))
    return value


def evaluate(workflow: Workflow, calls: list[Call], final_text: str, *,
             snapshot: dict | None = None, audit: list[dict] | None = None,
             before_snapshot: dict | None = None,
             historical: bool = False,
             trace_problems: tuple[tuple[str, str], ...] = (),
             state_problems: tuple[tuple[str, str], ...] = ()) -> dict:
    expected_results = {node.node_id: node.result for node in workflow.nodes if node.result is not None}
    expected_arguments = {
        node.node_id: _resolve(node.arguments, expected_results) for node in workflow.nodes
    }
    argument_total = sum(len(args) for args in expected_arguments.values())
    schemas = {name: VALIDATOR(_decimal_schema(schema)) for name, schema in workflow.schemas.items()}
    findings = []

    def add(code: str, detail: str, **fields):
        findings.append({"code": code, "detail": detail, **fields})

    for code, detail in trace_problems:
        add(code, detail)

    assigned = set()
    verified = {}
    matched_calls = {}
    observed_plan = []
    observed_sop = []
    seen_ids = set()
    argument_correct = 0
    previous_turn = -1

    for call in calls:
        identity = {"call_id": call.call_id, "tool": call.name, "turn": call.turn}
        call_id_valid = isinstance(call.call_id, str) and bool(call.call_id.strip())
        if (call.kind != "function" or not call_id_valid or call.call_id in seen_ids
                or type(call.turn) is not int or call.turn < 0 or call.turn < previous_turn):
            add("F05_PROTOCOL_ERROR", "invalid or repeated call identity or turn", **identity)
            continue
        seen_ids.add(call.call_id)
        previous_turn = call.turn
        if call.name in workflow.forbidden:
            add("F08_AUTHORIZATION_DENIAL", "forbidden tool proposal", **identity)
            continue
        candidates = [node for node in workflow.nodes if node.tool == call.name and node.node_id not in assigned]
        if not candidates:
            detail = ("duplicate call" if any(node.tool == call.name for node in workflow.nodes)
                      else "unexpected tool call")
            add("F02_MODEL_TOOL_SELECTION_ERROR", detail, **identity)
            continue
        try:
            args = decode_object(call.arguments_raw)
        except ValueError:
            add("F05_PROTOCOL_ERROR", "invalid raw argument JSON", **identity)
            continue

        ranked = []
        for node in candidates:
            correct, wrong = _argument_counts(expected_arguments[node.node_id], args)
            available = all(dep in verified and verified[dep][0] < call.turn for dep in node.depends_on)
            ranked.append((node, correct, wrong, available))
        node, correct, wrong, available = max(
            ranked, key=lambda item: (not item[2], item[3], item[1])
        )
        assigned.add(node.node_id)
        observed_plan.append({"node": node.node_id, "turn": call.turn, "call_id": call.call_id})
        identity["node"] = node.node_id
        valid_schema = call.name not in schemas or schemas[call.name].is_valid(args)
        if not valid_schema:
            add("F07_SCHEMA_VALIDATION_ERROR", "arguments violate the declared schema", **identity)
        if wrong:
            add("F03_MODEL_ARGUMENT_ERROR", "incorrect, missing or unexpected arguments", fields=wrong, **identity)
        if valid_schema:
            argument_correct += correct
        if not available:
            deps = [dep for dep in node.depends_on if dep not in verified or verified[dep][0] >= call.turn]
            add("F09_SOP_DEPENDENCY_ERROR", "required tool result unavailable on this turn", dependencies=deps, **identity)
        if valid_schema and not wrong and available:
            if call.result is None or (node.result is not None and not equal(node.result, call.result)):
                add("F10_TOOL_EXECUTION_ERROR", "missing or independently invalid tool result", **identity)
                continue
            verified[node.node_id] = (call.turn, call.result)
            matched_calls[call.call_id] = (call.name, args)
        observed_sop.append((node.node_id, call.turn))

    for node in workflow.nodes:
        if node.node_id not in assigned:
            add("F02_MODEL_TOOL_SELECTION_ERROR", "missing required call", node=node.node_id, tool=node.tool)
    for problem in workflow.final.check(final_text):
        add("F12_FINAL_ANSWER_ERROR", problem)

    trace_status = "FAIL" if findings else "PASS"
    expected_sop = [(node.node_id, index if node.sop_turn is None else node.sop_turn)
                    for index, node in enumerate(workflow.nodes)]
    strict_sop_status = "PASS" if trace_status == "PASS" and observed_sop == expected_sop else "FAIL"
    state_status = "NOT_RUN"
    if workflow.state is not None:
        if snapshot is None or audit is None:
            state_status = "BLOCKED"
            detail = "INSUFFICIENT_HISTORICAL_EVIDENCE" if historical else "MISSING_STATE_EVIDENCE"
            add("F15_INSUFFICIENT_EVIDENCE", detail)
        else:
            state_errors = [*state_problems, *workflow.state.check(snapshot, audit, matched_calls, before_snapshot)]
            state_status = "FAIL" if state_errors else "PASS"
            for code, detail in state_errors:
                add(code, detail)

    status = "FAIL" if "FAIL" in (trace_status, state_status) else (
        "BLOCKED" if state_status == "BLOCKED" else "PASS"
    )
    return {
        "status": status, "trace_status": trace_status, "strict_sop_status": strict_sop_status,
        "business_state_status": state_status, "argument_correct": argument_correct,
        "argument_total": argument_total, "observed_plan": observed_plan,
        "argument_unit": "required_top_level_parameter", "findings": findings,
    }
