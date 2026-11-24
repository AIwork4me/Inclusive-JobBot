"""Validate schemas and business arguments before resource authorization."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Callable

from jsonschema import Draft202012Validator, validators
from jsonschema.exceptions import ValidationError
from referencing import Registry
from referencing.exceptions import Unresolvable

from business_tools import UnitOfWork

from .authorization import ExecutionContext
from .errors import ErrorCode, GatewayError


def _closed(schema):
    if isinstance(schema, bool):
        return schema
    output = deepcopy(schema)
    for keyword in ("properties", "patternProperties", "$defs", "dependentSchemas"):
        if keyword in schema:
            output[keyword] = {key: _closed(value) for key, value in schema[keyword].items()}
    for keyword in ("items", "contains", "additionalProperties", "unevaluatedItems",
                    "unevaluatedProperties", "propertyNames", "not", "if", "then", "else"):
        if keyword in schema:
            output[keyword] = _closed(schema[keyword])
    for keyword in ("allOf", "anyOf", "oneOf", "prefixItems"):
        if keyword in schema:
            output[keyword] = [_closed(value) for value in schema[keyword]]
    for keyword in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"):
        if isinstance(schema.get(keyword), float):
            output[keyword] = Decimal(str(schema[keyword]))
    if (schema.get("type") == "object" or "properties" in schema) and not (
            {"allOf", "anyOf", "oneOf", "$ref", "$dynamicRef", "unevaluatedProperties"} & schema.keys()):
        output.setdefault("additionalProperties", False)
    for keyword in ("$ref", "$dynamicRef"):
        if keyword in schema and not schema[keyword].startswith("#"):
            raise ValueError("tool schemas may only reference local definitions")
    dialect = output.pop("$schema", "https://json-schema.org/draft/2020-12/schema")
    if dialect.removesuffix("#") != "https://json-schema.org/draft/2020-12/schema":
        raise ValueError("tool schemas must use Draft 2020-12")
    return output


def _exact_multiple(validator, divisor, instance, _schema):
    if validator.is_type(instance, "number") and (Fraction(instance) / Fraction(divisor)).denominator != 1:
        yield ValidationError("number is not a multiple of the configured step")


STRICT_SCHEMA = validators.extend(
    Draft202012Validator,
    validators={"multipleOf": _exact_multiple},
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine_many({
        "integer": lambda _, value: type(value) is int,
        "number": lambda _, value: type(value) in (int, Decimal),
    }),
)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    schema: dict
    resource: Callable[[dict], str]
    handler: Callable[[UnitOfWork, dict, ExecutionContext], dict]
    write: bool = False
    validate: Callable[[dict], None] | None = None
    draft_only: bool = False


def compile_schema(tool: ToolSpec):
    if tool.draft_only and not tool.write:
        raise ValueError("draft-only tool must be declared writable")
    STRICT_SCHEMA.check_schema(tool.schema)
    schema = _closed(tool.schema)
    if schema.get("type") != "object":
        raise ValueError("tool root schema must be an object")
    return STRICT_SCHEMA(schema, registry=Registry())


def validate_schema(validator, arguments: dict) -> None:
    try:
        failure = next(validator.iter_errors(arguments), None)
    except (Unresolvable, RecursionError):
        raise GatewayError(ErrorCode.SCHEMA_ERROR, "invalid schema reference") from None
    if failure is not None:
        raise GatewayError(ErrorCode.SCHEMA_ERROR, f"tool arguments violate the {failure.validator} constraint")
