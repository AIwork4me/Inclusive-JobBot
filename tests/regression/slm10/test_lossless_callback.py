from dataclasses import replace

import pytest

from model_gateway import GatewayError, Proposal
from model_gateway.callback_binding import BindingContext, CallbackBinder


CONTEXT = BindingContext("session", "read-assets", 1, "read-only-grant", 0)
SCHEMA = {
    "type": "object", "required": ["page"], "additionalProperties": False,
    "properties": {
        "page": {"type": "integer"},
        "filters": {"type": "object", "properties": {
            "widths": {"type": "array", "items": {"type": "integer"}},
            "optional": {"type": "null"},
        }},
    },
}


def prepared(raw='{"page":7}', *, authorize=None):
    binder = CallbackBinder({"layout": SCHEMA}, authorize or (lambda *_: True))
    binder.publish([Proposal("proposal", "layout", raw)], CONTEXT)
    return binder


def test_records_lossless_integer_conversion_with_nested_evidence():
    raw = '{"page":7,"filters":{"widths":[2048,64],"optional":null}}'
    binder = prepared(raw)
    callback = {"page": 7.0, "filters": {"widths": [2048.0, 64], "optional": None}}
    result = binder.claim("proposal", "layout", callback, CONTEXT)
    assert result.proposal.arguments_raw == raw
    assert type(result.parsed_arguments["page"]) is int
    assert type(result.callback_arguments["page"]) is float
    assert type(result.normalized_arguments["page"]) is int
    assert type(result.normalized_arguments["filters"]["widths"][0]) is int
    assert result.integer_conversions == (("page",), ("filters", "widths", 0))
    assert result.context == CONTEXT
    callback["page"] = 123
    assert result.callback_arguments["page"] == 7.0
    with pytest.raises(ValueError):
        binder.claim("proposal", "layout", callback, CONTEXT)


@pytest.mark.parametrize("value", [7.25, True, "7", float("nan"), float("inf"), -float("inf")])
def test_rejects_non_equivalent_callback_number(value):
    with pytest.raises(ValueError):
        prepared().claim("proposal", "layout", {"page": value}, CONTEXT)


@pytest.mark.parametrize("value", [2**53, 2**53 + 1, -(2**53)])
def test_rejects_integer_conversion_outside_safe_binary64_range(value):
    with pytest.raises(ValueError):
        prepared(f'{{"page":{value}}}').claim("proposal", "layout", {"page": float(value)}, CONTEXT)


def test_accepts_safe_boundary_and_preserves_optional_field_shape():
    number = 2**53 - 1
    binding = prepared(f'{{"page":{number}}}').claim("proposal", "layout", {"page": float(number)}, CONTEXT)
    assert binding.normalized_arguments == {"page": number}
    binder = prepared('{"page":7,"filters":{"optional":null}}')
    with pytest.raises(ValueError):
        binder.claim("proposal", "layout", {"page": 7, "filters": {}}, CONTEXT)


def test_rejects_duplicate_keys_and_identical_proposals_without_unique_identity():
    with pytest.raises(GatewayError):
        prepared('{"page":7,"page":8}')
    binder = CallbackBinder({"layout": SCHEMA}, lambda *_: True)
    binder.publish([Proposal(i, "layout", '{"page":7}') for i in ("first", "second")], CONTEXT)
    with pytest.raises(ValueError):
        binder.claim(None, "layout", {"page": 7.0}, CONTEXT)
    assert binder.claim("second", "layout", {"page": 7}, CONTEXT).proposal.call_id == "second"


@pytest.mark.parametrize("changes", [
    {"session_id": "other"}, {"scope": "other"}, {"revision": 2},
    {"authorization_binding": "write-grant"}, {"observation_revision": 1},
])
def test_rejects_changed_trusted_context(changes):
    with pytest.raises(ValueError):
        prepared().claim("proposal", "layout", {"page": 7}, replace(CONTEXT, **changes))


def test_rejects_fabricated_id_reuse_unknown_tool_and_revoked_grant():
    permit = True
    binder = prepared(authorize=lambda *_: permit)
    for call_id, tool in (("fabricated", "layout"), ("proposal", "write")):
        with pytest.raises(ValueError):
            binder.claim(call_id, tool, {"page": 7}, CONTEXT)
    permit = False
    with pytest.raises(ValueError):
        binder.claim("proposal", "layout", {"page": 7.0}, CONTEXT)
    with pytest.raises(ValueError):
        binder.publish([Proposal("proposal", "layout", '{"page":7}')], CONTEXT)


def test_integer_coercion_requires_explicit_integer_schema_and_precision():
    schema = {"type": "object", "properties": {"page": {"type": "number"}}}
    binder = CallbackBinder({"layout": schema}, lambda *_: True)
    binder.publish([Proposal("proposal", "layout", '{"page":7}')], CONTEXT)
    with pytest.raises(ValueError):
        binder.claim("proposal", "layout", {"page": 7.0}, CONTEXT)
    binder.publish([Proposal("decimal", "layout", '{"page":0.100000000000000001}')], CONTEXT)
    with pytest.raises(ValueError):
        binder.claim("decimal", "layout", {"page": 0.1}, CONTEXT)
