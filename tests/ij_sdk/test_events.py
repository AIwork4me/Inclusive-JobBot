"""D07 - the event log: closed vocabulary, honest capture labels, unique ids with causal
parents, resume-safe sequencing, a hash chain and a seal that detects tampering."""

from __future__ import annotations

import json
import unittest

from tests.ij_sdk.support import RepoTestCase, read_rows

EVENTS = "benchmarks.ij_sdk.contracts.events"


class EventLogCase(RepoTestCase):
    def setUp(self):
        super().setUp()
        self.mod = self.import_new(EVENTS)


class Labels(EventLogCase):
    def test_the_vocabulary_separates_decoded_responses_from_token_generation(self):
        stages = set(self.mod.STAGES)
        self.assertIn("server_response_decoded", stages, "there is no stage for a parsed response")
        self.assertIn("model_generation", stages)

    def test_a_parsed_response_cannot_be_labelled_model_generation(self):
        log = self.mod.EventLog(str(self.path("label.jsonl")))
        self.addCleanup(log.close)
        parsed = {"body": {"choices": [{"message": {"role": "assistant", "content": "x"}}], "object": "chat.completion"}}
        with self.assertRaises(ValueError):
            log.emit("r", "t", "model_generation", parsed)
        with self.assertRaises(ValueError):
            log.emit("r", "t", "model_generation", {"body": {"choices": []}})
        self.assertEqual(log.emit("r", "t", "model_generation", {"token_ids": [1, 2, 3]}), 1)
        self.assertEqual(log.emit("r", "t", "model_generation", {"status": "not_captured", "reason": "no ids"}), 2)

    def test_unknown_stages_are_refused(self):
        log = self.mod.EventLog(str(self.path("vocab.jsonl")))
        self.addCleanup(log.close)
        with self.assertRaises(ValueError):
            log.emit("r", "t", "model_thought", {})

    def test_a_stage_that_could_not_be_observed_is_declared(self):
        log = self.mod.EventLog(str(self.path("nc.jsonl")))
        self.addCleanup(log.close)
        log.not_captured("r", "t", "chat_template", "rendered inside the server")
        row = read_rows(self.path("nc.jsonl"))[0]
        self.assertEqual(row["payload"], {"status": "not_captured", "reason": "rendered inside the server"})
        self.assertEqual(row["stage"], "chat_template")


class Identity(EventLogCase):
    def test_rows_carry_unique_ids_and_resolve_their_parents(self):
        log = self.mod.EventLog(str(self.path("ids.jsonl")))
        self.addCleanup(log.close)
        log.emit("r", "t", "task_input", {"prompt": "p"})
        task = log.last_event_id
        log.emit("r", "t", "server_request", {"attempt": 1}, parent_id=task)
        request = log.last_event_id
        log.emit("r", "t", "server_response_decoded", {"status": "ok"}, parent_id=request, call_id="c1")
        response = log.last_event_id
        log.emit("r", "t", "tool_gateway", {"decision": "allow"}, parent_id=response, call_id="c1")
        rows = read_rows(self.path("ids.jsonl"))
        ids = [row["event_id"] for row in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(isinstance(i, str) and i for i in ids), ids)
        self.assertEqual([row["parent_id"] for row in rows], [None, ids[0], ids[1], ids[2]])
        self.assertEqual(rows[-1]["call_id"], "c1")
        self.assertEqual(log.last_event_id, ids[-1])

    def test_resuming_a_log_does_not_restart_sequence_numbers(self):
        path = str(self.path("resume.jsonl"))
        first = self.mod.EventLog(path)
        first.emit("r", "t", "task_input", {"prompt": "a"})
        first.emit("r", "t", "task_input", {"prompt": "b"})
        first.close()
        second = self.mod.EventLog(path)
        second.emit("r", "t", "task_input", {"prompt": "c"})
        second.close()
        rows = read_rows(path)
        self.assertEqual([row["seq"] for row in rows], [1, 2, 3])
        self.assertEqual(len({row["event_id"] for row in rows}), 3)


