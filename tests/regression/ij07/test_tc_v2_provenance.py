import json

from benchmarks.tool_calling_v2.holdout.qualify import pid_counter_proof


def test_fixed_fixture_requires_physical_counters_without_generation_observer(tmp_path):
    counter = tmp_path / "gpu.jsonl"
    rows = [
        {"kind": "gpu_engine", "instance": "pid_102_compute", "engtype": "Compute", "utilization": 7},
        {"kind": "gpu_process_memory", "instance": "pid_102_mem", "committed_bytes": 100},
    ]
    counter.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    (tmp_path / "boot.log").write_text("physical launch", encoding="utf-8")
    session = {"pid": 102, "backend": "vulkan", "counter_file": "gpu.jsonl",
               "server_file": "boot.log", "trace_file": "generation.jsonl"}
    assert pid_counter_proof(tmp_path, session)["status"] == "BLOCKED"
    fixture = pid_counter_proof(tmp_path, {**session, "phase": "fixed_fixture"})
    assert fixture["status"] == "PASS"
    assert fixture["source_capture"] == "NOT_RUN"
