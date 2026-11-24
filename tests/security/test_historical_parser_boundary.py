"""Software replay of the unchanged, previously captured native wire outputs."""

import json
from pathlib import Path

import pytest

from business_tools import BusinessStore
from model_gateway import ExecutionContext, Gateway, GatewayError, Grant, Policy, ToolSpec, decode_completion

REPO = Path(__file__).resolve().parents[2]
CASES = {
    "fx-valid-whitespace-between-tags": "SCHEMA_ERROR",
    "fx-invalid-duplicate-param": "PROTOCOL_ERROR",
    "fx-invalid-missing-close-param": "PROTOCOL_ERROR",
    "fx-invalid-unclosed-function": "PROTOCOL_ERROR",
    "fx-invalid-enum-outside-schema": "SCHEMA_ERROR",
    "fx-invalid-unclosed-cdata": "PROTOCOL_ERROR",
}


@pytest.mark.parametrize("backend", ["vulkan", "rocm"])
@pytest.mark.parametrize(("case_id", "code"), CASES.items())
def test_original_native_parser_failure_is_blocked_at_gateway(backend, case_id, code, tmp_path):
    root = REPO / "evidence/IJ0/protocol"
    captured = json.loads((root / f"parser_fixtures_strict_{backend}/fixtures.json").read_text(encoding="utf-8"))
    row = next(row for row in captured["results"] if row["id"] == case_id)
    body = json.dumps({"choices": [{"message": row["message"], "finish_reason": row["finish_reason"]}]})
    store = BusinessStore(tmp_path / "state.db")
    context = ExecutionContext("fixture-user", "clerk", "fixture-session", "inspect")
    original = json.loads((REPO / "benchmarks/tool_calling/fixtures/minicpm5_parser_fixtures.json")
                          .read_text(encoding="utf-8"))
    schema_map = {item["function"]["name"]: item["function"]["parameters"] for item in original["tools"]}
    schema_map["get_purchase_order"]["properties"]["order_id"]["pattern"] = r"^PO-[0-9]{4}-[0-9]{4}\Z"
    tool = row["message"]["tool_calls"][0]["function"]["name"]
    called = []

    def record_handler(*_):
        called.append(True)
        return {}

    gateway = Gateway(store, {tool: ToolSpec(schema_map[tool], lambda _: "synthetic", record_handler)},
                      Policy((Grant(context.actor, context.role, tool, frozenset({"synthetic"}),
                                    frozenset({context.workflow_state})),)))
    with pytest.raises(GatewayError) as failure:
        completion = decode_completion(body)
        for proposal in completion.calls:
            gateway.prepare(proposal, context)
        for proposal in completion.calls:
            gateway.execute(proposal, context)
    assert failure.value.code == code
    assert called == []
    assert all(not records for records in store.snapshot().values())
