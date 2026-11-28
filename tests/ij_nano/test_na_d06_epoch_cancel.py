"""NA-D06 adversarial tests: epoch and cancellation protection at boundaries.

Red against the audited source: SafeToolGateway.call accepts
state_epoch_getter but never consults it; there is no cancellation or
deadline check before dispatch or before commit, so late handlers commit
effects after session reset / cancellation / deadline expiry.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.core.budget import BudgetController, BudgetSpec, DeadlineExceeded  # noqa: E402
from nanoagent.core.checkpoint import CancellationToken  # noqa: E402
from nanoagent.core.state import Session  # noqa: E402
from nanoagent.gateway.gateway import GatewayDenial, SafeToolGateway, ToolSpec  # noqa: E402


def spec(name="update_order", permission="orders.write", handler=None, **kw):
    def default(tool, args, draft):
        draft[f"last:{tool}"] = args
        return {"ok": True}
    return ToolSpec(
        name=name,
        parameters={"type": "object", "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"], "additionalProperties": False},
        handler=handler or default,
        permission=permission, **kw)


def gateway(tool, store=None):
    gw = SafeToolGateway({tool.name: tool}, store=store)
    gw.grant(tool.permission)
    return gw


class TestEpochProtection(unittest.TestCase):
    def test_epoch_mismatch_denied_before_dispatch(self):
        # RED: audited gateway ignores state_epoch entirely.
        t = spec()
        gw = gateway(t)
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("update_order", {"order_id": "PO-1"}, call_key="c1",
                    state_epoch=0, state_epoch_getter=lambda: 1)
        self.assertEqual(cm.exception.stage, "epoch")
        self.assertNotIn("last:update_order", gw.store)

    def test_delayed_handler_completing_after_reset_commits_nothing(self):
        # RED: handler resets the session mid-flight, then returns normally.
        s = Session()
        t = spec(handler=lambda tool, args, draft: s.reset())
        gw = gateway(t)
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("update_order", {"order_id": "PO-1"}, call_key="c1",
                    state_epoch=s.epoch, state_epoch_getter=lambda: s.epoch)
        self.assertEqual(cm.exception.stage, "epoch")
        self.assertNotIn("last:update_order", gw.store)
        self.assertEqual(s.epoch, 1)

    def test_epoch_recheck_happens_before_commit(self):
        # The getter is consulted again between handler return and commit.
        checks = {"n": 0}

        def getter():
            checks["n"] += 1
            return 0 if checks["n"] < 2 else 99     # changes mid-call
        t = spec()
        gw = gateway(t)
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("update_order", {"order_id": "PO-1"}, call_key="c1",
                    state_epoch=0, state_epoch_getter=getter)
        self.assertEqual(cm.exception.stage, "epoch")
        self.assertNotIn("last:update_order", gw.store)


class TestCancellationProtection(unittest.TestCase):
    def test_cancelled_before_dispatch_denied(self):
        t = spec()
        gw = gateway(t)
        tok = CancellationToken()
        tok.set()
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("update_order", {"order_id": "PO-1"}, call_key="c1", cancel=tok)
        self.assertEqual(cm.exception.stage, "cancellation")
        self.assertNotIn("last:update_order", gw.store)

    def test_cancelled_during_handler_commits_nothing(self):
        # RED: handler cancels mid-flight, then returns normally.
        tok = CancellationToken()
        t = spec(handler=lambda tool, args, draft: tok.set())
        gw = gateway(t)
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("update_order", {"order_id": "PO-1"}, call_key="c1", cancel=tok)
        self.assertEqual(cm.exception.stage, "cancellation")
        self.assertNotIn("last:update_order", gw.store)


class TestDeadlineProtection(unittest.TestCase):
    def test_deadline_expired_before_dispatch_denied(self):
        # RED: audited gateway has no deadline hook.
        bc = BudgetController(BudgetSpec(model_calls=1, wall_clock_seconds=1))

        def expired():
            raise DeadlineExceeded("expired")
        t = spec()
        gw = gateway(t)
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("update_order", {"order_id": "PO-1"}, call_key="c1",
                    deadline_check=expired)
        self.assertEqual(cm.exception.stage, "deadline")
        self.assertNotIn("last:update_order", gw.store)

    def test_deadline_expired_during_handler_commits_nothing(self):
        bc = BudgetController(BudgetSpec(model_calls=1, wall_clock_seconds=1))

        def handler(tool, args, draft):
            bc._deadline = 0        # expire mid-flight
            return {"ok": True}
        t = spec(handler=handler)
        gw = gateway(t)
        with self.assertRaises(GatewayDenial) as cm:
            gw.call("update_order", {"order_id": "PO-1"}, call_key="c1",
                    deadline_check=bc.check_deadline)
        self.assertEqual(cm.exception.stage, "deadline")
        self.assertNotIn("last:update_order", gw.store)


class TestNonReversibleActions(unittest.TestCase):
    def test_non_reversible_requires_approval_by_contract(self):
        # RED: audited ToolSpec has no non-reversible contract; registering
        # one without approval must fail closed at registration time.
        with self.assertRaises(ValueError):
            spec(name="send_payment", non_reversible=True)   # no approval

    def test_non_reversible_with_approval_accepted(self):
        t = spec(name="send_payment", non_reversible=True, requires_approval=True)
        gw = gateway(t)
        gw.approve("pay-1", tool="send_payment",
                   args={"order_id": "PO-1"}, operation_id="op-9")
        res = gw.call("send_payment", {"order_id": "PO-1"}, call_key="pay-1",
                      effect_key="pay-PO-1")
        self.assertTrue(res["ok"])


if __name__ == "__main__":
    unittest.main()
