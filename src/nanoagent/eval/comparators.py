"""Deterministic semantic comparators for the N05A cognitive evaluator.

No substring matching as a primary correctness method: closed-vocabulary
labels compare canonically (case/whitespace folding of a *closed* id set),
entities compare by identity, quantities compare through the unit registry
(conversion when the dimension matches, never across incompatible units),
state claims compare as typed predicates.
"""
from __future__ import annotations

import math

from .contracts import Expectation, Quantity, Response, SlotSpec, StatePredicate

# -- closed unit registry ------------------------------------------------------

# base unit per dimension and conversion factors into it
_UNIT_REGISTRY: dict[str, tuple[str, float]] = {
    # length -> metre
    "mm": ("length", 0.001), "cm": ("length", 0.01), "m": ("length", 1.0),
    "km": ("length", 1000.0),
    # mass -> gram
    "g": ("mass", 1.0), "kg": ("mass", 1000.0), "t": ("mass", 1_000_000.0),
    # time -> second
    "s": ("time", 1.0), "min": ("time", 60.0), "h": ("time", 3600.0),
    "day": ("time", 86400.0),
    # money: currencies never convert into each other
    "CNY": ("money:CNY", 1.0), "USD": ("money:USD", 1.0), "EUR": ("money:EUR", 1.0),
    # count: dimensionless
    "": ("count", 1.0), "pcs": ("count", 1.0), "个": ("count", 1.0),
}

_EPS = 1e-9

# canonical folding for CLOSED vocabularies only (ids, tool names, branches):
# case + outer whitespace + underscore/space unification
def canonical_label(s: str) -> str:
    return " ".join(str(s).strip().lower().replace("_", " ").split())


def check_quantity(actual_value: float, actual_unit: str,
                   expected: Quantity) -> list[str]:
    """Compare a numeric value+unit against the expected quantity.
    Returns reason codes (empty = equal)."""
    if not isinstance(actual_value, (int, float)) or isinstance(actual_value, bool):
        return ["TYPE_MISMATCH"]
    if not math.isfinite(float(actual_value)):
        return ["TYPE_MISMATCH"]
    if actual_unit not in _UNIT_REGISTRY:
        return ["UNIT_INVALID"]
    if expected.unit not in _UNIT_REGISTRY:
        raise ValueError(f"expectation uses unregistered unit {expected.unit!r}")
    dim_a = _UNIT_REGISTRY[actual_unit]
    dim_e = _UNIT_REGISTRY[expected.unit]
    if dim_a[0] != dim_e[0]:
        return ["UNIT_MISMATCH"]
    a = float(actual_value) * dim_a[1]
    e = float(expected.value) * dim_e[1]
    if abs(a - e) > _EPS * max(1.0, abs(e)):
        return ["VALUE_MISMATCH"]
    return []


def check_slot(actual_args: dict, slot: SlotSpec) -> list[str]:
    """Compare one typed slot expectation against the runtime's arguments."""
    if slot.name not in actual_args:
        return ["MISSING_SLOT"]
    v = actual_args[slot.name]
    if slot.type == "quantity":
        if isinstance(v, dict):
            value, unit = v.get("value"), v.get("unit", "")
        else:
            value, unit = v, slot.unit
        if unit is None:
            unit = ""
        if not isinstance(unit, str):
            return ["TYPE_MISMATCH"]
        return check_quantity(value, unit,
                              Quantity(float(slot.expected), slot.unit or ""))
    if slot.type == "entity":
        if not isinstance(v, str):
            return ["TYPE_MISMATCH"]
        return [] if canonical_label(v) == canonical_label(str(slot.expected)) \
            else ["ENTITY_MISMATCH"]
    if slot.type == "enum":
        return [] if canonical_label(str(v)) == canonical_label(str(slot.expected)) \
            else ["VALUE_MISMATCH"]
    if slot.type == "boolean":
        if not isinstance(v, bool):
            return ["TYPE_MISMATCH"]
        return [] if v is bool(slot.expected) else ["VALUE_MISMATCH"]
    if slot.type == "text":
        return [] if v == slot.expected else ["VALUE_MISMATCH"]
    raise ValueError(f"unknown slot type {slot.type!r}")


_OPS = {
    "eq": lambda a, e: a == e,
    "ne": lambda a, e: a != e,
    "gt": lambda a, e: a > e,
    "ge": lambda a, e: a >= e,
    "lt": lambda a, e: a < e,
    "le": lambda a, e: a <= e,
}


def predicate_holds(claimed: StatePredicate, expected: StatePredicate) -> list[str]:
    """Check a runtime state claim against the expected typed predicate.
    Same entity+property and same claimed OPERATOR required (a flipped
    operator is a polarity error), then the comparison must actually hold."""
    if canonical_label(claimed.entity_id) != canonical_label(expected.entity_id):
        return ["ENTITY_MISMATCH"]
    if canonical_label(claimed.property) != canonical_label(expected.property):
        return ["ENTITY_MISMATCH"]
    if claimed.op not in _OPS:
        return ["TYPE_MISMATCH"]
    if claimed.op != expected.op:
        return ["VALUE_MISMATCH"]        # polarity flip
    if expected.unit is not None:
        reasons = check_quantity(claimed.value, getattr(claimed, "unit", "") or "",
                                 Quantity(float(expected.value), expected.unit))
        if reasons:
            return reasons
        a = float(claimed.value) * _UNIT_REGISTRY[claimed.unit or ""][1] \
            if (claimed.unit or "") in _UNIT_REGISTRY else float(claimed.value)
        e = float(expected.value) * _UNIT_REGISTRY[expected.unit][1]
    else:
        a, e = claimed.value, expected.value
    return [] if _OPS[expected.op](a, e) else ["VALUE_MISMATCH"]


