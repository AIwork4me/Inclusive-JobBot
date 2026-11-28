"""NA-D02 adversarial tests: evidence integrity envelope.

Red against the audited source (envelope gaps): parent_id and ts_utc are
outside the hash, restored rows are not checked for trial identity, dangling
parents, duplicate ids or invalid stages, appended payloads share nested
references with the caller, and no seal digest exists to anchor a manifest.
Cases marked GUARD pass for defense-in-depth both before and after repair.
"""
import hashlib
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.core.events import Event, EventLog, _canonical  # noqa: E402


def chain(n=3, trial="t1"):
    log = EventLog(trial)
    for i in range(n):
        log.append("request_sent", "req", {"i": i})
    return log


def rebuild(rows, trial):
    """Re-chain rows with the canonical envelope so only the property under
    test differs from a valid log (usable once the envelope is canonical)."""
    prev = "0" * 64
    for i, r in enumerate(rows):
        r["seq"] = i
        r["prev_hash"] = prev
        r["trial_id"] = trial
        r["hash"] = hashlib.sha256(
            (r["prev_hash"] + "|" + trial + "|" + str(i) + "|" + r["stage"] + "|"
             + r["kind"] + "|" + r["event_id"] + "|" + str(r.get("parent_id"))
             + "|" + r["ts_utc"] + "|" + _canonical(r.get("payload", {})))
            .encode("utf-8")).hexdigest()
        prev = r["hash"]
    return rows


class TestIntegrityEnvelope(unittest.TestCase):
    def test_parent_reassignment_detected(self):
        # RED: parent_id is not covered by the audited hash.
        log = EventLog("t1")
        a = log.append("request_sent", "req", {})
        b = log.append("tool_call_started", "call", {}, parent=a)
        c = log.append("tool_call_finished", "done", {}, parent=b)
        self.assertTrue(log.verify())
        rows = [e.to_json() for e in log.events()]
        rows[2]["parent_id"] = a.event_id
        forged = EventLog("t1")
        forged._events = [Event(**r) for r in rows]
        self.assertFalse(forged.verify())

    def test_timestamp_tampering_detected(self):
        # RED: ts_utc is not covered by the audited hash.
        log = chain(2)
        rows = [e.to_json() for e in log.events()]
        rows[0]["ts_utc"] = "2000-01-01T00:00:00.000000Z"
        forged = EventLog("t1")
        forged._events = [Event(**r) for r in rows]
        self.assertFalse(forged.verify())

    def test_dangling_parent_rejected_on_restore(self):
        # RED: audited verify() ignores parent existence entirely; parent_id is
        # also outside the hash, so this surgery keeps the chain valid.
        log = EventLog("t1")
        a = log.append("request_sent", "req", {})
        log.append("tool_call_started", "call", {}, parent=a)
        rows = [e.to_json() for e in log.events()]
        rows[1]["parent_id"] = "nonexistent-parent"
        with self.assertRaises(ValueError):
            EventLog.from_events("t1", rows)

    def test_cross_trial_rows_rejected(self):
        # RED: audited verify() never compares row trial_id to the log's.
        other = chain(2, trial="t-other")
        mixed = EventLog("t1", initial=list(other.events()))
        self.assertFalse(mixed.verify())
        rows = [e.to_json() for e in other.events()]
        with self.assertRaises(ValueError):
            EventLog.from_events("t1", rows)

    def test_invalid_stage_rejected_on_restore(self):
        # RED (guard component): audited restore path never re-checks stages;
        # the hash makes this fail only indirectly once stages are covered.
        log = chain(2)
        rows = [e.to_json() for e in log.events()]
        rows[1]["stage"] = "totally_bogus_stage"
        with self.assertRaises(ValueError):
            EventLog.from_events("t1", rows)

    def test_duplicate_event_id_rejected_on_restore(self):
        # GUARD: a chain rebuilt over a duplicated event id must be rejected
        # by identity checks even when every hash is canonical.
        log = chain(3)
        rows = [e.to_json() for e in log.events()]
        dup = dict(rows[1])
        dup["parent_id"] = rows[0]["event_id"]
        rows.append(dup)
        rebuild(rows, "t1")
        with self.assertRaises(ValueError):
            EventLog.from_events("t1", rows)

    def test_truncation_detected_against_seal(self):
        # RED: no seal-vs-content comparison exists in the audited source.
        log = chain(5)
        seal = log.seal()
        truncated = [e.to_json() for e in log.events()][:3]
        restored = EventLog.from_events("t1", truncated)
        self.assertTrue(restored.verify())   # a chain prefix alone is blind
        self.assertFalse(restored.verify_against_seal(seal))

    def test_payload_mutation_through_nested_reference(self):
        # RED: audited append() shallow-copies the payload, so the recorded
        # evidence is mutable through the caller's reference.
        payload = {"outer": {"inner": 1}}
        log = EventLog("t1")
        log.append("request_sent", "req", payload)
        payload["outer"]["inner"] = 999
        ev = log.events()[0]
        self.assertEqual(ev.payload["outer"]["inner"], 1)
        self.assertTrue(log.verify())

    def test_seal_digest_anchors_external_manifest(self):
        # RED: audited seal() has no digest binding an external manifest.
        log = chain(3)
        seal = log.seal()
        self.assertEqual(len(seal.get("digest", "")), 64)
        self.assertTrue(log.verify_against_seal(seal))


if __name__ == "__main__":
    unittest.main()
