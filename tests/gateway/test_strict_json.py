from decimal import Decimal

import pytest

from model_gateway import GatewayError
from model_gateway.strict_json import strict_object


@pytest.mark.parametrize("raw", [
    '{"a":1,"a":2}', '{"a":{"b":1,"b":2}}', '{"a":[{"b":1,"b":2}]}',
    r'{"a":1,"\u0061":2}', '{"a":null,"a":null}', '{"a":true,"a":false}',
    '{"a":[1,2],"a":[3]}', '{"a":"同","a":"字"}', '{"参数":0,"参数":1}',
    '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}', '{"a":[NaN]}',
    '{"a":1e400}', '{"a":1e-400}', '{"a":1e+10000000}',
    '{"a":99999999999999999999999999999999999999999999999}',
    '{"a":9223372036854775808}', '{"a":-9223372036854775809}',
    '{"a":999999999999999999999.1}',
    '{"a":0.00000000000000000000000000000000001}',
    '{"a":0.99999999999999999999999999999999999}',
    '[]', '"text"', 'true', 'false', 'null', '0', '', ' ', '{', '}{',
    '{"a":}', '{"a":1,}', '{"a":[1,]}', '{"a":01}', '{"a":+1}', '{"a":.5}',
    '{"a":1.}', '{"a":1e}', r'{"a":"\x41"}', r'{"a":"\uD800"}',
    r'{"a":"\uDC00"}', r'{"\uD800":1}', '{"a":"\ud800"}',
    '{"a":"\0"}', '{"a":"\n"}', b'{"a":"\xff"}', b'\xef\xbb\xbf{}',
    '{}{}', '{} null', '{//comment\n"a":1}', '{1:2}', '{"a";1}',
    '{"a":true false}', '{"a": {"b": 2} "c": 3}', {'a': 1}, None,
    '{"a":"' + '纸' * 6000 + '"}',
    '{"a":' + '[' * 33 + '0' + ']' * 33 + '}',
], ids=[
    "duplicate", "nested-duplicate", "array-object-duplicate", "escaped-duplicate",
    "null-duplicate", "boolean-duplicate", "array-duplicate", "duplicate-different-text",
    "unicode-duplicate", "nan", "positive-infinity", "negative-infinity", "nested-nan",
    "large-exponent", "tiny-exponent", "huge-exponent", "huge-integer", "above-int64",
    "below-int64", "decimal-magnitude", "scale", "precision", "array-root", "string-root",
    "true-root", "false-root", "null-root", "number-root", "empty", "space", "unclosed",
    "wrong-close", "missing-value", "trailing-object-comma", "trailing-array-comma",
    "leading-zero", "leading-plus", "no-integer", "no-fraction", "no-exponent",
    "non-json-escape", "escaped-high-surrogate", "escaped-low-surrogate", "key-surrogate",
    "raw-surrogate", "raw-null", "raw-newline", "invalid-utf8", "bom", "second-object",
    "trailing-value", "comment", "non-string-key", "wrong-separator", "adjacent-literals",
    "missing-comma", "decoded-object", "python-none", "utf8-byte-limit", "nesting-limit",
])
def test_rejects_ambiguous_or_unbounded_arguments(raw):
    with pytest.raises(GatewayError) as problem:
        strict_object(raw)
    assert problem.value.code == "PROTOCOL_ERROR"


@pytest.mark.parametrize(("raw", "expected"), [
    ('{"x":0.10}', {"x": Decimal("0.10")}),
    ('{"x":1e-2}', {"x": Decimal("0.01")}),
    ('{"x":-9223372036854775808}', {"x": -9223372036854775808}),
    ('{"x":9223372036854775807}', {"x": 9223372036854775807}),
    ('{"x":true,"y":false,"z":null}', {"x": True, "y": False, "z": None}),
    ('{"x":" 记\\n  "}', {"x": " 记\n  "}),
    (r'{"x":"\uD83D\uDCDA"}', {"x": "📚"}),
    ('{"x":{"v":[1,2,"文本"]}}', {"x": {"v": [1, 2, "文本"]}}),
])
def test_accepted_values_preserve_type_precision_and_whitespace(raw, expected):
    value = strict_object(raw)
    assert value == expected
    assert [type(v) for v in value.values()] == [type(v) for v in expected.values()]
