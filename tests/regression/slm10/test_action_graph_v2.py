from copy import deepcopy

from benchmarks.slm10.action_graph_v2 import replay


def test_legal_repeat_requires_distinct_calls_and_evidence_from_prior_action():
    schema = {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}
    arguments = {"key": "A"}
    graph = {"schemas": {"lookup": schema}, "actions": [
        {"action_id": "first", "tool": "lookup", "arguments": arguments, "depends_on": [],
         "observation": {"retry_key": "A"}},
        {"action_id": "retry", "tool": "lookup", "arguments": arguments, "depends_on": ["first"],
         "input_sources": {"key": ["first", "retry_key"]}, "observation": {"status": "ready"}},
    ]}
    first = {"call_id": "call-one", "completion_id": "one", "turn": 0, "tool": "lookup", "arguments_raw": '{"key":"A"}',
             "observation": {"retry_key": "A"}, "observation_sources": {}}
    second = {"call_id": "call-two", "completion_id": "two", "turn": 1, "tool": "lookup",
              "arguments_raw": '{"key":"A"}', "observation": {"status": "ready"},
              "observation_sources": {"key": {"action_id": "first", "call_id": "call-one", "key": "retry_key"}}}
    evidence = {"complete": True, "calls": [first, second]}
    result = replay(graph, evidence)
    assert result["status"] == "PASS"
    assert [row["action_id"] for row in result["mapped"]] == ["first", "retry"]
    bad = deepcopy(evidence)
    bad["calls"][1]["observation_sources"]["key"]["call_id"] = "invented"
    assert replay(graph, bad)["status"] == "FAIL"
    bad = deepcopy(evidence)
    del bad["calls"][1]["observation_sources"]
    assert replay(graph, bad)["status"] == "BLOCKED"
    bad = deepcopy(evidence)
    bad["calls"][1]["turn"] = 0
    assert replay(graph, bad)["status"] == "FAIL"
    bad = deepcopy(evidence)
    bad["calls"][1]["call_id"] = first["call_id"]
    assert replay(graph, bad)["reason"] == "REUSED_CALL_ID"

def test_extension_graph_size_boundaries():
    from benchmarks.slm10.sdk_extension import graph_size_controls

    controls = graph_size_controls()
    assert [(item["nodes"], item["observed"]) for item in controls] == [
        (18, "PASS"), (19, "PASS"), (20, "PASS"), (21, "FAIL"),
    ]
    assert all(item["status"] == "PASS" for item in controls)
