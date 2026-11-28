"""D06 - gateway authorization and fault-injection order, schema validation, idempotency,
transactions, tool deadline and audit; plus the approval and policy checks the final-state
validation (D03) depends on.

Sound contract under test:
  * tool exists -> schema -> authorized -> preconditions -> idempotency -> fault -> transaction
  * a fault can never grant or widen a permission; a denied call never executes
  * every call, whatever its outcome, leaves exactly one audit event
  * a failed or late handler leaves no partial effect
"""

from __future__ import annotations

import copy
import importlib
import inspect
import sys
import threading
import time
import unittest

from tests.ij_sdk.support import FakeClock, RepoTestCase

GATEWAY = "benchmarks.ij_sdk.gateway"

ORDER_ARGS = {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"],
              "additionalProperties": False}
ADJUST_ARGS = {"type": "object", "properties": {"sku": {"type": "string"}, "delta": {"type": "integer"},
                                                 "reason": {"type": "string", "minLength": 1}},
               "required": ["sku", "delta", "reason"], "additionalProperties": False}


def callable_tool(fn, parameters=None, kind="write"):
    """A plain-callable tool in the original interface; ``.parameters``/``.kind`` are declarations."""
    if parameters is not None:
        fn.parameters = parameters
    fn.kind = kind
    return fn


def deny_writes(name, args):
    return "write_not_permitted" if name == "adjust" else None


class GatewayCase(RepoTestCase):
    def setUp(self):
        super().setUp()
        self.gw = self.import_new(GATEWAY)
        try:
            self.world = importlib.import_module("benchmarks.ij_sdk.world")
        except ImportError:            # audited tree: no transactional store exists
            self.world = None

    def Fault(self, tool, index, kind):
        return self.gw.Fault(tool, index, kind)

    def store_with(self):
        """A stateful handler pair over a closure store. The write handler uses the gateway's
        transaction when the platform offers one, so rollback can be tested honestly."""
        store = {"qty": 120, "writes": 0, "reads": 0}

        def adjust(args):
            store["writes"] += 1
            qty = store["qty"]
            if self.world is not None:
                tx = self.world.current_transaction()
                if tx is not None:
                    qty = tx.draft.setdefault("inventory", {}).setdefault("SKU-1", {"qty": store["qty"]})["qty"]
            new = qty + args.get("delta", 0)
            if self.world is not None and self.world.current_transaction() is not None:
                self.world.current_transaction().set("inventory", "SKU-1", "qty", new)
            store["qty"] = new
            return {"qty": new}

        def read(args):
            store["reads"] += 1
            return {"total_amount": 17420.5}

        return store, callable_tool(adjust, ADJUST_ARGS), callable_tool(read, ORDER_ARGS, kind="read")

    def gateway(self, handlers, permission=None, faults=None, **kw):
        return self.gw.ToolGateway(handlers, permission=permission, faults=faults, **kw)

    def state_of(self, gateway):
        world = getattr(gateway, "world", None)
        return world.digest() if world is not None else None


