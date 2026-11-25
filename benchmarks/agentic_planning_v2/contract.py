"""Version 2 finite conditional plans, evaluated only against host observations."""
from enum import Enum
import json
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA = Path(__file__).resolve().parents[2] / "schemas/conditional_plan_v2.schema.json"
VALIDATOR = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf8")))
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
        return type(left) is type(right) and left == right
    if type(left) is not int or type(right) is not int:
        return UNKNOWN
    return {"lt": left < right, "le": left <= right, "gt": left > right, "ge": left >= right}[op]


def references(tree):
    if isinstance(tree, dict):
        if tree.keys() == {"from", "field"}:
            yield tree["from"], tree["field"]
        else:
            for item in tree.values():
                yield from references(item)
    elif isinstance(tree, list):
        for item in tree:
            yield from references(item)
