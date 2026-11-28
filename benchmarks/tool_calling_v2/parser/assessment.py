"""Grade native parser semantics and strict arguments as independent layers."""

from __future__ import annotations

import json
from decimal import Decimal

from jsonschema import Draft202012Validator

from model_gateway.errors import GatewayError
from model_gateway.strict_json import strict_object


def close_objects(schema):
    """Fixture schemas may predate the gateway's closed-object contract."""
    schema = dict(schema)
    if "properties" in schema:
        schema["properties"] = {key: close_objects(value) for key, value in schema["properties"].items()}
        schema.setdefault("additionalProperties", False)
    if "items" in schema:
        schema["items"] = close_objects(schema["items"])
    return schema


def validators_for(tools):
    return {tool["function"]["name"]: Draft202012Validator(close_objects(tool["function"]["parameters"]))
            for tool in tools}


def numeric_json(value):
    return json.loads(json.dumps(value), parse_float=Decimal)


def typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(typed_equal(value, right[key]) for key, value in left.items())
    if isinstance(left, list):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def raw_calls(message):
    return [(call["function"]["name"], call["function"]["arguments"]) for call in message.get("tool_calls") or []]


def native_observation(row, *, stream=False):
    if stream:
        if row.get("stream_rejected"):
            return {"parser_rejected": True}
        message = row["stream_message"]
    else:
        if row.get("parser_rejected"):
            return {"parser_rejected": True}
        message = row["message"]
    return {"calls": raw_calls(message), "content": message.get("content") or "",
            "reasoning": message.get("reasoning_content") or ""}


def assess(fixture, row, validators):
    """Measure parser output, strict argument checks and stream parity independently."""
    full = native_observation(row)
    stream = native_observation(row, stream=True)
    calls = full.get("calls") or []
    result = {}
    if fixture["expect"] == "reject" and fixture["layer"] == "native":
        result["native"] = "FAIL" if calls else "PASS"
    elif fixture["expect"] == "exact":
        try:
            observed = [{"name": name, "arguments": strict_object(args)} for name, args in calls]
        except GatewayError:
            observed = None
        expected = numeric_json(fixture["calls"])
        result["native"] = (
            "PASS" if not full.get("parser_rejected") and typed_equal(observed, expected)
            and full.get("reasoning", "").strip() == fixture.get("reasoning", "")
            and ("content" not in fixture or fixture["content"] == full.get("content"))
            else "FAIL"
        )
    else:
        result["native"] = "NOT_RUN"

    def all_valid(observation):
        try:
            return all(name in validators and validators[name].is_valid(strict_object(args))
                       for name, args in observation["calls"])
        except GatewayError:
            return False

    expect_allowed = fixture["expect"] == "exact"
    safety = []
    for observation in (full, stream):
        if expect_allowed:
            safety.append(not observation.get("parser_rejected")
                          and len(observation["calls"]) == len(fixture["calls"]) and all_valid(observation))
        else:
            safety.append(not observation.get("calls") or not all_valid(observation))
    result["strict_arguments"] = "PASS" if all(safety) else "FAIL"
    result["parser_stream_parity"] = "PASS" if full == stream else "FAIL"
    return result