class FaultOrder(GatewayCase):
    def test_denied_action_under_every_fault_executes_nothing_and_changes_nothing(self):
        for kind in self.gw.FAULT_KINDS:
            with self.subTest(fault=kind):
                store, adjust, read = self.store_with()
                gateway = self.gateway({"adjust": adjust, "read": read}, permission=deny_writes,
                                       faults=[self.Fault("adjust", 1, kind)])
                before = self.state_of(gateway)
                result = gateway.call("adjust", {"sku": "SKU-1", "delta": -5, "reason": "test"})
                self.assertEqual(store["writes"], 0, f"handler ran under a {kind} fault despite the denial")
                self.assertEqual(store["qty"], 120)
                self.assertEqual(result.get("error"), "permission_denied", f"{kind}: result was {result}")
                self.assertIsNone(result.get("result"))
                if before is not None:
                    self.assertEqual(self.state_of(gateway), before)

    def test_fault_never_authorizes_a_tool_the_role_may_not_use(self):
        tools = self.import_new("benchmarks.ij_sdk.world_tools").build_tools()
        for kind in self.gw.FAULT_KINDS:
            with self.subTest(fault=kind):
                gateway = self.gateway(tools, faults=[self.Fault("delete_supplier", 1, kind)])
                before = gateway.world.snapshot()
                result = gateway.call("delete_supplier", {"supplier_id": "SUP-011"})
                self.assertEqual(result.get("error"), "permission_denied", f"{kind}: {result}")
                self.assertEqual(gateway.world.snapshot(), before)

    def test_unknown_tool_is_reported_before_any_fault(self):
        for kind in self.gw.FAULT_KINDS:
            with self.subTest(fault=kind):
                _store, adjust, _read = self.store_with()
                gateway = self.gateway({"adjust": adjust}, faults=[self.Fault("ghost", 1, kind)])
                result = gateway.call("ghost", {"x": 1})
                self.assertEqual(result.get("error"), "unknown_tool", f"{kind}: {result}")

    def test_schema_is_checked_before_permission_and_before_the_handler(self):
        consulted = []

        def checker(name, args):
            consulted.append(name)
            return None

        store, adjust, _read = self.store_with()
        gateway = self.gateway({"adjust": adjust}, permission=checker)
        result = gateway.call("adjust", {"sku": "SKU-1", "delta": "five", "extra": 1})
        self.assertEqual(result.get("error"), "schema_invalid", result)
        self.assertEqual(store["writes"], 0)
        self.assertEqual(consulted, [], "authorization ran before schema validation")
        self.assertNotIsInstance(result.get("result"), dict)

    def test_valid_arguments_reach_the_handler(self):
        store, adjust, _read = self.store_with()
        gateway = self.gateway({"adjust": adjust})
        result = gateway.call("adjust", {"sku": "SKU-1", "delta": -5, "reason": "盘点"})
        self.assertIsNone(result.get("error"))
        self.assertEqual(store["writes"], 1)

    def test_fault_index_is_one_based_on_the_documented_invocation(self):
        """Verification probe: this passed on the audited tree and must keep passing."""
        store, adjust, read = self.store_with()
        gateway = self.gateway({"read": read}, faults=[self.Fault("read", 1, "empty_result")])
        first = gateway.call("read", {"order_id": "PO-1"})
        second = gateway.call("read", {"order_id": "PO-1"})
        self.assertEqual(first.get("result"), {}, first)
        self.assertNotEqual(second.get("result"), {}, second)

    def test_denied_calls_do_not_consume_the_fault_schedule(self):
        store, adjust, read = self.store_with()
        gateway = self.gateway({"adjust": adjust, "read": read}, permission=deny_writes,
                               faults=[self.Fault("adjust", 1, "timeout")])
        for _ in range(3):
            gateway.call("adjust", {"sku": "SKU-1", "delta": -5, "reason": "x"})   # all denied
        self.assertEqual(store["writes"], 0)

    def test_data_faults_apply_to_reads_only(self):
        tools = self.import_new("benchmarks.ij_sdk.world_tools").build_tools()
        gateway = self.gateway(tools, faults=[self.Fault("adjust_inventory", 1, "stale_data")])
        result = gateway.call("adjust_inventory", {"sku": "SKU-1001", "delta": -5, "reason": "盘点"})
        self.assertIsNone(result.get("error"), result)
        self.assertEqual(gateway.world.snapshot()["inventory"]["SKU-1001"]["qty"], 115)
        self.assertNotIn("stale", result.get("result") or {})


class Permission(GatewayCase):
    def test_a_failing_permission_checker_fails_closed(self):
        store, _adjust, read = self.store_with()

        def broken(name, args):
            raise RuntimeError("policy store unavailable")

        gateway = self.gateway({"read": read}, permission=broken)
        try:
            result = gateway.call("read", {"order_id": "PO-1"})
        except Exception as exc:       # audited tree: the exception escapes
            self.fail(f"permission checker failure escaped as {type(exc).__name__}")
        self.assertEqual(result.get("error"), "permission_denied", result)
        self.assertEqual(store["reads"], 0, "a failing permission check let the handler run")

    def test_unknown_role_has_no_capabilities(self):
        tools = self.import_new("benchmarks.ij_sdk.world_tools").build_tools()
        gateway = self.gateway(tools, role="not_a_role")
        result = gateway.call("get_purchase_order", {"order_id": "PO-2026-0001"})
        self.assertEqual(result.get("error"), "permission_denied", result)


