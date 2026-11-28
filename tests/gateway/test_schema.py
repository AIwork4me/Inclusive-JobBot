from decimal import Decimal

import pytest

from business_tools import BusinessStore
from model_gateway import ExecutionContext, Gateway, GatewayError, Grant, Policy, Proposal, ToolSpec


def setup(tmp_path, field_schema):
    schema = {"type": "object", "required": ["value"], "properties": {"value": field_schema}}
    context = ExecutionContext("clerk", "review", "session", "inspect")
    grant = Grant("clerk", "review", "check", frozenset({"example"}), frozenset({"inspect"}))
    gateway = Gateway(BusinessStore(tmp_path / "case.db"), {
        "check": ToolSpec(schema, lambda _: "example", lambda _, arguments, context: arguments),
    }, Policy((grant,)))
    return gateway, context


@pytest.mark.parametrize("value", ["true", "false", "1.0", "1e0", "0.0", "null", '"1"', "[]"])
def test_integer_fields_reject_numeric_coercion_even_nested(tmp_path, value):
    gateway, context = setup(tmp_path, {"type": "array", "items": {"type": "integer"}})
    with pytest.raises(GatewayError) as failure:
        gateway.execute(Proposal("id-1", "check", '{"value":[' + value + ']}'), context)
    assert failure.value.code == "SCHEMA_ERROR"


def test_literal_schema_values_are_not_rewritten(tmp_path):
    field = {"const": {"type": "object", "setting": "display"}}
    gateway, context = setup(tmp_path, field)
    raw = '{"value":{"type":"object","setting":"display"}}'
    assert gateway.execute(Proposal("id-1", "check", raw), context)["value"] == field["const"]


def test_monetary_multiple_uses_exact_arithmetic(tmp_path):
    gateway, context = setup(tmp_path, {"type": "number", "multipleOf": 0.0000000000000000000000000001})
    raw = '{"value":9223372036854775807}'
    assert gateway.execute(Proposal("id-1", "check", raw), context)["value"] == 9223372036854775807
    gateway, context = setup(tmp_path, {"type": "number", "multipleOf": 0.01})
    assert gateway.execute(Proposal("id-2", "check", '{"value":0.29}'), context)["value"] == Decimal("0.29")
    with pytest.raises(GatewayError) as failure:
        gateway.execute(Proposal("id-3", "check", '{"value":0.291}'), context)
    assert failure.value.code == "SCHEMA_ERROR"


def test_openapi_schema_cannot_resolve_remote_documents(tmp_path):
    with pytest.raises(ValueError, match="local"):
        setup(tmp_path, {"$ref": "http://example.com/schema"})
