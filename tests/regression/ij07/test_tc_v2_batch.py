"""Software-only coverage for the single-server competitive TC-V2 roster."""

from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from benchmarks.competitive_slm import tc_v2_batch as batch
from benchmarks.competitive_slm import tc_v2_candidate as candidate
from benchmarks.tool_calling_v2.holdout import dataset
from business_tools import BusinessStore


@pytest.fixture(scope="module")
def frozen():
    return batch.make_roster("full")


def test_full_roster_uses_first_stream_and_all_frozen_repeats(frozen):
    _, manifest = dataset.load("holdout")
    _, roster = frozen
    assert len({trial["key"] for trial in roster}) == len(roster) == 1150
    assert [row["phase"] for row in roster] == ["first"] * 500 + ["stream"] * 500 + ["repeat"] * 150
    assert all(row["seed"] == manifest["first_pass_seed"] for row in roster[:1000])
    assert {row["case_id"] for row in roster[1000:]} == set(manifest["repeat"]["cases"])
    assert {row["seed"] for row in roster[1000:]} == set(manifest["repeat"]["seeds"])
    assert set(row["attempt"] for row in roster) == {1}


@pytest.fixture
def fixture_run(tmp_path, monkeypatch, frozen):
    cases, roster = frozen
    configuration = {"candidate": "B", "budgets": candidate.BUDGETS,
                     "engine": {"build": "fixture-build", "layers": 4},
                     "gpu": candidate.VULKAN_DEVICE, "template": {"sha256": "fixture-template"}}
    args = SimpleNamespace(port=8102, resume=False, batch_size=2)
    active = []

    @contextmanager
    def mock_server(_binary, _model, backend, _env, output, _port, tag, observe, *, alias):
        assert backend == "vulkan" and observe and alias == "ij07-candidate-b"
        active.append({"tag": tag, "cases": [], "wire": None})
        counter, trace = f"{tag}-gpu.jsonl", f"{tag}-source.jsonl"
        (output / f"{tag}-server.log").write_text("simulated boot evidence", encoding="utf-8")
        (output / trace).write_text('{"mock":true}\n', encoding="utf-8")
        (output / counter).write_text("\n".join(map(json.dumps, (
            {"kind": "gpu_engine", "instance": "pid_100_foo", "engtype": "Compute", "utilization": 30},
            {"kind": "gpu_process_memory", "instance": "pid_100_foo", "committed_bytes": 100},
        ))) + "\n", encoding="utf-8")
        yield SimpleNamespace(trace_path=output / trace), {
            "pid": 100, "owns_port": True, "backend": backend, "gpu": candidate.VULKAN_DEVICE,
            "build": "fixture-build", "template_sha256": "fixture-template",
            "layers_offloaded": 4, "layers_total": 4, "args": ["--ctx-size", "8192"],
            "counter_file": counter, "trace_file": trace,
        }

    def mock_trajectory(case, wire, database, *, stream, seed):
        active[-1]["cases"].append((case["id"], stream, seed))
        assert active[-1]["wire"] in (None, wire)
        active[-1]["wire"] = wire
        BusinessStore(database, initial=case["initial"])
        return {
            "status": "FAIL" if case["id"] == roster[0]["case_id"] else "PASS",
            "requests": [{"source_generation": {"sampled_token_ids": [10]}}],
            "calls": [], "findings": [], "native_parser_rejected": False,
            "completed": True, "protocol_status": "PASS", "reasoning_status": "PASS",
            "seed": seed, "stream": stream,
        }

    monkeypatch.setattr(batch, "gpu_server", mock_server)
    monkeypatch.setattr(candidate.runner, "run_trajectory", mock_trajectory)
    return args, configuration, cases, roster[:3], tmp_path, active


def execute(fixture_run):
    args, configuration, cases, roster, output, _ = fixture_run
    return batch.execute_locked(args, configuration, cases, roster, output, Path("engine"), Path("model"), {})


