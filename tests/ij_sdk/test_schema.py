"""D06 - strict argument schemas: exact validation, and refusal of schemas the
gateway cannot enforce."""

from __future__ import annotations

import unittest

from tests.ij_sdk.support import RepoTestCase

SCHEMA = "benchmarks.ij_sdk.schema"


class SchemaLint(RepoTestCase):
    def setUp(self):
        super().setUp()
        self.schema = self.import_new(SCHEMA)

    def test_unknown_keywords_are_refused(self):
        for unsupported in ({"type": "string", "format": "email"}, {"type": "object", "$defs": {}},
                            {"type": "string", "default": "x"}):
            with self.subTest(unsupported=unsupported):
                self.assertTrue(self.schema.lint_schema(unsupported))

    def test_open_objects_are_refused(self):
        self.assertTrue(self.schema.lint_schema({"type": "object"}))
        self.assertTrue(self.schema.lint_schema({"type": "object", "additionalProperties": True}))
        self.assertEqual(self.schema.lint_schema(
            {"type": "object", "properties": {}, "additionalProperties": False}), [])

    def test_required_must_be_declared(self):
        self.assertTrue(self.schema.lint_schema(
            {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["b"], "additionalProperties": False}))

    def test_enforce_raises_on_unenforceable(self):
        with self.assertRaises(self.schema.SchemaError):
            self.schema.enforce_schema({"type": "string", "format": "date"})


class SchemaValidation(RepoTestCase):
    def setUp(self):
        super().setUp()
        self.validate = self.import_new(SCHEMA).validate

    def test_types(self):
        valid = [(5, "integer"), (5.0, "integer"), (5.5, "number"), ("x", "string"), (True, "boolean"),
                 (None, "null"), ([], "array"), ({}, "object")]
        for value, kind in valid:
            with self.subTest(value=value, kind=kind):
                self.assertEqual(self.validate(value, {"type": kind}), [])
        invalid = [(True, "integer"), (True, "number"), (5, "string"), ("5", "number"), (5.5, "integer"),
                   ([], "object"), ({}, "array")]
        for value, kind in invalid:
            with self.subTest(value=value, kind=kind):
                self.assertTrue(self.validate(value, {"type": kind}))

    def test_required_and_undeclared_properties(self):
        schema = {"type": "object", "properties": {"sku": {"type": "string"}, "delta": {"type": "integer"}},
                  "required": ["sku", "delta"], "additionalProperties": False}
        self.assertEqual(self.validate({"sku": "A", "delta": -5}, schema), [])
        errors = self.validate({"sku": "A", "delta": "five", "extra": 1}, schema)
        joined = " ".join(errors)
        self.assertIn("extra", joined)              # undeclared property
        self.assertIn("delta", joined)              # wrong type
        self.assertTrue(self.validate({"sku": "A"}, schema))        # missing required

    def test_object_without_properties_rejects_every_key(self):
        schema = {"type": "object", "additionalProperties": False}
        self.assertEqual(self.validate({}, schema), [])
        self.assertTrue(self.validate({"anything": 1}, schema))

    def test_bounds_length_pattern_enum_const(self):
        self.assertTrue(self.validate(0, {"minimum": 1}))
        self.assertTrue(self.validate(1, {"exclusiveMinimum": 1}))
        self.assertEqual(self.validate(1, {"minimum": 1}), [])
        self.assertTrue(self.validate("abc", {"minLength": 4}))
        self.assertTrue(self.validate("abc", {"maxLength": 2}))
        self.assertTrue(self.validate("abc", {"pattern": "^[0-9]+$"}))
        self.assertTrue(self.validate("b", {"enum": ["a", "c"]}))
        self.assertTrue(self.validate(2, {"const": 1}))
        self.assertTrue(self.validate([1], {"minItems": 2}))
        self.assertTrue(self.validate([1, 2, 3], {"maxItems": 2}))

    def test_nested_items(self):
        schema = {"type": "array", "items": {"type": "object", "properties": {"n": {"type": "integer"}},
                                             "required": ["n"], "additionalProperties": False}}
        self.assertEqual(self.validate([{"n": 1}], schema), [])
        errors = self.validate([{"n": 1}, {"n": "x"}, {"m": 2}], schema)
        # {"n": "x"}: wrong type; {"m": 2}: missing required "n" and undeclared "m"
        self.assertEqual(len(errors), 3)

    def test_any_of_one_of_all_of(self):
        self.assertEqual(self.validate(3, {"anyOf": [{"type": "string"}, {"type": "integer"}]}), [])
        self.assertTrue(self.validate(3.5, {"anyOf": [{"type": "string"}, {"type": "integer"}]}))
        self.assertEqual(self.validate(3, {"oneOf": [{"type": "string"}, {"type": "integer"}]}), [])
        self.assertTrue(self.validate(3, {"oneOf": [{"type": "integer"}, {"type": "number"}]}))
        self.assertTrue(self.validate(3, {"allOf": [{"type": "integer"}, {"minimum": 5}]}))

    def test_canonical_json_is_order_independent(self):
        canonical = self.import_new(SCHEMA).canonical_json
        self.assertEqual(canonical({"b": 1, "a": [2, 3]}), canonical({"a": [2, 3], "b": 1}))


if __name__ == "__main__":
    unittest.main()
