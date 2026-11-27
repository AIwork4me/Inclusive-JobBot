"""Positive and negative control battery for the cognitive evaluator
(contract v2, N05A-R).

Every scoring rule maps to at least one positive and one negative control.
Each negative declares the single reason code it must fail with (controls
are single-defect: exactly one semantic error per negative), which makes
mutation tests against weakened evaluators exact.

v2 changes (EV01-EV07):
- entity ids and tool ids are EXACT identity: the v1 folded-entity and
  folded-tool "alternative representation" positives became negatives
  (case_variant, underscore_space) per EV04;
- new controls: missing/duplicate/contradictory predicates, reordered
  predicates, extra out-of-scope predicate (EV01); undeclared arguments,
  unauthorized consequential option, declared optional argument,
  duplicate raw keys (EV02); substring trap (EV04); unit-missing scalar
  and publicly-declared unit scalar (EV05); PARSE_INVALID controls
  including empty intent (EV07);
- TRUTH_CONTROLS: predicate_truth controls against independent world
  observations, incl. the ordering-polarity trap that detects
  inequality-flip mutants (EV03/EV06).
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

    # -- intent ------------------------------------------------------------ (EV07: PARSE_INVALID control)
    B.append(case("intent.pos", "intent", "positive",
                  Response(intent="refund_request"),
                  intent="refund_request"))
    B.append(case("intent.pos.alt_case", "intent", "positive",
                  Response(intent="Refund  Request"),   # closed-vocab folding
                  intent="refund_request"))
    B.append(case("intent.neg.wrong", "intent", "negative:INTENT_MISMATCH",
                  Response(intent="exchange_request"),
                  intent="refund_request"))
    B.append(case("intent.neg.parse_invalid", "intent", "negative:PARSE_INVALID",
                  Response(),                            # no intent at all
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
    B.append(case("tool.neg.underscore_space", "tool_selection",
                  "negative:TOOL_MISMATCH",                    # EV04
                  Response(tool="adjust stock"),
                  tool="adjust_stock"))

    # -- action_representation --------------------------------------------- (EV02)
    slots = (SlotSpec("order_id", "entity", "ORD-1042"),
             SlotSpec("amount", "quantity", 120.0, unit="CNY"))
    ok_args = {"order_id": "ORD-1042", "amount": {"value": 120.0, "unit": "CNY"}}
    B.append(case("action.pos", "action_representation", "positive",
                  Response(tool="refunds.submit", args=ok_args),
                  tool="refunds.submit", slots=slots))
    # correct alternative representation: int-valued amount in the declared
    # quantity shape (tool and entity ids stay exact per EV04)
    B.append(case("action.pos.alt_repr", "action_representation", "positive",
                  Response(tool="refunds.submit",
                           args={"order_id": "ORD-1042",
                                 "amount": {"value": 120, "unit": "CNY"}}),
                  tool="refunds.submit", slots=slots))
    # declared optional argument supplied correctly
    opt_slots = slots + (SlotSpec("notify_channel", "enum", "email", optional=True),)
    B.append(case("action.pos.optional_arg", "action_representation", "positive",
                  Response(tool="refunds.submit",
                           args={**ok_args, "notify_channel": "Email"}),
                  tool="refunds.submit", slots=opt_slots))
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
    # substring trap: "ORD-1042X" contains the expected id (EV04/EV06)
    B.append(case("action.neg.entity_substring_trap", "action_representation",
                  "negative:ENTITY_MISMATCH",
                  Response(tool="refunds.submit",
                           args={"order_id": "ORD-1042X",
                                 "amount": {"value": 120.0, "unit": "CNY"}}),
                  tool="refunds.submit", slots=slots))
    # missing required slot
    B.append(case("action.neg.missing_slot", "action_representation",
                  "negative:MISSING_SLOT",
                  Response(tool="refunds.submit",
                           args={"order_id": "ORD-1042"}),
                  tool="refunds.submit", slots=slots))
    # unknown argument key smuggled alongside a valid action (EV02)
    B.append(case("action.neg.undeclared_arg", "action_representation",
                  "negative:ARGUMENT_UNDECLARED",
                  Response(tool="refunds.submit",
                           args={**ok_args, "customer_tier": "gold"}),
                  tool="refunds.submit", slots=slots))
    # consequential unauthorized option (EV02)
    B.append(case("action.neg.unauthorized_option", "action_representation",
                  "negative:ARGUMENT_UNDECLARED",
                  Response(tool="refunds.submit",
                           args={**ok_args, "force_skip_policy": True}),
                  tool="refunds.submit", slots=slots))
    # extra incorrect assertion smuggled alongside a valid action
    B.append(case("action.neg.extra_assertion", "action_representation",
                  "negative:EXTRA_ASSERTION",
                  Response(tool="refunds.submit", args=ok_args,
                           extra_assertions=("customer.tier=gold",)),
                  tool="refunds.submit", slots=slots))
    # duplicate keys in the raw structured output (EV02)
    B.append(case("action.neg.duplicate_raw_key", "action_representation",
                  "negative:PARSE_INVALID",
                  Response(tool="refunds.submit", args=ok_args,
                           raw=('{"order_id": "ORD-1042", '
                                '"order_id": "ORD-9999", "amount": 120}')),
                  tool="refunds.submit", slots=slots))

    # -- entity_reference ------------------------------------------------------
    B.append(case("entity.pos", "entity_reference", "positive",
                  Response(entities=("ORD-1042", "C-9")),
                  entity_ids=("ORD-1042", "C-9")))
    # EV04: case folding no longer merges entity ids - former alt_case
    # positive is now a collision negative
    B.append(case("entity.neg.case_variant", "entity_reference",
                  "negative:ENTITY_MISMATCH",
                  Response(entities=("ord-1042", "c-9")),
                  entity_ids=("ORD-1042", "C-9")))
    B.append(case("entity.neg.wrong_entity", "entity_reference",
                  "negative:ENTITY_MISMATCH",
                  Response(entities=("ORD-1043", "C-9")),
                  entity_ids=("ORD-1042", "C-9")))
    B.append(case("entity.neg.substring_trap", "entity_reference",
                  "negative:ENTITY_MISMATCH",                 # EV04/EV06
                  Response(entities=("ORD-1042", "C-9X")),
                  entity_ids=("ORD-1042", "C-9")))
    B.append(case("entity.neg.extra", "entity_reference",
                  "negative:EXTRA_ASSERTION",
                  Response(entities=("ORD-1042", "C-9", "C-77")),
                  entity_ids=("ORD-1042", "C-9")))

    # -- slot_value ----------------------------------------------------------- (EV02/EV05)
    sslots = (SlotSpec("order_id", "entity", "ORD-1042"),
              SlotSpec("accept", "boolean", True),
              SlotSpec("reason", "enum", "damaged_item"))
    B.append(case("slot.pos", "slot_value", "positive",
                  Response(args={"order_id": "ORD-1042", "accept": True,
                                 "reason": "Damaged Item"}),
                  slots=sslots))
    # EV05: publicly declared unit lets a bare scalar inherit it
    unit_slots = (SlotSpec("amount", "quantity", 120.0, unit="CNY",
                           unit_publicly_declared=True),)
    B.append(case("slot.pos.public_unit", "slot_value", "positive",
                  Response(args={"amount": 120.0}),
                  slots=unit_slots))
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
    B.append(case("slot.neg.undeclared", "slot_value",
                  "negative:ARGUMENT_UNDECLARED",              # EV02
                  Response(args={"order_id": "ORD-1042", "accept": True,
                                 "reason": "damaged_item", "priority": "asap"}),
                  slots=sslots))
    # EV05: scalar without public declaration must not inherit the unit
    hidden_unit_slots = (SlotSpec("amount", "quantity", 120.0, unit="CNY"),)
    B.append(case("slot.neg.unit_missing", "slot_value",
                  "negative:UNIT_MISSING",
                  Response(args={"amount": 120.0}),
                  slots=hidden_unit_slots))

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
    B.append(case("num.neg.malformed_raw", "numeric_value_unit",
                  "negative:PARSE_INVALID",
                  Response(raw='{"value": 120.0, "value": 125.0}'),
                  quantity=Quantity(120.0, "CNY")))

    # -- state_interpretation ------------------------------------------------ (EV01/EV03)
    P_SHIP = StatePredicate("ORD-1042", "ship_status", "eq", "shipped")
    P_PAID = StatePredicate("ORD-1042", "payment_status", "eq", "paid")
    P_AGE = StatePredicate("ORD-1042", "days_since_order", "le", 30)
    B.append(case("state.pos", "state_interpretation", "positive",
                  Response(state_predicates=(P_SHIP,)),
                  state_predicates=(P_SHIP,)))
    B.append(case("state.pos.multi", "state_interpretation", "positive",
                  Response(state_predicates=(P_SHIP, P_PAID, P_AGE)),
                  state_predicates=(P_SHIP, P_PAID, P_AGE)))
    B.append(case("state.pos.reordered", "state_interpretation", "positive",
                  Response(state_predicates=(P_AGE, P_PAID, P_SHIP)),
                  state_predicates=(P_SHIP, P_PAID, P_AGE)))
    B.append(case("state.neg.wrong_entity", "state_interpretation",
                  "negative:ENTITY_MISMATCH",
                  Response(state_predicates=(
                      StatePredicate("ORD-1043", "ship_status", "eq", "shipped"),)),
                  state_predicates=(P_SHIP,)))
    neg_pred = StatePredicate("ORD-1042", "refund_status", "ne", "approved")
    B.append(case("state.neg.wrong_polarity", "state_interpretation",
                  "negative:VALUE_MISMATCH",
                  Response(state_predicates=(neg_pred,)),
                  state_predicates=(
                      StatePredicate("ORD-1042", "refund_status", "eq", "approved"),)))
    B.append(case("state.neg.missing_final", "state_interpretation",
                  "negative:MISSING_PREDICATE",
                  Response(state_predicates=(P_SHIP,)),
                  state_predicates=(P_SHIP, P_PAID)))
    B.append(case("state.neg.missing_middle", "state_interpretation",
                  "negative:MISSING_PREDICATE",
                  Response(state_predicates=(P_SHIP, P_AGE)),
                  state_predicates=(P_SHIP, P_PAID, P_AGE)))
    B.append(case("state.neg.duplicate", "state_interpretation",
                  "negative:DUPLICATE_PREDICATE",
                  Response(state_predicates=(P_SHIP, P_PAID, P_SHIP)),
                  state_predicates=(P_SHIP, P_PAID)))
    B.append(case("state.neg.contradictory", "state_interpretation",
                  "negative:DUPLICATE_PREDICATE",
                  Response(state_predicates=(
                      P_SHIP, P_PAID,
                      StatePredicate("ORD-1042", "payment_status", "ne", "paid"))),
                  state_predicates=(P_SHIP, P_PAID)))
    B.append(case("state.neg.extra", "state_interpretation",
                  "negative:EXTRA_ASSERTION",
                  Response(state_predicates=(
                      P_SHIP, P_PAID,
                      StatePredicate("ORD-9999", "ship_status", "eq", "lost"))),
                  state_predicates=(P_SHIP, P_PAID)))
    B.append(case("state.neg.type_invalid_value", "state_interpretation",
                  "negative:TYPE_MISMATCH",
                  Response(state_predicates=(
                      StatePredicate("ORD-1042", "days_since_order",
                                     "le", "thirty"),)),
                  state_predicates=(P_AGE,)))

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


# -- predicate-truth controls (EV03/EV06) --------------------------------------
# These exercise ``comparators.predicate_truth`` against independent world
# observations. The ordering-polarity trap (fliptrap) is what detects
# inequality-flip mutants: the flipped comparator accepts a claim that is
# demonstrably false against the observed world.

TRUTH_CONTROLS: list[dict] = [
    {"name": "truth.eq_boundary",
     "pred": StatePredicate("INV-7", "qty", "eq", 5),
     "world": {("INV-7", "qty"): 5}, "expect": []},
    {"name": "truth.eq_false",
     "pred": StatePredicate("INV-7", "qty", "eq", 5),
     "world": {("INV-7", "qty"): 6}, "expect": ["VALUE_MISMATCH"]},
    {"name": "truth.ne_true",
     "pred": StatePredicate("INV-7", "qty", "ne", 6),
     "world": {("INV-7", "qty"): 5}, "expect": []},
    {"name": "truth.gt_boundary_false",
     "pred": StatePredicate("INV-7", "qty", "gt", 5),
     "world": {("INV-7", "qty"): 5}, "expect": ["VALUE_MISMATCH"]},
    {"name": "truth.ge_boundary_true",
     "pred": StatePredicate("INV-7", "qty", "ge", 5),
     "world": {("INV-7", "qty"): 5}, "expect": []},
    {"name": "truth.lt_true",
     "pred": StatePredicate("INV-7", "qty", "lt", 5.0001),
     "world": {("INV-7", "qty"): 5}, "expect": []},
    {"name": "truth.le_true",
     "pred": StatePredicate("INV-7", "qty", "le", 5.0001),
     "world": {("INV-7", "qty"): 5}, "expect": []},
    {"name": "truth.fliptrap_le",
     "pred": StatePredicate("ORD-1042", "days_since_order", "le", 30),
     "world": {("ORD-1042", "days_since_order"): 45},
     "expect": ["VALUE_MISMATCH"]},
    {"name": "truth.type_invalid_observed",
     "pred": StatePredicate("INV-7", "qty", "gt", 100),
     "world": {("INV-7", "qty"): "high"}, "expect": ["TYPE_MISMATCH"]},
    {"name": "truth.unit_conversion",
     "pred": StatePredicate("ORD-1042", "weight", "le", 2.0, unit="km"),
     "world": {("ORD-1042", "weight"): {"value": 1500.0, "unit": "m"}},
     "expect": []},
    {"name": "truth.unit_missing_observation",
     "pred": StatePredicate("ORD-1042", "total", "ge", 100.0, unit="CNY"),
     "world": {("ORD-1042", "total"): 120.0}, "expect": ["UNIT_MISSING"]},
    {"name": "truth.unknown_identity",
     "pred": StatePredicate("ORD-8888", "ship_status", "eq", "shipped"),
     "world": {("ORD-1042", "ship_status"): "shipped"},
     "expect": ["ENTITY_MISMATCH"]},
]
