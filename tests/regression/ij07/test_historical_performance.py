import gzip
from hashlib import sha256
import json

import pytest

from benchmarks.root_cause.performance import summarize


def stable_digest(value):
    return sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def capture(wall_ms, *, stream=False, timings=None, usage=None, messages=None):
    response = {"choices": [], "usage": usage, "timings": timings}
    raw = json.dumps(response)
    if stream:
        raw = f"data: {raw}\n\ndata: [DONE]\n\n"
    return {"request": {"stream": stream, "messages": [] if messages is None else messages}, "http_status": 200,
            "wall_ms": wall_ms, "raw_response": raw, "source_generation": {}}


def create_run(directory, cases, *, planned=None, counters=None, compressed=False):
    configuration = {"arm": "R0-V", "backend": "vulkan", "case_ids": planned or [row["id"] for row in cases]}
    run = {"run_id": "fixture-run", "configuration": configuration, "fingerprint": stable_digest(configuration),
           "sessions": [{"pid": 23, "backend": "vulkan", "counter_file": "gpu.jsonl"}]}
    (directory / "run.json").write_text(json.dumps(run), encoding="utf-8")
    rows = []
    for case in cases:
        row = {**case, "run_id": run["run_id"], "server_session": 1, "status": "PASS"}
        rows.append({**row, "artifact_sha256": stable_digest(row)})
    lines = b"".join(json.dumps(row).encode() + b"\n" for row in rows)
    (directory / "summary.json").write_text(json.dumps({"run_id": run["run_id"], "cases": len(cases),
                                                        "result_sha256": sha256(lines).hexdigest()}), encoding="utf-8")
    for name, data in (("results.jsonl", lines), ("gpu.jsonl", b"".join(json.dumps(row).encode() + b"\n"
                                                                       for row in counters or []))):
        if name == "gpu.jsonl" and counters is None:
            continue
        if compressed:
            (directory / (name + ".gz")).write_bytes(gzip.compress(data))
        else:
            (directory / name).write_bytes(data)


def test_latency_phase_totals_and_stream_probe_are_read_from_capture(tmp_path):
    first = {"prompt_n": 8, "prompt_ms": 2.0, "prompt_per_second": 4000.0,
             "predicted_n": 6, "predicted_ms": 10.0, "predicted_per_second": 500.0, "cache_n": 1}
    second = {"prompt_n": 8, "prompt_ms": 8.0, "prompt_per_second": 1000.0,
              "predicted_n": 6, "predicted_ms": 20.0, "predicted_per_second": 250.0, "cache_n": 1}
    usage = {"prompt_tokens": 9, "completion_tokens": 6}
    create_run(tmp_path, [{"id": "C1", "wall_ms": 42, "capture": [capture(12, stream=True, timings=first, usage=usage),
                                                                  capture(20, timings=second, usage=usage),
                                                                  capture(30, messages=[{"role": "assistant", "content": "a"}])]},
                          {"id": "C2", "wall_ms": 100, "capture": []}], planned=["C1", "C2", "C3"], compressed=True)
    summary = summarize(tmp_path, include_turns=True)
    assert summary["cases"]["planned"] == 3
    assert summary["cases"]["status_counts"]["NOT_RUN"] == 1
    assert summary["latency"]["task_recorded_wall_ms"]["p95"] == 100
    assert summary["latency"]["request_wall_ms"]["p50"] == 20
    assert summary["workload"]["parity_requests"] == 1
    assert summary["phases"]["prefill"]["duration_ms"]["sum"] == 10
    assert summary["phases"]["prefill"]["duration_weighted_tokens_per_second"] == 1600
    assert summary["phases"]["decode"]["duration_weighted_tokens_per_second"] == pytest.approx(333.333333, rel=0.00001)
    assert summary["trajectory_phases"]["decode"]["duration_weighted_tokens_per_second"] == 500.0
    assert summary["tokens"]["wire_prompt"]["sum"] == 18
    assert summary["tokens"]["wire_prompt"]["missing"] == 1
    assert summary["unmeasured"]["task_end_to_end_latency"]["status"] == "NOT_RUN"
    assert summary["unmeasured"]["time_to_first_token"]["status"] == "NOT_RUN"
    assert [turn["role"] for turn in summary["turns"]] == ["trajectory", "stream_parity_probe", "trajectory"]


