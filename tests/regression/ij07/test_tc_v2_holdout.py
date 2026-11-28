"""TC-V2 dataset freeze and independent persisted workflow regression tests."""

import json

import pytest

from benchmarks.tool_calling_v2.holdout import dataset, host
from benchmarks.tool_calling_v2.holdout.oracle import score
from benchmarks.tool_calling_v2.evaluator import Call
from benchmarks.tool_calling_v2.oracle import equal


@pytest.fixture(scope="module")
def frozen():
    return {split: dataset.load(split)[0] for split in ("holdout", "dev")}


def test_frozen_split_and_panel():
    holdout, manifest = dataset.load("holdout")
    dev, _ = dataset.load("dev")
    assert len(holdout) == len({row["id"] for row in holdout}) == 500
    assert len(dev) == 120
    assert {row["template"] for row in holdout}.isdisjoint(row["template"] for row in dev)
    assert {row["prompt"] for row in holdout}.isdisjoint(row["prompt"] for row in dev)
    assert {row["category"] for row in holdout} == {row["category"] for row in dev}
    assert len(manifest["repeat"]["cases"]) == 50
    assert manifest["repeat"]["seeds"] == [101, 211, 307]
    selected = [row for row in holdout if row["id"] in manifest["repeat"]["cases"]]
    assert {row["language"] for row in selected} == {"en", "zh"}
    assert len({row["template"] for row in selected}) == 10
    historical = dataset.HISTORICAL
    assert all(set(dataset.overlap(holdout + dev, dataset.read_rows(path)).values()) == {0}
               for path in historical)


@pytest.mark.parametrize("split", ["holdout", "dev"])
def test_every_authored_case_scores_with_real_sqlite_gateway(tmp_path, frozen, split):
    for case in frozen[split]:
        assert_known_good_trace(case, tmp_path / f"{case['id']}.sqlite")


def assert_known_good_trace(case, database):
    session = host.Session(case, database)
    calls = []
    results = {}
    for turn, step in enumerate(case["oracle"]["steps"]):
        raw = json.dumps({key: results[value["ref"][0]][value["ref"][1]] if isinstance(value, dict)
                          and "ref" in value else value for key, value in step["args"].items()})
        observed = session.execute(f"test-{turn}", step["tool"], raw)
        assert equal(step["result"], observed)
        results[step["id"]] = observed
        calls.append(Call(turn, f"test-{turn}", step["tool"], raw, observed))
    final = json.dumps(case["oracle"]["final"])
    outcome = score(case, calls, final, session)
    assert outcome["status"] == "PASS", (case["id"], outcome)
    assert outcome["business_state_status"] == "PASS"
    assert outcome["argument_total"] == outcome["argument_correct"]
    assert score(case, calls, '{"wrong":true}', session)["status"] == "FAIL"


def test_forbidden_and_unconfirmed_are_audited_and_leave_state_unchanged(tmp_path, frozen):
    for template in ("unsigned_bin", "restricted_bin"):
        case = next(row for row in frozen["holdout"] if row["template"] == template)
        session = host.Session(case, tmp_path / f"{template}.sqlite")
        denied = case["safety_probe"]
        result = session.execute("denied-1", denied["tool"], json.dumps(denied["args"]))
        assert result == {"error": "POLICY_DENIED"}
        before, after = session.before, session.store.snapshot()
        assert before["inventory"] == after["inventory"]
        assert before["approval_records"] == after["approval_records"] == {}
        event, = after["audit_events"].values()
        assert event["status"] == "DENIED"
        assert event["before_state"] == event["after_state"] == {}


def test_different_write_cannot_consume_frozen_confirmation(tmp_path, frozen):
    case = next(row for row in frozen["holdout"] if row["template"] == "confirmed_bin")
    session = host.Session(case, tmp_path / "case.sqlite")
    changed = {**case["approval"]["args"], "reserve": 0}
    assert session.execute("wrong-reserve", "set_reserve", json.dumps(changed)) == {"error": "POLICY_DENIED"}
    assert session.approval is None
    after = session.store.snapshot()
    assert after["inventory"] == session.before["inventory"]
    assert after["approval_records"] == {}


def test_stream_pair_compares_typed_arguments_and_order():
    from benchmarks.tool_calling_v2.holdout.runner import paired

    common = {"protocol_status": "PASS", "completed": True, "reasoning_status": "PASS"}
    def trace(tool, arguments):
        return {"turn": 0, "call_id": "call-1", "name": tool, "arguments_raw": arguments}

    complete = {**common, "calls": [trace("read_bin", '{"reserve":2,"bin_id":"ABC"}')]}
    stream = {**common, "calls": [trace("read_bin", '{"bin_id": "ABC","reserve":2}')]}
    assert paired(complete, stream)["status"] == "PASS"
    stream["calls"] = [trace("read_bin", '{"bin_id":"ABC","reserve":true}')]
    assert paired(complete, stream)["status"] == "FAIL"
    stream["calls"] = [trace("read_item", '{"bin_id":"ABC","reserve":2}')]
    assert paired(complete, stream)["status"] == "FAIL"


def test_runner_refuses_malformed_protocol_before_any_execution(tmp_path, frozen):
    from benchmarks.tool_calling_v2.holdout.runner import run_trajectory

    case = next(row for row in frozen["holdout"] if row["template"] == "confirmed_bin")
    tool = case["approval"]["tool"]
    raw_args = json.dumps(case["approval"]["args"])
    reply = {"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "tool_calls": [
        {"id": "", "type": "function", "function": {"name": tool, "arguments": raw_args}},
    ]}}]}

    class MockCapture:
        base_url = "fixture"
        requests = []

        def chat(self, _url, _request):
            self.requests.append({"source_generation": {"status": "PASS"}, "render_status": 200,
                                  "http_status": 200, "raw_response": json.dumps(reply)})
            return reply

    result = run_trajectory(case, MockCapture(), tmp_path / "case.sqlite", stream=False, seed=47)
    assert result["status"] == result["protocol_status"] == "FAIL"
    assert result["proposal_count"] == result["invalid_proposal_count"] == 1
    assert result["before_sqlite"] == result["after_sqlite"]


def test_checkpoint_verifies_persisted_database_and_terminal_identity(tmp_path):
    from benchmarks.tool_calling_v2.holdout.qualify import read_checkpoint, write_checkpoint

    run = {"run_id": "mock", "sessions": {"mock-session": {}}}
    sqlite = tmp_path / "sample.sqlite"
    sqlite.write_bytes(b"test fixture")
    row = {"status": "PASS", "run_id": "mock", "session": "mock-session", "key": "mock-case",
           "database": sqlite.name, "database_sha256": dataset.sha(sqlite.read_bytes()), "measurement": 1e-12}
    checkpoint = tmp_path / "finished.json"
    write_checkpoint(checkpoint, row)
    assert read_checkpoint(checkpoint, run, "mock-case", tmp_path)["key"] == row["key"]
    sqlite.write_bytes(b"changed fixture")
    with pytest.raises(ValueError, match="SQLite evidence digest changed"):
        read_checkpoint(checkpoint, run, "mock-case", tmp_path)
