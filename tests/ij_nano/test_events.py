"""Layer A regression tests: event log (D07 event-log half)."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.core.events import Event, EventLog  # noqa: E402


class TestEventLog(unittest.TestCase):
    def test_decoded_response_and_token_ids_are_distinct_stages(self):
        # D07: decoded response and token ids must be different stages.
        log = EventLog("t1")
        e1 = log.append("token_ids", "sample", {"ids": [1, 2, 3]})
        e2 = log.append("response_decoded", "text", {"text": "hello"}, parent=e1)
        self.assertNotEqual(e1.stage, e2.stage)
        self.assertEqual(log.by_call(e1.event_id)[0].event_id, e2.event_id)

    def test_sequence_and_chain_verify(self):
        log = EventLog("t1")
        for i in range(5):
            log.append("request_sent", "req", {"i": i})
        self.assertTrue(log.verify())
        self.assertEqual([e.seq for e in log.events()], list(range(5)))

    def test_tampering_detected(self):
        log = EventLog("t1")
        log.append("request_sent", "req", {"prompt": "abc"})
        ev = log.append("response_decoded", "text", {"text": "ok"})
        # Forge a modified copy of the log.
        rows = [e.to_json() for e in log.events()]
        rows[0]["payload"] = {"prompt": "tampered"}
        forged = EventLog("t1")
        forged._events = [Event(**r) for r in rows]
        self.assertFalse(forged.verify())

    def test_reordering_detected(self):
        log = EventLog("t1")
        log.append("request_sent", "req", {"i": 1})
        log.append("response_decoded", "text", {"i": 2})
        rows = [e.to_json() for e in log.events()][::-1]
        forged = EventLog("t1")
        forged._events = [Event(**r) for r in rows]
        self.assertFalse(forged.verify())

    def test_seal_blocks_appends(self):
        log = EventLog("t1")
        log.append("task_started", "start", {})
        seal = log.seal()
        self.assertEqual(seal["count"], 1)
        with self.assertRaises(RuntimeError):
            log.append("task_finished", "end", {})

    def test_resume_safe_sequence_after_restore(self):
        log = EventLog("t1")
        for i in range(3):
            log.append("request_sent", "req", {"i": i})
        rows = [e.to_json() for e in log.events()]
        restored = EventLog.from_events("t1", rows)
        self.assertEqual(restored.next_seq(), 3)
        e = restored.append("response_decoded", "text", {"text": "x"})
        self.assertEqual(e.seq, 3)
        self.assertTrue(restored.verify())

    def test_restore_rejects_broken_chain(self):
        log = EventLog("t1")
        log.append("request_sent", "req", {"i": 1})
        rows = [e.to_json() for e in log.events()]
        rows[0]["hash"] = "0" * 64
        with self.assertRaises(ValueError):
            EventLog.from_events("t1", rows)

    def test_unknown_stage_rejected(self):
        log = EventLog("t1")
        with self.assertRaises(ValueError):
            log.append("not_a_stage", "x", {})


if __name__ == "__main__":
    unittest.main()
