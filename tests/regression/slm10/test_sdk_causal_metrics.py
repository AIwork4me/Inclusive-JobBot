from benchmarks.slm10.sdk_causal_metrics import answer_metrics, action_identity, assign_actions


def test_json_fence_proves_value_comprehension_but_fails_exact_contract():
    result = answer_metrics("\x60\x60\x60json\n{\"code\":\"ZX\"}\n\x60\x60\x60", {"code": "ZX"}, True, True)
    assert result == {"result_comprehension": "PASS", "final_answer": "FAIL", "answer_kind": "fenced_json"}


def test_value_without_verified_delivery_abstains_on_comprehension():
    result = answer_metrics('{"code":"ZX"}', {"code": "ZX"}, True, False)
    assert result == {"result_comprehension": "BLOCKED", "final_answer": "PASS", "answer_kind": "exact_json"}


def test_same_tool_different_entities_and_legal_repeated_actions_are_distinct():
    def node(reference):
        return {"tool": "lookup", "arguments": {"reference": reference}}

    def call(reference, turn):
        return {"tool": "lookup", "arguments": {"reference": reference}, "turn": turn, "call_id": str(turn)}

    nodes = [node("A"), node("B"), node("A")]
    calls = [call("A", 0), call("A", 1), call("B", 2), call("A", 3)]
    assert action_identity("lookup", {"a": 1, "b": 2}) == action_identity("lookup", {"b": 2, "a": 1})
    assert assign_actions(nodes, [[0, 1], [1, 2]], calls) == ([0, None, 1, 2], [1])
