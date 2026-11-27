"""Deterministic semantic comparators for the cognitive evaluator.

Contract v2 (N05A-R, IJ-NANO-1.2). Fixes relative to v1, by concern:

- EV01: state_interpretation matches claims to expectations by
  (entity, property) identity, detects missing required predicates
  (MISSING_PREDICATE), duplicate/contradictory claims on one identity
  (DUPLICATE_PREDICATE), and accepts any claim order.
- EV02: action_representation / slot_value reject undeclared argument
  keys (ARGUMENT_UNDECLARED) from response.args alone, support declared
  optional slots, and structurally reject duplicate keys in raw
  structured output (PARSE_INVALID) without relying on an upstream
  parser's extra_assertions.
- EV03: predicate EXPRESSION equivalence (``predicates_equivalent``) is
  separated from predicate TRUTH against an independently supplied world
  state (``predicate_truth``). A claimed threshold is never treated as an
  observed business value; invalid value types return TYPE_MISMATCH
  instead of raising.
- EV04: folding (``canonical_label``) applies to closed-vocabulary
  natural-language labels only. Tool/entity/action identifiers compare by
  exact identity unless an explicit alias contract is declared
  (``identifier_matches``).
- EV05: a scalar quantity inherits the expected unit only when the slot
  publicly declares that unit (``SlotSpec.unit_publicly_declared``);
  otherwise UNIT_MISSING.

Mutant harness (EV06): ``apply_mutant``/``clear_mutant`` swap real
comparator functions/handlers with weakened implementations; the
qualification gate must reject every mutant class.
"""
from __future__ import annotations

import json
import math

from .contracts import Expectation, Quantity, Response, SlotSpec, StatePredicate
from .units import UNIT_REGISTRY, dimension_of, to_base, values_equal

# -- closed-vocabulary label folding (LABEL kind only) ------------------

def canonical_label(s: str) -> str:
    """Case + outer whitespace + underscore/space unification.

    LABEL-scope only (intent, goal types, enum values, branches, recovery
    actions, decisions, clarification topics - closed natural-language
    vocabularies). EV04: never applied to tool/entity/action identifiers.
    """
    return " ".join(str(s).strip().lower().replace("_", " ").split())


def identifier_matches(actual, expected, kind: str, aliases: dict | None = None) -> bool:
    """EV04 identifier contract.

    kind "label": closed-vocabulary folding.
    kind "tool"/"entity"/"action": EXACT string identity, unless an
    explicit alias contract maps the expected identifier to declared
    accepted variants (matched exactly, no normalization).
    """
    actual_s, expected_s = str(actual), str(expected)
    if kind == "label":
        return canonical_label(actual_s) == canonical_label(expected_s)
    if kind in ("tool", "entity", "action"):
        if actual_s == expected_s:
            return True
        for canonical, variants in (aliases or {}).items():
            if str(canonical) == expected_s:
                return actual_s in tuple(str(v) for v in variants)
        return False
    raise ValueError(f"unknown identifier kind {kind!r}")


def _alias_dict(exp: Expectation) -> dict | None:
    return {c: tuple(v) for c, v in exp.alias_contract} if exp.alias_contract else None


# -- quantities ------------------------------------------------------------

def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_quantity(actual_value, actual_unit, expected: Quantity) -> list[str]:
    """Compare a numeric value+unit against the expected quantity.
    Returns reason codes (empty = equal)."""
    if not _is_number(actual_value):
        return ["TYPE_MISMATCH"]
    if not math.isfinite(float(actual_value)):
        return ["TYPE_MISMATCH"]
    if actual_unit not in UNIT_REGISTRY:
        return ["UNIT_INVALID"]
    if expected.unit not in UNIT_REGISTRY:
        raise ValueError(f"expectation uses unregistered unit {expected.unit!r}")
    if dimension_of(actual_unit) != dimension_of(expected.unit):
        return ["UNIT_MISMATCH"]
    a = to_base(actual_value, actual_unit)
    e = to_base(expected.value, expected.unit)
    if not values_equal(a, e):
        return ["VALUE_MISMATCH"]
    return []


