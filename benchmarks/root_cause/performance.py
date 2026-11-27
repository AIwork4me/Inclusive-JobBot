"""Derive diagnostic performance and resources from a historical IJ-0.7 replay.

Usage: python -m benchmarks.root_cause.performance .runtime/ij07-historical/R0-V
Accepts raw run directories and archives containing results and counters as .jsonl.gz.
"""

import argparse
from collections import Counter, defaultdict
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path
import re


STATUSES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
MEMORY_FIELDS = ("dedicated", "shared", "committed")
ADAPTER_INSTANCE = re.compile(r"luid_0x[0-9a-f]+_0x[0-9a-f]+_phys_\d+", re.IGNORECASE)
UNMEASURED = {
    "time_to_first_token": "Raw SSE frames have no individual arrival timestamps.",
    "task_end_to_end_latency": "Historical case wall_ms sums benchmark step requests. There is no enclosing task clock.",
    "host_device_transfers": "Engine utilization counters do not contain transfer bytes or transfer durations.",
    "energy_and_power": "This capture has no sampled power or energy meter.",
    "soak_qualification": "Counter windows contain historical benchmark sessions. No dedicated soak trial was recorded.",
}


def stable_digest(value):
    return sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def available_file(directory, name):
    if type(name) is not str or Path(name).name != name or any(ch in name for ch in "/\\:") or name in {"", ".", ".."}:
        raise ValueError("counter filename must be local to the run directory")
    raw = directory / name
    compressed = directory / (name + ".gz")
    return raw if raw.is_file() else compressed if compressed.is_file() else None


def jsonl_bytes(path):
    opener = gzip.open if path.suffix == ".gz" else Path.open
    with opener(path, "rb") as handle:
        yield from handle


def nonnegative(value):
    return value if (type(value) is int or (type(value) is float and math.isfinite(value))) and value >= 0 else None


def token_count(value):
    return value if type(value) is int and value >= 0 else None


def distribution(values, eligible):
    ordered = sorted(value for value in values if value is not None)
    count = len(ordered)
    return {
        "observations": count, "missing": eligible - count,
        "sum": round(sum(ordered), 6) if count else None,
        "min": ordered[0] if count else None,
        "p50": ordered[math.ceil(count * 0.50) - 1] if count else None,
        "p95": ordered[math.ceil(count * 0.95) - 1] if count else None,
        "max": ordered[-1] if count else None,
    }


def wire_metadata(raw, stream):
    """Read the server's timing and usage objects from JSON or completed SSE."""
    if not isinstance(raw, str):
        return {}, {}, "invalid_wire"
    try:
        if stream:
            frames = raw.replace("\r\n", "\n")
            if not frames.endswith("\n\n"):
                raise ValueError("unterminated SSE event")
            frames = frames[:-2].split("\n\n")
            if any(not frame.startswith("data:") or "\n" in frame for frame in frames):
                raise ValueError("invalid SSE framing")
            data = [frame[5:].lstrip() for frame in frames]
            if data[-1] != "[DONE]" or data.count("[DONE]") != 1:
                raise ValueError("invalid SSE terminator")
            events = [json.loads(event) for event in data[:-1]]
        else:
            events = [json.loads(raw)]
        if not events or any(not isinstance(row, dict) or "error" in row for row in events):
            raise ValueError("invalid response metadata")
        timing = next((row["timings"] for row in reversed(events) if isinstance(row.get("timings"), dict)), {})
        usage = next((row["usage"] for row in reversed(events) if isinstance(row.get("usage"), dict)), {})
        return timing, usage, "observed" if timing or usage else "unavailable"
    except (ValueError, RecursionError):
        return {}, {}, "invalid_wire"


def observed_tokens(source, field):
    values = source.get(field)
    return len(values) if isinstance(values, list) and all(token_count(value) is not None for value in values) else None


