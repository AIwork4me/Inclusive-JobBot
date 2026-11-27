"""NA-D03 adversarial tests: checkpoint integrity and real recovery.

Red against the audited source: checkpoints bind neither experiment identity,
budget specification, evidence seal, idempotency state nor an integrity hash;
restore() does not validate (callers may forget); deadlines are monotonic-only
so a restart silently grants a fresh budget; publication is not atomic.
"""
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.core.budget import BudgetController, BudgetSpec  # noqa: E402
from nanoagent.core.checkpoint import Checkpoint, CheckpointInvalid  # noqa: E402
from nanoagent.core.events import EventLog  # noqa: E402
from nanoagent.core.state import Fact, Session  # noqa: E402


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def parts(model_calls=9, wall=None):
    log = EventLog("trial-1")
    s = Session(trial_id="trial-1", event_log=log)
    st = s.state
    st.set_goal("g", epoch=st.epoch)
    src = log.append("tool_call_finished", "tool.done", {"entity": "PO", "amt": 9.5})
    st.apply_verified(Fact("PO", "amt", 9.5, "number", source_event_id=src.event_id),
                      epoch=st.epoch)
    bc = BudgetController(BudgetSpec(model_calls=model_calls, wall_clock_seconds=wall),
                          clock=FakeClock())
    bc.reserve("model_calls", 2)
    log.append("request_sent", "req", {"i": 1})
    return s, bc, log


class TestCheckpointBinding(unittest.TestCase):
    def test_restore_rejects_tampered_checkpoint(self):
        # RED: audited restore() performs no validation at all.
        s, bc, log = parts()
        cp = Checkpoint.capture(s, bc, log, experiment_id="exp-1")
        d = json.loads(cp.to_json())
        d["budget"]["counters"]["model_calls"] = 0        # hide usage
        with self.assertRaises(CheckpointInvalid):
            Checkpoint.restore(json.dumps(d))

    def test_restore_rejects_wrong_experiment_identity(self):
        s, bc, log = parts()
        cp = Checkpoint.capture(s, bc, log, experiment_id="exp-1")
        d = json.loads(cp.to_json())
        d["experiment_id"] = "exp-other"
        with self.assertRaises(CheckpointInvalid):
            Checkpoint.restore(json.dumps(d))

    def test_restore_rejects_state_epoch_mismatch(self):
        s, bc, log = parts()
        cp = Checkpoint.capture(s, bc, log, experiment_id="exp-1")
        d = json.loads(cp.to_json())
        d["state"]["epoch"] = 42
        with self.assertRaises(CheckpointInvalid):
            Checkpoint.restore(json.dumps(d))

    def test_restore_rejects_budget_spec_swap(self):
        # RED: spec is not bound at all in the audited capture.
        s, bc, log = parts()
        cp = Checkpoint.capture(s, bc, log, experiment_id="exp-1")
        d = json.loads(cp.to_json())
        d["budget_spec"]["model_calls"] = 999             # inflate the cap
        with self.assertRaises(CheckpointInvalid):
            Checkpoint.restore(json.dumps(d))

    def test_restore_rejects_event_truncation(self):
        s, bc, log = parts()
        cp = Checkpoint.capture(s, bc, log, experiment_id="exp-1")
        d = json.loads(cp.to_json())
        d["events"] = d["events"][:1]
        d["event_count"] = 1
        with self.assertRaises(CheckpointInvalid):
            Checkpoint.restore(json.dumps(d))

    def test_integrity_hash_covers_every_field(self):
        s, bc, log = parts()
        cp = Checkpoint.capture(s, bc, log, experiment_id="exp-1")
        d = json.loads(cp.to_json())
        d["idempotency"] = [["k", "tool", "deadbeef", {"fake": True}]]
        with self.assertRaises(CheckpointInvalid):
            Checkpoint.restore(json.dumps(d))