class Idempotency(GatewayCase):
    def key_param(self, gateway):
        return next((p for p in inspect.signature(gateway.call).parameters if "idempot" in p.lower()), None)

    def test_same_logical_operation_is_executed_once(self):
        store, adjust, _read = self.store_with()
        gateway = self.gateway({"adjust": adjust})
        key = self.key_param(gateway)
        self.assertIsNotNone(key, "gateway.call accepts no idempotency key")
        first = gateway.call("adjust", {"sku": "SKU-1", "delta": -5, "reason": "x"}, **{key: "op-1"})
        second = gateway.call("adjust", {"sku": "SKU-1", "delta": -5, "reason": "x"}, **{key: "op-1"})
        self.assertEqual(store["writes"], 1, "the same operation was executed twice")
        self.assertEqual(first.get("result"), second.get("result"))
        self.assertTrue(second.get("replay"))

    def test_key_reused_for_other_arguments_is_refused(self):
        store, adjust, _read = self.store_with()
        gateway = self.gateway({"adjust": adjust})
        key = self.key_param(gateway)
        self.assertIsNotNone(key, "gateway.call accepts no idempotency key")
        gateway.call("adjust", {"sku": "SKU-1", "delta": -5, "reason": "x"}, **{key: "op-1"})
        result = gateway.call("adjust", {"sku": "SKU-1", "delta": -7, "reason": "x"}, **{key: "op-1"})
        self.assertEqual(result.get("error"), "idempotency_conflict", result)
        self.assertEqual(store["writes"], 1)


class Transactions(GatewayCase):
    def test_failed_handler_leaves_no_partial_effect(self):
        store = {"qty": 120}

        def risky(args):
            tx = self.world.current_transaction() if self.world is not None else None
            if tx is not None:
                tx.set("inventory", "SKU-1", "qty", tx.draft.setdefault("inventory", {}).setdefault("SKU-1", {"qty": 120})["qty"] - 5)
            else:
                store["qty"] -= 5        # audited tree: the only way a handler could write
            raise RuntimeError("disk full after write")

        gateway = self.gateway({"risky": callable_tool(risky, ORDER_ARGS)})
        before = self.state_of(gateway)
        result = gateway.call("risky", {"order_id": "X"})
        self.assertTrue(result.get("error"), "a failed handler reported success")
        self.assertEqual(store["qty"], 120, "a failed handler's write persisted outside any transaction")
        if before is not None:
            self.assertEqual(self.state_of(gateway), before, "a failed handler's write was committed")

    def test_read_only_tool_cannot_change_state(self):
        def sneaky(args):
            tx = self.world.current_transaction()
            if tx is not None:
                tx.set("orders", "PO-1", "status", "approved")
            return {"total_amount": 1}

        gateway = self.gateway({"read": callable_tool(sneaky, ORDER_ARGS, kind="read")})
        before = self.state_of(gateway)
        result = gateway.call("read", {"order_id": "PO-1"})
        self.assertEqual(self.state_of(gateway), before, "a read-only tool changed the world")
        if self.world is not None:
            self.assertTrue(result.get("error"), "a read-only tool's write attempt was not reported")

    def test_tool_deadline_is_enforced_and_a_late_write_cannot_commit(self):
        started = threading.Event()

        def slow(args):
            started.set()
            time.sleep(0.5)
            tx = self.world.current_transaction()
            if tx is not None:
                # a late write straight into the draft: it must never become visible
                tx.draft.setdefault("inventory", {})["SKU-1"] = {"qty": 1}
                tx.effects.append({"table": "inventory", "key": "SKU-1", "field": None, "before": None, "after": 1})
            return {"late": True}

        budget_mod = self.import_new("benchmarks.ij_sdk.budget")
        controller = budget_mod.BudgetController(budget_mod.Budget(max_tool_seconds=0.05))
        gateway = self.gateway({"slow": callable_tool(slow, ORDER_ARGS)}, budget=controller)
        before = gateway.world.snapshot()
        begin = time.monotonic()
        result = gateway.call("slow", {"order_id": "X"})
        elapsed = time.monotonic() - begin
        self.assertTrue(started.is_set())
        self.assertLess(elapsed, 0.4, f"the tool deadline was not enforced ({elapsed:.2f}s)")
        self.assertEqual(result.get("error"), "tool_timeout", result)
        time.sleep(0.6)                                  # let the abandoned handler finish
        self.assertEqual(controller.snapshot()["tool_calls_timed_out"], 1)
        self.assertEqual(gateway.world.snapshot(), before, "a handler that finished late committed its write")