# -- slots -------------------------------------------------------------------

def check_slot(actual_args: dict, slot: SlotSpec,
               aliases: dict | None = None) -> list[str]:
    """Compare one typed slot expectation against the runtime's arguments."""
    if slot.name not in actual_args:
        return [] if slot.optional else ["MISSING_SLOT"]
    v = actual_args[slot.name]
    if slot.type == "quantity":
        unit_public = bool(slot.unit_publicly_declared and slot.unit)
        if isinstance(v, dict):
            value = v.get("value")
            if "unit" in v and isinstance(v["unit"], str):
                unit = v["unit"]
            elif unit_public:
                unit = slot.unit
            else:
                return ["UNIT_MISSING"]        # EV05: mandatory unit absent
        else:
            value = v
            unit = slot.unit if unit_public else None
            if unit is None:
                return ["UNIT_MISSING"]        # EV05: no silent inheritance
        if not isinstance(unit, str):
            return ["TYPE_MISMATCH"]
        return check_quantity(value, unit,
                              Quantity(slot.expected, slot.unit or ""))
    if slot.type == "entity":
        if not isinstance(v, str):
            return ["TYPE_MISMATCH"]
        return [] if identifier_matches(v, slot.expected, "entity", aliases) \
            else ["ENTITY_MISMATCH"]
    if slot.type == "enum":
        return [] if identifier_matches(v, slot.expected, "label") \
            else ["VALUE_MISMATCH"]
    if slot.type == "boolean":
        if not isinstance(v, bool):
            return ["TYPE_MISMATCH"]
        return [] if v is bool(slot.expected) else ["VALUE_MISMATCH"]
    if slot.type == "text":
        return [] if v == slot.expected else ["VALUE_MISMATCH"]
    raise ValueError(f"unknown slot type {slot.type!r}")


# -- predicates (EV03) ---------------------------------------------------------

_OPS = {
    "eq": lambda a, e: a == e,
    "ne": lambda a, e: a != e,
    "gt": lambda a, e: a > e,
    "ge": lambda a, e: a >= e,
    "lt": lambda a, e: a < e,
    "le": lambda a, e: a <= e,
}
_ORDERING = ("gt", "ge", "lt", "le")


def _typed_pair(a, e, ordering: bool) -> tuple[float, float] | None:
    """Return (a, e) as numbers, or None when the types are invalid for the
    comparison (EV03: TYPE_MISMATCH, never a Python crash)."""
    if ordering or isinstance(e, (int, float)):
        if not (_is_number(a) and math.isfinite(float(a))):
            return None
        if not (_is_number(e) and math.isfinite(float(e))):
            return None
        return float(a), float(e)
    # eq/ne on non-numeric expectations: same-type equality only
    if type(a) is not type(e):
        return None
    return None if isinstance(a, bool) else (a, e)  # sentinel: non-numeric pair


