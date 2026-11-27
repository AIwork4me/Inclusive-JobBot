"""Minimal JSON-schema-like argument validation (stdlib only).

Supports the subset the Job Package tool contracts need: object types,
string/number/integer/boolean, required properties, enum, additionalProperties
false, and one nesting level of object/array items. Strict: unknown types and
unvalidated constructs are rejected rather than ignored (fail closed).
"""
from __future__ import annotations

from typing import Any

_TYPES = {"string": str, "number": (int, float), "integer": int, "boolean": bool, "object": dict}


def validate_args(args: Any, schema: dict) -> None:
    """Raise ValueError with a precise reason when args violate schema."""
    if not isinstance(args, dict):
        raise ValueError("arguments must be an object")
    stype = schema.get("type", "object")
    if stype != "object":
        raise ValueError(f"top-level tool schema must be object, got {stype}")
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        raise ValueError("schema properties must be an object")
    required = schema.get("required", [])
    for name in required:
        if name not in args:
            raise ValueError(f"missing required argument: {name}")
    if schema.get("additionalProperties") is False:
        for name in args:
            if name not in props:
                raise ValueError(f"unexpected argument: {name}")
    for name, value in args.items():
        sub = props.get(name)
        if sub is None:
            continue
        _validate_value(name, value, sub)


def _validate_value(name: str, value: Any, schema: dict) -> None:
    stype = schema.get("type")
    if stype not in _TYPES:
        raise ValueError(f"argument {name}: unsupported schema type {stype!r}")
    py = _TYPES[stype]
    if stype == "integer" and isinstance(value, bool):
        raise ValueError(f"argument {name}: boolean is not an integer")
    if stype == "number" and isinstance(value, bool):
        raise ValueError(f"argument {name}: boolean is not a number")
    if not isinstance(value, py):
        raise ValueError(f"argument {name}: expected {stype}, got {type(value).__name__}")
    if "enum" in schema:
        if value not in schema["enum"]:
            raise ValueError(f"argument {name}: {value!r} not in enum")
    if stype == "object":
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
