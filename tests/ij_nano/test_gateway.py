"""Layer A regression tests: safe tool gateway (D06 defect class)."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.gateway.gateway import (GatewayDenial, SafeToolGateway,  # noqa: E402
                                       ToolError, ToolSpec)
from nanoagent.gateway.schema import validate_args  # noqa: E402


def spec(name="get_order", permission="orders.read", **kw):
    def handler(tool, args, draft):
        draft[f"last:{tool}"] = args
        return {"ok": True, "echo": args}
    return ToolSpec(
        name=name,
        parameters={"type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"], "additionalProperties": False},
        handler=kw.pop("handler", handler),
        permission=permission,
        preconditions=kw.pop("preconditions", ()),
        requires_approval=kw.pop("requires_approval", False),
        idempotent=kw.pop("idempotent", False),
    )


class TestGatewayOrdering(unittest.TestCase):
    def test_unknown_tool_denied_at_stage_1(self):
        gw = SafeToolGateway({})
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("nope", {}, call_key="c1")
        self.assertEqual(cm.exception.stage, "tool_exists")

    def test_bad_arguments_denied_at_stage_2(self):
        gw = SafeToolGateway({spec().name: spec()})
        gw.grant("orders.read")
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("get_order", {"order_id": 123}, call_key="c1")  # wrong type
        self.assertEqual(cm.exception.stage, "schema")
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("get_order", {"order_id": "PO-1", "extra": 1}, call_key="c2")
        self.assertEqual(cm.exception.stage, "schema")

    def test_unauthorized_denied_at_stage_3(self):
        gw = SafeToolGateway({spec().name: spec()})
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("get_order", {"order_id": "PO-1"}, call_key="c1")
        self.assertEqual(cm.exception.stage, "authorize")

    def test_fault_cannot_grant_permission(self):
        # D06 core: a fault must never turn a denial into an accept.
        def evil_fault(name, args):
            pass  # even a fault that 'does nothing' must not bypass ordering
        faults = {"c1": evil_fault}
        gw = SafeToolGateway({spec().name: spec()}, fault_schedule=faults)
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("get_order", {"order_id": "PO-1"}, call_key="c1")
        self.assertEqual(cm.exception.stage, "authorize")
        stages = [a["stage"] for a in gw.audit]
        self.assertIn("authorize", stages)
        self.assertNotIn("fault", stages)  # fault stage never reached

    def test_preconditions_and_approval(self):
        gw = SafeToolGateway({spec(requires_approval=True).name:
                              spec(preconditions=("order.loaded",), requires_approval=True)})
        gw.grant("orders.read")
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("get_order", {"order_id": "PO-1"}, call_key="c1")
        self.assertEqual(cm.exception.stage, "preconditions")
        gw.store["order.loaded"] = True
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("get_order", {"order_id": "PO-1"}, call_key="c1")
        self.assertEqual(cm.exception.stage, "approval")
        gw.approve("c1", tool="get_order", args={"order_id": "PO-1"},
                   operation_id="op-1")
        res = gw.call("get_order", {"order_id": "PO-1"}, call_key="c1")
        self.assertTrue(res["ok"])

    def test_idempotency_prevents_duplicate_effects(self):
        calls = []

        def counting(tool, args, draft):
            calls.append(args["order_id"])
            return {"n": len(calls)}
        s = spec(idempotent=True, handler=counting)
        gw = SafeToolGateway({s.name: s})
        gw.grant("orders.read")
        r1 = gw.call("get_order", {"order_id": "PO-1"}, call_key="c1", effect_key="PO-1")
        r2 = gw.call("get_order", {"order_id": "PO-1"}, call_key="c2", effect_key="PO-1")
        self.assertEqual(r1, r2)
        self.assertEqual(calls, ["PO-1"])  # executed once

    def test_handler_failure_rolls_back_draft(self):
        def boom(tool, args, draft):
            draft["mutated"] = True
            raise ValueError("exploded")
        s = spec(handler=boom)
        gw = SafeToolGateway({s.name: s})
        gw.grant("orders.read")
        with self.assertRaises(ToolError):
            gw.call("get_order", {"order_id": "PO-1"}, call_key="c1")
        self.assertNotIn("mutated", gw.store)  # draft discarded
        stages = [a["stage"] for a in gw.audit]
        self.assertIn("rollback", stages)
        self.assertNotIn("commit", stages)

    def test_audit_records_every_decision(self):
        gw = SafeToolGateway({spec().name: spec()})
        try:
            gw.call("get_order", {"order_id": "PO-1"}, call_key="c1")
        except GatewayDenial:
            pass
        gw.grant("orders.read")
        gw.call("get_order", {"order_id": "PO-1"}, call_key="c2")
        tools = [a["tool"] for a in gw.audit]
        self.assertTrue(all(t == "get_order" for t in tools))
        self.assertTrue(len(gw.audit) >= 6)


class TestSchema(unittest.TestCase):
    def test_nested_validation(self):
        schema = {"type": "object",
                  "properties": {"item": {"type": "object",
                                          "properties": {"sku": {"type": "string"},
                                                         "qty": {"type": "integer"}},
                                          "required": ["sku"], "additionalProperties": False}},
                  "required": ["item"], "additionalProperties": False}
        validate_args({"item": {"sku": "S1", "qty": 2}}, schema)
        with self.assertRaises(ValueError):
            validate_args({"item": {"sku": "S1", "qty": "two"}}, schema)
        with self.assertRaises(ValueError):
            validate_args({"item": {"sku": "S1", "extra": 0}}, schema)
        with self.assertRaises(ValueError):
            validate_args({"item": {"qty": 1}}, schema)

    def test_enum_and_bool_strictness(self):
        schema = {"type": "object", "properties": {"a": {"type": "string", "enum": ["x", "y"]}}}
        validate_args({"a": "x"}, schema)
        with self.assertRaises(ValueError):
            validate_args({"a": "z"}, schema)
        ischema = {"type": "object", "properties": {"n": {"type": "integer"}}}
        with self.assertRaises(ValueError):
            validate_args({"n": True}, ischema)  # bool is not integer

    def test_unsupported_type_fails_closed(self):
        # Arrays are supported since NA-D08; genuinely unsupported types
        # (outside the declared subset) still fail closed.
        schema = {"type": "object", "properties": {"x": {"type": "null"}}}
        with self.assertRaises(ValueError):
            validate_args({"x": []}, schema)
        # Array validation is real, not a blanket rejection:
        ok = {"type": "object",
              "properties": {"x": {"type": "array",
                                   "items": {"type": "string"}}}}
        validate_args({"x": ["a"]}, ok)
        with self.assertRaises(ValueError):
            validate_args({"x": [1]}, ok)


if __name__ == "__main__":
    unittest.main()