def predicates_equivalent(claimed: StatePredicate,
                          expected: StatePredicate) -> list[str]:
    """EV03 (1): predicate EXPRESSION equivalence.

    Explicit equivalence rule (no cross-operator logical rewriting):
    same entity+property identity, same operator, and equal threshold
    values (unit-aware for numeric thresholds). ge 5 is NOT equivalent to
    gt 4 even when extensionally equal on integers - the supported
    contract is exact operator identity plus value equality.
    """
    if not identifier_matches(claimed.entity_id, expected.entity_id, "entity"):
        return ["ENTITY_MISMATCH"]
    if claimed.property != expected.property:
        return ["ENTITY_MISMATCH"]
    if claimed.op not in _OPS:
        return ["TYPE_MISMATCH"]
    if claimed.op != expected.op:
        return ["VALUE_MISMATCH"]        # polarity/operator flip
    if expected.unit is not None or claimed.unit is not None:
        cu = claimed.unit or ""
        if not cu:
            return ["UNIT_MISSING"]
        eu = expected.unit or ""
        if cu not in UNIT_REGISTRY:
            return ["UNIT_INVALID"]
        if eu not in UNIT_REGISTRY:
            raise ValueError(f"expectation uses unregistered unit {eu!r}")
        if dimension_of(cu) != dimension_of(eu):
            return ["UNIT_MISMATCH"]
        if not (_is_number(claimed.value) and _is_number(expected.value)):
            return ["TYPE_MISMATCH"]
        a, e = to_base(claimed.value, cu), to_base(expected.value, eu)
        return [] if values_equal(a, e) else ["VALUE_MISMATCH"]
    pair = _typed_pair(claimed.value, expected.value,
                       ordering=claimed.op in _ORDERING)
    if pair is None:
        return ["TYPE_MISMATCH"]
    a, e = pair
    # equivalence = threshold equality for every operator (the operator
    # itself was already required identical above)
    if isinstance(a, str):
        return [] if a == e else ["VALUE_MISMATCH"]
    return [] if values_equal(a, e) else ["VALUE_MISMATCH"]


def predicate_truth(pred: StatePredicate, world: dict) -> list[str]:
    """EV03 (2): predicate TRUTH against an independently supplied world
    state.

    ``world`` maps (entity_id, property) -> observation. An observation is
    a number, a string, or a quantity-like {"value": .., "unit": ..} /
    Quantity. Returns [] when the predicate holds against the observation;
    ENTITY_MISMATCH when no observation exists for the claimed identity.
    The predicate's own threshold is never evidence of the observed value.
    """
    key = (pred.entity_id, pred.property)
    if key not in world:
        return ["ENTITY_MISMATCH"]
    obs = world[key]
    if isinstance(obs, Quantity):
        ov, ou = obs.value, obs.unit
    elif isinstance(obs, dict):
        ov, ou = obs.get("value"), obs.get("unit")
    else:
        ov, ou = obs, None
    if pred.unit is not None:
        if ou is None or ou == "":
            return ["UNIT_MISSING"]
        for u in (ou, pred.unit):
            if u not in UNIT_REGISTRY:
                return ["UNIT_INVALID"]
        if dimension_of(ou) != dimension_of(pred.unit):
            return ["UNIT_MISMATCH"]
        if not (_is_number(ov) and _is_number(pred.value)):
            return ["TYPE_MISMATCH"]
        a, e = to_base(ov, ou), to_base(pred.value, pred.unit)
    else:
        pair = _typed_pair(ov, pred.value, ordering=pred.op in _ORDERING)
        if pair is None:
            return ["TYPE_MISMATCH"]
        a, e = pair
        if isinstance(a, str):
            ok = (a == e) if pred.op == "eq" else (a != e) if pred.op == "ne" else False
            return [] if ok else ["VALUE_MISMATCH"]
    return [] if _OPS[pred.op](a, e) else ["VALUE_MISMATCH"]


# -- raw structured output gate (EV02) ---------------------------------------

