"""Regression controls for the supplemental TC-V3 assessment."""

from copy import deepcopy
import gzip
from hashlib import sha256
import json

import pytest

from benchmarks.slm10 import tc_capability_metrics as metrics
from benchmarks.slm10.tc_dashboard import objects
from benchmarks.slm10.tc_v3 import HERE, case_data
from evaluation.aeve.runtime import canonical


def wire_turn(number, messages, *, calls=(), answer=None, tokens=True):
    request = canonical({"stream": False, "messages": messages})
    reply = {
        "id": f"completion-{number}", "choices": [{"index": 0, "message": {
            "role": "assistant", "content": answer, "tool_calls": list(calls),
        }, "finish_reason": "tool_calls" if calls else "stop"}],
        "timings": {"prompt_ms": 2, "predicted_ms": 3},
    }
    if tokens:
        reply["usage"] = {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}
    response = canonical(reply)
    return {"provider_request_id": f"request-{number}", "completion_id": reply["id"], "trial_id": "trial",
            "provider_request": request.decode(), "provider_request_sha256": sha256(request).hexdigest(),
            "response": response.decode(), "response_sha256": sha256(response).hexdigest(),
            "http_status": 200, "content_type": "application/json"}


def trace(nodes, answer, *, action_sequence=None, denied=(), tokens=True):
    wire, callbacks, messages = [], [], []
    sequence = list(range(len(nodes))) if action_sequence is None else action_sequence
    for number, action in enumerate(sequence):
        node, call_id = nodes[action], f"call-{number}"
        arguments = canonical(node["arguments"]).decode()
        proposal = {"id": call_id, "type": "function", "function": {
            "name": node["tool"], "arguments": arguments,
        }}
        event = wire_turn(number, messages, calls=(proposal,), tokens=tokens)
        callback = {key: event[key] for key in ("provider_request_id", "completion_id", "trial_id")}
        callback.update(turn=number, call_id=call_id, tool=node["tool"], arguments_raw=arguments,
                        arguments=node["arguments"], result=node["result"],
                        decision="DENIED" if number in denied else "EXECUTED")
        wire.append(event)
        callbacks.append(callback)
        messages = [*messages, {"role": "tool", "tool_call_id": call_id, "content": canonical(node["result"]).decode()}]
    wire.append(wire_turn(len(wire), messages, answer=answer, tokens=tokens))
    return {"trial_id": "trial", "track": "direct_first", "wire": wire, "calls": callbacks,
            "answer": answer, "failure": None,
            "before": {"external_approval": None, "releases": {}},
            "after": {"external_approval": None, "releases": {}}}


def test_fenced_answer_certifies_facts_with_original_d25_preserved():
    _, _, oracle = case_data("roundtrip", "en", "H", 0)
    trial = trace(oracle["nodes"], '```json\n' + json.dumps(oracle["answer"]) + '\n```')
    result = metrics.assess(trial, oracle, "BLOCKED")
    assert result["metrics"] == {
        "BUSINESS_FACT_CORRECTNESS": "PASS", "OUTPUT_CONTRACT_COMPLIANCE": "FAIL",
        "EXECUTION_PROCESS_CORRECTNESS": "PASS", "STRICT_END_TO_END_SUCCESS": "BLOCKED",
        "FIRST_TOOL_CHOICE": "PASS", "REQUIRED_ACTION_COVERAGE": "PASS", "EXACT_ACTION_SEQUENCE": "PASS",
        "RESULT_DELIVERY": "PASS", "RESULT_COMPREHENSION": "PASS", "TERMINATION_CORRECTNESS": "PASS",
        "QUALIFIED_BUSINESS_COMPLETION": "FAIL",
    }
    assert result["fact_outcomes"] == {"code": "PASS", "dock": "PASS"}


def test_bare_schema_valid_wrong_value_does_not_certify_facts():
    _, _, oracle = case_data("roundtrip", "en", "H", 0)
    answer = oracle["answer"] | {"dock": "DOCK-WRONG"}
    result = metrics.assess(trace(oracle["nodes"], json.dumps(answer)), oracle, "BLOCKED")
    assert result["metrics"]["OUTPUT_CONTRACT_COMPLIANCE"] == "PASS"
    assert result["metrics"]["BUSINESS_FACT_CORRECTNESS"] == "FAIL"
    assert result["metrics"]["RESULT_COMPREHENSION"] == "FAIL"
    assert result["fact_outcomes"] == {"code": "PASS", "dock": "FAIL"}


def test_duplicate_denied_proposal_and_redundant_execution_use_distinct_denominators():
    _, _, oracle = case_data("single", "en", "H", 0)
    answer = json.dumps(oracle["answer"])
    denied = metrics.assess(trace(oracle["nodes"], answer, action_sequence=[0, 0], denied={1}), oracle, "BLOCKED")
    executed = metrics.assess(trace(oracle["nodes"], answer, action_sequence=[0, 0]), oracle, "BLOCKED")
    assert denied["call_counts"] == {"proposals": 2, "duplicate_proposals": 1, "executions": 1, "redundant_executions": 0}
    assert executed["call_counts"] == {"proposals": 2, "duplicate_proposals": 1, "executions": 2, "redundant_executions": 1}
    assert denied["metrics"]["EXACT_ACTION_SEQUENCE"] == "FAIL"
    assert denied["metrics"]["EXECUTION_PROCESS_CORRECTNESS"] == "PASS"
    assert executed["metrics"]["EXECUTION_PROCESS_CORRECTNESS"] == "FAIL"
    assert denied["metrics"]["TERMINATION_CORRECTNESS"] == "FAIL"


