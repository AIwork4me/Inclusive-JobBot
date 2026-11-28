"""Typed evaluation contracts for the cognitive evaluator.

Contract version history:
- v1 (N05A): 12 families, 16 reason codes, closed-vocab folding everywhere.
- v2 (N05A-R, IJ-NANO-1.2): EV01-EV07 concerns addressed. Reason codes
  reconciled (ARGUMENT_MISMATCH declared obsolete with an explicit
  disposition; ARGUMENT_UNDECLARED / UNIT_MISSING / MISSING_PREDICATE /
  DUPLICATE_PREDICATE added and controlled). Strict construction-time
  validation rejects malformed evaluator inputs (EV07). SlotSpec gains the
  optional-argument contract (EV02) and the public unit declaration
  contract (EV05).

Design rules (mission order section 5, unchanged):
- Deterministic semantic comparisons; substring matching is never the
  primary correctness method.
- Expected results live on the EVALUATOR side only. The tested runtime
  submits a bare ``Response``; it never receives an EvalCase, expectation
  or reason code.
- Every scoring rule maps to positive and negative controls
  (``nanoagent.eval.controls``); every negative control carries the reason
  code it must fail with.
"""
from __future__ import annotations

import dataclasses
from typing import Any

from .units import unit_registered

CONTRACT_VERSION = 2

FAMILIES = (
    "intent",
    "goal",
    "tool_selection",
    "action_representation",
    "entity_reference",
    "slot_value",
    "numeric_value_unit",
    "state_interpretation",
    "conditional_branch",
    "recovery_action",
    "stop_continue",
    "clarification",
)

# Reason codes a negative control may declare as its intended failure.
# EV07 reconciliation: every declared code is reachable and carries at
# least one negative control; obsolete codes are documented in
# REASON_CODE_DISPOSITIONS instead of being silently dropped.
REASON_CODES = (
    "INTENT_MISMATCH", "GOAL_MISMATCH",
    "TOOL_MISMATCH", "ARGUMENT_UNDECLARED",
    "ENTITY_MISMATCH", "VALUE_MISMATCH", "UNIT_MISMATCH", "UNIT_INVALID",
    "UNIT_MISSING", "TYPE_MISMATCH", "MISSING_SLOT", "EXTRA_ASSERTION",
    "MISSING_PREDICATE", "DUPLICATE_PREDICATE",
    "BRANCH_MISMATCH", "RECOVERY_INVALID", "DECISION_MISMATCH",
    "CLARIFICATION_MISMATCH", "PARSE_INVALID",
)

# Dispositions for codes that are NOT in REASON_CODES (v1-only) or whose
# reachability is restricted. EV07: declared/reachable/tested must
# reconcile; this record is the audit trail for the difference.
REASON_CODE_DISPOSITIONS = {
    "ARGUMENT_MISMATCH": {
        "status": "obsolete (removed in contract v2, N05A-R EV07)",
        "reason": "single 'argument wrong' code conflated distinct defect "
                  "classes that v2 reports precisely",
        "subsumed_by": [
            "MISSING_SLOT",          # required argument absent
            "ARGUMENT_UNDECLARED",   # unauthorized/unpermitted argument key
            "VALUE_MISMATCH",        # wrong scalar/enum/text value
            "ENTITY_MISMATCH",       # wrong business identifier value
            "TYPE_MISMATCH",         # wrong value type
            "UNIT_MISMATCH",         # wrong unit/dimension
            "UNIT_MISSING",          # mandatory unit absent
        ],
    },
}

_OPS = ("eq", "ne", "gt", "ge", "lt", "le")


def _nonempty_str(v, what: str) -> str:
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{what} must be a non-empty string, got {v!r}")
    return v


@dataclasses.dataclass(frozen=True)
class Quantity:
    """A numeric value with a unit from the closed unit registry."""
    value: float
    unit: str

    def __post_init__(self):
        try:
            object.__setattr__(self, "value", float(self.value))
        except (TypeError, ValueError) as e:
            raise ValueError(f"quantity value must be numeric: {self.value!r}") from e
        if not isinstance(self.unit, str) or not unit_registered(self.unit):
            raise ValueError(f"quantity uses unregistered unit {self.unit!r}")


@dataclasses.dataclass(frozen=True)
class SlotSpec:
    """One expected slot: name, closed type, expected value (and unit for
    quantities).

    EV02: ``optional=True`` marks a DECLARED optional argument — supplying
    it is permitted (still checked when supplied); omitting it is not a
    defect. Keys not matching any declared slot are undeclared arguments.

    EV05: ``unit_publicly_declared=True`` records that the unit for this
    slot is part of the public task/schema contract (the runtime was told
    "amounts are in CNY"), so a bare scalar may inherit that PUBLIC unit.
    Without this flag a scalar never inherits the hidden expected unit.
    """
    name: str
    type: str                  # entity | quantity | text | enum | boolean
    expected: Any
    unit: str | None = None
    optional: bool = False
    unit_publicly_declared: bool = False

    def __post_init__(self):
        _nonempty_str(self.name, "slot name")
        if self.type not in ("entity", "quantity", "text", "enum", "boolean"):
            raise ValueError(f"unknown slot type {self.type!r}")
        if self.type == "quantity":
            if not isinstance(self.unit, str) or not unit_registered(self.unit):
                raise ValueError(
                    f"quantity slot {self.name!r} needs a registered unit, "
                    f"got {self.unit!r}")
        if self.type == "boolean" and not isinstance(self.expected, bool):
            raise ValueError("boolean slot expectation must be a bool")


