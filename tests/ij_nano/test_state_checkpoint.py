"""Layer A regression tests: typed state reset/epoch (D04) + checkpoints.

Updated at N06A-R for the NA-D05 provenance contract: apply_verified now
requires a bound EventLog and a real authorized source event (facts with
bare id strings were the audited defect). Checkpoints gained integrity
binding (NA-D03); round-trip tests use the new validating restore.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.core.budget import BudgetController, BudgetSpec  # noqa: E402
from nanoagent.core.checkpoint import (CancellationToken, Checkpoint,  # noqa: E402
                                       CheckpointInvalid, OperationCancelled)
from nanoagent.core.events import EventLog  # noqa: E402
from nanoagent.core.state import Fact, Session, StaleEpochError, UnverifiedSourceError  # noqa: E402


def fact_session(trial="trial-1"):
    """Session with a bound event log; returns (session, log)."""
    log = EventLog(trial)
    s = Session(trial_id=trial, event_log=log)
    return s, log


def tool_event(log, **payload):
    return log.append("tool_call_finished", "tool.done", payload)


class TestState(unittest.TestCase):
    def test_complete_reset_no_cross_trial_residue(self):
        # D04: session contamination - a reset must leave nothing behind.
        s, log = fact_session()
        st = s.state
        st.set_goal("audit PO-1", epoch=st.epoch)
        ev = tool_event(log, entity="PO-1")
        st.apply_verified(Fact("PO-1", "total", 100.0, "number",
                               source_event_id=ev.event_id), epoch=st.epoch)
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
        s, _ = fact_session()
        old = s.state
        old_epoch = old.epoch
        s.reset()
        with self.assertRaises(StaleEpochError):
            old.set_goal("late write", epoch=old_epoch)
        self.assertTrue(s.epoch_was_aborted(old_epoch))

    def test_generated_text_cannot_write_facts(self):
        # Only verified, event-backed facts enter state.
        s, log = fact_session()
        with self.assertRaises(UnverifiedSourceError):
            s.state.apply_verified(Fact("E", "p", 1, "number"), epoch=s.state.epoch)
        model_text = log.append("response_decoded", "text", {"text": "total is 5"})
        with self.assertRaises(UnverifiedSourceError):
            s.state.apply_verified(
                Fact("E", "p", 1, "number", source_event_id=model_text.event_id),
                epoch=s.state.epoch)

    def test_fact_versioning_and_scope_invalidation(self):
        s, log = fact_session()
        st = s.state
        ea = tool_event(log, i=1)
        st.apply_verified(Fact("E", "qty", 5, "integer", source_event_id=ea.event_id),
                          epoch=st.epoch)
        v1 = st.fact("E", "qty").state_version
        eb = tool_event(log, i=2)
        st.apply_verified(Fact("E", "qty", 3, "integer", source_event_id=eb.event_id),
                          epoch=st.epoch)
        self.assertEqual(st.fact("E", "qty").value, 3)
        self.assertGreater(st.fact("E", "qty").state_version, v1)
        ec = tool_event(log, i=3)
        st.apply_verified(Fact("E", "loc", "W-1", "string", source_event_id=ec.event_id,
                               validity_scope="before-move"), epoch=st.epoch)
        dropped = st.invalidate_scope("before-move", epoch=st.epoch)
        self.assertEqual(dropped, 1)
        self.assertIsNone(st.fact("E", "loc"))
        self.assertIsNotNone(st.fact("E", "qty"))


class TestCheckpoint(unittest.TestCase):
    def _session_parts(self):
        s, log = fact_session()
        st = s.state
        st.set_goal("g", epoch=st.epoch)
        ev = tool_event(log, entity="PO", amt=9.5)
        st.apply_verified(Fact("PO", "amt", 9.5, "number", source_event_id=ev.event_id),
                          epoch=st.epoch)
        bc = BudgetController(BudgetSpec(model_calls=9))
        bc.reserve("model_calls", 2)
        log.append("request_sent", "req", {"i": 1})
        return s, bc, log

    def test_checkpoint_round_trip_and_resume(self):
        s, bc, log = self._session_parts()
        cp = Checkpoint.capture(s, bc, log, experiment_id="exp-test")
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
        cp = Checkpoint.capture(s, bc, log, experiment_id="exp-test")
        cp.event_count = 99
        self.assertFalse(cp.validate())

    def test_checkpoint_restore_rejects_tampering(self):
        import json
        s, bc, log = self._session_parts()
        cp = Checkpoint.capture(s, bc, log, experiment_id="exp-test")
        d = json.loads(cp.to_json())
        d["budget"]["counters"]["model_calls"] = 0
        with self.assertRaises(CheckpointInvalid):
            Checkpoint.restore(json.dumps(d))

    def test_cancellation_cooperative(self):
        tok = CancellationToken()
        self.assertFalse(tok.is_set)
        tok.set()
        with self.assertRaises(OperationCancelled):
            tok.raise_if_set()


if __name__ == "__main__":
    unittest.main()