def test_required_coverage_is_independent_of_order_and_parallel_orders_are_legal():
    for workflow, exact in (("parallel", "PASS"), ("dependency", "FAIL")):
        _, _, oracle = case_data(workflow, "en", "H", 0)
        result = metrics.assess(trace(oracle["nodes"], json.dumps(oracle["answer"]), action_sequence=[1, 0]),
                                oracle, "BLOCKED")
        assert result["metrics"]["REQUIRED_ACTION_COVERAGE"] == "PASS"
        assert result["metrics"]["EXACT_ACTION_SEQUENCE"] == exact
        assert result["metrics"]["EXECUTION_PROCESS_CORRECTNESS"] == exact
        if workflow == "dependency":
            assert result["metrics"]["BUSINESS_FACT_CORRECTNESS"] == "BLOCKED"


def test_unlinked_callback_blocks_proof_and_counts():
    _, _, oracle = case_data("single", "en", "H", 0)
    trial = trace(oracle["nodes"], json.dumps(oracle["answer"]))
    trial["calls"][0]["completion_id"] = "different-completion"
    result = metrics.assess(trial, oracle, "BLOCKED")
    for label in ("EXECUTION_PROCESS_CORRECTNESS", "RESULT_DELIVERY", "RESULT_COMPREHENSION",
                  "BUSINESS_FACT_CORRECTNESS"):
        assert result["metrics"][label] == "BLOCKED"
    assert result["call_counts"]["executions"] is None


def test_substituted_final_answer_cannot_certify_provider_linked_facts():
    _, _, oracle = case_data("single", "en", "H", 0)
    trial = trace(oracle["nodes"], '{"code":"wrong"}')
    trial["answer"] = json.dumps(oracle["answer"])
    result = metrics.assess(trial, oracle, "BLOCKED")
    assert result["metrics"]["OUTPUT_CONTRACT_COMPLIANCE"] == "PASS"
    assert result["metrics"]["RESULT_COMPREHENSION"] == "FAIL"
    assert result["metrics"]["BUSINESS_FACT_CORRECTNESS"] == "BLOCKED"


def test_verified_callback_result_without_delivery_cannot_credit_comprehension():
    _, _, oracle = case_data("single", "en", "H", 0)
    trial = trace(oracle["nodes"], json.dumps(oracle["answer"]))
    trial["wire"][-1] = wire_turn(1, [], answer=trial["answer"])
    result = metrics.assess(trial, oracle, "BLOCKED")
    assert result["metrics"]["EXECUTION_PROCESS_CORRECTNESS"] == "PASS"
    assert result["metrics"]["RESULT_DELIVERY"] == "FAIL"
    assert result["metrics"]["RESULT_COMPREHENSION"] == "BLOCKED"
    assert result["metrics"]["TERMINATION_CORRECTNESS"] == "FAIL"


def test_portable_sdk_request_can_redact_system_text_but_not_tool_payload():
    _, _, oracle = case_data("single", "en", "H", 0)
    trial = trace(oracle["nodes"], json.dumps(oracle["answer"]))
    trial["track"] = "sdk_first"
    reply_payload = canonical({"result": canonical(oracle["nodes"][0]["result"]).decode()}).decode()
    result_text = ("Created At: 1\nCompleted At: 2\nTool response for read_dispatch:\n"
                   "```json\n" + reply_payload + "\n```")
    messages = [{"role": "system", "content": "SDK workspace location"},
                {"role": "tool", "name": "read_dispatch", "tool_call_id": "call-0", "content": result_text}]
    trial["wire"][-1] = wire_turn(1, messages, answer=trial["answer"])
    trial["wire"][-1]["provider_request"] = trial["wire"][-1]["provider_request"].replace(
        "SDK workspace location", "SDK workspace Users/<REDACTED>")
    assert metrics.assess(trial, oracle, "BLOCKED")["metrics"]["RESULT_DELIVERY"] == "BLOCKED"
    accepted = metrics.assess(trial, oracle, "BLOCKED", verified_portable_seal=True)
    assert accepted["metrics"]["BUSINESS_FACT_CORRECTNESS"] == "PASS"
    assert accepted["provider_request_bindings"] == {"exact_sha256": 1, "sealed_system_redaction": 1, "blocked": 0}
    trial["wire"][-1]["provider_request"] = trial["wire"][-1]["provider_request"].replace(
        "Created At: 1", "Created At: <REDACTED>")
    rejected = metrics.assess(trial, oracle, "BLOCKED", verified_portable_seal=True)
    assert rejected["metrics"]["RESULT_DELIVERY"] == "BLOCKED"


