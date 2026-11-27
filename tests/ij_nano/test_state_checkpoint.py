"""Layer A regression tests: typed state reset/epoch (D04) + checkpoints."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.core.budget import BudgetController, BudgetSpec  # noqa: E402
from nanoagent.core.checkpoint import (CancellationToken, Checkpoint,  # noqa: E402
                                       OperationCancelled)
from nanoagent.core.events import EventLog  # noqa: E402
from nanoagent.core.state import Fact, Session, StaleEpochError, UnverifiedSourceError  # noqa: E402


class TestState(unittest.TestCase):
    def test_complete_reset_no_cross_trial_residue(self):
        # D04: session contamination - a reset must leave nothing behind.
        s = Session()
        st = s.state
        st.set_goal("audit PO-1", epoch=st.epoch)
        st.apply_verified(Fact("PO-1", "total", 100.0, "number",
                               source_event_id="ev1"), epoch=st.epoch)
        st.record_action("act-1", epoch=st.epoch)
        st.record_error("boom", epoch=st.epoch)
        fresh = s.reset()
        self.assertIs(fresh, s.state)
        self.assertNotEqual(fresh.epoch, st.epoch)
        self.assertIsNone(fresh.goal)
        self.assertEqual(fresh.facts, {})
        self.assertEqual(fresh.completed_actions, [])
        self.assertEqual(fresh.recent_errors, [])
        self.assertEqual(fresh.version, 0)

    def test_epoch_abort_rejects_late_writes(self):
        s = Session()
        old = s.state
        old_epoch = old.epoch
        s.reset()
        with self.assertRaises(StaleEpochError):
            old.set_goal("late write", epoch=old_epoch)
        self.assertTrue(s.epoch_was_aborted(old_epoch))

    def test_generated_text_cannot_write_facts(self):
        # Only verified, event-backed facts enter state.
        st = Session().state
        with self.assertRaises(UnverifiedSourceError):
            st.apply_verified(Fact("E", "p", 1, "number"), epoch=st.epoch)

    def test_fact_versioning_and_scope_invalidation(self):
        s = Session()
        st = s.state
        st.apply_verified(Fact("E", "qty", 5, "integer", source_event_id="a"),
                          epoch=st.epoch)
        v1 = st.fact("E", "qty").state_version
        st.apply_verified(Fact("E", "qty", 3, "integer", source_event_id="b"),
                          epoch=st.epoch)
        self.assertEqual(st.fact("E", "qty").value, 3)
        self.assertGreater(st.fact("E", "qty").state_version, v1)
        st.apply_verified(Fact("E", "loc", "W-1", "string", source_event_id="c",
                               validity_scope="before-move"), epoch=st.epoch)
        dropped = st.invalidate_scope("before-move", epoch=st.epoch)
        self.assertEqual(dropped, 1)
        self.assertIsNone(st.fact("E", "loc"))
        self.assertIsNotNone(st.fact("E", "qty"))


class TestCheckpoint(unittest.TestCase):
    def _session_parts(self):
        s = Session()
        st = s.state
        st.set_goal("g", epoch=st.epoch)
        st.apply_verified(Fact("PO", "amt", 9.5, "number", source_event_id="e1"),
                          epoch=st.epoch)
        bc = BudgetController(BudgetSpec(model_calls=9))
        bc.reserve("model_calls", 2)
        log = EventLog("trial-1")
        log.append("task_started", "start", {})
        log.append("request_sent", "req", {"i": 1})
        return s, bc, log

    def test_checkpoint_round_trip_and_resume(self):
        s, bc, log = self._session_parts()
        cp = Checkpoint.capture(s, bc, log)
        raw = cp.to_json()
        cp2, log2 = Checkpoint.restore(raw)
        self.assertTrue(cp2.validate())
        self.assertEqual(log2.next_seq(), 2)
        e = log2.append("response_decoded", "text", {"text": "ok"})
        self.assertEqual(e.seq, 2)
        self.assertTrue(log2.verify())
        self.assertEqual(cp2.budget["counters"]["model_calls"], 2)

    def test_checkpoint_detects_count_tampering(self):
        s, bc, log = self._session_parts()
        cp = Checkpoint.capture(s, bc, log)
        cp.event_count = 99
        self.assertFalse(cp.validate())

    def test_cancellation_cooperative(self):
        tok = CancellationToken()
        self.assertFalse(tok.is_set)
        tok.set()
        with self.assertRaises(OperationCancelled):
            tok.raise_if_set()


if __name__ == "__main__":
    unittest.main()