class TestDeadlineSurvival(unittest.TestCase):
    def test_deadline_survives_restart_without_new_budget(self):
        # RED: audited BudgetController has no wall-clock anchor; a restarted
        # controller starts a fresh window.
        clock = FakeClock(t=2000.0)
        wall = FakeClock(t=1000.0)     # wall clock for real-time anchoring
        spec = BudgetSpec(model_calls=9, wall_clock_seconds=10)
        bc = BudgetController(spec, clock=clock, wall_clock=wall)
        bc.reserve("model_calls", 2)
        clock.advance(6)              # 4 wall seconds left
        wall.advance(6)
        snap = bc.snapshot()
        # Restart: new controller, clocks start "later".
        clock2 = FakeClock(t=5000.0)
        wall2 = FakeClock(t=1006.5)   # 0.5s past the remaining window edge? no: 10-6=4 left
        wall2.t = 1000.0 + 12         # 12 wall seconds elapsed -> deadline passed
        bc2 = BudgetController.restore(spec, snap, clock=clock2, wall_clock=wall2)
        with self.assertRaises(Exception):
            bc2.reserve("model_calls", 1)

    def test_budget_counters_recovered_exactly(self):
        s, bc, log = parts(model_calls=9)
        cp = Checkpoint.capture(s, bc, log, experiment_id="exp-1")
        cp2, _ = Checkpoint.restore(cp.to_json())
        bc2 = BudgetController.restore(
            BudgetSpec(**cp2.budget_spec), cp2.budget,
            clock=FakeClock(t=777.0), wall_clock=FakeClock(t=777.0))
        self.assertEqual(bc2.remaining("model_calls"), 7)   # 9 - 2, not reset

    def test_executable_state_recovered(self):
        # Restoring a data record is not resuming: the restored session must
        # accept writes at the restored epoch and keep prior facts.
        s, bc, log = parts()
        cp = Checkpoint.capture(s, bc, log, experiment_id="exp-1")
        cp2, log2 = Checkpoint.restore(cp.to_json())
        s2 = Session.restore(cp2.state, cp2.trial_id, log2)
        st2 = s2.state
        self.assertEqual(st2.epoch, cp2.state["epoch"])
        self.assertIsNotNone(st2.fact("PO", "amt"))
        e = log2.append("response_decoded", "text", {"text": "resumed"})
        st2.record_action("act-2", epoch=st2.epoch)
        self.assertIn("act-2", st2.completed_actions)
        self.assertTrue(log2.verify())


class TestAtomicPublication(unittest.TestCase):
    def test_interrupted_publication_never_loads_half(self):
        # RED: no atomic save exists in the audited source; here we also prove
        # a truncated file is rejected rather than partially restored.
        s, bc, log = parts()
        cp = Checkpoint.capture(s, bc, log, experiment_id="exp-1")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "cp.json")
            cp.save(path)                       # atomic write
            self.assertTrue(os.path.exists(path))
            good = open(path, "rb").read()
            with open(path, "wb") as f:         # simulate interruption mid-write
                f.write(good[: len(good) // 2])
            with self.assertRaises(CheckpointInvalid):
                Checkpoint.load(path)
            # A temp-file remnant must not be loadable as the checkpoint.
            leftovers = [n for n in os.listdir(td) if n != "cp.json"]
            self.assertTrue(all(not n.endswith(".json") for n in leftovers))

    def test_save_replaces_previous_publication_atomically(self):
        s, bc, log = parts()
        cp1 = Checkpoint.capture(s, bc, log, experiment_id="exp-1")
        bc.reserve("model_calls", 1)
        cp2 = Checkpoint.capture(s, bc, log, experiment_id="exp-1")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "cp.json")
            cp1.save(path)
            cp2.save(path)                      # overwrite must be atomic too
            cp3, _ = Checkpoint.load(path)
            self.assertEqual(cp3.budget["counters"]["model_calls"], 3)


if __name__ == "__main__":
    unittest.main()