def test_output_exhaustion_and_uncaptured_stop_do_not_share_a_verdict():
    _, _, oracle = case_data("single", "en", "H", 0)
    trial = trace(oracle["nodes"], json.dumps(oracle["answer"]))
    trial["wire"].pop()
    trial["failure"] = {"type": "BudgetExceeded"}
    exhausted = metrics.assess(trial, oracle, "BLOCKED")
    assert exhausted["metrics"]["TERMINATION_CORRECTNESS"] == "FAIL"
    assert exhausted["metrics"]["OUTPUT_CONTRACT_COMPLIANCE"] == "FAIL"
    trial["failure"] = {"type": "AntigravityConnectionError"}
    uncertain = metrics.assess(trial, oracle, "BLOCKED")
    assert uncertain["metrics"]["TERMINATION_CORRECTNESS"] == "BLOCKED"
    assert uncertain["metrics"]["OUTPUT_CONTRACT_COMPLIANCE"] == "BLOCKED"


def test_missing_telemetry_blocks_cost_and_counts_successes_explicitly():
    _, _, oracle = case_data("roundtrip", "en", "H", 0)
    answer = json.dumps(oracle["answer"])
    one = metrics.assess(trace(oracle["nodes"], answer), oracle, "BLOCKED")
    two = metrics.assess(trace(oracle["nodes"], answer, tokens=False), oracle, "BLOCKED")
    cost = metrics.summarize_cell([one, two])["cost_per_outcome"]
    assert cost["correct_fact"]["denominator"] == 4
    assert cost["strict_output"]["denominator"] == 2
    assert cost["verified_execution"]["denominator"] == 2
    assert cost["qualified_business_completion"]["denominator"] == 2
    assert cost["correct_fact"]["telemetry"]["model_requests"] == {
        "status": "PASS", "value": 1, "observed_total": 4, "observed_trials": 2, "missing_trials": 0,
    }
    assert cost["correct_fact"]["telemetry"]["input_tokens"] == {
        "status": "BLOCKED", "value": None, "observed_total": 14, "observed_trials": 1, "missing_trials": 1,
    }


def test_unqualified_or_nonphysical_scope_never_earns_business_credit():
    _, _, oracle = case_data("authorization", "en", "H", 0)
    sound = trace(oracle["nodes"], json.dumps(oracle["answer"]))
    result = metrics.assess(sound, oracle, "BLOCKED")
    assert result["metrics"]["BUSINESS_FACT_CORRECTNESS"] == "BLOCKED"
    assert result["metrics"]["QUALIFIED_BUSINESS_COMPLETION"] == "BLOCKED"
    assert result["metrics"]["EXECUTION_PROCESS_CORRECTNESS"] == "PASS"
    corrupt = deepcopy(sound)
    corrupt["after"]["releases"]["record"] = True
    assert metrics.assess(corrupt, oracle, "BLOCKED")["metrics"]["EXECUTION_PROCESS_CORRECTNESS"] == "FAIL"
    unavailable = metrics.assess(None, oracle, "NOT_RUN")
    assert unavailable["metrics"]["FIRST_TOOL_CHOICE"] == "BLOCKED"
    assert unavailable["metrics"]["STRICT_END_TO_END_SUCCESS"] == "NOT_RUN"


def test_public_seal_replay_includes_additional_candidates_and_preserves_original(tmp_path):
    dataset = sha256((HERE / "manifest.json").read_bytes()).hexdigest()
    statuses = {"F": "FAIL", "G": "BLOCKED"}
    for candidate, status in statuses.items():
        spec = next(row for row in objects(HERE / "roster.jsonl") if row["candidate"] == candidate)
        run = tmp_path / f"software-control-{candidate}"
        run.mkdir()
        record = {"trial_id": spec["trial_id"], "physical_execution": "BLOCKED", "status": status,
                  "reason": "software-only reservation fixture"}
        payload = gzip.compress(canonical(record) + b"\n", mtime=0)
        (run / "trials.jsonl.gz").write_bytes(payload)
        seal = {
            "identity": {"run_id": run.name, "candidate": candidate,
                         "enrollment": {"dataset_manifest_sha256": dataset}},
            "launch": {"pid": 1, "backend": "vulkan", "owns_port": False, "layers_offloaded": 0,
                       "layers_total": 0},
            "gpu_execution": "BLOCKED", "reservations": 1,
            "artifacts": {"trials.jsonl.gz": sha256(payload).hexdigest()},
        }
        (run / "manifest.json").write_bytes(canonical(seal) + b"\n")
    rows, report = metrics.build(tmp_path)
    assert {row["candidate"]: row["metrics"]["STRICT_END_TO_END_SUCCESS"] for row in rows} == statuses
    assert report["models"]["F"] == {"planned": 1650, "sealed": 1, "executed": 0, "unsealed": 1649}
    assert report["models"]["G"]["sealed"] == 1
    assert report["models"]["A"]["sealed"] == 0
    with pytest.raises(ValueError, match="artifact does not match"):
        (tmp_path / "software-control-F" / "trials.jsonl.gz").write_bytes(b"changed")
        metrics.build(tmp_path)