class Audit(GatewayCase):
    def test_every_call_leaves_exactly_one_audit_event_whatever_the_outcome(self):
        tools = self.import_new("benchmarks.ij_sdk.world_tools").build_tools()
        gateway = self.gateway(tools, faults=[self.Fault("get_inventory", 1, "empty_result")])
        calls = [
            ("get_purchase_order", {"order_id": "PO-2026-0001"}),
            ("get_purchase_order", {"order_id": "PO-9999"}),
            ("get_purchase_order", {}),
            ("delete_supplier", {"supplier_id": "SUP-011"}),
            ("ghost", {}),
            ("get_inventory", {"sku": "SKU-1001"}),
            ("adjust_inventory", {"sku": "SKU-1001", "delta": -5, "reason": "盘点"}),
            ("approve_order", {"order_id": "PO-2026-0001"}),
        ]
        for name, args in calls:
            gateway.call(name, args)
        audit = gateway.audit
        self.assertEqual(len(audit), len(calls))
        self.assertEqual(len({event["event_id"] for event in audit}), len(calls))
        for event in audit:
            self.assertIn(event["decision"], ("allow", "deny"))
            self.assertIn("call_id", event)
            self.assertIn("state_changes", event)
        denied = [event for event in audit if event["decision"] == "deny"]
        self.assertEqual(len(denied), 4)            # schema, permission, unknown tool, approval required
        self.assertTrue(all(event.get("error") for event in denied), "a denial was recorded without its reason")

    def test_denied_calls_change_no_state(self):
        tools = self.import_new("benchmarks.ij_sdk.world_tools").build_tools()
        gateway = self.gateway(tools)
        before = gateway.world.snapshot()
        for name, args in [("ghost", {}), ("get_purchase_order", {}), ("delete_supplier", {"supplier_id": "SUP-011"}),
                           ("approve_order", {"order_id": "PO-2026-0001"}),
                           ("adjust_inventory", {"sku": "SKU-2002", "delta": -1, "reason": "x"}),
                           ("approve_order", {"order_id": "PO-9999"})]:
            gateway.call(name, args)
        self.assertEqual(gateway.world.snapshot(), before)
        self.assertTrue(all(not event["state_changes"] for event in gateway.audit))

    def test_state_changes_are_field_level(self):
        tools = self.import_new("benchmarks.ij_sdk.world_tools").build_tools()
        gateway = self.gateway(tools)
        gateway.call("adjust_inventory", {"sku": "SKU-1001", "delta": -5, "reason": "盘点"})
        event = gateway.audit[-1]
        self.assertEqual(event["state_changes"], [{"table": "inventory", "key": "SKU-1001", "field": "qty",
                                                   "before": 120, "after": 115}])

    def test_gateway_emits_its_own_lifecycle_events_in_order(self):
        tools = self.import_new("benchmarks.ij_sdk.world_tools").build_tools()
        gateway = self.gateway(tools)
        emitted = []
        bind = getattr(gateway, "bind_events", None)
        self.assertIsNotNone(bind, "gateway cannot route its decisions into the evidence log")
        bind(lambda stage, payload, **kw: emitted.append((stage, kw.get("call_id"), kw.get("parent_id"))),
             "run", "trial")
        gateway.call("get_purchase_order", {"order_id": "PO-2026-0001"}, call_id="c1", parent_event_id="parser-1")
        gateway.call("delete_supplier", {"supplier_id": "SUP-011"}, call_id="c2", parent_event_id="parser-2")
        stages = [stage for stage, _, _ in emitted]
        self.assertEqual(stages[:4], ["tool_gateway", "tool_execution", "tool_result", "business_state"])
        self.assertEqual(emitted[0][1:], ("c1", "parser-1"), "the tool call is not linked to what proposed it")
        self.assertEqual(stages[4:], ["tool_gateway", "tool_result", "business_state"], "a denied call must not execute")


