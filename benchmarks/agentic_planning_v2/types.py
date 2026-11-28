"""Validate resolved arguments against the host's JSON Schema before dispatch."""
from jsonschema import Draft202012Validator, FormatChecker

from benchmarks.agentic_planning_v1.contract import TOOLS


def input_schema(tool, spec):
    if "input_schema" in spec:
        return spec["input_schema"]
    if tool in TOOLS:
        return {"type": "object", "required": list(TOOLS[tool][1]), "additionalProperties": False,
                "properties": {field: {"type": "string"} for field in TOOLS[tool][1]}}
    return {"type": "object", "required": spec["inputs"], "additionalProperties": False,
            "properties": dict.fromkeys(spec["inputs"], {})}


def matches(instance, schema):
    return Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(instance)