def _no_duplicate_keys(pairs):
    keys = [k for k, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate object key in raw output")
    return dict(pairs)


def _raw_reasons(resp: Response) -> list[str]:
    raw = getattr(resp, "raw", None)
    if raw is None or not isinstance(raw, str):
        return []
    try:
        json.loads(raw, object_pairs_hook=_no_duplicate_keys)
    except ValueError:
        return ["PARSE_INVALID"]
    return []


# -- family handlers ----------------------------------------------------------

def eval_intent(exp: Expectation, resp: Response) -> list[str]:
    if resp.intent is None:
        return ["PARSE_INVALID"]
    return [] if identifier_matches(resp.intent, exp.intent or "", "label") \
        else ["INTENT_MISMATCH"]


def eval_goal(exp: Expectation, resp: Response) -> list[str]:
    if resp.goal_type is None:
        return ["PARSE_INVALID"]
    if not identifier_matches(resp.goal_type, exp.goal_type or "", "label"):
        return ["GOAL_MISMATCH"]
    got = tuple(resp.goal_params or ())
    if got != tuple(exp.goal_params):
        return ["GOAL_MISMATCH"]
    return []


def eval_tool_selection(exp: Expectation, resp: Response) -> list[str]:
    if resp.tool is None:
        return ["PARSE_INVALID"]
    return [] if identifier_matches(resp.tool, exp.tool or "", "tool",
                                    _alias_dict(exp)) else ["TOOL_MISMATCH"]


def eval_action_representation(exp: Expectation, resp: Response) -> list[str]:
    reasons: list[str] = []
    if resp.tool is None:
        return ["PARSE_INVALID"]
    if not identifier_matches(resp.tool, exp.tool or "", "tool", _alias_dict(exp)):
        reasons.append("TOOL_MISMATCH")
    args = resp.args if isinstance(resp.args, dict) else None
    if args is None:
        return reasons + ["PARSE_INVALID"]
    aliases = _alias_dict(exp)
    for slot in exp.slots:
        reasons.extend(check_slot(args, slot, aliases))
    declared = {s.name for s in exp.slots}
    reasons.extend("ARGUMENT_UNDECLARED" for k in args if k not in declared)
    if not exp.allow_extra_assertions and resp.extra_assertions:
        reasons.append("EXTRA_ASSERTION")
    return reasons


def eval_entity_reference(exp: Expectation, resp: Response) -> list[str]:
    got = {str(e) for e in (resp.entities or ())}
    want = set(exp.entity_ids)
    if got == want:
        return []
    return ["ENTITY_MISMATCH"] if want - got else ["EXTRA_ASSERTION"]


def eval_slot_value(exp: Expectation, resp: Response) -> list[str]:
    args = resp.args if isinstance(resp.args, dict) else None
    if args is None:
        return ["PARSE_INVALID"]
    reasons: list[str] = []
    aliases = _alias_dict(exp)
    for slot in exp.slots:
        reasons.extend(check_slot(args, slot, aliases))
    declared = {s.name for s in exp.slots}
    reasons.extend("ARGUMENT_UNDECLARED" for k in args if k not in declared)
    return reasons


def eval_numeric_value_unit(exp: Expectation, resp: Response) -> list[str]:
    v = resp.args.get("value") if isinstance(resp.args, dict) else None
    u = resp.args.get("unit") if isinstance(resp.args, dict) else None
    if v is None and resp.raw is not None and isinstance(resp.raw, dict):
        v, u = resp.raw.get("value"), resp.raw.get("unit", "")
    if v is None:
        return ["PARSE_INVALID"]
    return check_quantity(v, u if isinstance(u, str) else "",
                          exp.quantity or Quantity(0.0, ""))


def eval_state_interpretation(exp: Expectation, resp: Response) -> list[str]:
    """EV01: identity-based matching contract.

    - claims are keyed by exact (entity_id, property) identity;
    - a second claim on one identity (including an eq/ne contradiction)
      is DUPLICATE_PREDICATE;
    - required identities with no claim are MISSING_PREDICATE - except
      when some claim targets the same PROPERTY on a wrong entity: that
      substitution is reported once as ENTITY_MISMATCH;
    - unmatched claims about properties outside the expected scope (or
      redundant extra claims about already-satisfied properties) are
      EXTRA_ASSERTION unless explicitly allowed.
    """
    got = list(resp.state_predicates or ())
    want = {p.identity: p for p in exp.state_predicates}
    if not got:
        return ["PARSE_INVALID"]
    reasons: list[str] = []
    claimed: dict[tuple[str, str], StatePredicate] = {}
    for g in got:
        if g.identity in claimed:
            reasons.append("DUPLICATE_PREDICATE")
            continue
        claimed[g.identity] = g
    for key, g in claimed.items():
        w = want.get(key)
        if w is not None:
            reasons.extend(predicates_equivalent(g, w))
        elif not exp.allow_extra_assertions:
            want_same_prop = [k for k in want if k[1] == g.property]
            if want_same_prop and any(k not in claimed for k in want_same_prop):
                reasons.append("ENTITY_MISMATCH")   # right property, wrong entity
            else:
                reasons.append("EXTRA_ASSERTION")   # property outside scope, or
                                                    # redundant extra claim
    for key in want:
        if key in claimed:
            continue
        if any(g.property == key[1] for g in claimed.values()):
            continue        # already reported as ENTITY_MISMATCH substitution
        reasons.append("MISSING_PREDICATE")
    return reasons


def eval_conditional_branch(exp: Expectation, resp: Response) -> list[str]:
    if resp.branch is None:
        return ["PARSE_INVALID"]
    return [] if identifier_matches(resp.branch, exp.branch or "", "label") \
        else ["BRANCH_MISMATCH"]


def eval_recovery_action(exp: Expectation, resp: Response) -> list[str]:
    if resp.recovery is None:
        return ["PARSE_INVALID"]
    return [] if identifier_matches(resp.recovery, exp.recovery or "", "label") \
        else ["RECOVERY_INVALID"]


def eval_stop_continue(exp: Expectation, resp: Response) -> list[str]:
    if resp.decision is None:
        return ["PARSE_INVALID"]
    d = canonical_label(resp.decision)
    if d not in ("stop", "continue"):
        return ["TYPE_MISMATCH"]
    return [] if d == (exp.decision or "") else ["DECISION_MISMATCH"]


def eval_clarification(exp: Expectation, resp: Response) -> list[str]:
    got = {canonical_label(str(t)) for t in (resp.clarification_topics or ())}
    want = {canonical_label(str(t)) for t in exp.clarification_topics}
    return [] if got == want else ["CLARIFICATION_MISMATCH"]


_FAMILY_HANDLER_NAMES = {
    "intent": "eval_intent",
    "goal": "eval_goal",
    "tool_selection": "eval_tool_selection",
    "action_representation": "eval_action_representation",
    "entity_reference": "eval_entity_reference",
    "slot_value": "eval_slot_value",
    "numeric_value_unit": "eval_numeric_value_unit",
    "state_interpretation": "eval_state_interpretation",
    "conditional_branch": "eval_conditional_branch",
    "recovery_action": "eval_recovery_action",
    "stop_continue": "eval_stop_continue",
    "clarification": "eval_clarification",
}


def evaluate_family(exp: Expectation, resp: Response) -> list[str]:
    """Semantic comparison for one family. Returns reason codes; an empty
    list means PASS. Handlers are resolved through module globals at call
    time so the EV06 mutant harness swaps take effect."""
    raw_reasons = _raw_reasons(resp)
    if raw_reasons:
        return raw_reasons
    fam = exp.family
    name = _FAMILY_HANDLER_NAMES.get(fam)
    if name is None:
        raise ValueError(f"unknown family {fam!r}")
    return _dedupe(globals()[name](exp, resp))


def _dedupe(reasons: list[str]) -> list[str]:
    seen, out = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


# -- comparator-level mutant harness (EV06) -----------------------------------
# Originals are bound at import time so weakened implementations never
# recurse into the very name they replace.

_ORIGINAL_EVAL_STATE = eval_state_interpretation
_ORIGINAL_EVAL_ACTION = eval_action_representation
_ORIGINAL_EVAL_SLOT = eval_slot_value
_ORIGINAL_CHECK_SLOT = check_slot


def _mut_skip_missing_predicate(exp, resp):
    reasons = _ORIGINAL_EVAL_STATE(exp, resp)
    return [r for r in reasons if r != "MISSING_PREDICATE"]


def _mut_ignore_extra_arguments_action(exp, resp):
    reasons = _ORIGINAL_EVAL_ACTION(exp, resp)
    return [r for r in reasons
            if r not in ("ARGUMENT_UNDECLARED", "EXTRA_ASSERTION")]


def _mut_ignore_extra_arguments_slot(exp, resp):
    reasons = _ORIGINAL_EVAL_SLOT(exp, resp)
    return [r for r in reasons
            if r not in ("ARGUMENT_UNDECLARED", "EXTRA_ASSERTION")]


def _mut_check_slot_substring(actual_args, slot, aliases=None):
    if slot.type == "entity" and slot.name in actual_args:
        v = actual_args[slot.name]
        if isinstance(v, str) and (v in str(slot.expected)
                                   or str(slot.expected) in v):
            return []          # substring containment wrongly accepted
    return _ORIGINAL_CHECK_SLOT(actual_args, slot, aliases)


def _mut_identifier_matches_fold_everything(actual, expected, kind, aliases=None):
    return canonical_label(str(actual)) == canonical_label(str(expected))


def _mut_check_quantity_unit_blind(actual_value, actual_unit, expected):
    if not _is_number(actual_value) or not math.isfinite(float(actual_value)):
        return ["TYPE_MISMATCH"]
    return [] if values_equal(float(actual_value), expected.value) \
        else ["VALUE_MISMATCH"]


def _mut_check_quantity_no_threshold(actual_value, actual_unit, expected):
    return []


def _mut_check_quantity_types_valid(actual_value, actual_unit, expected):
    # coerces string numerics, substitutes the expected unit for invalid
    # ones, accepts non-finite floats
    try:
        v = float(actual_value)
    except (TypeError, ValueError):
        return ["VALUE_MISMATCH"]
    if not math.isfinite(v):
        return ["VALUE_MISMATCH"]
    unit = actual_unit if actual_unit in UNIT_REGISTRY else expected.unit
    if dimension_of(unit) != dimension_of(expected.unit):
        return ["UNIT_MISMATCH"]
    return [] if values_equal(to_base(v, unit),
                              to_base(expected.value, expected.unit)) \
        else ["VALUE_MISMATCH"]


_FLIPPED_OPS = {
    "eq": lambda a, e: a == e,
    "ne": lambda a, e: a != e,
    "gt": lambda a, e: a <= e,
    "ge": lambda a, e: a < e,
    "lt": lambda a, e: a >= e,
    "le": lambda a, e: a > e,
}


def _mut_raw_reasons_disabled(resp):
    return []


MUTANTS: dict[str, dict[str, object]] = {
    "skip_missing_predicate": {
        "eval_state_interpretation": _mut_skip_missing_predicate},
    "ignore_extra_arguments": {
        "eval_action_representation": _mut_ignore_extra_arguments_action,
        "eval_slot_value": _mut_ignore_extra_arguments_slot},
    "entity_substring": {"check_slot": _mut_check_slot_substring},
    "normalize_identifiers_incorrectly": {
        "identifier_matches": _mut_identifier_matches_fold_everything},
    "accept_incorrect_units": {
        "check_quantity": _mut_check_quantity_unit_blind},
    "flip_inequality_ops": {"_OPS": _FLIPPED_OPS},
    "ignore_numeric_thresholds": {
        "check_quantity": _mut_check_quantity_no_threshold},
    "invalid_types_as_valid": {
        "check_quantity": _mut_check_quantity_types_valid},
    "accept_malformed_raw": {"_raw_reasons": _mut_raw_reasons_disabled},
}

_MUTANT_BACKUPS: dict[str, object] = {}


def apply_mutant(name: str) -> None:
    """Swap real comparator functions with a weakened implementation."""
    if name not in MUTANTS:
        raise ValueError(f"unknown mutant {name!r}")
    for attr, replacement in MUTANTS[name].items():
        _MUTANT_BACKUPS.setdefault(attr, globals()[attr])
        globals()[attr] = replacement


def clear_mutant() -> None:
    """Restore every function swapped by apply_mutant."""
    while _MUTANT_BACKUPS:
        attr, original = _MUTANT_BACKUPS.popitem()
        globals()[attr] = original
