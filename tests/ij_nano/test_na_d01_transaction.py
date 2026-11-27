"""NA-D01 adversarial tests: transaction isolation (nested-state aliasing).

Red against the audited source: `Transaction.begin` copies only the top level
(`dict(self._store)`), so handlers mutate shared nested objects and rollback
cannot restore the original business state.
"""
import pathlib
import sys
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.gateway.gateway import (SafeToolGateway, ToolError,  # noqa: E402
                                       ToolSpec)


def gw_with(tool_spec, store=None):
    gw = SafeToolGateway({tool_spec.name: tool_spec}, store=store)
    gw.grant(tool_spec.permission)
    return gw


def nested_spec(handler):
    return ToolSpec(
        name="update_order",
        parameters={"type": "object", "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"], "additionalProperties": False},
        handler=handler,
        permission="orders.write",
    )


class TestNestedIsolation(unittest.TestCase):
    def _store(self):
        return {
            "orders": {"PO-1": {"status": "new", "lines": [{"sku": "A", "qty": 1}]}},
            "customer": {"C-9": {"tier": "gold", "tags": ["vip"]}},
        }

    def test_handler_exception_leaves_nested_dicts_intact(self):
        def boom(tool, args, draft):
            draft["orders"]["PO-1"]["status"] = "corrupted"
            draft["orders"]["PO-1"]["lines"].append({"sku": "X", "qty": 99})
            raise ValueError("handler exploded")
        store = self._store()
        gw = gw_with(nested_spec(boom), store=store)
        with self.assertRaises(ToolError):
            gw.call("update_order", {"order_id": "PO-1"}, call_key="c1")
        self.assertEqual(store["orders"]["PO-1"]["status"], "new")
        self.assertEqual(len(store["orders"]["PO-1"]["lines"]), 1)

    def test_handler_exception_leaves_nested_lists_intact(self):
        def boom(tool, args, draft):
            draft["customer"]["C-9"]["tags"].append("hacked")
            draft["customer"]["C-9"]["tier"] = "platinum"
            raise RuntimeError("fail")
        store = self._store()
        gw = gw_with(nested_spec(boom), store=store)
        with self.assertRaises(ToolError):
            gw.call("update_order", {"order_id": "PO-1"}, call_key="c1")
        self.assertEqual(store["customer"]["C-9"]["tags"], ["vip"])
        self.assertEqual(store["customer"]["C-9"]["tier"], "gold")

    def test_multiple_entities_isolated_on_rollback(self):
        def boom(tool, args, draft):
            draft["orders"]["PO-1"]["status"] = "x"
            draft["customer"]["C-9"]["tier"] = "x"
            draft["brand.new"] = "x"
            raise ValueError("fail")
        store = self._store()
        gw = gw_with(nested_spec(boom), store=store)
        with self.assertRaises(ToolError):
            gw.call("update_order", {"order_id": "PO-1"}, call_key="c1")
        self.assertEqual(store["orders"]["PO-1"]["status"], "new")
        self.assertEqual(store["customer"]["C-9"]["tier"], "gold")
        self.assertNotIn("brand.new", store)

    def test_commit_does_not_alias_draft_into_store(self):
        seen = {}

        def ok(tool, args, draft):
            draft["orders"]["PO-1"]["status"] = "paid"
            seen["draft"] = draft
            return {"ok": True}
        store = self._store()
        gw = gw_with(nested_spec(ok), store=store)
        gw.call("update_order", {"order_id": "PO-1"}, call_key="c1")
        self.assertEqual(store["orders"]["PO-1"]["status"], "paid")
        # Post-commit mutation through the handler's draft reference must not
        # reach the store (no shared nested objects).
        seen["draft"]["orders"]["PO-1"]["status"] = "mutated-after-commit"
        self.assertEqual(store["orders"]["PO-1"]["status"], "paid")

    def test_handler_cannot_reach_store_object(self):
        store = self._store()

        def sneaky(tool, args, draft):
            # The handler must receive a draft, never the store itself.
            seen["is_store"] = draft is store
            seen["nested_shared"] = draft["orders"] is store["orders"]
            return {"ok": True}
        seen = {}
        gw = gw_with(nested_spec(sneaky), store=store)
        gw.call("update_order", {"order_id": "PO-1"}, call_key="c1")
        self.assertFalse(seen["is_store"])
        self.assertFalse(seen["nested_shared"])

    def test_invalid_commit_and_double_commit_rejected(self):
        from nanoagent.gateway.gateway import Transaction
        store = self._store()
        tx = Transaction(store)
        tx.begin()
        tx.commit()
        with self.assertRaises(RuntimeError):
            tx.commit()          # double commit
        tx2 = Transaction(store)
        with self.assertRaises(RuntimeError):
            tx2.commit()         # commit without begin
        tx3 = Transaction(store)
        tx3.begin()
        tx3.rollback()
        with self.assertRaises(RuntimeError):
            tx3.commit()         # commit after rollback

    def test_concurrent_calls_serialized_not_interleaved(self):
        # Concurrent writes "where supported": the in-memory store must never
        # observe interleaved half-transactions; calls serialize.
        errors = []

        def slow(tool, args, draft):
            draft["orders"]["PO-1"]["status"] = f"by-{args['order_id']}"
            import time
            time.sleep(0.01)
            if len(draft["orders"]) != 1:
                errors.append("interleaved")
            return {"ok": True}
        store = self._store()
        gw = gw_with(nested_spec(slow), store=store)
        threads = [threading.Thread(target=gw.call,
                                    args=("update_order", {"order_id": f"t{i}"}),
                                    kwargs={"call_key": f"c{i}"})
                   for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertIn(store["orders"]["PO-1"]["status"],
                      {f"by-t{i}" for i in range(4)})


if __name__ == "__main__":
    unittest.main()
