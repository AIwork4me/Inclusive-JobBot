"""Summaries of the counter rows written by scripts/windows/sample_gpu_counters.ps1."""

from __future__ import annotations

import collections
import pathlib
import re

MIB = 1024 * 1024


def load(path: pathlib.Path) -> list[dict]:
  import json

  rows = []
  with path.open(encoding="utf-8") as handle:
    for line in handle:
      line = line.strip()
      if line:
        rows.append(json.loads(line))
  return rows


def _mean(values: list[float]) -> float:
  return sum(values) / len(values) if values else 0.0


def summarize(rows: list[dict]) -> dict:
  """Aggregate one arm's counter rows.

  Engine utilization is summed per timestamp within an engine type, because one
  type can span several engine instances. "Busy" means the 3D and Compute
  engines together were at or above 5 percent at that timestamp.
  """
  by_type: dict[str, dict[float, float]] = collections.defaultdict(lambda: collections.defaultdict(float))
  timestamps = {row["t"] for row in rows}
  process_luids: set[str] = set()
  process_memory = [row for row in rows if row["kind"] == "gpu_process_memory"]
  adapter_memory = [row for row in rows if row["kind"] == "gpu_adapter_memory"]
  processes = [row for row in rows if row["kind"] == "process"]
  errors = [row for row in rows if row["kind"] == "sample_error"]

  # The perf provider occasionally returns values outside 0..100, from rounding
  # (101) up to uninitialised garbage. Those samples are excluded from the
  # statistics and counted, never dropped silently.
  invalid = 0
  for row in rows:
    if row["kind"] == "gpu_engine":
      if 0.0 <= row["utilization"] <= 100.0:
        by_type[row["engtype"]][row["t"]] += row["utilization"]
      else:
        invalid += 1
    elif row["kind"] == "gpu_process_memory":
      match = re.search(r"luid_[0-9A-Fa-fx_]+", row.get("instance", ""))
      if match:
        process_luids.add(match.group(0))

  def stats(series: list[float]) -> dict:
    ordered = sorted(series)
    if not ordered:
      return {"samples": 0, "median_percent": 0.0, "p95_percent": 0.0, "max_percent": 0.0, "mean_percent": 0.0}
    return {
        "samples": len(ordered),
        "median_percent": round(_mean(ordered[len(ordered) // 2 : len(ordered) // 2 + 1]), 2),
        "p95_percent": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 2),
        "max_percent": round(ordered[-1], 2),
        "mean_percent": round(_mean(ordered), 2),
    }

  engines = {engine_type: stats(list(per_timestamp.values())) for engine_type, per_timestamp in sorted(by_type.items())}
  # Busy = the 3D and Compute engines together were at or above the threshold.
  # Timestamps with an invalid sample in those engines are excluded and counted.
  busy = []
  excluded = 0
  for stamp in timestamps:
    if any(
        not 0.0 <= row["utilization"] <= 100.0
        for row in rows
        if row["kind"] == "gpu_engine" and row["t"] == stamp and row["engtype"] in ("3D", "Compute")
    ):
      excluded += 1
      continue
    busy.append(sum(by_type[engine_type].get(stamp, 0.0) for engine_type in ("3D", "Compute")))
  busy_threshold = 5.0

  adapter = None
  matching = [row for row in adapter_memory if any(row["instance"].startswith(luid) for luid in process_luids)]
  if matching:
    adapter = {
        "luid": sorted(process_luids),
        "max_dedicated_mib": round(max(r["dedicated_bytes"] for r in matching) / MIB, 1),
        "max_shared_mib": round(max(r["shared_bytes"] for r in matching) / MIB, 1),
    }

  cpu = []
  for row in processes:
    cores = row.get("logical_processors") or 1
    cpu.append(row["cpu_percent_of_one_core"] / cores)

  return {
      "sample_timestamps": len(timestamps),
      "duration_seconds": round(max((r["elapsed_s"] for r in rows), default=0.0), 2),
      "counter_quality": "OK" if invalid == 0 else "INVALID_SAMPLES_PRESENT",
      "invalid_utilization_samples": invalid,
      "engine_utilization": engines,
      "gpu_busy_fraction": round(sum(1 for value in busy if value >= busy_threshold) / len(busy), 3) if busy else 0.0,
      "gpu_busy_threshold_percent": busy_threshold,
      "timestamps_excluded_from_busy": excluded,
      "process_gpu_memory_max_mib": (
          {
              "dedicated": round(max(r["dedicated_bytes"] for r in process_memory) / MIB, 1),
              "shared": round(max(r["shared_bytes"] for r in process_memory) / MIB, 1),
          }
          if process_memory
          else None
      ),
      "adapter_gpu_memory_max_mib": adapter,
      "process": (
          {
              "cpu_mean_percent_of_machine": round(_mean(cpu), 2),
              "cpu_max_percent_of_machine": round(max(cpu), 2),
              "working_set_private_max_mib": round(max(r["working_set_private_bytes"] for r in processes) / MIB, 1),
              "private_bytes_max_mib": round(max(r["private_bytes"] for r in processes) / MIB, 1),
              "threads_max": max(r["threads"] for r in processes),
          }
          if processes
          else None
      ),
      "sample_error_count": len(errors),
  }