def evaluate_family(exp: Expectation, resp: Response) -> list[str]:
    """Semantic comparison for one family. Returns reason codes; an empty
    list means PASS."""
    fam = exp.family
    if fam == "intent":
        if resp.intent is None:
            return ["PARSE_INVALID"]
        return [] if canonical_label(resp.intent) == canonical_label(exp.intent or "") \
            else ["INTENT_MISMATCH"]
    if fam == "goal":
        if resp.goal_type is None:
            return ["PARSE_INVALID"]
        if canonical_label(resp.goal_type) != canonical_label(exp.goal_type or ""):
            return ["GOAL_MISMATCH"]
        got = tuple(resp.goal_params or ())
        if got != tuple(exp.goal_params):
            return ["GOAL_MISMATCH"]
        return []
    if fam == "tool_selection":
        if resp.tool is None:
            return ["PARSE_INVALID"]
        return [] if canonical_label(resp.tool) == canonical_label(exp.tool or "") \
            else ["TOOL_MISMATCH"]
    if fam == "action_representation":
        reasons: list[str] = []
        if resp.tool is None:
            return ["PARSE_INVALID"]
        if canonical_label(resp.tool) != canonical_label(exp.tool or ""):
            reasons.append("TOOL_MISMATCH")
        args = resp.args if isinstance(resp.args, dict) else None
        if args is None:
            return reasons + ["PARSE_INVALID"]
        for slot in exp.slots:
            reasons.extend(check_slot(args, slot))
        if not exp.allow_extra_assertions and resp.extra_assertions:
            reasons.append("EXTRA_ASSERTION")
        return _dedupe(reasons)
    if fam == "entity_reference":
        got = {canonical_label(str(e)) for e in (resp.entities or ())}
        want = {canonical_label(str(e)) for e in exp.entity_ids}
        if got != want:
            missing = want - got
            return ["ENTITY_MISMATCH"] if missing else ["EXTRA_ASSERTION"]
        return []
    if fam == "slot_value":
        args = resp.args if isinstance(resp.args, dict) else None
        if args is None:
            return ["PARSE_INVALID"]
        reasons = []
        for slot in exp.slots:
            reasons.extend(check_slot(args, slot))
        known = {s.name for s in exp.slots}
        if not exp.allow_extra_assertions:
            reasons.extend(f"EXTRA_ASSERTION" for k in args if k not in known)
        return _dedupe(reasons)
    if fam == "numeric_value_unit":
        v = resp.args.get("value") if isinstance(resp.args, dict) else None
        u = resp.args.get("unit") if isinstance(resp.args, dict) else None
        if v is None and resp.raw is not None and isinstance(resp.raw, dict):
            v, u = resp.raw.get("value"), resp.raw.get("unit", "")
        if v is None:
            return ["PARSE_INVALID"]
        return check_quantity(v, u if isinstance(u, str) else "",
                              exp.quantity or Quantity(0.0, ""))
    if fam == "state_interpretation":
        got = list(resp.state_predicates or ())
        want = list(exp.state_predicates)
        if not got:
            return ["PARSE_INVALID"]
        reasons = []
        for g, w in zip(got, want):
            reasons.extend(predicate_holds(g, w))
        if len(got) > len(want) and not exp.allow_extra_assertions:
            reasons.append("EXTRA_ASSERTION")
        return _dedupe(reasons)
    if fam == "conditional_branch":
        if resp.branch is None:
            return ["PARSE_INVALID"]
        return [] if canonical_label(resp.branch) == canonical_label(exp.branch or "") \
            else ["BRANCH_MISMATCH"]
    if fam == "recovery_action":
        if resp.recovery is None:
            return ["PARSE_INVALID"]
        return [] if canonical_label(resp.recovery) == canonical_label(exp.recovery or "") \
            else ["RECOVERY_INVALID"]
    if fam == "stop_continue":
        if resp.decision is None:
            return ["PARSE_INVALID"]
        d = canonical_label(resp.decision)
        if d not in ("stop", "continue"):
            return ["TYPE_MISMATCH"]
        return [] if d == (exp.decision or "") else ["DECISION_MISMATCH"]
    if fam == "clarification":
        got = {canonical_label(str(t)) for t in (resp.clarification_topics or ())}
        want = {canonical_label(str(t)) for t in exp.clarification_topics}
        return [] if got == want else ["CLARIFICATION_MISMATCH"]
    raise ValueError(f"unknown family {fam!r}")


def _dedupe(reasons: list[str]) -> list[str]:
    seen, out = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out