def test_counter_coverage_preserves_invalid_and_absent_observations(tmp_path):
    rows = [
        {"kind": "process", "t": "tick1", "elapsed_s": 0, "logical_processors": 4,
         "cpu_percent_of_one_core": 200, "working_set_private_bytes": 4, "private_bytes": 8, "threads": 7},
        {"kind": "gpu_engine", "t": "tick1", "elapsed_s": 0, "instance": "pid_23_luid_0x1_0x2_phys_0_eng_0",
         "engtype": "3D", "utilization": 80},
        {"kind": "gpu_engine", "t": "tick2", "elapsed_s": 1, "instance": "pid_23_luid_0x1_0x2_phys_0_eng_0",
         "engtype": "3D", "utilization": 101},
        {"kind": "gpu_engine", "t": "tick2", "elapsed_s": 1, "instance": "pid_24_luid_0x1_0x2_phys_0_eng_0",
         "engtype": "3D", "utilization": 99},
        {"kind": "gpu_process_memory", "t": "tick1", "elapsed_s": 0, "instance": "pid_23_luid_0x1_0x2_phys_0",
         "dedicated_bytes": 10, "shared_bytes": 20, "committed_bytes": 30},
        {"kind": "gpu_adapter_memory", "t": "tick1", "elapsed_s": 0, "instance": "luid_0x1_0x2_phys_0",
         "dedicated_bytes": 11, "shared_bytes": 21, "committed_bytes": 31},
        {"kind": "gpu_adapter_memory", "t": "tick1", "elapsed_s": 0, "instance": "luid_0x3_0x4_phys_0",
         "dedicated_bytes": 99, "shared_bytes": 99, "committed_bytes": 99},
    ]
    create_run(tmp_path, [{"id": "C1", "wall_ms": 0, "capture": []}], counters=rows)
    counter_summary = summarize(tmp_path)["resources"]
    assert counter_summary["timestamps"] == 2
    assert counter_summary["cpu_sampled_timestamps"] == 1
    assert counter_summary["gpu_engine_sampled_timestamps"] == 1
    assert counter_summary["gpu_engine_invalid_rows"] == 1
    assert counter_summary["gpu_compute_3d_observed_timestamps"] == 1
    assert counter_summary["cpu_percent_of_machine"]["max"] == 50
    assert counter_summary["process_gpu_memory_peak_bytes"]["shared"] == 20
    assert counter_summary["matched_adapter_gpu_memory_peak_bytes"]["shared"] == 21


def test_missing_counter_file_and_modified_case_digest_are_visible(tmp_path):
    create_run(tmp_path, [{"id": "C1", "wall_ms": 1, "capture": []}])
    assert summarize(tmp_path)["resources"]["counter_files_missing"] == 1
    result_path = tmp_path / "results.jsonl"
    result_path.write_bytes(result_path.read_bytes().replace(b'"wall_ms": 1', b'"wall_ms": 9'))
    with pytest.raises(ValueError, match="case artifact digest"):
        summarize(tmp_path)


def test_unterminated_sse_cannot_supply_observed_timing(tmp_path):
    interrupted = capture(5, stream=True, timings={"prompt_ms": 1, "predicted_ms": 2})
    interrupted["raw_response"] = interrupted["raw_response"].removesuffix("data: [DONE]\n\n")
    create_run(tmp_path, [{"id": "C1", "wall_ms": 5, "capture": [interrupted]}])
    summary = summarize(tmp_path)
    assert summary["latency"]["request_wall_ms"]["p50"] == 5
    assert summary["phases"]["prefill"]["duration_ms"]["missing"] == 1
    assert summary["phases"]["decode"]["duration_weighted_tokens_per_second"] is None
    assert summary["workload"]["wire_metadata"] == {"invalid_wire": 1}
