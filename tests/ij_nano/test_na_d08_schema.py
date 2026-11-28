"""NA-D08 adversarial tests: schema validation strictness.

Red against the audited source: numeric bounds, string length and pattern
constraints are silently ignored; arrays are unsupported as a type but schemas
using array keywords on other types slip through; non-finite numbers pass;
schemas containing unsupported keywords are accepted at registration.
"""
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.gateway.gateway import SafeToolGateway, ToolSpec  # noqa: E402
from nanoagent.gateway.schema import (validate_args,  # noqa: E402
                                      validate_tool_schema)


class TestNumericBounds(unittest.TestCase):
    def setUp(self):
        self.schema = {"type": "object",
                       "properties": {"qty": {"type": "integer",
                                              "minimum": 1, "maximum": 10}},
                       "required": ["qty"]}

    def test_minimum_enforced(self):
        # RED: audited validator ignores 'minimum'.
        with self.assertRaises(ValueError):
            validate_args({"qty": 0}, self.schema)
        validate_args({"qty": 1}, self.schema)

    def test_maximum_enforced(self):
        # RED: audited validator ignores 'maximum'.
        with self.assertRaises(ValueError):
            validate_args({"qty": 11}, self.schema)
        validate_args({"qty": 10}, self.schema)

    def test_exclusive_bounds_enforced(self):
        schema = {"type": "object",
                  "properties": {"n": {"type": "number",
                                       "exclusiveMinimum": 0,
                                       "exclusiveMaximum": 1}}}
        with self.assertRaises(ValueError):
            validate_args({"n": 0}, schema)
        with self.assertRaises(ValueError):
            validate_args({"n": 1}, schema)
        validate_args({"n": 0.5}, schema)

    def test_non_finite_numbers_rejected(self):
        # RED: audited validator accepts NaN/Infinity as 'number'.
        schema = {"type": "object", "properties": {"n": {"type": "number"}}}
        with self.assertRaises(ValueError):
            validate_args({"n": float("nan")}, schema)
        with self.assertRaises(ValueError):
            validate_args({"n": float("inf")}, schema)
        nested = {"type": "object",
                  "properties": {"payload": {"type": "object",
                                             "properties": {"n": {"type": "number"}}}}}
        with self.assertRaises(ValueError):
            validate_args({"payload": {"n": float("-inf")}}, nested)


class TestStringConstraints(unittest.TestCase):
    def test_length_enforced(self):
        # RED: audited validator ignores minLength/maxLength.
        schema = {"type": "object",
                  "properties": {"sku": {"type": "string",
                                         "minLength": 2, "maxLength": 4}}}
        with self.assertRaises(ValueError):
            validate_args({"sku": "A"}, schema)
        with self.assertRaises(ValueError):
            validate_args({"sku": "TOOLONG"}, schema)
        validate_args({"sku": "AB"}, schema)

    def test_pattern_enforced(self):
        # RED: audited validator ignores 'pattern'.
        schema = {"type": "object",
                  "properties": {"order_id": {"type": "string",
                                              "pattern": "^PO-\\d+$"}}}
        with self.assertRaises(ValueError):
            validate_args({"order_id": "XX-1"}, schema)
        validate_args({"order_id": "PO-42"}, schema)


class TestArraysAndNesting(unittest.TestCase):
    def test_array_items_and_bounds(self):
        # RED: audited validator rejects the type outright instead of
        # validating arrays per the declared schema.
        schema = {"type": "object",
                  "properties": {"tags": {"type": "array",
                                          "items": {"type": "string"},
                                          "minItems": 1, "maxItems": 3,
                                          "uniqueItems": True}}}
        validate_args({"tags": ["a"]}, schema)
        with self.assertRaises(ValueError):
            validate_args({"tags": []}, schema)                 # minItems
        with self.assertRaises(ValueError):
            validate_args({"tags": ["a", "b", "c", "d"]}, schema)  # maxItems
        with self.assertRaises(ValueError):
            validate_args({"tags": ["a", "a"]}, schema)         # uniqueItems
        with self.assertRaises(ValueError):
            validate_args({"tags": ["a", 1]}, schema)           # item type

    def test_deep_nesting(self):
        schema = {"type": "object",
                  "properties": {"a": {"type": "object",
                                       "properties": {"b": {"type": "object",
                                                            "properties": {"c": {
                                                                "type": "integer",
                                                                "minimum": 0}}}}}}}
        validate_args({"a": {"b": {"c": 1}}}, schema)
        with self.assertRaises(ValueError):
            validate_args({"a": {"b": {"c": -1}}}, schema)

    def test_unknown_properties_when_open(self):
        # Without additionalProperties:false unknown keys are allowed but must
        # still not be validated against nothing; with it, they are rejected.
        closed = {"type": "object", "properties": {"a": {"type": "string"}},
                  "additionalProperties": False}
        with self.assertRaises(ValueError):
            validate_args({"a": "x", "rogue": 1}, closed)
        open_ = {"type": "object", "properties": {"a": {"type": "string"}}}
        validate_args({"a": "x", "extra": 1}, open_)


class TestRegistrationStrictness(unittest.TestCase):
    def test_unsupported_keyword_rejected_at_registration(self):
        # RED: audited gateway accepts schemas whose semantic keywords are
        # silently ignored (here: 'multipleOf' and 'format').
        for kw in ({"multipleOf": 2}, {"format": "date-time"}, {"minProperties": 1},
                   {"oneOf": []}, {"allOf": []}, {"$ref": "#/$defs/x"}):
            schema = {"type": "object", "properties": {"n": {"type": "integer", **kw}}}
            with self.assertRaises(ValueError):
                validate_tool_schema(schema)

    def test_invalid_schema_definition_rejected(self):
        # RED: nothing validates the schema itself today.
        bad_type = {"type": "object", "properties": {"n": {"type": "warpdrive"}}}
        with self.assertRaises(ValueError):
            validate_tool_schema(bad_type)
        bad_pattern = {"type": "object",
                       "properties": {"s": {"type": "string", "pattern": "["}}}
        with self.assertRaises(ValueError):
            validate_tool_schema(bad_pattern)
        nonfinite = {"type": "object",
                     "properties": {"n": {"type": "integer", "minimum": float("nan")}}}
        with self.assertRaises(ValueError):
            validate_tool_schema(nonfinite)

    def test_valid_schema_accepted(self):
        schema = {"type": "object",
                  "properties": {"n": {"type": "integer", "minimum": 0, "maximum": 9},
                                 "s": {"type": "string", "minLength": 1},
                                 "tags": {"type": "array", "items": {"type": "string"}}},
                  "required": ["n"], "additionalProperties": False}
        validate_tool_schema(schema)   # must not raise

    def test_gateway_validates_schemas_at_registration(self):
        # RED: audited gateway accepts tools with ignored-keyword schemas.
        bad = ToolSpec(
            name="t", permission="p",
            parameters={"type": "object",
                        "properties": {"n": {"type": "integer", "multipleOf": 3}}},
            handler=lambda tool, args, draft: None)
        with self.assertRaises(ValueError):
            SafeToolGateway({bad.name: bad})


if __name__ == "__main__":
    unittest.main()
