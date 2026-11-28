"""N02R semantic scoring via the qualified cognitive evaluator (contract
v2, N05AR). Deterministic; expectations evaluator-side only.
"""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from nanoagent.eval.comparators import evaluate_family  # noqa: E402
from nanoagent.eval.contracts import (Expectation, Response,  # noqa: E402
                                      SlotSpec)

_QUANTITY_UNITS = {"CNY", "USD", "EUR", "pcs", "kg"}


def expectation_for(task: dict) -> Expectation:
    fam = task["family"]
    exp_args = task["expected"]["args"] if "args" in task["expected"] else {}
    if fam == "tool_selection":
        return Expectation("tool_selection", tool=task["expected"]["tool"])
    if fam == "slot_extraction":
        k = task["schema_hint"]
        slot, stype = k["slot"], k["slot_type"]
        if stype == "quantity":
            v = exp_args[slot]
            return Expectation("slot_value", slots=(
                SlotSpec(slot, "quantity", float(v["value"]), unit=v["unit"],
                         unit_publicly_declared=False),))
        return Expectation("slot_value", slots=(
            SlotSpec(slot, stype, exp_args[slot]),))
    if fam == "structured_action":
        k = task["schema_hint"]
        slots = []
        for s in k["slots"]:
            v = exp_args[s]
            if isinstance(v, dict):          # quantity {"value","unit"}
                slots.append(SlotSpec(s, "quantity", float(v["value"]),
                                      unit=v["unit"], unit_publicly_declared=False))
            elif s == "reason":
                slots.append(SlotSpec(s, "enum", v))
            else:
                slots.append(SlotSpec(s, "entity", v))
        return Expectation("action_representation",
                           tool=task["expected"]["tool"], slots=tuple(slots))
    if fam == "enumerated_action":
        return Expectation("intent", intent=task["expected"]["action_label"])
    if fam == "conditional_branch":
        return Expectation("conditional_branch", branch=task["expected"]["branch"])
    if fam == "stop_continue":
        return Expectation("stop_continue", decision=task["expected"]["decision"])
    raise ValueError(fam)


def score(task: dict, payload: dict | None) -> dict:
    """Returns {semantic_correct, reasons, tool_correct, args_correct}."""
    if payload is None:
        return {"semantic_correct": False, "reasons": ["PARSE_INVALID"],
                "tool_correct": False, "args_correct": False}
    fam = task["family"]
    fields = {k: v for k, v in payload.items() if k in
              ("tool", "args", "intent", "branch", "decision")}
    reasons = evaluate_family(expectation_for(task), Response(**fields))
    tool_correct = ("TOOL_MISMATCH" not in reasons) if (
        fam in ("tool_selection", "structured_action")) else True
    args_correct = not any(r in reasons for r in
                           ("MISSING_SLOT", "ENTITY_MISMATCH", "VALUE_MISMATCH",
                            "UNIT_MISMATCH", "UNIT_MISSING", "UNIT_INVALID",
                            "TYPE_MISMATCH", "ARGUMENT_UNDECLARED"))
    return {"semantic_correct": not reasons, "reasons": reasons,
            "tool_correct": tool_correct, "args_correct": args_correct}