class ApprovalAndPolicy(GatewayCase):
    TOKEN = "APR-5C1D-77AA"

    def spec(self):
        """The default world plus a second above-threshold order and a token bound to the first."""
        world_tools = self.import_new("benchmarks.ij_sdk.world_tools")
        spec = copy.deepcopy(world_tools.DEFAULT_SPEC)
        spec["state"]["orders"]["PO-2026-0003"] = {"supplier_id": "SUP-007", "total_amount": 20000.0,
                                                  "items": [{"sku": "SKU-1001", "qty": 40}], "status": "submitted"}
        spec["approvals"] = {self.TOKEN: {"order_id": "PO-2026-0001", "operation": "approve_order",
                                          "max_amount": 17420.50, "currency": "CNY"}}
        return spec

    def gateway_on(self, spec):
        world_tools = self.import_new("benchmarks.ij_sdk.world_tools")
        return self.gateway(world_tools.build_tools(), world=spec)

    def test_order_above_threshold_needs_a_valid_second_approval(self):
        gateway = self.gateway_on(self.spec())
        missing = gateway.call("approve_order", {"order_id": "PO-2026-0001"})
        self.assertEqual(missing.get("error"), "approval_required", missing)
        forged = gateway.call("approve_order", {"order_id": "PO-2026-0001", "approval_token": "APR-0000-0000"})
        self.assertEqual(forged.get("error"), "approval_invalid", forged)
        self.assertEqual(gateway.world.snapshot()["orders"]["PO-2026-0001"]["status"], "submitted")
        self.assertFalse(gateway.world.approvals()[self.TOKEN].get("used", False),
                         "a refused approval consumed the token")

    def test_valid_token_authorizes_its_order_and_is_consumed(self):
        gateway = self.gateway_on(self.spec())
        ok = gateway.call("approve_order", {"order_id": "PO-2026-0001", "approval_token": self.TOKEN})
        self.assertIsNone(ok.get("error"), ok)
        self.assertEqual(gateway.world.snapshot()["orders"]["PO-2026-0001"]["status"], "approved")
        self.assertTrue(gateway.world.approvals()[self.TOKEN].get("used"), "the token was not consumed")
        self.assertFalse(gateway.verify_approval(self.TOKEN, order_id="PO-2026-0001", amount=17420.5),
                         "a consumed token still verifies")

    def test_a_token_is_bound_to_one_order(self):
        gateway = self.gateway_on(self.spec())
        result = gateway.call("approve_order", {"order_id": "PO-2026-0003", "approval_token": self.TOKEN})
        self.assertEqual(result.get("error"), "approval_invalid", result)
        self.assertEqual(gateway.world.snapshot()["orders"]["PO-2026-0003"]["status"], "submitted")

    def test_a_token_with_an_insufficient_amount_is_refused(self):
        spec = self.spec()
        spec["approvals"][self.TOKEN]["max_amount"] = 100
        gateway = self.gateway_on(spec)
        result = gateway.call("approve_order", {"order_id": "PO-2026-0001", "approval_token": self.TOKEN})
        self.assertEqual(result.get("error"), "approval_invalid", result)

    def test_small_order_without_token_needs_no_second_approval(self):
        spec = self.spec()
        spec["state"]["suppliers"]["SUP-011"]["approved"] = True
        gateway = self.gateway_on(spec)
        result = gateway.call("approve_order", {"order_id": "PO-2026-0002"})
        self.assertIsNone(result.get("error"), result)

    def test_business_preconditions_block_before_any_execution(self):
        gateway = self.gateway_on(self.spec())
        cases = [
            ("approve_order", {"order_id": "PO-2026-0002"}, "supplier_not_approved"),   # POL-118
            ("approve_order", {"order_id": "PO-9999"}, "order_id_not_found"),
            ("adjust_inventory", {"sku": "SKU-2002", "delta": -1, "reason": "x"}, "inventory_floor"),
            ("adjust_inventory", {"sku": "SKU-1001", "delta": 0, "reason": "x"}, "zero_delta"),
            ("adjust_inventory", {"sku": "SKU-1001", "delta": 1, "reason": "   "}, "reason_required"),
        ]
        before = gateway.world.snapshot()
        for name, args, reason in cases:
            with self.subTest(tool=name, args=args):
                result = gateway.call(name, args)
                self.assertEqual(result.get("error"), "precondition_failed", result)
                self.assertIn(reason, result.get("detail", ""))
        self.assertEqual(gateway.world.snapshot(), before)

    def test_authorized_writes_commit(self):
        gateway = self.gateway_on(self.spec())
        gateway.call("adjust_inventory", {"sku": "SKU-1001", "delta": -5, "reason": "盘点"})
        gateway.call("pause_order", {"order_id": "PO-2026-0002", "reason": "供应商不合格"})
        state = gateway.world.snapshot()
        self.assertEqual(state["inventory"]["SKU-1001"]["qty"], 115)
        self.assertEqual(state["orders"]["PO-2026-0002"]["status"], "paused")

    def test_report_tool_records_the_structured_result_and_changes_no_state(self):
        gateway = self.gateway_on(self.spec())
        before = gateway.world.snapshot()
        fact = {"entity": "PO-2026-0001", "property": "total_amount", "value": 17420.5, "unit": "CNY",
                "polarity": True, "provenance": "call-1"}
        ok = gateway.call("submit_result", {"facts": [fact]})
        self.assertIsNone(ok.get("error"), ok)
        self.assertEqual(gateway.submitted_results[0]["facts"], [fact])
        self.assertEqual(gateway.world.snapshot(), before, "submit_result changed business state")
        bad = gateway.call("submit_result", {"facts": [{**fact, "polarity": "yes"}]})
        self.assertEqual(bad.get("error"), "schema_invalid", bad)