def read_turns(row):
    captures = row["capture"]
    for index, capture in enumerate(captures):
        request = capture["request"]
        stream = request.get("stream") is True
        parity = index == 1 and captures[0]["request"].get("stream") is True and not stream and (
            {key: value for key, value in captures[0]["request"].items() if key not in {"stream", "stream_options"}}
            == {key: value for key, value in request.items() if key not in {"stream", "stream_options"}}
        )
        http_status = capture.get("http_status")
        timings, usage, metadata = wire_metadata(capture.get("raw_response"), stream) if http_status == 200 else ({}, {}, "http_error")
        source = capture.get("source_generation")
        if not isinstance(source, dict):
            source = {}
        yield {
            "case_id": row["id"], "turn": index + 1, "server_session": row["server_session"],
            "role": "stream_parity_probe" if parity else "trajectory", "stream": stream,
            "http_status": http_status, "wire_metadata": metadata, "request_wall_ms": nonnegative(capture.get("wall_ms")),
            "prompt_n": token_count(timings.get("prompt_n")), "cache_n": token_count(timings.get("cache_n")),
            "prefill_ms": nonnegative(timings.get("prompt_ms")), "prefill_tps": nonnegative(timings.get("prompt_per_second")),
            "predicted_n": token_count(timings.get("predicted_n")), "decode_ms": nonnegative(timings.get("predicted_ms")),
            "decode_tps": nonnegative(timings.get("predicted_per_second")),
            "wire_prompt": token_count(usage.get("prompt_tokens")), "wire_completion": token_count(usage.get("completion_tokens")),
            "source_prompt": observed_tokens(source, "prompt_token_ids"),
            "source_sampled": observed_tokens(source, "sampled_token_ids"),
            "truncated": source.get("truncated") if type(source.get("truncated")) is bool else None,
        }


def phase_stats(turns, name, token_field):
    duration, rate = f"{name}_ms", f"{name}_tps"
    measured = [turn for turn in turns if turn[duration] is not None and turn[duration] > 0 and turn[rate] is not None]
    seconds = sum(turn[duration] for turn in measured) / 1000
    weighted = sum(turn[duration] * turn[rate] / 1000 for turn in measured)
    return {
        "duration_ms": distribution((turn[duration] for turn in turns), len(turns)),
        "native_reported_token_count": distribution((turn[token_field] for turn in turns), len(turns)),
        "native_rate_observations": len(measured),
        "native_rate_unavailable_or_zero_duration": len(turns) - len(measured),
        "rate_weight_duration_ms": round(seconds * 1000, 6) if measured else None,
        "duration_weighted_tokens_per_second": round(weighted / seconds, 6) if seconds else None,
    }


def capture_cases(directory, run):
    configuration = run["configuration"]
    roster = configuration["case_ids"]
    if stable_digest(configuration) != run["fingerprint"] or len(set(roster)) != len(roster):
        raise ValueError("run configuration digest or case roster differs")
    result_path = available_file(directory, "results.jsonl")
    cases, turns = [], []
    trace_digest = sha256()
    if result_path:
        for index, raw in enumerate(jsonl_bytes(result_path)):
            trace_digest.update(raw)
            row = json.loads(raw)
            if (row.get("run_id") != run["run_id"] or index >= len(roster) or row.get("id") != roster[index]
                    or row.get("status") not in STATUSES[:3] or type(row.get("server_session")) is not int
                    or not 1 <= row["server_session"] <= len(run["sessions"])):
                raise ValueError("result is outside the run identity, case roster or session")
            payload = {key: value for key, value in row.items() if key != "artifact_sha256"}
            if stable_digest(payload) != row.get("artifact_sha256"):
                raise ValueError(f"case artifact digest differs for {row['id']}")
            cases.append({"status": row["status"], "wall_ms": nonnegative(row.get("wall_ms")), "requests": len(row["capture"])})
            turns.extend(read_turns(row))
    sha = trace_digest.hexdigest() if result_path else None
    summary_path = directory / "summary.json"
    summary_status = "NOT_RUN"
    if summary_path.is_file():
        original = read_json(summary_path)
        if original["run_id"] != run["run_id"] or original["cases"] > len(cases):
            raise ValueError("summary refers to another run or missing results")
        if original["cases"] == len(cases):
            if original["result_sha256"] != sha:
                raise ValueError("result archive digest differs from historical summary")
            summary_status = "PASS"
    return cases, turns, sha, summary_status