def test_batch_reuses_one_session_and_resumes_only_new_first_attempts(fixture_run):
    args, configuration, _, roster, output, active = fixture_run
    first = execute(fixture_run)
    assert len(active) == 1 and len(active[0]["cases"]) == 2
    assert first["phases"]["first"]["status_counts"] == {"PASS": 1, "FAIL": 1, "BLOCKED": 0, "NOT_RUN": 1}
    args.resume = True
    second = execute(fixture_run)
    assert len(active) == 2 and len(active[1]["cases"]) == 1
    assert second["run_id"] == first["run_id"] and second["coverage_status"] == "PASS"
    assert second["phases"]["first"]["status_counts"]["FAIL"] == 1
    assert len(list((output / "sqlite").glob("*.sqlite"))) == 3
    assert execute(fixture_run) == second and len(active) == 2
    configuration["template"] = {"sha256": "different-template"}
    with pytest.raises(ValueError, match="exact original"):
        execute(fixture_run)
    assert roster[0]["case_id"] == active[0]["cases"][0][0]


def test_orphaned_first_attempt_stays_blocked_on_resume(fixture_run, monkeypatch):
    args, _, _, _, output, active = fixture_run
    original = candidate.runner.run_trajectory

    def interrupted(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(candidate.runner, "run_trajectory", interrupted)
    with pytest.raises(KeyboardInterrupt):
        execute(fixture_run)
    assert len(list((output / "attempts").glob("*.json"))) == 1
    monkeypatch.setattr(candidate.runner, "run_trajectory", original)
    args.resume = True
    result = execute(fixture_run)
    assert len(active) == 2 and len(active[1]["cases"]) == 2
    assert result["phases"]["first"]["status_counts"] == {"PASS": 2, "FAIL": 0, "BLOCKED": 1, "NOT_RUN": 0}


def test_resume_refuses_changed_sqlite_or_sealed_session_capture(fixture_run):
    args, _, _, _, output, active = fixture_run
    execute(fixture_run)
    args.resume = True
    sqlite = next((output / "sqlite").glob("*.sqlite"))
    original = sqlite.read_bytes()
    sqlite.write_bytes(b"changed database fixture")
    with pytest.raises(ValueError, match="SQLite.*digest"):
        execute(fixture_run)
    sqlite.write_bytes(original)
    trace = output / f"{active[0]['tag']}-source.jsonl"
    trace.write_text("changed trace fixture", encoding="utf-8")
    with pytest.raises(ValueError, match="session artifact digest"):
        execute(fixture_run)


def test_resume_refuses_deleted_sealed_attempt_even_if_database_is_deleted(fixture_run):
    args, _, _, roster, output, _ = fixture_run
    execute(fixture_run)
    args.resume = True
    key = roster[0]["key"]
    for folder, suffix in (("attempts", ".json"), ("trajectories", ".json"), ("sqlite", ".sqlite")):
        (output / folder / (key + suffix)).unlink()
    with pytest.raises(ValueError, match="sealed session checkpoint inventory"):
        execute(fixture_run)


def test_stream_and_repeats_stay_separate_from_primary(fixture_run, frozen):
    args, config, cases, _, output, active = fixture_run
    args.batch_size = None
    _, full = frozen
    key = next(trial["case_id"] for trial in full if trial["phase"] == "repeat")
    roster = [trial for trial in full if trial["case_id"] == key]
    result = execute((args, config, cases, roster, output, active))
    assert result["coverage_status"] == "PASS"
    assert len(active) == 1 and len(active[0]["cases"]) == 5
    assert result["phases"]["first"]["planned"] == result["phases"]["stream"]["planned"] == 1
    assert result["streaming_pairs"]["status_counts"]["PASS"] == 1
    assert result["repeat"] == {"planned_groups": 1, "assessed_groups": 1, "pass_at_3": 1, "pass_all_3": 1}
