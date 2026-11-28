"""D04 - adapter session contamination, and D05 - budgets as enforced through the real B0
loop against a scripted model server.

The model server is a SCRIPTED SOFTWARE FIXTURE. Nothing in this module is model or GPU
evidence; it exists to drive adapter code deterministically.

Sound contract under test:
  * a reused adapter behaves exactly like a fresh one on every trial
  * reset_session clears usage, counters, tokens, retries, history, answer, errors, tool
    registrations and the business world
  * every request receives the remaining budget; the deadline is absolute
  * a failed, timed-out or garbled call is charged and ends the trial with a stop reason
"""

from __future__ import annotations

import unittest

from tests.ij_sdk.support import RepoTestCase, final, read_rows, tool_call, usage_dict

from benchmarks.ij_sdk.adapters.base import Budget, Task, ToolManifest
from benchmarks.ij_sdk.adapters.b0_raw import B0RawAdapter

TOOL_DEFS = [{"type": "function", "function": {"name": "get_purchase_order",
                                                "parameters": {"type": "object"}}}]


def plain_handler(calls=None):
    def handler(name, args):
        if calls is not None:
            calls.append((name, dict(args)))
        return {"name": name, "result": {"total_amount": 17420.5}}
    return handler


class AdapterCase(RepoTestCase):
    def adapter(self, server, **config):
        adapter = B0RawAdapter("run-test", self.log())
        adapter.initialize("fixture", {"base_url": server.base_url}, config)
        return adapter

    def trial_steps(self, index, prompt_tokens=100, completion_tokens=50, name="get_purchase_order",
                    args=None, delay=0.0):
        args = {"order_id": "PO-2026-0001"} if args is None else args
        return [("json", 200, tool_call(f"c{index}", name, args, prompt_tokens, completion_tokens), delay),
                ("json", 200, final("订单总金额 17420.50 元。", prompt_tokens, completion_tokens), 0.0)]

    def run_trial(self, adapter, task_id, budget=None, tools=True, handler=None):
        if tools:
            adapter.register_tools(ToolManifest(tools=list(TOOL_DEFS), handler=handler or plain_handler()))
        return adapter.run_task(Task(task_id=task_id, prompt=f"task {task_id}", budget=budget or Budget()))


