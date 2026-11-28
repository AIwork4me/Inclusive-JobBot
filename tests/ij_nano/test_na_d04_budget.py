"""NA-D04 adversarial tests: authoritative budget reservation and settlement.

Red against the audited source: zero-unit reservations bypass counting,
negative specs are accepted, there is no settlement (reserved vs actual vs
released vs unknown), no max_tokens binding, and reservations are not atomic
under threads.
"""
import pathlib
import sys
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.core.budget import (BudgetController, BudgetExhausted,  # noqa: E402
                                   BudgetSpec)


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


class TestNoBypass(unittest.TestCase):
    def test_zero_unit_reservation_rejected(self):
        # RED: audited reserve() accepts units=0 and counts nothing while the
        # caller can still claim a reservation object.
        bc = BudgetController(BudgetSpec(model_calls=2), clock=FakeClock())
        with self.assertRaises(ValueError):
            bc.reserve("model_calls", 0)

    def test_negative_spec_rejected(self):
        # RED: audited BudgetSpec accepts negative caps.
        for bad in (-1, -100):
            with self.assertRaises(ValueError):
                BudgetSpec(model_calls=bad)
            with self.assertRaises(ValueError):
                BudgetSpec(completion_tokens=bad)
            with self.assertRaises(ValueError):
                BudgetSpec(corrective_retries=bad)
        with self.assertRaises(ValueError):
            BudgetSpec(wall_clock_seconds=-5)
        with self.assertRaises(ValueError):
            BudgetSpec(tool_timeout_seconds=-5)
        with self.assertRaises(ValueError):
            BudgetSpec(prompt_tokens=-5)

    def test_negative_units_rejected(self):
        bc = BudgetController(BudgetSpec(model_calls=2), clock=FakeClock())
        with self.assertRaises(ValueError):
            bc.reserve("model_calls", -1)

    def test_no_retry_when_retry_budget_exhausted(self):
        bc = BudgetController(BudgetSpec(model_calls=10, corrective_retries=1),
                              clock=FakeClock())
        bc.reserve("model_calls", 1, corrective=True)
        with self.assertRaises(BudgetExhausted) as cm:
            bc.reserve("model_calls", 1, corrective=True)
        self.assertEqual(cm.exception.kind, "corrective_retries")


class TestSettlement(unittest.TestCase):
    def test_settle_releases_unused_reservation(self):
        # RED: audited Reservation has no settle(); only overrun charge exists,
        # so a 100-token reservation for 12 actual tokens silently burns 88.
        bc = BudgetController(BudgetSpec(completion_tokens=100), clock=FakeClock())
        r = bc.reserve("completion_tokens", 100)
        r.settle(12)
        self.assertEqual(bc.remaining("completion_tokens"), 88)

    def test_settle_overrun_charged(self):
        bc = BudgetController(BudgetSpec(completion_tokens=100), clock=FakeClock())
        r = bc.reserve("completion_tokens", 50)
        r.settle(80)
        self.assertEqual(bc.remaining("completion_tokens"), 20)

    def test_unknown_usage_conservatively_charged(self):
        # Transport failure with unknown actual usage: keep the full hold.
        bc = BudgetController(BudgetSpec(completion_tokens=100), clock=FakeClock())
        r = bc.reserve("completion_tokens", 40)
        r.settle_unknown()
        self.assertEqual(bc.remaining("completion_tokens"), 60)

    def test_attempt_count_never_refunded(self):
        # A model call attempt is an attempt even if it "used" 0 tokens.
        bc = BudgetController(BudgetSpec(model_calls=3), clock=FakeClock())
        r = bc.reserve("model_calls", 1)
        r.settle(0)
        self.assertEqual(bc.remaining("model_calls"), 2)

    def test_reservation_states_distinguished(self):
        bc = BudgetController(BudgetSpec(completion_tokens=100), clock=FakeClock())
        r = bc.reserve("completion_tokens", 30)
        self.assertEqual(r.state, "reserved")
        r.settle(20)
        self.assertEqual(r.state, "settled")
        r2 = bc.reserve("completion_tokens", 10)
        r2.settle_unknown()
        self.assertEqual(r2.state, "settled_unknown")


class TestRequestBinding(unittest.TestCase):
    def test_max_tokens_bound_to_remaining_budget(self):
        # RED: audited controller exposes no max-tokens binding; a request may
        # ask for more than the remaining budget.
        bc = BudgetController(BudgetSpec(completion_tokens=100), clock=FakeClock())
        r = bc.reserve("completion_tokens", 80)
        r.settle(75)     # 5 reserved units released back
        self.assertEqual(bc.remaining("completion_tokens"), 25)
        self.assertEqual(bc.max_completion_tokens(500), 25)
        self.assertEqual(bc.max_completion_tokens(10), 10)

    def test_overrun_cannot_double_charge_below_zero(self):
        bc = BudgetController(BudgetSpec(completion_tokens=10), clock=FakeClock())
        r = bc.reserve("completion_tokens", 10)
        r.settle(14)      # overrun beyond cap is charged, remaining floors at 0
        self.assertEqual(bc.remaining("completion_tokens"), 0)
        with self.assertRaises(BudgetExhausted):
            bc.reserve("completion_tokens", 1)


class TestAtomicReservation(unittest.TestCase):
    def test_no_concurrent_reservation_race(self):
        # RED: audited reserve() is not synchronized; concurrent reservations
        # can both pass the remaining-check and overshoot the cap.
        spec = BudgetSpec(model_calls=200)
        results = []

        def worker(bc):
            for _ in range(100):
                try:
                    bc.reserve("model_calls", 1)
                    results.append(1)
                except BudgetExhausted:
                    results.append(0)

        bc = BudgetController(spec, clock=FakeClock())
        threads = [threading.Thread(target=worker, args=(bc,)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sum(results), 200)
        self.assertEqual(bc.snapshot()["counters"]["model_calls"], 200)


if __name__ == "__main__":
    unittest.main()