def memory_peaks(samples):
    return {field: max((row[field] for row in samples), default=None) for field in MEMORY_FIELDS}


def counter_data(directory, sessions):
    ticks = set()
    cpu = {}
    engines = defaultdict(dict)
    process_memory, adapter_memory = {}, {}
    proc_bytes = defaultdict(list)
    invalid_engine_ticks = defaultdict(set)
    counts = Counter()
    coverage = []
    for index, session in enumerate(sessions, 1):
        path = available_file(directory, session["counter_file"]) if session.get("counter_file") else None
        if path is None:
            coverage.append({"session": index, "counter_file_status": "NOT_RUN"})
            continue
        file_digest = sha256()
        elapsed = {}
        local_ticks = set()
        adapter_ids = set()
        pending_adapters = []
        prefix = f"pid_{session['pid']}_"
        for raw in jsonl_bytes(path):
            file_digest.update(raw)
            row = json.loads(raw)
            stamp, kind = row.get("t"), row.get("kind")
            if not isinstance(stamp, str) or not stamp:
                counts["invalid_counter_rows"] += 1
                continue
            tick = index, stamp
            local_ticks.add(tick)
            if (elapsed_s := nonnegative(row.get("elapsed_s"))) is not None:
                elapsed[tick] = elapsed_s
            instance = row.get("instance")
            if kind in {"gpu_engine", "gpu_process_memory", "gpu_adapter_memory"} and not isinstance(instance, str):
                counts["invalid_counter_rows"] += 1
                continue
            if kind in {"gpu_engine", "gpu_process_memory"} and not instance.startswith(prefix):
                counts["foreign_process_rows"] += 1
                continue
            if kind == "process":
                cores = token_count(row.get("logical_processors"))
                balance = nonnegative(row.get("cpu_percent_of_one_core"))
                if cores and balance is not None:
                    cpu[tick] = balance / cores
                for name in ("working_set_private_bytes", "private_bytes", "threads"):
                    if (value := token_count(row.get(name))) is not None:
                        proc_bytes[name].append(value)
            elif kind == "gpu_engine":
                engine_type = row.get("engtype")
                util = nonnegative(row.get("utilization"))
                if util is None or util > 100 or not isinstance(engine_type, str) or not engine_type:
                    counts["gpu_engine_invalid_rows"] += 1
                    if isinstance(engine_type, str):
                        invalid_engine_ticks[engine_type].add(tick)
                    continue
                engines[engine_type].setdefault(tick, {})[instance] = util
            elif kind in {"gpu_process_memory", "gpu_adapter_memory"}:
                memory = {field: token_count(row.get(f"{field}_bytes")) for field in MEMORY_FIELDS}
                adapter = ADAPTER_INSTANCE.search(instance)
                if any(value is None for value in memory.values()) or adapter is None:
                    counts["invalid_counter_rows"] += 1
                    continue
                key = adapter.group(0).lower()
                if kind == "gpu_process_memory":
                    adapter_ids.add(key)
                    process_memory[tick, instance] = memory
                else:
                    pending_adapters.append((tick, key, memory))
            elif kind in {"sample_error", "no_data"}:
                counts[kind] += 1
        for tick, key, memory in pending_adapters:
            if key in adapter_ids:
                adapter_memory[tick, key] = memory
        ticks.update(local_ticks)
        values = sorted(elapsed.values())
        coverage.append({"session": index, "counter_file_status": "PASS" if local_ticks else "NOT_RUN",
                         **{key: session.get(key) for key in ("backend", "gpu", "build", "layers_offloaded", "layers_total", "template_sha256")},
                         "counter_uncompressed_sha256": file_digest.hexdigest(), "timestamps": len(local_ticks),
                         "cpu_sampled_timestamps": len(cpu.keys() & local_ticks),
                         "gpu_engine_sampled_timestamps": len(set().union(*(set(rows) for rows in engines.values())) & local_ticks),
                         "observed_window_seconds": round(values[-1] - values[0], 6) if len(values) >= 2 else None,
                         "sampling_gap_seconds": distribution((right - left for left, right in zip(values, values[1:])),
                                                              max(len(values) - 1, 0))})
    gpu_ticks = set().union(*(set(samples) for samples in engines.values()))
    relevant = set(engines["3D"]) | set(engines["Compute"])
    invalid_busy = invalid_engine_ticks["3D"] | invalid_engine_ticks["Compute"]
    busy_ticks = relevant - invalid_busy
    active = sum(
        sum(sum(engines[name].get(tick, {}).values()) for name in ("3D", "Compute")) >= 5 for tick in busy_ticks
    )
    return {
        "counter_files_present": sum("counter_uncompressed_sha256" in session for session in coverage),
        "counter_files_missing": sum("counter_uncompressed_sha256" not in session for session in coverage),
        "timestamps": len(ticks), "cpu_sampled_timestamps": len(cpu), "gpu_engine_sampled_timestamps": len(gpu_ticks),
        "cpu_and_gpu_sampled_timestamps": len(cpu.keys() & gpu_ticks),
        "gpu_compute_3d_observed_timestamps": len(busy_ticks), "gpu_compute_3d_excluded_timestamps": len(invalid_busy),
        "gpu_engine_invalid_rows": counts["gpu_engine_invalid_rows"], "invalid_counter_rows": counts["invalid_counter_rows"],
        "foreign_process_rows": counts["foreign_process_rows"], "sample_error_rows": counts["sample_error"],
        "no_data_rows": counts["no_data"], "gpu_compute_3d_busy_threshold_percent": 5,
        "gpu_compute_3d_busy_fraction": round(active / len(busy_ticks), 6) if busy_ticks else None,
        "gpu_engine_sum_utilization_percent": {name: distribution((sum(instances.values()) for tick, instances in rows.items()
                                                                    if tick not in invalid_engine_ticks[name]), len(ticks))
                                               for name, rows in sorted(engines.items()) if rows},
        "cpu_percent_of_machine": distribution(cpu.values(), len(ticks)),
        "process_gpu_memory_sampled_timestamps": len({tick for tick, _ in process_memory}),
        "matched_adapter_gpu_memory_sampled_timestamps": len({tick for tick, _ in adapter_memory}),
        "process_gpu_memory_peak_bytes": memory_peaks(process_memory.values()),
        "matched_adapter_gpu_memory_peak_bytes": memory_peaks(adapter_memory.values()),
        "process_peak": {name: max(proc_bytes[name], default=None) for name in ("working_set_private_bytes", "private_bytes", "threads")},
        "sessions": coverage,
    }


