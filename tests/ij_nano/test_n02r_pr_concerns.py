"""N02R addendum reproduction suite: PR-D02..PR-D05 offline controls.

Red phase: run against the audited implementation (9b137f6) BEFORE the
repairs; every EV-relevant assertion fails where the concern is real.
After repair this file is the permanent parser x evaluator integration
regression backing N02R_PARSER_EVALUATOR_INTEGRATION_GO.

Controls are end-to-end: raw API-shaped response -> parse_response ->
scorer.score -> verdict, per the addendum's mandatory-negative list.
"""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks" / "ij_nano"))

# The red run (evidence/IJNANO/N02R/pr_concerns_red_run.txt) executed this
# suite against the audited v1 implementation (`from n02r import arms`).
# The permanent regression targets the corrected implementation.
from n02r import arms_v2 as arms  # noqa: E402
from n02r import scorer, tasks  # noqa: E402


def _require(test, description, fn):
    try:
        return fn()
    except (AttributeError, ImportError, TypeError, KeyError) as e:
        test.fail(f"capability absent: {description} "
                  f"({type(e).__name__}: {e})")


def task_by_family(fam: str) -> dict:
    return next(t for t in tasks.build_suite() if t["family"] == fam)


def chat_http(content: str, **choice_extra) -> dict:
    ch = {"message": {"content": content, "role": "assistant"}, "finish_reason": "stop"}
    ch.update(choice_extra)
    return {"choices": [ch], "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                                       "total_tokens": 15}}


def toolcall_http(calls: list[dict]) -> dict:
    return {"choices": [{"message": {"role": "assistant",
                                     "content": None,
                                     "tool_calls": calls},
                         "finish_reason": "tool_calls"}]}


def call(name: str, args) -> dict:
    return {"id": "c0", "type": "function",
            "function": {"name": name,
                         "arguments": args if isinstance(args, str)
                         else json.dumps(args)}}


def verdict(arm, task, http):
    parsed = arms.parse_response(arm, task, http, None)
    scored = scorer.score(task, parsed.get("payload"))
    return parsed, scored


class TestPRD02P5Contract(unittest.TestCase):
    """P5 structured-action contract: a response that perfectly satisfies
    the SUPPLIED tool definition must not be structurally rejected."""

    def setUp(self):
        self.task = task_by_family("structured_action")
        _, body = arms.build_request("P5B", self.task, 1024, None)
        self.supplied_tools = body["tools"]

    def test_supplied_contract_is_record_answer_typed(self):
        # the corrected B contract declares record_answer with typed fields
        names = [t["function"]["name"] for t in self.supplied_tools]
        self.assertEqual(names, ["record_answer"])
        params = self.supplied_tools[0]["function"]["parameters"]
        self.assertIn("tool", params["properties"])
        self.assertEqual(params["properties"]["tool"]["type"], "string")

    def test_perfect_record_answer_response_not_rejected(self):
        exp = self.task["expected"]
        fargs = {"tool": exp["tool"], **exp["args"]}
        http = toolcall_http([call("record_answer", fargs)])
        parsed, scored = verdict("P5B", self.task, http)
        self.assertTrue(parsed.get("structural_ok"),
                        f"valid per supplied contract rejected: {parsed}")
        self.assertTrue(scored["semantic_correct"],
                        f"perfect contract response scored wrong: {scored}")

    def test_p5a_business_tool_contract(self):
        # arm A: real typed business tool schemas; a valid business call
        # must parse and score correctly
        _, body = arms.build_request("P5A", self.task, 1024, None)
        names = [t["function"]["name"] for t in body["tools"]]
        self.assertIn(self.task["expected"]["tool"], names)
        exp = self.task["expected"]
        http = toolcall_http([call(exp["tool"], exp["args"])])
        parsed, scored = verdict("P5A", self.task, http)
        self.assertTrue(parsed.get("structural_ok"),
                        f"valid business tool call rejected: {parsed}")
        self.assertTrue(scored["semantic_correct"],
                        f"valid business tool call scored wrong: {scored}")


class TestPRD03P7Applicability(unittest.TestCase):
    """P7 applicability must be preregistered per task contract; impossible
    protocol/task combinations are INAPPLICABLE, not model failures."""

    def test_applicability_matrix_exists_and_is_preregistered(self):
        applicable = _require(
            self, "arms.P7_APPLICABILITY registry",
            lambda: arms.P7_APPLICABILITY)
        self.assertEqual(applicable.get("tool_selection"), True)
        self.assertEqual(applicable.get("enumerated_action"), True)
        self.assertEqual(applicable.get("conditional_branch"), True)
        self.assertEqual(applicable.get("stop_continue"), True)
        # slot/structured answers cannot be enumerated without leaking the
        # hidden expected argument
        self.assertEqual(applicable.get("slot_extraction"), False)
        self.assertEqual(applicable.get("structured_action"), False)

    def test_p7_slot_prompt_has_no_degenerate_candidate_list(self):
        task = task_by_family("slot_extraction")
        with self.assertRaises(ValueError) as cm:
            arms.build_request("P7", task, 1024, None)
        self.assertIn("inapplicable", str(cm.exception))


class TestPRD04ParserNegatives(unittest.TestCase):
    """Mandatory negatives: raw response -> parser -> evaluator verdict.
    A parser must not silently transform a semantically invalid output
    into a correct answer."""

    def _assert_rejected(self, arm, task, http, label):
        parsed, scored = verdict(arm, task, http)
        self.assertFalse(scored["semantic_correct"],
                          f"{label}: semantically invalid output ACCEPTED "
                          f"(parsed={parsed})")

    # -- P0 free text ------------------------------------------------------
    def test_multiple_competing_candidates_rejected(self):
        task = task_by_family("tool_selection")
        http = chat_http("Maybe orders.cancel_order, or perhaps "
                         "orders.get_refund_eligibility, hard to say.")
        self._assert_rejected("P0", task, http, "competing candidates")

    def test_competing_candidates_expected_first_still_rejected(self):
        # ambiguity must be detected as such - not resolved by the
        # candidate-list ordering luck
        task = task_by_family("tool_selection")
        exp = task["expected"]["tool"]
        http = chat_http(f"Use {exp}, not orders.cancel_order.")
        parsed, scored = verdict("P0", task, http)
        self.assertFalse(scored["semantic_correct"],
                          "ambiguous answer accepted because the expected "
                          "candidate happens to be found first")

    def test_negated_candidate_rejected(self):
        task = task_by_family("tool_selection")
        exp = task["expected"]["tool"]
        http = chat_http(f"Definitely do not call {exp}; pick something else.")
        self._assert_rejected("P0", task, http, "negated candidate")

    def test_tool_name_at_sentence_end_parses(self):
        # adjacent defect found while reproducing the negation control:
        # sentence punctuation must not block closed-set matching
        task = task_by_family("tool_selection")
        exp = task["expected"]["tool"]
        http = chat_http(f"Call {exp}.")
        parsed, scored = verdict("P0", task, http)
        self.assertTrue(parsed.get("structural_ok"),
                        f"punctuation boundary rejects valid answer: {parsed}")

    def test_contradictory_final_answer_rejected(self):
        task = task_by_family("stop_continue")
        http = chat_http("stop. Actually, continue. Final answer: stop again?")
        self._assert_rejected("P0", task, http, "contradictory answer")

    def test_trailing_contradictory_content_rejected(self):
        task = task_by_family("conditional_branch")
        http = chat_http("requires_manager_approval. Ignore that: auto_approve.")
        self._assert_rejected("P0", task, http, "trailing contradiction")

    # -- structured channels ------------------------------------------------
    def test_duplicate_json_key_in_content_rejected(self):
        task = task_by_family("tool_selection")
        exp = task["expected"]["tool"]
        http = chat_http(json.dumps({"tool": exp, "tool": "orders.cancel_order"}))
        self._assert_rejected("P1", task, http, "duplicate JSON key")

    def test_unexpected_tool_argument_visible_to_evaluator(self):
        task = task_by_family("slot_extraction")
        slot = task["schema_hint"]["slot"]
        val = task["expected"]["args"][slot]
        val = val if isinstance(val, str) else json.dumps(val)
        http = toolcall_http([call("record_answer",
                                   {"value": val, "admin_override": True})])
        self._assert_rejected("P5", task, http, "unexpected tool argument")

    def test_multiple_tool_calls_flagged(self):
        task = task_by_family("conditional_branch")
        http = toolcall_http([
            call("record_answer", {"branch": task["expected"]["branch"]}),
            call("record_answer", {"branch": "reject_out_of_policy"})])
        self._assert_rejected("P5", task, http, "multiple tool calls")

    def test_wrong_record_answer_name_rejected_for_closed_families(self):
        task = task_by_family("conditional_branch")
        http = toolcall_http([
            call("record_answer2", {"branch": task["expected"]["branch"]})])
        self._assert_rejected("P5", task, http, "wrong record_answer name")

    # -- DSL -----------------------------------------------------------------
    def _sa_task(self):
        task = task_by_family("structured_action")
        return task

    def test_duplicate_dsl_key_rejected(self):
        task = task_by_family("slot_extraction")
        slot = task["schema_hint"]["slot"]
        val = task["expected"]["args"][slot]
        v = val if isinstance(val, str) else f"{val['value']}@{val['unit']}"
        http = {"content": f"SLOT {slot}={v} {slot}=WRONG-1"}
        self._assert_rejected("P6", task, http, "duplicate DSL key")

    def test_incorrect_dsl_slot_name_rejected(self):
        task = task_by_family("slot_extraction")
        slot = task["schema_hint"]["slot"]
        val = task["expected"]["args"][slot]
        v = val if isinstance(val, str) else f"{val['value']}@{val['unit']}"
        http = {"content": f"SLOT wrong_{slot}={v}"}
        self._assert_rejected("P6", task, http, "incorrect DSL slot name")

    def test_trailing_contradictory_dsl_rejected(self):
        task = self._sa_task()
        exp, args = task["expected"]["tool"], task["expected"]["args"]
        kv = " ".join(f"{k}={v['value']}@{v['unit']}" if isinstance(v, dict) else f"{k}={v}"
                      for k, v in args.items())
        http = {"content": f"TOOL {exp} {kv} but actually use "
                           f"orders.cancel_order instead"}
        self._assert_rejected("P6", task, http, "trailing contradictory DSL")

    def test_malformed_quantity_rejected(self):
        task = task_by_family("structured_action")
        exp, args = task["expected"]["tool"], task["expected"]["args"]
        kv = " ".join(f"{k}=abc@CNY" if isinstance(v, dict) else f"{k}={v}"
                      for k, v in args.items())
        http = {"content": f"TOOL {exp} {kv}"}
        self._assert_rejected("P6", task, http, "malformed quantity")

    def test_invalid_dsl_header_rejected(self):
        task = self._sa_task()
        http = {"content": "TOOLX refunds.submit order_id=ORD-1"}
        parsed, scored = verdict("P6", task, http)
        self.assertFalse(parsed.get("structural_ok"))

    # -- anchors that must stay rejected -------------------------------------
    def test_wrong_entity_stays_rejected(self):
        task = task_by_family("tool_selection")
        http = chat_http("orders.cancel_order")
        parsed, scored = verdict("P0", task, http)
        self.assertFalse(scored["semantic_correct"])

    def test_truncated_output_stays_rejected(self):
        task = task_by_family("tool_selection")
        exp = task["expected"]["tool"]
        http = chat_http('{"tool": "' + exp[:4], finish_reason="length")
        self._assert_rejected("P1", task, http, "truncated")

    def test_missing_required_answer_stays_rejected(self):
        task = task_by_family("tool_selection")
        http = chat_http("", finish_reason="stop")
        parsed, scored = verdict("P0", task, http)
        self.assertFalse(parsed.get("structural_ok"))


class TestPRD05EvidencePreservation(unittest.TestCase):
    """Parser output must preserve raw response, warnings, structural and
    semantic verdicts separately; unknown fields reach the evaluator."""

    def test_parse_result_carries_warnings_and_raw(self):
        def go():
            task = task_by_family("slot_extraction")
            parsed = arms.parse_response(
                "P5", task,
                toolcall_http([call("record_answer",
                                    {"value": "ORD-1042", "extra": 1})]), None)
            return parsed
        parsed = _require(self, "parser warnings/raw fields", go)
        for key in ("warnings", "raw_content", "structural_ok", "payload"):
            self.assertIn(key, parsed, f"parser result lacks {key!r}")


if __name__ == "__main__":
    unittest.main()
