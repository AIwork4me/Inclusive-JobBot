"""Positive and negative control battery for the N05A evaluator.

Every scoring rule maps to at least one positive and one negative control.
Each negative declares the single reason code it must fail with (controls
are single-defect: exactly one semantic error per negative), which makes
mutation tests against weakened evaluators exact: a mutant that drops a
scoring rule must wrongly accept the negative whose only reason is that
rule.

Control classes used (mission order section 5):
correct alternative representation (positive), wrong entity, wrong
polarity, wrong numeric value, invalid units, missing required slots,
extra incorrect assertions, structurally valid but semantically incorrect
actions, incorrect branch, invalid recovery, premature stop, unnecessary
continuation, wrong clarification topics.
"""
from __future__ import annotations

from .contracts import (ControlCase, Expectation, Quantity, Response,  # noqa: F401
                        SlotSpec, StatePredicate)


def case(case_id: str, family: str, control_class: str, response: Response,
         **exp) -> ControlCase:
    """Build one control case from an expectation (keyword fields) and the
    response the control submits."""
    return ControlCase(case_id, family, control_class,
                       Expectation(family, **exp), response)


def battery() -> list[ControlCase]:
    B: list[ControlCase] = []

    # -- intent ------------------------------------------------------------
    B.append(case("intent.pos", "intent", "positive",
                  Response(intent="refund_request"),
                  intent="refund_request"))
    B.append(case("intent.pos.alt_case", "intent", "positive",
                  Response(intent="Refund  Request "),   # closed-vocab folding
                  intent="refund_request"))
    B.append(case("intent.neg.wrong", "intent", "negative:INTENT_MISMATCH",
                  Response(intent="exchange_request"),
                  intent="refund_request"))

    # -- goal ----------------------------------------------------------------
    B.append(case("goal.pos", "goal", "positive",
                  Response(goal_type="issue_refund", goal_params=("ORD-1042",)),
                  goal_type="issue_refund", goal_params=("ORD-1042",)))
    B.append(case("goal.neg.wrong_params", "goal", "negative:GOAL_MISMATCH",
                  Response(goal_type="issue_refund", goal_params=("ORD-1043",)),
                  goal_type="issue_refund", goal_params=("ORD-1042",)))

    # -- tool_selection --------------------------------------------------------
    B.append(case("tool.pos", "tool_selection", "positive",
                  Response(tool="orders.get_refund_eligibility"),
                  tool="orders.get_refund_eligibility"))
    B.append(case("tool.neg.wrong_tool", "tool_selection", "negative:TOOL_MISMATCH",
                  Response(tool="orders.cancel_order"),
                  tool="orders.get_refund_eligibility"))

    # -- action_representation ---------------------------------------------
    slots = (SlotSpec("order_id", "entity", "ORD-1042"),
             SlotSpec("amount", "quantity", 120.0, unit="CNY"))
    ok_args = {"order_id": "ORD-1042", "amount": {"value": 120.0, "unit": "CNY"}}
    B.append(case("action.pos", "action_representation", "positive",
                  Response(tool="refunds.submit", args=ok_args),
                  tool="refunds.submit", slots=slots))
    # correct alternative representation: folded label + int-valued amount
    B.append(case("action.pos.alt_repr", "action_representation", "positive",
                  Response(tool="Refunds.Submit",
                           args={"order_id": " ord-1042 ",
                                 "amount": {"value": 120, "unit": "CNY"}}),
                  tool="refunds.submit", slots=slots))
    # structurally valid, semantically wrong tool
    B.append(case("action.neg.wrong_tool", "action_representation",
                  "negative:TOOL_MISMATCH",
                  Response(tool="orders.cancel_order", args=ok_args),
                  tool="refunds.submit", slots=slots))
    # structurally valid, wrong entity in an argument
    B.append(case("action.neg.wrong_entity", "action_representation",
                  "negative:ENTITY_MISMATCH",
                  Response(tool="refunds.submit",
                           args={"order_id": "ORD-9999",
                                 "amount": {"value": 120.0, "unit": "CNY"}}),
                  tool="refunds.submit", slots=slots))
    # missing required slot
    B.append(case("action.neg.missing_slot", "action_representation",
                  "negative:MISSING_SLOT",
                  Response(tool="refunds.submit",
                           args={"order_id": "ORD-1042"}),
                  tool="refunds.submit", slots=slots))
    # extra incorrect assertion smuggled alongside a valid action
    B.append(case("action.neg.extra_assertion", "action_representation",
                  "negative:EXTRA_ASSERTION",
                  Response(tool="refunds.submit", args=ok_args,
                           extra_assertions=("customer.tier=gold",)),
                  tool="refunds.submit", slots=slots))

    # -- entity_reference ------------------------------------------------------
    B.append(case("entity.pos", "entity_reference", "positive",
                  Response(entities=("ORD-1042", "C-9")),
                  entity_ids=("ORD-1042", "C-9")))
    B.append(case("entity.pos.alt_case", "entity_reference", "positive",
                  Response(entities=("ord-1042", "c-9")),
                  entity_ids=("ORD-1042", "C-9")))
    B.append(case("entity.neg.wrong_entity", "entity_reference",
                  "negative:ENTITY_MISMATCH",
                  Response(entities=("ORD-1043", "C-9")),
                  entity_ids=("ORD-1042", "C-9")))
    B.append(case("entity.neg.extra", "entity_reference",
                  "negative:EXTRA_ASSERTION",
                  Response(entities=("ORD-1042", "C-9", "C-77")),
                  entity_ids=("ORD-1042", "C-9")))

    # -- slot_value -----------------------------------------------------------
    sslots = (SlotSpec("order_id", "entity", "ORD-1042"),
              SlotSpec("accept", "boolean", True),
              SlotSpec("reason", "enum", "damaged_item"))
    B.append(case("slot.pos", "slot_value", "positive",
                  Response(args={"order_id": "ORD-1042", "accept": True,
                                 "reason": "Damaged Item"}),
                  slots=sslots))
    # wrong polarity on the boolean slot
    B.append(case("slot.neg.polarity", "slot_value", "negative:VALUE_MISMATCH",
                  Response(args={"order_id": "ORD-1042", "accept": False,
                                 "reason": "damaged_item"}),
                  slots=sslots))
    B.append(case("slot.neg.missing", "slot_value", "negative:MISSING_SLOT",
                  Response(args={"order_id": "ORD-1042", "accept": True}),
                  slots=sslots))
    B.append(case("slot.neg.wrong_enum", "slot_value", "negative:VALUE_MISMATCH",
                  Response(args={"order_id": "ORD-1042", "accept": True,
                                 "reason": "wrong_item"}),
                  slots=sslots))
    B.append(case("slot.neg.extra", "slot_value", "negative:EXTRA_ASSERTION",
                  Response(args={"order_id": "ORD-1042", "accept": True,
                                 "reason": "damaged_item", "priority": "asap"}),
                  slots=sslots))

    # -- numeric_value_unit ------------------------------------------------------
    B.append(case("num.pos", "numeric_value_unit", "positive",
                  Response(args={"value": 120.0, "unit": "CNY"}),
                  quantity=Quantity(120.0, "CNY")))
    # correct alternative representation: convertible unit
    B.append(case("num.pos.convert", "numeric_value_unit", "positive",
                  Response(args={"value": 1500, "unit": "m"}),
                  quantity=Quantity(1.5, "km")))
    B.append(case("num.neg.wrong_value", "numeric_value_unit",
                  "negative:VALUE_MISMATCH",
                  Response(args={"value": 125.0, "unit": "CNY"}),
                  quantity=Quantity(120.0, "CNY")))
    B.append(case("num.neg.unit_mismatch", "numeric_value_unit",
                  "negative:UNIT_MISMATCH",
                  Response(args={"value": 120.0, "unit": "USD"}),
                  quantity=Quantity(120.0, "CNY")))
    B.append(case("num.neg.unit_invalid", "numeric_value_unit",
                  "negative:UNIT_INVALID",
                  Response(args={"value": 120.0, "unit": "yuán"}),
                  quantity=Quantity(120.0, "CNY")))
    B.append(case("num.neg.type", "numeric_value_unit",
                  "negative:TYPE_MISMATCH",
                  Response(args={"value": "120", "unit": "CNY"}),
                  quantity=Quantity(120.0, "CNY")))

    # -- state_interpretation ------------------------------------------------
    pred = StatePredicate("ORD-1042", "refund_status", "eq", "approved")
    B.append(case("state.pos", "state_interpretation", "positive",
                  Response(state_predicates=(pred,)),
                  state_predicates=(pred,)))
    neg_pred = StatePredicate("ORD-1042", "refund_status", "ne", "approved")
    B.append(case("state.neg.wrong_entity", "state_interpretation",
                  "negative:ENTITY_MISMATCH",
                  Response(state_predicates=(
                      StatePredicate("ORD-1043", "refund_status", "eq", "approved"),)),
                  state_predicates=(pred,)))
    B.append(case("state.neg.wrong_polarity", "state_interpretation",
                  "negative:VALUE_MISMATCH",
                  Response(state_predicates=(neg_pred,)),
                  state_predicates=(pred,)))

    # -- conditional_branch ------------------------------------------------------
    B.append(case("branch.pos", "conditional_branch", "positive",
                  Response(branch="requires_manager_approval"),
                  branch="requires_manager_approval"))
    B.append(case("branch.neg.wrong", "conditional_branch",
                  "negative:BRANCH_MISMATCH",
                  Response(branch="auto_approve"),
                  branch="requires_manager_approval"))

    # -- recovery_action ----------------------------------------------------------
    B.append(case("recovery.pos", "recovery_action", "positive",
                  Response(recovery="requery_missing_slot"),
                  recovery="requery_missing_slot"))
    B.append(case("recovery.neg.invalid", "recovery_action",
                  "negative:RECOVERY_INVALID",
                  Response(recovery="retry_same_call_forever"),
                  recovery="requery_missing_slot"))

    # -- stop_continue ---------------------------------------------------------
    B.append(case("stop.pos", "stop_continue", "positive",
                  Response(decision="continue"),
                  decision="continue"))
    B.append(case("stop.neg.premature", "stop_continue",
                  "negative:DECISION_MISMATCH",
                  Response(decision="stop"),          # premature stop
                  decision="continue"))
    B.append(case("stop.neg.unnecessary", "stop_continue",
                  "negative:DECISION_MISMATCH",
                  Response(decision="continue"),      # unnecessary continuation
                  decision="stop"))

    # -- clarification -----------------------------------------------------------
    B.append(case("clar.pos", "clarification", "positive",
                  Response(clarification_topics=("order_id", "refund_reason")),
                  clarification_topics=frozenset({"order_id", "refund_reason"})))
    B.append(case("clar.pos.alt_case", "clarification", "positive",
                  Response(clarification_topics=("Order ID", "Refund Reason")),
                  clarification_topics=frozenset({"order_id", "refund_reason"})))
    B.append(case("clar.neg.wrong_topics", "clarification",
                  "negative:CLARIFICATION_MISMATCH",
                  Response(clarification_topics=("order_id",)),
                  clarification_topics=frozenset({"order_id", "refund_reason"})))

    return B