class SessionReset(AdapterCase):
    def test_reused_instance_matches_fresh_instance_on_every_trial(self):
        server = self.server(sum((self.trial_steps(i) for i in range(3)), []) * 2)
        fresh = [self.run_trial(self.adapter(server), f"F{i}") for i in range(3)]
        reused_adapter = self.adapter(server)
        reused = []
        for i in range(3):
            reused_adapter.reset_session(f"world-{i}")
            reused.append(self.run_trial(reused_adapter, f"R{i}"))
        for i in range(3):
            with self.subTest(trial=i):
                self.assertEqual(usage_dict(reused[i]), usage_dict(fresh[i]))
                self.assertEqual(reused[i]["status"], fresh[i]["status"])
                self.assertEqual(reused[i]["final_answer"], fresh[i]["final_answer"])

    def test_previous_trials_do_not_consume_the_next_budget(self):
        budget = Budget(max_model_calls=2)             # exactly what one trial needs
        server = self.server(sum((self.trial_steps(i) for i in range(3)), []) * 2)
        fresh = [self.run_trial(self.adapter(server), f"F{i}", budget=budget) for i in range(3)]
        reused_adapter = self.adapter(server)
        reused = []
        for i in range(3):
            reused_adapter.reset_session(f"world-{i}")
            reused.append(self.run_trial(reused_adapter, f"R{i}", budget=budget))
        self.assertEqual([r["status"] for r in fresh], ["PASS"] * 3)
        self.assertEqual([r["status"] for r in reused], ["PASS"] * 3,
                         f"a reused adapter charged earlier trials to this budget: {[r['detail'] for r in reused]}")

    def test_reset_session_clears_tool_registrations(self):
        server = self.server(self.trial_steps(0) + [("json", 200, final("ok"), 0.0)])
        adapter = self.adapter(server)
        self.run_trial(adapter, "T0")
        mark = len(server.requests)
        adapter.reset_session("world-1")
        adapter.run_task(Task(task_id="T1", prompt="p"))            # registers nothing
        first_trial = [bool((body or {}).get("tools")) for _, body in server.requests[:mark]]
        second_trial = [bool((body or {}).get("tools")) for _, body in server.requests[mark:]]
        self.assertTrue(first_trial and all(first_trial), "the detector saw no tools in the first trial")
        self.assertFalse(any(second_trial), "the previous task's tool registrations leaked into the next task")

    def test_counters_are_zero_after_reset_session(self):
        server = self.server(self.trial_steps(0))
        adapter = self.adapter(server)
        result = self.run_trial(adapter, "T0")
        self.assertEqual(usage_dict(result)["model_calls"], 2)      # the trial really used the counters
        adapter.reset_session("world-1")
        usage = adapter.export_usage()
        data = dict(vars(usage)) if hasattr(usage, "__dict__") else dict(usage)
        self.assertEqual({k: v for k, v in data.items() if v and k != "wall_seconds"}, {},
                         "counters survived reset_session")

    def test_reset_session_gives_a_fresh_business_world(self):
        store = {"qty": 120, "resets": []}

        class WorldHandler:
            def __call__(self, name, args):
                if name == "adjust_inventory":
                    store["qty"] += args.get("delta", 0)
                return {"name": name, "result": {"qty": store["qty"]}}

            def reset_session(self, world_id):
                store["qty"] = 120
                store["resets"].append(world_id)

        server = self.server(self.trial_steps(0, name="adjust_inventory", args={"sku": "SKU-1001", "delta": -5}))
        adapter = self.adapter(server)
        self.run_trial(adapter, "T0", handler=WorldHandler())
        self.assertEqual(store["qty"], 115)
        adapter.reset_session("world-B")
        self.assertEqual(store["qty"], 120, "reset_session did not give the next task a fresh business world")
        self.assertEqual(store["resets"][-1], "world-B", "reset_session did not tell the gateway which world comes next")

    def test_usage_is_a_copy_not_a_live_reference(self):
        server = self.server(self.trial_steps(0) + self.trial_steps(1))
        adapter = self.adapter(server)
        first = self.run_trial(adapter, "T0")
        snapshot = usage_dict(first)
        second = self.run_trial(adapter, "T1")
        self.assertEqual(usage_dict(first), snapshot, "a returned usage record changed after a later trial")
        self.assertIsNot(first["usage"], second["usage"])
        self.assertEqual(usage_dict(second), snapshot)

    def test_resetting_the_session_during_a_trial_aborts_that_trial(self):
        holder = {}

        def resetting_handler(name, args):
            holder["adapter"].reset_session("other-world")
            return {"name": name, "result": {"total_amount": 1}}

        server = self.server(self.trial_steps(0))
        adapter = holder["adapter"] = self.adapter(server)
        result = self.run_trial(adapter, "T0", handler=resetting_handler)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertEqual(result["detail"].get("stop_reason"), "session_reset_during_trial")
        self.assertEqual(len(server.requests), 1, "the aborted trial kept talking to the server")


