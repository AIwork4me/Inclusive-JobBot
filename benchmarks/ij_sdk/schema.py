"""IJ-SDK-1.1 P4A (D06): strict JSON-Schema subset validator for tool arguments.

Zero third-party dependencies, so every SDK environment validates with the
same code. Two rules make it safe to rely on:

1. A tool schema may only use the keywords below. Anything else is rejected
   when the tool is registered (``lint_schema``), because a constraint the
   gateway cannot enforce must not look enforced.
2. Validation is exact: no coercion, no ignored keys. JSON booleans are not
   numbers even though ``bool`` subclasses ``int`` in Python.

Supported keywords:
    type (object, array, string, integer, number, boolean, null),
    properties, required, additionalProperties (must be false), items,
    enum, const, minimum, maximum, exclusiveMinimum, exclusiveMaximum,
    minLength, maxLength, minItems, maxItems, pattern,
    anyOf, oneOf, allOf, description, title
"""

from __future__ import annotations

import json
import re
from typing import Any

TYPES = ("object", "array", "string", "integer", "number", "boolean", "null")
KEYWORDS = {
    "type", "properties", "required", "additionalProperties", "items", "enum", "const",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength",
    "minItems", "maxItems", "pattern", "anyOf", "oneOf", "allOf", "description", "title",
}
COMBINATORS = ("anyOf", "oneOf", "allOf")


class SchemaError(ValueError):
    """The schema itself is invalid or uses something this validator cannot enforce."""


def canonical_json(value: Any) -> str:
    """Deterministic JSON text: sorted keys, no insignificant whitespace."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def lint_schema(schema: Any, path: str = "$") -> list[str]:
    """Return the reasons ``schema`` cannot be enforced here (empty list = usable)."""
    errors: list[str] = []
    if not isinstance(schema, dict):
        return [f"{path}: schema must be an object, got {type(schema).__name__}"]
    unknown = sorted(set(schema) - KEYWORDS)
    if unknown:
        errors.append(f"{path}: unsupported keyword(s) {unknown}")
    declared = schema.get("type")
    if declared is not None:
        allowed = declared if isinstance(declared, list) else [declared]
        for name in allowed:
            if name not in TYPES:
                errors.append(f"{path}: unsupported type {name!r}")
    describes_object = "object" in (declared if isinstance(declared, list) else [declared]) if declared is not None \
        else ("properties" in schema or "required" in schema)
    if describes_object and schema.get("additionalProperties") is not False:
        errors.append(f"{path}: object schemas must declare additionalProperties: false "
                      "(open objects cannot be validated exactly)")
    if "pattern" in schema:
        try:
            re.compile(schema["pattern"])
        except re.error as exc:
            errors.append(f"{path}: pattern is not a valid regex: {exc}")
    for key in ("required",):
        value = schema.get(key)
        if value is not None and (not isinstance(value, list) or not all(isinstance(v, str) for v in value)):
            errors.append(f"{path}: {key} must be a list of strings")
    properties = schema.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            errors.append(f"{path}: properties must be an object")
        else:
            for name, sub in properties.items():
                errors.extend(lint_schema(sub, f"{path}.properties.{name}"))
            missing = sorted(set(schema.get("required") or []) - set(properties))
            if missing:
                errors.append(f"{path}: required names not declared in properties: {missing}")
    if "items" in schema:
        errors.extend(lint_schema(schema["items"], f"{path}.items"))
    for combinator in COMBINATORS:
        if combinator in schema:
            branches = schema[combinator]
            if not isinstance(branches, list) or not branches:
                errors.append(f"{path}: {combinator} must be a non-empty array")
            else:
                for index, branch in enumerate(branches):
                    errors.extend(lint_schema(branch, f"{path}.{combinator}[{index}]"))
    return errors


def enforce_schema(schema: Any, path: str = "$") -> dict:
    """Lint and return the schema, or raise. Registration-time failure is a programming error."""
    errors = lint_schema(schema, path)
    if errors:
        raise SchemaError("; ".join(errors))
    return schema


def _json_type_of(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _type_ok(value: Any, name: str) -> bool:
    actual = _json_type_of(value)
    if name == "number":
        return actual in ("integer", "number")
    if name == "integer":
        return actual == "integer" or (actual == "number" and float(value).is_integer())
    return actual == name


def _compare(value: Any, bound: Any, strict: bool, lower: bool) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or isinstance(bound, bool) \
            or not isinstance(bound, (int, float)):
        return True  # bounds only constrain numbers; non-numbers are reported by type checks
    return (value > bound if strict else value >= bound) if lower else (value < bound if strict else value <= bound)


def validate(instance: Any, schema: dict, path: str = "$") -> list[str]:
    """Return every way ``instance`` violates ``schema`` (empty list = valid)."""
    errors: list[str] = []
    if not isinstance(schema, dict):
        return [f"{path}: schema is not an object"]
    declared = schema.get("type")
    if declared is not None:
        allowed = declared if isinstance(declared, list) else [declared]
        if not any(_type_ok(instance, name) for name in allowed):
            return [f"{path}: expected {' or '.join(allowed)}, got {_json_type_of(instance)}"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: must equal {canonical_json(schema['const'])}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {canonical_json(instance)} is not one of {canonical_json(schema['enum'])}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']}")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: does not match {schema['pattern']!r}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        bounds = (("minimum", False, True), ("maximum", False, False),
                  ("exclusiveMinimum", True, True), ("exclusiveMaximum", True, False))
        for key, strict, lower in bounds:
            if key in schema and not _compare(instance, schema[key], strict, lower):
                errors.append(f"{path}: {instance} violates {key} {schema[key]}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for index, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], f"{path}[{index}]"))
    if isinstance(instance, dict):
        properties = schema.get("properties") or {}
        for name in schema.get("required") or []:
            if name not in instance:
                errors.append(f"{path}: missing required property {name!r}")
        for name, value in instance.items():
            if name in properties:
                errors.extend(validate(value, properties[name], f"{path}.{name}"))
            elif schema.get("additionalProperties", False) is False and declared in (None, "object"):
                errors.append(f"{path}: undeclared property {name!r}")
    for index, branch in enumerate(schema.get("allOf") or []):
        errors.extend(validate(instance, branch, f"{path} (allOf[{index}])"))
    for combinator in ("anyOf", "oneOf"):
        branches = schema.get(combinator)
        if branches:
            outcomes = [validate(instance, branch, path) for branch in branches]
            passed = sum(1 for outcome in outcomes if not outcome)
            needed = 1 if combinator == "anyOf" else None
            if combinator == "anyOf" and passed < 1:
                errors.append(f"{path}: matches no anyOf branch")
            if combinator == "oneOf" and passed != 1:
                errors.append(f"{path}: matches {passed} oneOf branches (exactly 1 required)")
    return errors


def first_error(errors: list[str]) -> str:
    """The single most useful violation, for model-facing error feedback."""
    return errors[0] if errors else ""