class Integrity(EventLogCase):
    def sealed_log(self):
        path = str(self.path("seal.jsonl"))
        log = self.mod.EventLog(path)
        task = log.emit("r", "t", "task_input", {"prompt": "p"})
        log.emit("r", "t", "final_answer", {"final_answer": "17420.50"}, parent_id=task)
        seal = log.seal()
        log.close()
        return path, seal

    def ok(self, path, seal):
        verdict = self.mod.verify(path, seal)
        return verdict is True or (isinstance(verdict, dict) and verdict.get("ok") is True)

    def test_an_untouched_sealed_log_verifies(self):
        path, seal = self.sealed_log()
        self.assertTrue(self.ok(path, seal))
        self.assertTrue(self.ok(path, self.mod.load_seal(path)))

    def test_an_edited_row_is_detected(self):
        path, seal = self.sealed_log()
        text = self.path("seal.jsonl").read_text(encoding="utf-8").replace("17420.50", "99999.99")
        self.path("seal.jsonl").write_text(text, encoding="utf-8")
        self.assertFalse(self.ok(path, seal))
        self.assertFalse(self.ok(path, None), "the chain alone did not detect an edited row")

    def test_a_truncated_log_is_detected(self):
        path, seal = self.sealed_log()
        lines = self.path("seal.jsonl").read_text(encoding="utf-8").splitlines()
        self.path("seal.jsonl").write_text(lines[0] + "\n", encoding="utf-8")
        self.assertFalse(self.ok(path, seal))
        self.assertFalse(self.ok(path, seal["last_hash"]), "appending after the seal was not detected against the head")

    def test_an_appended_row_after_sealing_is_detected(self):
        path, seal = self.sealed_log()
        log = self.mod.EventLog(path)
        log.emit("r", "t", "task_input", {"prompt": "late"})
        log.close()
        self.assertFalse(self.ok(path, seal))
        self.assertFalse(self.ok(path, seal["last_hash"]))

    def rewrite(self, path, rows):
        with open(path, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    def test_an_edited_inner_row_is_detected_even_when_its_own_hash_is_recomputed(self):
        path = str(self.path("inner.jsonl"))
        log = self.mod.EventLog(path)
        log.emit("r", "t", "task_input", {"prompt": "p"})
        log.emit("r", "t", "server_request", {"attempt": 1})
        log.emit("r", "t", "final_answer", {"final_answer": "17420.50"})
        log.close()
        rows = read_rows(path)
        rows[1]["payload"]["attempt"] = 2
        rows[1]["hash"] = self.mod.row_hash(rows[1])       # the attacker repairs the edited row itself
        self.rewrite(path, rows)
        self.assertFalse(self.ok(path, None), "the next row's prev_hash no longer matched and nothing noticed")

    def test_an_edited_last_row_is_detected_by_the_seal(self):
        """The chain alone cannot see an edit to its own last row. That is why the seal,
        or at least the expected chain head, must travel with the evidence."""
        path, seal = self.sealed_log()
        rows = read_rows(path)
        rows[-1]["payload"]["final_answer"] = "1.00"
        rows[-1]["hash"] = self.mod.row_hash(rows[-1])
        self.rewrite(path, rows)
        self.assertTrue(self.ok(path, None), "precondition: the chain alone does not cover its last row")
        self.assertFalse(self.ok(path, seal), "the seal did not detect an edited last row")
        self.assertFalse(self.ok(path, seal["last_hash"]), "the expected chain head did not detect an edited last row")

    def test_duplicate_sequence_numbers_are_detected(self):
        path, _seal = self.sealed_log()
        rows = read_rows(path)
        rows.append(dict(rows[-1]))
        with open(path, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
        verdict = self.mod.verify(path)
        self.assertFalse(verdict is True or verdict.get("ok"))


if __name__ == "__main__":
    unittest.main()