@dataclasses.dataclass(frozen=True)
class StatePredicate:
    """Typed claim about business state (entity, property, operator, value).

    EV03: this object is a predicate EXPRESSION. Whether it is TRUE is a
    separate question answered against an independently supplied world
    state (``comparators.predicate_truth``); equivalence between two
    expressions is ``comparators.predicates_equivalent``.
    """
    entity_id: str
    property: str
    op: str                    # eq | ne | gt | ge | lt | le
    value: Any
    unit: str | None = None

    def __post_init__(self):
        _nonempty_str(self.entity_id, "predicate entity_id")
        _nonempty_str(self.property, "predicate property")
        if self.op not in _OPS:
            raise ValueError(f"unknown predicate operator {self.op!r}")
        if self.value is None:
            raise ValueError("predicate value must not be None")
        if self.unit is not None and not unit_registered(self.unit):
            raise ValueError(f"predicate uses unregistered unit {self.unit!r}")

    @property
    def identity(self) -> tuple[str, str]:
        return (self.entity_id, self.property)


@dataclasses.dataclass(frozen=True)
class Expectation:
    """Semantic ground truth for one evaluation case. Only the fields
    relevant to the family are populated; construction REJECTS malformed
    combinations (EV07 strict dataset qualification)."""
    family: str
    intent: str | None = None
    goal_type: str | None = None
    goal_params: tuple = ()
    tool: str | None = None
    slots: tuple[SlotSpec, ...] = ()
    entity_ids: tuple[str, ...] = ()
    quantity: Quantity | None = None
    state_predicates: tuple[StatePredicate, ...] = ()
    branch: str | None = None
    recovery: str | None = None
    decision: str | None = None            # "stop" | "continue"
    clarification_topics: frozenset[str] = frozenset()
    allow_extra_assertions: bool = False
    alias_contract: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def __post_init__(self):
        if self.family not in FAMILIES:
            raise ValueError(f"unknown family: {self.family}")
        # every slot/predicate must be the typed contract object
        for s in self.slots:
            if not isinstance(s, SlotSpec):
                raise ValueError(f"slot {s!r} is not a SlotSpec")
        for p in self.state_predicates:
            if not isinstance(p, StatePredicate):
                raise ValueError(f"predicate {p!r} is not a StatePredicate")
        slot_names = [s.name for s in self.slots]
        if len(set(slot_names)) != len(slot_names):
            raise ValueError(f"duplicate slot names: {slot_names}")
        for a, variants in self.alias_contract:
            _nonempty_str(a, "alias canonical id")
            if not all(isinstance(v, str) and v for v in variants):
                raise ValueError(f"alias variants for {a!r} must be non-empty strings")
        f = self.family
        if f == "intent":
            _nonempty_str(self.intent, "intent expectation")
        elif f == "goal":
            _nonempty_str(self.goal_type, "goal_type expectation")
            if not isinstance(self.goal_params, (tuple, list)):
                raise ValueError("goal_params must be a tuple/list")
        elif f == "tool_selection":
            _nonempty_str(self.tool, "tool expectation")
        elif f == "action_representation":
            _nonempty_str(self.tool, "tool expectation")
            if not any(not s.optional for s in self.slots):
                raise ValueError("action_representation needs >=1 required slot")
        elif f == "entity_reference":
            if not self.entity_ids:
                raise ValueError("entity_reference needs >=1 entity id")
            for e in self.entity_ids:
                _nonempty_str(e, "entity id")
            if len(set(self.entity_ids)) != len(self.entity_ids):
                raise ValueError("duplicate entity ids in expectation")
        elif f == "slot_value":
            if not self.slots:
                raise ValueError("slot_value needs >=1 slot")
        elif f == "numeric_value_unit":
            if not isinstance(self.quantity, Quantity):
                raise ValueError("numeric_value_unit needs a Quantity")
        elif f == "state_interpretation":
            if not self.state_predicates:
                raise ValueError("state_interpretation needs >=1 predicate")
            identities = [p.identity for p in self.state_predicates]
            if len(set(identities)) != len(identities):
                raise ValueError(
                    "expectation asserts one (entity, property) identity twice")
        elif f == "conditional_branch":
            _nonempty_str(self.branch, "branch expectation")
        elif f == "recovery_action":
            _nonempty_str(self.recovery, "recovery expectation")
        elif f == "stop_continue":
            if self.decision not in ("stop", "continue"):
                raise ValueError("stop_continue decision must be stop|continue")
        elif f == "clarification":
            if not self.clarification_topics:
                raise ValueError("clarification needs >=1 topic")
            for t in self.clarification_topics:
                _nonempty_str(t, "clarification topic")


@dataclasses.dataclass(frozen=True)
class Response:
    """What the tested runtime produced. Contains ONLY runtime output —
    never expectations, hints or evaluator metadata."""
    intent: str | None = None
    goal_type: str | None = None
    goal_params: tuple | list = ()
    tool: str | None = None
    args: dict | None = None
    entities: tuple | list = ()
    branch: str | None = None
    recovery: str | None = None
    decision: str | None = None
    clarification_topics: tuple | list = ()
    state_predicates: tuple | list = ()
    extra_assertions: tuple | list = ()
    raw: Any = None


@dataclasses.dataclass(frozen=True)
class ControlCase:
    """One control: a case id, its expectation, the control class
    (positive, or negative with the intended failure reason), and the
    response the control submits."""
    case_id: str
    family: str
    control_class: str        # "positive" | "negative:<REASON>"
    expectation: Expectation
    response: Response


@dataclasses.dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    family: str
    passed: bool
    reasons: tuple[str, ...] = ()

    @property
    def intended_reason(self) -> str | None:
        return self.reasons[0] if self.reasons else None
