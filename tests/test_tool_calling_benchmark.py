import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks/tool_calling/runner"))
from evaluate import compare_arguments, evaluate_case
from run_benchmark import read_checkpoint
from run_parser_fixtures import assistant_prefix, score
from tool_simulators import ToolHost


class BenchmarkScoringTests(unittest.TestCase):
  def test_api_error_counts_as_failure_with_missing_arguments(self):
    case = {
        "expected": {"first_call": {"name": "get_purchase_order", "arguments": {"order_id": "PO-1"}}},
        "options": {},
    }
    result = evaluate_case(case, [{"error": "connection refused"}], [], [], [], "")
    self.assertFalse(result["pass"])
    self.assertEqual(result["argument_total"], 1)
    self.assertEqual(result["argument_correct"], 0)
    self.assertTrue(any("connection refused" in failure for failure in result["failures"]))

  def test_arguments_keep_json_types(self):
    _, correct, total = compare_arguments(
        {"count": 1, "flags": {"archived": False}, "text": "123"},
        {"count": True, "flags": {"archived": 0}, "text": 123},
    )
    self.assertEqual((correct, total), (0, 3))

  def test_stream_disagreement_fails_case(self):
    result = evaluate_case({"options": {}}, [{"tool_calls": [], "stream_matches_non_stream": False}], [], [], [], "done")
    self.assertFalse(result["pass"])


class ToolHostTests(unittest.TestCase):
  def setUp(self):
    self.host = ToolHost({
        "world": {"orders": {"PO-1": {"total": 30}}},
        "tools": [
            {"function": {"name": name, "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            }}}
            for name in ("get_purchase_order", "delete_purchase_order")
        ],
        "expected": {"forbidden_attempts": ["delete_purchase_order"]},
    })

  def test_declared_but_forbidden_tool_is_denied(self):
    result = self.host.dispatch("delete_purchase_order", {"order_id": "PO-1"})
    self.assertEqual(result["error"], "policy_denied")
    self.assertEqual(self.host.denied, ["delete_purchase_order"])
    self.assertEqual(self.host.executed, [])

  def test_invalid_arguments_never_reach_handler(self):
    for arguments in (None, {}, {"order_id": 1}, {"order_id": "PO-1", "extra": "value"}):
      with self.subTest(arguments=arguments):
        result = self.host.dispatch("get_purchase_order", arguments)
        self.assertEqual(result["error"], "invalid_arguments")
    self.assertEqual(self.host.executed, [])
    self.assertEqual(self.host.dispatch("get_purchase_order", {"order_id": "PO-1"}), {"total": 30})


class CheckpointAndFixtureTests(unittest.TestCase):
  def test_checkpoint_requires_a_valid_prefix(self):
    with tempfile.TemporaryDirectory() as directory:
      path = Path(directory) / "results.jsonl"
      path.write_text('{"id":"a"}\n', encoding="utf-8")
      self.assertEqual(list(read_checkpoint(path, ["a", "b"])), ["a"])
      path.write_text('{"id":"a"}\n{"id":"a"}\n', encoding="utf-8")
      with self.assertRaises(ValueError):
        read_checkpoint(path, ["a", "b"])

  def test_fixture_prefix_preserves_reasoning_and_content(self):
    self.assertEqual(
        assistant_prefix("<think>\nthink\n</think>\n\ntext"),
        {"role": "assistant", "reasoning_content": "think", "content": "text"},
    )

  def test_fixture_checks_arguments_as_typed_json(self):
    fixture = {"expect_mode": "exact", "expected": {"calls": [{"name": "test", "arguments": {"n": 1}}]}}
    call = {"id": "call", "type": "function", "function": {"name": "test", "arguments": '{"n": true}'}}
    self.assertTrue(score(fixture, {"tool_calls": [call]}))
    call["function"]["arguments"] = '{"n": 1}'
    self.assertEqual(score(fixture, {"tool_calls": [call]}), [])


if __name__ == "__main__":
  unittest.main()
