"""IJ-NANO-1.2R regression tests: offline replay integrity qualification.

Guards the RS01 defect class (positional unpacking of persisted stage
dicts) end-to-end: raw artifact -> validated loader -> stage reconstruction
-> parser -> evaluator -> trial record -> analyzer. The audited
dictionary-unpacking mutant must be rejected by the same controls that the
corrected loader passes (red-to-green, mission section 4).
"""
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ij_nano"))
sys.path.insert(0, str(ROOT / "benchmarks" / "root_cause"))
sys.path.insert(0, str(ROOT / "benchmarks" / "ij_nano"))
sys.path.insert(0, str(ROOT / "src"))

import n02rr_replay_lib as rl                    # noqa: E402
import n02rr_qualification_lib as qlib           # noqa: E402

RUNS = ROOT / "evidence" / "IJNANO" / "N02R" / "runs"


@unittest.skipUnless((RUNS / "ec5b95357e960f99" / "results.jsonl").exists(),
                     "sealed N02R evidence not present")
class TestReplayQualification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = qlib.make_controller()
        cls.tmp = tempfile.TemporaryDirectory(
            prefix="n02rr_test_", dir=str(ROOT / ".runtime"))
        cls.battery = qlib.ControlBattery(cls.c, pathlib.Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_green_all_controls_pass(self):
        results = self.battery.run_green()
        failed = [r for r in results if not r["passed"]]
        self.assertEqual(failed, [],
                         f"green controls failed: {failed}")

    def test_positive_controls_reach_parser_as_dicts(self):
        results = self.battery.run_green()
        n = sum(1 for r in results
                if r["checks"].get("parser_input_is_dict") is True)
        self.assertGreaterEqual(n, 5)

    def test_mutant_rejected(self):
        red = self.battery.run_red()
        self.assertTrue(red["mutant_rejected"],
                        f"audited mutant not rejected: {red['controls']}")
        self.assertGreaterEqual(red["n_positive_controls"], 5)

    def test_mutant_unpack_returns_key_strings(self):
        art = {"stages": [{"stage": 1, "path": "/x", "http": {"a": 1},
                           "http_error": None, "latency_s": 0.1}]}
        m = rl.mutant_unpack_last_stage(art)
        self.assertEqual(m["raw_http_json"], "http")
        self.assertIsNone(m["http_json"])
        self.assertEqual(m["http_error"], "http_error")
        self.assertEqual(m["latency"], "latency_s")

    def test_loader_rejects_non_dict_stage(self):
        art = {"trial_id": "t", "stages": [
            {"stage": 1, "path": "/x", "http": {}, "http_error": None,
             "latency_s": 0.1, "extra": 1}]}
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "t.json"
            p.write_text(json.dumps(art), encoding="utf-8")
            with self.assertRaises(rl.ArtifactIntegrityError) as cm:
                rl.load_artifact(p)
            self.assertEqual(cm.exception.code,
                             rl.ArtifactIntegrityError.REJECT_STAGE_SCHEMA)

    def test_published_witness_replays_to_source_verdict(self):
        engine = rl.ReplayEngine(self.c)
        dst_rows = [json.loads(l) for l in
                    (RUNS / "ec5b95357e960f99" / "results.jsonl")
                    .read_text(encoding="utf-8").splitlines()]
        wrow = next(r for r in dst_rows if r["response_artifact"].endswith(
            "003abb9e2604141bd8b016ec.json"))
        src = {r["trial_id"]: r for r in (
            json.loads(l) for l in
            (RUNS / "7a1b9d7d160202d8" / "results.jsonl")
            .read_text(encoding="utf-8").splitlines())}
        srow = src[wrow["execution"]["source_trial_id"]]
        rec = engine.replay(wrow, source_row=srow)
        self.assertTrue(rec["parser"]["structural_ok"])
        self.assertEqual(rec["parser"]["payload"], srow["parser"]["payload"])
        self.assertEqual(rec["telemetry"]["latency_s"],
                         srow["telemetry"]["latency_s"])
        self.assertIsInstance(rec["telemetry"]["usage"], dict)

    def test_wrong_stage_selection_not_hidden(self):
        results = {r["control"]: r for r in self.battery.run_green()}
        self.assertTrue(results["incorrect_first_stage_selection"]["passed"])
        self.assertEqual(
            results["wrong_selection_hidden_by_final_response"]
            ["failure_class"],
            "EVIDENCE_INCONSISTENT_STAGE2_TOOL")


if __name__ == "__main__":
    unittest.main()