def summarize(directory, *, include_turns=False):
    run = read_json(directory / "run.json")
    config = run["configuration"]
    names = [session["counter_file"] for session in run["sessions"] if session.get("counter_file")]
    if (len(names) != len(set(names)) or any(session.get("backend") != config["backend"] for session in run["sessions"])):
        raise ValueError("session backend or counter file identity differs")
    cases, turns, results_sha, integrity = capture_cases(directory, run)
    number = len(turns)
    roster_count = len(config["case_ids"])
    counts = Counter({status: 0 for status in STATUSES})
    counts.update(case["status"] for case in cases)
    counts["NOT_RUN"] = roster_count - len(cases)
    primary = [turn for turn in turns if turn["role"] == "trajectory"]
    paired = {"prompt": ("wire_prompt", "source_prompt"), "completion": ("wire_completion", "source_sampled")}
    mismatches = {}
    for name, (wire_token, source_token) in paired.items():
        pairs = [(turn[wire_token], turn[source_token]) for turn in turns
                 if turn[wire_token] is not None and turn[source_token] is not None]
        mismatches[name] = {"paired_requests": len(pairs), "disagreements": sum(left != right for left, right in pairs)}
    summary = {
        "schema_version": 1, "scope": "IJ07 historical diagnostic; observational timings for the captured configuration",
        "identity": {"arm": config["arm"], "backend": config["backend"], "run_id": run["run_id"],
                     "fingerprint": run["fingerprint"], "engine": config.get("engine"), "git": config.get("git"),
                     "model_sha256": config.get("model_sha256"), "modelscope_revision": config.get("modelscope_revision"),
                     "dataset_sha256": config.get("dataset_sha256"), "results_uncompressed_sha256": results_sha,
                     "result_archive_digest_check": integrity},
        "cases": {"planned": roster_count, "recorded": len(cases), "status_counts": counts,
                  "without_captured_requests": sum(row["requests"] == 0 for row in cases)},
        "workload": {"requests": number, "trajectory_requests": len(primary), "parity_requests": number - len(primary),
                     "streaming_requests": sum(turn["stream"] for turn in turns),
                     "wire_metadata": Counter(turn["wire_metadata"] for turn in turns),
                     "http_status": Counter(str(turn["http_status"]) for turn in turns),
                     "source_truncated": sum(turn["truncated"] is True for turn in turns),
                     "source_truncation_unobserved": sum(turn["truncated"] is None for turn in turns)},
        "latency": {"request_wall_ms": distribution((turn["request_wall_ms"] for turn in turns), number),
                    "trajectory_request_wall_ms": distribution((turn["request_wall_ms"] for turn in primary), len(primary)),
                    "task_recorded_wall_ms": distribution((case["wall_ms"] for case in cases), len(cases))},
        "phases": {"prefill": phase_stats(turns, "prefill", "prompt_n"), "decode": phase_stats(turns, "decode", "predicted_n")},
        "trajectory_phases": {"prefill": phase_stats(primary, "prefill", "prompt_n"),
                              "decode": phase_stats(primary, "decode", "predicted_n")},
        "tokens": {field: distribution((turn[field] for turn in turns), number)
                   for field in ("wire_prompt", "wire_completion", "source_prompt", "source_sampled", "cache_n")},
        "wire_source_token_comparison": mismatches,
        "resources": counter_data(directory, run["sessions"]),
        "unmeasured": {name: {"status": "NOT_RUN", "reason": reason} for name, reason in UNMEASURED.items()},
        "method": {
            "percentiles": "Nearest rank over observed values; missing observations remain counted separately.",
            "request_wall_ms": "CaptureClient chat HTTP request wall time. The separate template-render request is outside this clock.",
            "task_recorded_wall_ms": "Historical runner's sum of step request wall times, including recorded step errors.",
            "phase_throughput": "Duration-weighted average of the native prompt_per_second or predicted_per_second. The native decode rate can exclude the first token.",
            "counter_coverage": "Observed sampler timestamps counted separately by session. Engine utilization is summed across process engines of one type; process and adapter memory peaks are the largest individual observed counter values.",
        },
    }
    if include_turns:
        summary["turns"] = turns
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directories", type=Path, nargs="+")
    parser.add_argument("--include-turns", action="store_true", help="Include per-turn timings and counts without raw prompts")
    args = parser.parse_args()
    summaries = [summarize(path, include_turns=args.include_turns) for path in args.run_directories]
    print(json.dumps(summaries[0] if len(summaries) == 1 else summaries, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