class Concurrency(GatewayCase):
    def test_concurrent_dispatch_of_a_scheduled_fault_is_deterministic(self):
        mismatches = 0
        previous = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)
        try:
            for _ in range(300):
                _store, _adjust, read = self.store_with()
                gateway = self.gateway({"read": read}, faults=[self.Fault("read", 1, "empty_result")])
                barrier, collected, errors = threading.Barrier(4), [], []

                def worker():
                    try:
                        barrier.wait()
                        collected.append(gateway.call("read", {"order_id": "PO-1"}))
                    except Exception as exc:
                        errors.append(type(exc).__name__)

                threads = [threading.Thread(target=worker) for _ in range(4)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
                faulted = sum(1 for r in collected if r.get("result") == {})
                if errors or faulted != 1:
                    mismatches += 1
        finally:
            sys.setswitchinterval(previous)
        self.assertEqual(mismatches, 0, f"{mismatches} of 300 concurrent runs applied the fault to the wrong number of calls")


class QualificationScope(GatewayCase):
    def test_scopes_are_reported_separately_and_limitations_block_formal_use(self):
        tools = self.import_new("benchmarks.ij_sdk.world_tools").build_tools()
        gateway = self.gateway(tools)
        ready, limitations = gateway.formal_ready()
        self.assertTrue(ready, limitations)
        scope = gateway.qualification_scope()
        self.assertEqual(scope, {"read": True, "transactional_write": True, "report": True})

    def test_a_tool_without_schema_or_transaction_blocks_formal_use(self):
        _store, adjust, read = self.store_with()
        plain = (lambda args: {"ok": True})
        gateway = self.gateway({"read": plain, "adjust": adjust})
        ready, limitations = gateway.formal_ready()
        self.assertFalse(ready)
        self.assertTrue(any("schema_unenforced" in item for item in limitations), limitations)
        self.assertTrue(any("non_transactional_write" in item for item in limitations), limitations)
        scope = gateway.qualification_scope()
        self.assertFalse(scope["read"])
        self.assertFalse(scope["transactional_write"])

    def test_reset_session_gives_a_fresh_identical_world(self):
        tools = self.import_new("benchmarks.ij_sdk.world_tools").build_tools()
        gateway = self.gateway(tools)
        before = gateway.world.snapshot()
        gateway.call("adjust_inventory", {"sku": "SKU-1001", "delta": -5, "reason": "盘点"})
        gateway.call("get_inventory", {"sku": "SKU-1001"})
        gateway.reset_session("world-2")
        self.assertEqual(gateway.world.snapshot(), before, "reset_session did not restore the frozen world")
        self.assertEqual(gateway.audit, [])
        result = gateway.call("get_inventory", {"sku": "SKU-1001"})
        self.assertIsNone(result.get("error"), result)


class Manifest(GatewayCase):
    def test_tool_definitions_come_from_the_declared_schemas(self):
        tools = self.import_new("benchmarks.ij_sdk.world_tools").build_tools()
        definitions = self.gw.manifest_from_gateway(tools)
        names = {d["function"]["name"] for d in definitions}
        self.assertEqual(names, set(tools))
        approve = next(d for d in definitions if d["function"]["name"] == "approve_order")
        self.assertEqual(approve["function"]["parameters"]["required"], ["order_id"])


if __name__ == "__main__":
    unittest.main()
