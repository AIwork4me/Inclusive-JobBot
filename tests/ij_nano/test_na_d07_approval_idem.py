"""NA-D07 adversarial tests: approval and idempotency binding.

Red against the audited source: approval is a bare reusable call_key string;
idempotency keys are not bound to the canonical operation; idempotent tools
can be called without an effect key; in-flight duplicates are not detected;
idempotency state is not exportable for checkpoint binding.
"""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.gateway.gateway import GatewayDenial, SafeToolGateway, ToolSpec  # noqa: E402


def spec(name="submit_refund", permission="orders.write", handler=None, **kw):
    calls = []

    def default(tool, args, draft):
        calls.append(json.dumps(args, sort_keys=True))
        draft.setdefault("refunds", []).append(args)
        return {"refund": args["order_id"], "n": len(calls)}
    return ToolSpec(
        name=name,
        parameters={"type": "object",
                    "properties": {"order_id": {"type": "string"},
                                   "amount": {"type": "number"}},
                    "required": ["order_id"], "additionalProperties": False},
        handler=handler or default,
        permission=permission, **kw)


def gateway(tool, store=None, now=None):
    gw = SafeToolGateway({tool.name: tool}, store=store, now=now)
    gw.grant(tool.permission)
    return gw


class TestApprovalBinding(unittest.TestCase):
    def test_approval_bound_to_tool(self):
        # RED: audited approve(key) + any tool + that key == accepted.
        t = spec(requires_approval=True)
        gw = gateway(t)
        gw.approve("k1", tool="other_tool", args={"order_id": "PO-1"},
                   operation_id="op1")
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("submit_refund", {"order_id": "PO-1"}, call_key="k1")
        self.assertEqual(cm.exception.stage, "approval")

    def test_approval_bound_to_canonical_arguments(self):
        # RED: same key, different arguments must be denied.
        t = spec(requires_approval=True)
        gw = gateway(t)
        gw.approve("k1", tool="submit_refund",
                   args={"order_id": "PO-1", "amount": 10}, operation_id="op1")
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("submit_refund", {"order_id": "PO-2"}, call_key="k1")
        self.assertEqual(cm.exception.stage, "approval")

    def test_key_ordering_is_canonicalized(self):
        # Same arguments in different key order are the same operation.
        t = spec(requires_approval=True)
        gw = gateway(t)
        gw.approve("k1", tool="submit_refund",
                   args={"amount": 10, "order_id": "PO-1"}, operation_id="op1")
        res = gw.call("submit_refund", {"order_id": "PO-1", "amount": 10},
                      call_key="k1")
        self.assertTrue(res["refund"] == "PO-1")

    def test_approval_expiry_enforced(self):
        t = spec(requires_approval=True)
        gw = gateway(t, now=lambda: 1000.0)
        gw.approve("k1", tool="submit_refund", args={"order_id": "PO-1"},
                   operation_id="op1", expires_at=999.0)
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("submit_refund", {"order_id": "PO-1"}, call_key="k1")
        self.assertIn("expire", cm.exception.reason)

    def test_approval_not_yet_expired_accepted(self):
        t = spec(requires_approval=True)
        gw = gateway(t, now=lambda: 1000.0)
        gw.approve("k1", tool="submit_refund", args={"order_id": "PO-1"},
                   operation_id="op1", expires_at=2000.0)
        res = gw.call("submit_refund", {"order_id": "PO-1"}, call_key="k1")
        self.assertEqual(res["refund"], "PO-1")


class TestIdempotencyBinding(unittest.TestCase):
    def test_missing_mandatory_effect_key_denied(self):
        # RED: audited gateway runs idempotent tools with effect_key=None.
        t = spec(idempotent=True)
        gw = gateway(t)
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("submit_refund", {"order_id": "PO-1"}, call_key="c1")
        self.assertEqual(cm.exception.stage, "idempotency")

    def test_same_effect_key_different_arguments_denied(self):
        # RED: audited idempotency keys are unbound strings.
        t = spec(idempotent=True)
        gw = gateway(t)
        gw.call("submit_refund", {"order_id": "PO-1"}, call_key="c1",
                effect_key="ref-1")
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("submit_refund", {"order_id": "PO-2"}, call_key="c2",
                    effect_key="ref-1")
        self.assertEqual(cm.exception.stage, "idempotency")

    def test_same_effect_key_different_tool_denied(self):
        t1 = spec(idempotent=True)
        t2 = spec(name="submit_refund_v2", idempotent=True)
        gw = SafeToolGateway({t1.name: t1, t2.name: t2})
        gw.grant("orders.write")
        gw.call("submit_refund", {"order_id": "PO-1"}, call_key="c1",
                effect_key="ref-1")
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("submit_refund_v2", {"order_id": "PO-1"}, call_key="c2",
                    effect_key="ref-1")
        self.assertEqual(cm.exception.stage, "idempotency")

    def test_duplicate_request_returns_recorded_effect(self):
        t = spec(idempotent=True)
        gw = gateway(t)
        r1 = gw.call("submit_refund", {"order_id": "PO-1"}, call_key="c1",
                     effect_key="ref-1")
        r2 = gw.call("submit_refund", {"order_id": "PO-1"}, call_key="c2",
                     effect_key="ref-1")
        self.assertEqual(r1, r2)
        self.assertEqual(len(gw.store["refunds"]), 1)   # executed once

    def test_duplicate_while_in_flight_denied(self):
        # RED: nothing marks an operation as pending during execution.
        entered = []
        release = threading_allocate()

        def slow(tool, args, draft):
            entered.append(1)
            release.wait(2)
            draft.setdefault("refunds", []).append(args)
            return {"refund": args["order_id"]}
        t = spec(idempotent=True, handler=slow)
        gw = gateway(t)
        import threading
        results = {}

        def run(key):
            try:
                results[key] = gw.call("submit_refund", {"order_id": "PO-1"},
                                       call_key=key, effect_key="ref-1")
            except GatewayDenial as e:
                results[key] = e
        th = threading.Thread(target=run, args=("c1",))
        th.start()
        import time
        while not entered:
            time.sleep(0.005)
        run("c2")                       # duplicate while c1 in flight
        release.set()
        th.join()
        self.assertIsInstance(results["c2"], GatewayDenial)
        self.assertEqual(results["c2"].stage, "idempotency")
        self.assertEqual(len(gw.store["refunds"]), 1)

    def test_idempotency_survives_restart_via_checkpoint_binding(self):
        # RED: audited gateway cannot export/load idempotency state.
        t = spec(idempotent=True)
        gw = gateway(t)
        gw.call("submit_refund", {"order_id": "PO-1"}, call_key="c1",
                effect_key="ref-1")
        exported = gw.export_idempotency()
        gw2 = gateway(spec(idempotent=True))
        gw2.load_idempotency(exported)
        r = gw2.call("submit_refund", {"order_id": "PO-1"}, call_key="c2",
                     effect_key="ref-1")
        self.assertEqual(r["refund"], "PO-1")
        self.assertEqual(len(gw2.store.get("refunds", [])), 0)  # not re-executed


def threading_allocate():
    import threading
    return threading.Event()


if __name__ == "__main__":
    unittest.main()
