"""Layer A regression tests: budget controller (D05 defect class)."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.core.budget import (BudgetController, BudgetExhausted,  # noqa: E402
                                   BudgetSpec, DeadlineExceeded)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s: float):
        self.t += s


class TestBudget(unittest.TestCase):
    def test_attempts_counted_at_reservation_time(self):
        # D05: counting at start, not completion.
        bc = BudgetController(BudgetSpec(model_calls=2), clock=FakeClock())
        r = bc.reserve("model_calls", 1)
        self.assertEqual(bc.remaining("model_calls"), 1)  # already consumed
        r.charge(1)
        self.assertEqual(bc.remaining("model_calls"), 1)

    def test_failed_call_is_charged(self):
        bc = BudgetController(BudgetSpec(model_calls=3), clock=FakeClock())
        try:
            with bc.reserve("model_calls", 1) as r:
                r.charge(0)
                raise RuntimeError("model call failed")
        except RuntimeError:
            pass
        self.assertEqual(bc.remaining("model_calls"), 2)  # failed call still charged

    def test_overuse_charged_beyond_reservation(self):
        bc = BudgetController(BudgetSpec(completion_tokens=100), clock=FakeClock())
        r = bc.reserve("completion_tokens", 50)
        r.charge(80)
        self.assertEqual(bc.remaining("completion_tokens"), 20)

    def test_reserve_beyond_remaining_refused(self):
        bc = BudgetController(BudgetSpec(model_calls=1), clock=FakeClock())
        with self.assertRaises(BudgetExhausted):
            bc.reserve("model_calls", 2)

    def test_absolute_monotonic_deadline(self):
        clock = FakeClock()
        bc = BudgetController(BudgetSpec(wall_clock_seconds=10), clock=clock)
        clock.advance(9)
        bc.check_deadline()  # fine
        clock.advance(2)
        with self.assertRaises(DeadlineExceeded):
            bc.reserve("model_calls", 1)

    def test_deadline_is_absolute_not_sliding(self):
        # Repeatedly reading the deadline must not push it into the future.
        clock = FakeClock()
        bc = BudgetController(BudgetSpec(wall_clock_seconds=5), clock=clock)
        for _ in range(8):          # 4 seconds of activity, still inside
            bc.check_deadline()
            bc.remaining_for_request()
            clock.advance(0.5)
        with self.assertRaises(DeadlineExceeded):
            clock.advance(2)        # now past the absolute deadline
            bc.check_deadline()

    def test_corrective_retries_bounded_separately(self):
        bc = BudgetController(BudgetSpec(model_calls=10, corrective_retries=2), clock=FakeClock())
        bc.reserve("model_calls", 1, corrective=True)
        bc.reserve("model_calls", 1, corrective=True)
        with self.assertRaises(BudgetExhausted) as cm:
            bc.reserve("model_calls", 1, corrective=True)
        self.assertEqual(cm.exception.kind, "corrective_retries")
        # First attempts still allowed.
        bc.reserve("model_calls", 1)

    def test_per_request_view_shows_real_remaining(self):
        bc = BudgetController(BudgetSpec(model_calls=5, completion_tokens=100), clock=FakeClock())
        with bc.reserve("model_calls", 2):
            pass
        view = bc.remaining_for_request()
        self.assertEqual(view["model_calls"], 3)
        self.assertEqual(view["completion_tokens"], 100)

    def test_snapshot_is_a_copy(self):
        # D04-adjacent: usage handed out must not be a live view.
        bc = BudgetController(BudgetSpec(model_calls=5), clock=FakeClock())
        snap = bc.snapshot()
        bc.reserve("model_calls", 5)
        self.assertEqual(snap["counters"]["model_calls"], 0)

    def test_tool_deadline_capped_by_task_deadline(self):
        # A tool timeout may never outlive the task's absolute deadline.
        clock = FakeClock()
        bc = BudgetController(BudgetSpec(wall_clock_seconds=10, tool_timeout_seconds=30),
                              clock=clock)
        self.assertLessEqual(bc.tool_deadline(), bc._deadline)
        clock.advance(9.5)
        self.assertLessEqual(bc.tool_deadline(), bc._deadline)


if __name__ == "__main__":
    unittest.main()
