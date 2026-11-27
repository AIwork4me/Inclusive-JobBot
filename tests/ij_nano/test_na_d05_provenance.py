"""NA-D05 adversarial tests: provenance integrity for trusted facts.

Red against the audited source: apply_verified accepts any nonempty
source_event_id string; there is no trial binding, no source-event existence
check, no authorized-stage check, no data-type/unit validation, and values
are stored by reference (nested mutation).
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.core.events import EventLog  # noqa: E402
from nanoagent.core.state import Fact, Session, UnverifiedSourceError  # noqa: E402


def session_with_log(trial="trial-1"):
    log = EventLog(trial)
    s = Session(trial_id=trial, event_log=log)
    return s, log


def good_event(log, entity="PO-1", value=42):
    return log.append("tool_call_finished", "tool.done",
                      {"entity": entity, "value": value})


class TestProvenance(unittest.TestCase):
    def test_fake_source_id_rejected(self):
        # RED: audited code accepts any nonempty string.
        s, log = session_with_log()
        with self.assertRaises(UnverifiedSourceError):
            s.state.apply_verified(
                Fact("PO-1", "total", 9.9, "number", source_event_id="made-up-id"),
                epoch=s.state.epoch)

    def test_cross_trial_source_rejected(self):
        # RED: an event id from another trial's log must not verify here.
        s1, log1 = session_with_log("trial-1")
        other = EventLog("trial-2")
        ev = other.append("tool_call_finished", "tool.done", {"entity": "PO-1"})
        with self.assertRaises(UnverifiedSourceError):
            log1  # noqa: B018  (trial-1 log stays empty on purpose)
            s1.state.apply_verified(
                Fact("PO-1", "total", 1.0, "number", source_event_id=ev.event_id),
                epoch=s1.state.epoch)

    def test_unauthorized_source_stage_rejected(self):
        # RED: request/response events are not authorized fact sources.
        s, log = session_with_log()
        req = log.append("request_sent", "req", {"prompt": "x"})
        with self.assertRaises(UnverifiedSourceError):
            s.state.apply_verified(
                Fact("PO-1", "total", 1.0, "number", source_event_id=req.event_id),
                epoch=s.state.epoch)

    def test_authorized_source_stage_accepted(self):
        s, log = session_with_log()
        ev = good_event(log)
        s.state.apply_verified(
            Fact("PO-1", "total", 42, "integer", source_event_id=ev.event_id),
            epoch=s.state.epoch)
        self.assertIsNotNone(s.state.fact("PO-1", "total"))

    def test_data_type_mismatch_rejected(self):
        s, log = session_with_log()
        ev = good_event(log)
        with self.assertRaises(ValueError):
            s.state.apply_verified(
                Fact("PO-1", "total", "forty-two", "integer",
                     source_event_id=ev.event_id),
                epoch=s.state.epoch)

    def test_bool_is_not_integer_fact(self):
        s, log = session_with_log()
        ev = good_event(log)
        with self.assertRaises(ValueError):
            s.state.apply_verified(
                Fact("PO-1", "count", True, "integer", source_event_id=ev.event_id),
                epoch=s.state.epoch)

    def test_invalid_unit_rejected(self):
        s, log = session_with_log()
        ev = good_event(log)
        with self.assertRaises(ValueError):
            s.state.apply_verified(
                Fact("PO-1", "total", 42, "integer", unit="",
                     source_event_id=ev.event_id),
                epoch=s.state.epoch)

    def test_empty_entity_or_property_rejected(self):
        s, log = session_with_log()
        ev = good_event(log)
        with self.assertRaises(ValueError):
            s.state.apply_verified(
                Fact("", "total", 42, "integer", source_event_id=ev.event_id),
                epoch=s.state.epoch)
        with self.assertRaises(ValueError):
            s.state.apply_verified(
                Fact("PO-1", "", 42, "integer", source_event_id=ev.event_id),
                epoch=s.state.epoch)

    def test_nested_value_not_stored_by_reference(self):
        # RED: audited code stores the Fact value as given; a dict value stays
        # mutable through the caller's reference.
        s, log = session_with_log()
        ev = log.append("tool_call_finished", "tool.done",
                        {"entity": "C-9", "profile": {"tier": "gold"}})
        payload = {"tier": "gold"}
        s.state.apply_verified(
            Fact("C-9", "profile", payload, "object", source_event_id=ev.event_id),
            epoch=s.state.epoch)
        payload["tier"] = "platinum"
        self.assertEqual(s.state.fact("C-9", "profile").value["tier"], "gold")

    def test_no_log_bound_facts_rejected(self):
        # RED: audited Session has no log binding; without a verifier nothing
        # may enter as a "verified" fact.
        s = Session()
        with self.assertRaises(UnverifiedSourceError):
            s.state.apply_verified(
                Fact("PO-1", "total", 1, "integer", source_event_id="whatever"),
                epoch=s.state.epoch)


if __name__ == "__main__":
    unittest.main()
