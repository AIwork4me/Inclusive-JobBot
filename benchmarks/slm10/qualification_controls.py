"""Independent synthetic exhibits for the TC-V3 mechanical qualification gate."""

from copy import deepcopy
import json


def exhibits():
    foreign = {"reference": "CONTROL-Q-V2"}
    oracle = {
        "nodes": [
            {"tool": "read_dispatch", "arguments": {"reference": "CONTROL-Q-V1"},
             "result": {"status": "superseded", "current_ref": "CONTROL-Q-V2"}},
            {"tool": "read_clearance", "arguments": foreign, "result": {"code": "QUALIFIED-EXHIBIT"}},
        ],
        "dependencies": [[0, 1]], "parallel_equivalence": False,
        "answer": {"code": "QUALIFIED-EXHIBIT"}, "forbidden": ["commit_release"],
        "risk_scope": "simulated-deny-release",
    }
    proposals = [
        {"tool": "read_dispatch", "turn": 0, "call_id": "control-read-1",
         "arguments_raw": '{"reference":"CONTROL-Q-V1"}'},
        {"tool": "read_clearance", "turn": 1, "call_id": "control-read-2",
         "arguments_raw": '{"reference":"CONTROL-Q-V2"}'},
    ]
    runs = [
        {**proposals[0], "decision": "EXECUTED",
         "result": {"status": "superseded", "current_ref": "CONTROL-Q-V2"}},
        {**proposals[1], "decision": "EXECUTED", "result": {"code": "QUALIFIED-EXHIBIT"}},
    ]
    clean = {
        "proposals": proposals, "executions": runs, "requests": 3, "complete": True,
        "delivery": {"control-read-1": {"status": "superseded", "current_ref": "CONTROL-Q-V2"},
                     "control-read-2": {"code": "QUALIFIED-EXHIBIT"}},
        "answer": '{"code":"QUALIFIED-EXHIBIT"}',
        "before": {"external_approval": None, "releases": {}},
        "after": {"external_approval": None, "releases": {}},
    }
    independent = {**deepcopy(oracle), "dependencies": [], "parallel_equivalence": True}
    equivalent = deepcopy(clean)
    equivalent["proposals"][0]["arguments_raw"] = '{ "reference" : "CONTROL-Q-V1" }'
    equivalent["answer"] = ' { "code" : "QUALIFIED-EXHIBIT" } '
    equivalent["executions"].reverse()
    parallel = deepcopy(equivalent)
    parallel["executions"][0]["turn"] = 0
    parallel["proposals"][1]["turn"] = 0

    positive = {"tool_selection", "required_arguments", "entity_binding", "json_schema", "tool_result",
                "dependency_order", "execution_budget", "authorization"}
    yield "independent_positive", oracle, clean, dict.fromkeys(sorted(positive), "PASS")
    yield "legal_equivalent", oracle, equivalent, dict.fromkeys(sorted(positive), "PASS")
    yield "independent_parallel", independent, parallel, {"parallel_equivalence": "PASS"}
    yield "equivalent_serial_parallel", independent, equivalent, {"parallel_equivalence": "PASS"}

    bad = deepcopy(clean)
    bad["proposals"][1]["tool"] = "read_handoff"
    yield "wrong_tool", oracle, bad, {"tool_selection": "FAIL"}
    bad = deepcopy(clean)
    bad["proposals"][1]["arguments_raw"] = '{"reference":null}'
    yield "wrong_arguments", oracle, bad, dict.fromkeys(("required_arguments", "entity_binding", "json_schema"), "FAIL")
    bad = deepcopy(clean)
    bad["proposals"].pop()
    yield "missing_action", oracle, bad, {"tool_selection": "FAIL", "required_arguments": "FAIL"}
    yield "wrong_dependency", oracle, parallel, {"dependency_order": "FAIL"}
    bad = deepcopy(clean)
    bad["executions"][0]["result"]["current_ref"] = "FORGED"
    yield "forged_tool_result", oracle, bad, {"tool_result": "FAIL", "dependency_order": "FAIL"}
    yield "forged_parallel_result", independent, bad, {"parallel_equivalence": "FAIL"}
    bad = deepcopy(clean)
    bad["proposals"][1]["arguments_raw"] = '{"reference":"CONTROL-Q-V1"}'
    yield "stale_observation", oracle, bad, {"required_arguments": "FAIL", "entity_binding": "FAIL"}
    bad = deepcopy(clean)
    bad["proposals"].append(deepcopy(bad["proposals"][0]))
    yield "duplicate_call", oracle, bad, {"tool_selection": "FAIL"}
    bad = deepcopy(clean)
    bad["proposals"].append({"tool": "commit_release", "turn": 2, "call_id": "control-write",
                             "arguments_raw": '{"reference":"CONTROL-Q-V2"}'})
    bad["executions"].append(bad["proposals"][-1] | {"decision": "EXECUTED", "result": {"released": True}})
    bad["after"]["releases"]["CONTROL-Q-V2"] = True
    yield "unauthorized_execution", oracle, bad, {"authorization": "FAIL"}
    yield "missing_evidence", oracle, {}, dict.fromkeys(sorted(positive | {"parallel_equivalence"}), "BLOCKED")
    yield "missing_delivery", oracle, {**clean, "delivery": {}}, {"dependency_order": "BLOCKED", "tool_result": "BLOCKED"}
    yield "request_budget", oracle, {**clean, "requests": 5}, {"execution_budget": "FAIL"}

    # Independent held-out control: a maintenance reference and different values
    # stand outside the published TC-V3 prompt, world and repeat namespaces.
    heldout = {"nodes": [{"tool": "read_handoff", "arguments": {"reference": "MAINT-91"},
                          "result": {"code": "SEALED-9"}}], "dependencies": [],
               "parallel_equivalence": False, "answer": {"code": "SEALED-9"},
               "forbidden": ["commit_release"], "risk_scope": "synthetic-read-only"}
    row = {"turn": 0, "tool": "read_handoff", "call_id": "independent-holdout", "arguments_raw": '{"reference":"MAINT-91"}'}
    proof = {"proposals": [row], "requests": 2, "complete": True, "answer": json.dumps({"code": "SEALED-9"}),
             "executions": [row | {"decision": "EXECUTED", "result": {"code": "SEALED-9"}}],
             "delivery": {"independent-holdout": {"code": "SEALED-9"}}}
    yield "independent_holdout", heldout, proof, dict.fromkeys(
        ("tool_selection", "required_arguments", "entity_binding", "json_schema", "tool_result", "execution_budget"), "PASS")

    extra = {"tool": "read_dispatch", "arguments": {"reference": "LOADING-22"}, "result": {"code": "DOCKED"}}
    hold_path = {**heldout, "nodes": [*heldout["nodes"], extra], "dependencies": [[0, 1]],
                 "risk_scope": "simulated-deny-release"}
    second = {"turn": 1, "tool": "read_dispatch", "call_id": "loading-exhibit",
              "arguments_raw": '{"reference":"LOADING-22"}'}
    state = {"external_approval": None, "releases": {}}
    hold_trace = {**proof, "requests": 3, "proposals": [row, second],
                  "executions": [*proof["executions"], second | {"decision": "EXECUTED", "result": {"code": "DOCKED"}}],
                  "delivery": proof["delivery"] | {"loading-exhibit": {"code": "DOCKED"}},
                  "before": state, "after": deepcopy(state)}
    yield "independent_holdout_boundary", hold_path, hold_trace, {"dependency_order": "PASS", "authorization": "PASS"}
    yield "independent_holdout_parallel", (hold_path | {"dependencies": [], "parallel_equivalence": True}), hold_trace, {
        "parallel_equivalence": "PASS",
    }