class BudgetsThroughTheLoop(AdapterCase):
    def test_generated_token_budget_is_enforced_across_model_calls(self):
        steps = [("json", 200, tool_call("c0", "get_purchase_order", {"order_id": "PO-2026-0001"}, 100, 60), 0.0),
                 ("json", 200, tool_call("c1", "get_purchase_order", {"order_id": "PO-2026-0001"}, 100, 60), 0.0),
                 ("json", 200, final("ok", 100, 60), 0.0)]
        server = self.server(steps)
        result = self.run_trial(self.adapter(server), "tok", budget=Budget(max_generated_tokens=100))
        exceeded = result["usage"].completion_tokens > 100
        self.assertFalse(result["status"] == "PASS" and exceeded,
                         f"{result['usage'].completion_tokens} tokens were generated against a budget of 100 and the trial passed")

    def test_each_request_receives_the_remaining_token_budget(self):
        server = self.server([("json", 200, tool_call("c0", "get_purchase_order", {"order_id": "PO-2026-0001"}, 100, 20), 0.0),
                              ("json", 200, final("ok", 100, 20), 0.0)])
        result = self.run_trial(self.adapter(server), "rem", budget=Budget(max_generated_tokens=50))
        requested = [(body or {}).get("max_tokens") for _, body in server.requests]
        self.assertEqual(result["status"], "PASS", result["detail"])
        self.assertEqual(requested, [50, 30], "requests did not carry the remaining budget")

    def test_prompt_tokens_are_bounded_before_a_request_is_sent(self):
        steps = [("json", 200, tool_call("c0", "get_purchase_order", {"order_id": "PO-2026-0001"}, 200, 20), 0.0),
                 ("json", 200, final("ok", 200, 20), 0.0)]
        server = self.server(steps)
        result = self.run_trial(self.adapter(server), "pt", budget=Budget(max_prompt_tokens=250))
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("prompt_tokens", result["detail"].get("stop_reason", ""))
        self.assertEqual(len(server.requests), 1, "a request known to exceed the prompt budget was still sent")

    def test_the_absolute_deadline_is_enforced(self):
        steps = [("json", 200, tool_call(f"c{i}", "get_purchase_order", {"order_id": "PO-2026-0001"}), 0.4)
                 for i in range(3)] + [("json", 200, final("ok"), 0.4)]
        server = self.server(steps)
        result = self.run_trial(self.adapter(server), "dl", budget=Budget(max_wall_seconds=1.0))
        wall = result["usage"].wall_seconds
        self.assertFalse(result["status"] == "PASS" and wall > 1.25,
                         f"the trial ran {wall:.2f}s against a 1.0s deadline and passed")
        self.assertLess(wall, 1.25, f"the trial ran {wall:.2f}s against a 1.0s deadline")
        self.assertEqual(result["detail"].get("stop_reason"), "transport_timeout")

    def test_failures_are_charged_and_never_escape(self):
        cases = [
            ("http_500", [("text", 500, b'{"error":"internal"}', 0.0)], Budget(), "http_error"),
            ("timeout", [("close", 0, None, 1.2)], Budget(max_wall_seconds=0.5), "transport_timeout"),
            ("no_choices", [("json", 200, {"object": "chat.completion"}, 0.0)], Budget(), "malformed_response"),
            ("html_body", [("text", 200, b"<html>502 Bad Gateway</html>", 0.0)], Budget(), "malformed_response"),
            ("partial_body", [("partial", 200, b'{"choices": [{', 0.0)], Budget(), "server_unreachable"),
        ]
        for label, steps, budget, reason in cases:
            with self.subTest(case=label):
                server = self.server(steps)
                adapter = self.adapter(server)
                try:
                    result = self.run_trial(adapter, f"f_{label}", budget=budget)
                except Exception as exc:                  # audited tree: the exception escapes run_task
                    self.fail(f"{label}: {type(exc).__name__} escaped run_task")
                self.assertEqual(result["status"], "FAIL", f"{label}: {result['detail']}")
                self.assertEqual(result["detail"].get("stop_reason"), reason, f"{label}: {result['detail']}")
                self.assertGreaterEqual(result["usage"].model_calls, 1, f"{label}: the failed attempt was not counted")
                self.assertGreater(result["usage"].completion_tokens, 0, f"{label}: the failed attempt looked free")

    def test_a_truncated_generation_is_flagged(self):
        server = self.server([("json", 200, final("订单 PO-2026-0001 的总金额为 17420", finish_reason="length"), 0.0)])
        result = self.run_trial(self.adapter(server), "trunc", tools=False)
        flagged = result["detail"].get("truncated") is True
        self.assertFalse(result["status"] == "PASS" and not flagged,
                         "a generation cut off by finish_reason=length was returned as a complete answer")
        self.assertTrue(flagged)

    def test_error_feedback_retries_are_bounded_and_charged(self):
        bad = [("json", 200, tool_call(f"b{i}", "get_purchase_order", {}, arguments="<<not json"), 0.0) for i in range(3)]
        outcomes = {}
        for allowed in (0, 2):
            server = self.server(bad + [("json", 200, final("ok"), 0.0)])
            result = self.run_trial(self.adapter(server), f"rt{allowed}", budget=Budget(corrective_retries=allowed))
            fed_back = sum(1 for _, body in server.requests
                           if any(m.get("role") == "tool" and "invalid_arguments" in str(m.get("content"))
                                  for m in (body or {}).get("messages", [])))
            outcomes[allowed] = (result, fed_back)
        result, fed_back = outcomes[0]
        self.assertEqual(fed_back, 0, "corrective retries were granted although none were budgeted")
        self.assertEqual(result["detail"].get("stop_reason"), "budget:retries_exhausted")
        result, fed_back = outcomes[2]
        self.assertGreaterEqual(fed_back, 1, "budgeted corrective retries were not granted")
        self.assertLessEqual(fed_back, 2, "more error feedback was given than the budget allows")
        self.assertEqual(result["usage"].retries, 2, "error feedback was not charged as retries")
        self.assertEqual(result["detail"].get("stop_reason"), "budget:retries_exhausted")

    def test_tool_call_budget_is_enforced_before_dispatch(self):
        steps = [("json", 200, tool_call("c0", "get_purchase_order", {"order_id": "PO-2026-0001"}), 0.0),
                 ("json", 200, tool_call("c1", "get_purchase_order", {"order_id": "PO-2026-0001"}), 0.0),
                 ("json", 200, final("ok"), 0.0)]
        calls = []
        server = self.server(steps)
        result = self.run_trial(self.adapter(server), "tc", budget=Budget(max_tool_calls=1), handler=plain_handler(calls))
        self.assertEqual(len(calls), 1, f"the tool-call budget did not stop dispatch: {len(calls)} calls")
        self.assertNotEqual(result["status"], "PASS")


