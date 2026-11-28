"""D05 - the budget controller: attempts counted at start, remaining budget per request,
absolute monotonic deadline, failed calls charged, permits closed once, overruns recorded,
unenforced limits reported."""

from __future__ import annotations

from tests.ij_sdk.support import FakeClock, RepoTestCase

BUDGET = "benchmarks.ij_sdk.budget"


class BudgetCase(RepoTestCase):
    def setUp(self):
        super().setUp()
        self.mod = self.import_new(BUDGET)
        self.clock = FakeClock()

    def controller(self, **limits):
        return self.mod.BudgetController(self.mod.Budget(**limits), clock=self.clock)

    def exhausted(self):
        return self.mod.BudgetExhausted


class Accounting(BudgetCase):
    def test_an_attempt_is_counted_when_it_starts(self):
        budget = self.controller()
        permit = budget.begin_model_call()
        self.assertEqual(budget.snapshot()["model_calls"], 1, "an in-flight call was not counted")
        budget.end_model_call(permit, completion_tokens=10)

    def test_each_request_receives_the_remaining_budget(self):
        budget = self.controller(max_generated_tokens=100)
        first = budget.begin_model_call()
        self.assertEqual(first.max_tokens, 100)
        budget.end_model_call(first, completion_tokens=60)
        second = budget.begin_model_call()
        self.assertEqual(second.max_tokens, 40, "the second request did not receive the remaining budget")
        budget.end_model_call(second, completion_tokens=40)
        with self.assertRaises(self.exhausted()) as caught:
            budget.begin_model_call()
        self.assertEqual(caught.exception.reason, "generated_tokens_exhausted")

    def test_per_request_cap_applies(self):
        budget = self.controller(max_generated_tokens=100000, max_request_tokens=64)
        self.assertEqual(budget.begin_model_call().max_tokens, 64)
        smaller = self.controller(max_generated_tokens=100000, max_request_tokens=64)
        self.assertEqual(smaller.begin_model_call(requested_max_tokens=8).max_tokens, 8)

    def test_model_call_and_tool_call_limits(self):
        budget = self.controller(max_model_calls=1, max_tool_calls=1)
        permit = budget.begin_model_call()
        budget.end_model_call(permit)
        with self.assertRaises(self.exhausted()):
            budget.begin_model_call()
        tool = budget.begin_tool_call()
        budget.end_tool_call(tool)
        with self.assertRaises(self.exhausted()) as caught:
            budget.begin_tool_call()
        self.assertEqual(caught.exception.reason, "tool_calls_exhausted")


class Charging(BudgetCase):
    def test_a_failed_call_is_charged_its_reservation(self):
        budget = self.controller()
        permit = budget.begin_model_call()
        budget.end_model_call(permit, error="http_error")
        snap = budget.snapshot()
        self.assertEqual(snap["model_calls"], 1)
        self.assertEqual(snap["model_calls_failed"], 1)
        self.assertEqual(snap["completion_tokens"], permit.max_tokens, "a failed call looked free")
        self.assertEqual(snap["completion_tokens_unreported"], permit.max_tokens)

    def test_a_timed_out_call_is_charged_its_reservation(self):
        budget = self.controller()
        permit = budget.begin_model_call()
        budget.end_model_call(permit, timed_out=True)
        snap = budget.snapshot()
        self.assertEqual(snap["model_calls_timed_out"], 1)
        self.assertEqual(snap["completion_tokens"], permit.max_tokens, "a timeout looked free")

    def test_reported_usage_is_charged_exactly(self):
        budget = self.controller()
        permit = budget.begin_model_call()
        budget.end_model_call(permit, prompt_tokens=120, completion_tokens=30)
        snap = budget.snapshot()
        self.assertEqual((snap["prompt_tokens"], snap["completion_tokens"], snap["completion_tokens_unreported"]),
                         (120, 30, 0))
        self.assertEqual(snap["model_calls_completed"], 1)

    def test_a_server_producing_more_than_permitted_is_an_overrun(self):
        budget = self.controller()
        permit = budget.begin_model_call()
        budget.end_model_call(permit, completion_tokens=permit.max_tokens + 5)
        snap = budget.snapshot()
        self.assertEqual(snap["completion_tokens"], permit.max_tokens + 5)
        self.assertEqual(snap["overruns"][0]["code"], "generated_tokens_exceeded_permit")
        self.assertFalse(snap["matched_budget"], "an overrun was hidden")

    def test_a_permit_cannot_be_closed_twice(self):
        budget = self.controller()
        permit = budget.begin_model_call()
        budget.end_model_call(permit, completion_tokens=1)
        budget.end_model_call(permit, completion_tokens=1)
        snap = budget.snapshot()
        self.assertEqual(snap["completion_tokens"], 1, "a double close double-charged")
        self.assertEqual(snap["enforcement_failures"][0]["code"], "permit_closed_twice_or_unknown")

    def test_a_permit_left_open_is_charged_and_reported(self):
        budget = self.controller()
        permit = budget.begin_model_call()
        snap = budget.finalize()
        self.assertEqual(snap["completion_tokens"], permit.max_tokens)
        self.assertEqual(snap["enforcement_failures"][0]["code"], "permit_left_open")
        self.assertFalse(snap["matched_budget"])


