import unittest

from benchmarks.slm10.lfm3_ha_admission import equivalent, intervention, numeric_row


class LoRANumericEvidenceTests(unittest.TestCase):
    def test_equal_and_reproducible_difference(self):
        base = [(0, -0.2), (1, -2.0)]
        self.assertTrue(equivalent(base, [(0, -0.200001), (1, -2.0)]))
        self.assertFalse(equivalent(base, [(1, -2.0), (0, -0.2)]))
        self.assertFalse(intervention(base, [(0, -0.20001), (1, -2.0)]))
        self.assertTrue(intervention(base, [(1, -0.3), (0, -2.0)]))
        self.assertFalse(intervention(base, [(20, -0.1), (21, -2.0)]))

    def test_native_numeric_row_refuses_incomplete_or_nonfinite_data(self):
        row = {"id": 0, "top_logprobs": [{"id": i, "logprob": -1.0 - i} for i in range(32)]}
        self.assertEqual(numeric_row({"completion_probabilities": [row]})[1][0], 1)
        for bad in ([], [row, row], [dict(row, id=80)],
                    [dict(row, top_logprobs=[{"id": 0, "logprob": float("nan")}] * 32)]):
            with self.assertRaises(ValueError):
                numeric_row({"completion_probabilities": bad})