class EvidenceThroughTheLoop(AdapterCase):
    def test_a_trial_on_the_real_gateway_carries_state_evidence_and_budget(self):
        gateway_mod = self.import_new("benchmarks.ij_sdk.gateway")
        tools = self.import_new("benchmarks.ij_sdk.world_tools").build_tools()
        server = self.server(self.trial_steps(0))
        adapter = self.adapter(server)
        gateway = gateway_mod.ToolGateway(tools)
        adapter.register_tools(ToolManifest(tools=gateway.definitions(), handler=gateway))
        result = adapter.run_task(Task(task_id="G0", prompt="查询 PO-2026-0001 的总金额。"))
        self.assertEqual(result["status"], "PASS", result["detail"])
        for key in ("initial_state", "final_state", "final_state_hash", "action_log", "budget"):
            self.assertIn(key, result)
        self.assertEqual(result["initial_state"], result["final_state"])
        self.assertEqual(result["action_log"][0]["decision"], "allow")
        self.assertTrue(result["budget"]["matched_budget"], result["budget"]["enforcement_failures"])

    def test_the_event_log_names_what_was_captured(self):
        gateway_mod = self.import_new("benchmarks.ij_sdk.gateway")
        tools = self.import_new("benchmarks.ij_sdk.world_tools").build_tools()
        server = self.server(self.trial_steps(0))
        adapter = self.adapter(server)
        gateway = gateway_mod.ToolGateway(tools)
        adapter.register_tools(ToolManifest(tools=gateway.definitions(), handler=gateway))
        adapter.run_task(Task(task_id="G1", prompt="查询 PO-2026-0001 的总金额。"))
        rows = read_rows(self.path("events.jsonl"))
        by_stage = {}
        for row in rows:
            by_stage.setdefault(row["stage"], []).append(row)
        self.assertNotIn("model_generation", {s for s, rs in by_stage.items()
                                              if any((r["payload"] or {}).get("status") != "not_captured" for r in rs)})
        self.assertIn("server_response_decoded", by_stage)
        self.assertTrue(all(row.get("event_id") for row in rows))
        self.assertTrue(all(row.get("parent_id") is None or row["parent_id"] in {r["event_id"] for r in rows}
                            for row in rows))
        for stage in ("sdk_request", "sdk_model_adapter", "chat_template", "model_generation"):
            self.assertIn(stage, by_stage, f"{stage} was neither captured nor declared not captured")
        tool_ids = {(r["call_id"]) for r in by_stage.get("tool_result", [])}
        self.assertTrue(tool_ids, "tool events carry no call id")
        self.assertEqual({r["call_id"] for r in by_stage.get("tool_gateway", [])}, tool_ids)


if __name__ == "__main__":
    unittest.main()
