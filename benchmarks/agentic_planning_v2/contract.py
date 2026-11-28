"""Version 2 finite conditional plans, evaluated only against host observations."""
from decimal import Decimal
from enum import Enum
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from benchmarks.tool_calling_v2.oracle import equal

SCHEMA = Path(__file__).resolve().parents[2] / "schemas/conditional_plan_v2.schema.json"
VALIDATOR = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf8")))
TYPED_SCHEMA = SCHEMA.with_name("conditional_plan_v2_typed.schema.json")
TYPED_VALIDATOR = Draft202012Validator(json.loads(TYPED_SCHEMA.read_bytes()))


def typed(contract):
    return any("input_schema" in spec for spec in contract["tools"].values())


UNKNOWN = object()
ABSENT = object()


class FactKind(str, Enum):
    PUBLIC = "PUBLIC_FACT"
    OBSERVED = "OBSERVED_FACT"
    DERIVED = "DERIVED_FACT"
    UNKNOWN = "UNKNOWN_FACT"
    EVENT = "EXTERNAL_EVENT"
    INVALIDATED = "INVALIDATED_FACT"
    PRIVATE = "PRIVATE_ORACLE_FACT"


def value(term, observations):
    if not isinstance(term, dict):
        return term
    if "literal" in term:
        return term["literal"]
    if "first" in term:
        for ref in term["first"]:
            item = value(ref, observations)
            if item is not UNKNOWN and item is not ABSENT:
                return item
        return UNKNOWN
    if "if" in term:
        condition = predicate(term["if"], observations)
        return UNKNOWN if condition is UNKNOWN else term["then" if condition else "else"]
    source = term["from"]
    if source not in observations:
        return UNKNOWN
    return observations[source].get(term["field"], ABSENT)


def predicate(expr, observations):
    """Strong Kleene Boolean operators. Missing fields on observed objects are known absent."""
    if isinstance(expr, bool):
        return expr
    op = expr["op"]
    if op == "exists":
        item = value(expr["ref"], observations)
        return UNKNOWN if item is UNKNOWN else item is not ABSENT
    if op == "not":
        result = predicate(expr["arg"], observations)
        return UNKNOWN if result is UNKNOWN else not result
    if op in ("and", "or"):
        values = [predicate(arg, observations) for arg in expr["args"]]
        decisive = op == "or"
        if decisive in values:
            return decisive
        return UNKNOWN if UNKNOWN in values else not decisive
    left = value(expr["left"], observations)
    right = value(expr["right"], observations)
    if UNKNOWN in (left, right) or ABSENT in (left, right):
        return UNKNOWN
    if op == "eq":
        return equal(left, right)
    if type(left) not in (int, float, Decimal) or type(right) not in (int, float, Decimal):
        return UNKNOWN
    left, right = Decimal(str(left)), Decimal(str(right))
    return {"lt": left < right, "le": left <= right, "gt": left > right, "ge": left >= right}[op]


def references(tree):
    if isinstance(tree, dict):
        if tree.keys() == {"literal"}:
            return
        if tree.keys() == {"from", "field"}:
            yield tree["from"], tree["field"]
        else:
            for item in tree.values():
                yield from references(item)
    elif isinstance(tree, list):
        for item in tree:
            yield from references(item)
