"""Strict JSON-schema-like argument validation (stdlib only).

NA-D08 repair. The supported subset is explicit and complete: every keyword
accepted here is actually enforced, and any keyword outside the subset is
rejected at registration time (``validate_tool_schema``) so a semantic
constraint can never be silently ignored. A trusted standard validator
(``jsonschema``) is listed in requirements.lock but is not installed in this
runtime environment; per the mission order the limited-validator branch
applies: fail closed at registration.
"""
from __future__ import annotations

import math
import re
from typing import Any

_TYPES = {"string": str, "number": (int, float), "integer": int,
          "boolean": bool, "object": dict, "array": list}

# Keywords enforced by this module. Anything else in a subschema is rejected
# by validate_tool_schema instead of being ignored.
_KEYWORDS = {
    "type", "properties", "required", "additionalProperties", "enum",
    "items", "minItems", "maxItems", "uniqueItems",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "minLength", "maxLength", "pattern",
    "title", "description",  # annotations only; safe to accept
}


def validate_tool_schema(schema: dict) -> None:
    """Validate a tool schema definition against the supported subset.

    Raises ValueError for unsupported keywords, invalid types, invalid
    patterns or non-finite bounds — at registration time, before any
    argument is ever checked against this schema.
    """
    if not isinstance(schema, dict):
        raise ValueError("schema must be an object")
    if schema.get("type", "object") != "object":
        raise ValueError("top-level tool schema must be object")
    _validate_subschema("schema", schema, top=True)


def validate_args(args: Any, schema: dict) -> None:
    """Raise ValueError with a precise reason when args violate schema."""
    if not isinstance(args, dict):
        raise ValueError("arguments must be an object")
    if schema.get("type", "object") != "object":
        raise ValueError("top-level tool schema must be object")
    props = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in args:
            raise ValueError(f"missing required argument: {name}")
    if schema.get("additionalProperties") is False:
        for name in args:
            if name not in props:
                raise ValueError(f"unexpected argument: {name}")
    for name, value in args.items():
        sub = props.get(name)
        if sub is not None:
            _validate_value(name, value, sub)


# -- internals ---------------------------------------------------------------

def _validate_subschema(path: str, sub: dict, top: bool = False) -> None:
    if not isinstance(sub, dict):
        raise ValueError(f"{path}: subschema must be an object")
    unknown = [k for k in sub if k not in _KEYWORDS]
    if unknown:
        raise ValueError(f"{path}: unsupported schema keyword(s): {sorted(unknown)}")
    stype = sub.get("type", "object" if not top else "object")
    if stype not in _TYPES:
        raise ValueError(f"{path}: unsupported schema type {stype!r}")
    for flag in ("additionalProperties", "uniqueItems"):
        if flag in sub and not isinstance(sub[flag], bool):
            raise ValueError(f"{path}: {flag} must be a boolean")
    if "enum" in sub:
        if not isinstance(sub["enum"], list) or not sub["enum"]:
            raise ValueError(f"{path}: enum must be a non-empty list")
    if "required" in sub:
        if (not isinstance(sub["required"], list)
                or not all(isinstance(r, str) for r in sub["required"])):
            raise ValueError(f"{path}: required must be a list of strings")
    for bound in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
        if bound in sub:
            v = sub[bound]
            if isinstance(v, bool) or not isinstance(v, (int, float)) \
                    or not math.isfinite(v):
                raise ValueError(f"{path}: {bound} must be a finite number")
    for length in ("minLength", "maxLength", "minItems", "maxItems"):
        if length in sub:
            v = sub[length]
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError(f"{path}: {length} must be a non-negative integer")
    if "pattern" in sub:
        try:
            re.compile(sub["pattern"])
        except re.error as e:
            raise ValueError(f"{path}: invalid pattern: {e}") from e
    if "properties" in sub:
        if not isinstance(sub["properties"], dict):
            raise ValueError(f"{path}: properties must be an object")
        for k, v in sub["properties"].items():
            _validate_subschema(f"{path}.{k}", v)
    if "items" in sub:
        if not isinstance(sub["items"], dict):
            raise ValueError(f"{path}: items must be a single subschema object")
        _validate_subschema(f"{path}[]", sub["items"])


def _check_finite(path: str, value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path}: non-finite numeric value is not allowed")


def _validate_value(name: str, value: Any, schema: dict) -> None:
    stype = schema.get("type")
    if stype not in _TYPES:
        raise ValueError(f"argument {name}: unsupported schema type {stype!r}")
    if stype in ("integer", "number") and isinstance(value, bool):
        raise ValueError(f"argument {name}: boolean is not a {stype}")
    if not isinstance(value, _TYPES[stype]):
        raise ValueError(f"argument {name}: expected {stype}, got {type(value).__name__}")
    if stype in ("number", "integer"):
        _check_finite(f"argument {name}", value)
        _validate_bounds(name, value, schema)
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"argument {name}: {value!r} not in enum")
    if stype == "string":
        _validate_string(name, value, schema)
    if stype == "array":
        _validate_array(name, value, schema)
    if stype == "object":
        _validate_object(name, value, schema)


def _validate_bounds(name: str, value: Any, schema: dict) -> None:
    if "minimum" in schema and value < schema["minimum"]:
        raise ValueError(f"argument {name}: {value} < minimum {schema['minimum']}")
    if "maximum" in schema and value > schema["maximum"]:
        raise ValueError(f"argument {name}: {value} > maximum {schema['maximum']}")
    if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
        raise ValueError(
            f"argument {name}: {value} <= exclusiveMinimum {schema['exclusiveMinimum']}")
    if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
        raise ValueError(
            f"argument {name}: {value} >= exclusiveMaximum {schema['exclusiveMaximum']}")


def _validate_string(name: str, value: str, schema: dict) -> None:
    if "minLength" in schema and len(value) < schema["minLength"]:
        raise ValueError(f"argument {name}: shorter than minLength {schema['minLength']}")
    if "maxLength" in schema and len(value) > schema["maxLength"]:
        raise ValueError(f"argument {name}: longer than maxLength {schema['maxLength']}")
    if "pattern" in schema and re.search(schema["pattern"], value) is None:
        raise ValueError(f"argument {name}: does not match pattern {schema['pattern']!r}")


def _validate_array(name: str, value: list, schema: dict) -> None:
    if "minItems" in schema and len(value) < schema["minItems"]:
        raise ValueError(f"argument {name}: fewer than minItems {schema['minItems']}")
    if "maxItems" in schema and len(value) > schema["maxItems"]:
        raise ValueError(f"argument {name}: more than maxItems {schema['maxItems']}")
    if schema.get("uniqueItems"):
        seen = []
        for item in value:
            if item in seen:
                raise ValueError(f"argument {name}: items are not unique")
            seen.append(item)
    items = schema.get("items")
    if items is not None:
        for i, item in enumerate(value):
            _check_finite(f"argument {name}[{i}]", item)
            _validate_value(f"{name}[{i}]", item, items)


def _validate_object(name: str, value: dict, schema: dict) -> None:
    sub_props = schema.get("properties", {})
    for r in schema.get("required", []):
        if r not in value:
            raise ValueError(f"argument {name}: missing nested required: {r}")
    if schema.get("additionalProperties") is False:
        for k in value:
            if k not in sub_props:
                raise ValueError(f"argument {name}: unexpected nested key {k}")
    for k, v in value.items():
        if k in sub_props:
            _validate_value(f"{name}.{k}", v, sub_props[k])