class PromptTokens(BudgetCase):
    def test_prompt_tokens_are_bounded(self):
        budget = self.controller(max_prompt_tokens=1000)
        permit = budget.begin_model_call(prompt_tokens_lower_bound=200)
        budget.end_model_call(permit, prompt_tokens=600, completion_tokens=10)
        budget.precheck_prompt_tokens(400)                       # exactly the remaining budget
        with self.assertRaises(self.exhausted()):
            budget.precheck_prompt_tokens(401)
        with self.assertRaises(self.exhausted()):
            budget.begin_model_call(prompt_tokens_lower_bound=401)
        second = budget.begin_model_call(prompt_tokens_lower_bound=400)
        budget.end_model_call(second, prompt_tokens=500, completion_tokens=10)   # the context grew
        self.assertEqual(budget.snapshot()["overruns"][-1]["code"], "prompt_tokens_exceeded")


class DeadlineAndTools(BudgetCase):
    def test_the_deadline_is_absolute_and_monotonic(self):
        budget = self.controller(max_wall_seconds=10.0)
        self.clock.advance(9.0)
        permit = budget.begin_model_call()
        self.assertAlmostEqual(permit.timeout_seconds, 1.0)
        self.assertAlmostEqual(permit.deadline, budget.deadline())
        budget.end_model_call(permit)
        self.clock.advance(1.0)
        with self.assertRaises(self.exhausted()) as caught:
            budget.begin_model_call()
        self.assertEqual(caught.exception.reason, "deadline_exceeded")
        with self.assertRaises(self.exhausted()):
            budget.begin_tool_call()

    def test_tool_deadline_is_the_smaller_limit_and_overrun_is_recorded(self):
        budget = self.controller(max_wall_seconds=100.0, max_tool_seconds=2.0)
        permit = budget.begin_tool_call()
        self.assertAlmostEqual(permit.timeout_seconds, 2.0)
        self.clock.advance(3.0)
        budget.end_tool_call(permit)
        snap = budget.snapshot()
        self.assertEqual(snap["overruns"][0]["code"], "tool_deadline_exceeded")
        self.assertEqual(snap["tool_calls_completed"], 1)
        self.assertFalse(snap["matched_budget"])

    def test_a_timed_out_tool_call_is_counted(self):
        budget = self.controller()
        permit = budget.begin_tool_call()
        budget.end_tool_call(permit, timed_out=True)
        self.assertEqual(budget.snapshot()["tool_calls_timed_out"], 1)


class RetriesAndLimits(BudgetCase):
    def test_corrective_retries_are_bounded_and_charged(self):
        budget = self.controller(corrective_retries=2)
        self.assertTrue(budget.charge_retry("a"))
        self.assertTrue(budget.charge_retry("b"))
        self.assertFalse(budget.charge_retry("c"), "a retry beyond the budget was granted")
        self.assertEqual(budget.snapshot()["retries"], 2)

    def test_no_retry_is_granted_when_none_are_budgeted(self):
        self.assertFalse(self.controller().charge_retry("a"))
        self.assertEqual(self.controller().snapshot()["retries"], 0)

    def test_cancellation_stops_every_further_attempt(self):
        budget = self.controller()
        budget.cancel("operator requested")
        for begin in (budget.begin_model_call, budget.begin_tool_call):
            with self.assertRaises(self.exhausted()) as caught:
                begin()
            self.assertEqual(caught.exception.reason, "cancelled: operator requested")
        self.assertEqual(budget.snapshot()["cancelled"], "operator requested")

    def test_a_limit_the_framework_cannot_honour_blocks_matched_budget(self):
        budget = self.controller()
        self.assertTrue(budget.matched_budget())
        budget.mark_unenforced("max_prompt_tokens", "SDK sets its own context truncation")
        snap = budget.snapshot()
        self.assertFalse(snap["matched_budget"])
        self.assertEqual(snap["unenforced"], [{"aspect": "max_prompt_tokens",
                                               "detail": "SDK sets its own context truncation"}])


class Isolation(BudgetCase):
    def test_the_budget_is_copied_not_shared(self):
        limits = self.mod.Budget(max_model_calls=3)
        budget = self.mod.BudgetController(limits, clock=self.clock)
        limits.max_model_calls = 99
        self.assertEqual(budget.budget.max_model_calls, 3)

    def test_snapshots_are_copies(self):
        budget = self.controller()
        snap = budget.snapshot()
        snap["model_calls"] = 42
        snap["limits"]["max_model_calls"] = 1
        self.assertEqual(budget.snapshot()["model_calls"], 0)
        self.assertEqual(budget.budget.max_model_calls, 16)


if __name__ == "__main__":
    import unittest
    unittest.main()
