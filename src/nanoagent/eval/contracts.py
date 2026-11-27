"""Typed evaluation contracts for cognitive evaluator qualification (N05A).

Families: intent, goal, tool_selection, action_representation,
entity_reference, slot_value, numeric_value_unit, state_interpretation,
conditional_branch, recovery_action, stop_continue, clarification.

Design rules (mission order section 5):
- Deterministic semantic comparisons; substring matching is never the
  primary correctness method (text is compared only through closed
  vocabularies and canonical ids).
- Expected results live on the EVALUATOR side only. The tested runtime
  submits a bare ``Response``; it never receives an EvalCase, expectation
  or reason code. The public entry point is
  ``CognitiveEvaluator.evaluate(case_id, response)``.
- Every scoring rule maps to positive and negative controls
  (``nanoagent.eval.controls``); every negative control carries the reason
  code it must fail with, so 'fails for the intended reason' is checkable.
"""
from __future__ import annotations

import dataclasses
from typing import Any

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
REASON_CODES = (
    "INTENT_MISMATCH", "GOAL_MISMATCH",
    "TOOL_MISMATCH", "ARGUMENT_MISMATCH",
    "ENTITY_MISMATCH", "VALUE_MISMATCH", "UNIT_MISMATCH", "UNIT_INVALID",
    "TYPE_MISMATCH", "MISSING_SLOT", "EXTRA_ASSERTION",
    "BRANCH_MISMATCH", "RECOVERY_INVALID", "DECISION_MISMATCH",
    "CLARIFICATION_MISMATCH", "PARSE_INVALID",
)


@dataclasses.dataclass(frozen=True)
class Quantity:
    """A numeric value with a unit from the closed unit registry."""
    value: float
    unit: str


@dataclasses.dataclass(frozen=True)
class SlotSpec:
    """One expected slot: name, closed type, expected value (and unit for
    quantities). ``polarity`` applies to boolean slots."""
    name: str
    type: str                  # entity | quantity | text | enum | boolean
    expected: Any
    unit: str | None = None


@dataclasses.dataclass(frozen=True)
class StatePredicate:
    """Typed claim about business state (entity, property, operator, value)."""
    entity_id: str
    property: str
    op: str                    # eq | ne | gt | ge | lt | le
    value: Any
    unit: str | None = None


@dataclasses.dataclass(frozen=True)
class Expectation:
    """Semantic ground truth for one evaluation case. Only the fields
    relevant to the family are populated (family-checked at construction)."""
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

    def __post_init__(self):
        if self.family not in FAMILIES:
            raise ValueError(f"unknown family: {self.family}")


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
