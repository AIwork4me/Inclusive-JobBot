#!/usr/bin/env python3
"""Render the two completed frozen benchmark runs to Markdown."""

from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import pathlib
import re

from run_benchmark import DATASET_DIR, DATASETS, parse_tool_arguments, read_checkpoint, summarize
from server_identity import ROOT, read_json, sha256_of


def load_arm(path: pathlib.Path, backend: str, dataset_sha256: str, ids: list[str]) -> tuple[dict, dict, list[dict]]:
  run = read_json(path / "run.json")
  metrics = read_json(path / "metrics.json")
  rows = list(read_checkpoint(path / "results.jsonl", ids, run=run).values())
  if (
      run["dataset"] != "test" or run["dataset_sha256"] != dataset_sha256
      or run["server"]["backend"] != backend or run["selected_case_ids"] != ids or len(rows) != len(ids)
      or metrics["run_id"] != run["run_id"] or any(row.get("run_id") != run["run_id"] for row in rows)
  ):
    raise ValueError(f"{backend} evidence is incomplete or has mismatched identities")
  if any(metrics[key] != expected for key, expected in summarize(rows).items()):
    raise ValueError(f"{backend} metrics differ from the per-case results")
  return run, metrics, rows


def audit_ticket_arguments(cases: list[dict], rows: list[dict]) -> tuple[int, list[str]]:
  """Audit the later write arguments independently of the frozen scorer."""
  checked = 0
  mismatched = []
  for case, row in zip(cases, rows):
    if not row["pass"] or case["expected"].get("sequence") != ["get_customer", "create_ticket"]:
      continue
    priority_match = re.search(r'优先级为“([低中高])”', case["messages"][0]["content"])
    if priority_match is None:
      raise ValueError(f"Missing priority in frozen ticket case {case['id']}")
    priority = priority_match[1]
    want = {"subject": "回访预约", "priority": priority, "tags": ["回访", f"{priority}优先级"]}
    created = [
        call["arguments"]
        for step in row["steps"] for call in step.get("tool_calls", [])
        if call["name"] == "create_ticket" and (call.get("tool_result") or {}).get("status") == "created"
    ]
    checked += 1
    if len(created) != 1 or created[0] != want:
      mismatched.append(case["id"])
  return checked, mismatched


def audit_argument_json(rows: list[dict]) -> tuple[int, list[str]]:
  checked = 0
  rejected = []
  for row in rows:
    for step in row["steps"]:
      for call in step.get("tool_calls", []):
        if call["arguments"] is None:
          continue
        checked += 1
        try:
          parse_tool_arguments(call["arguments_raw"])
        except ValueError:
          rejected.append(row["id"])
  return checked, rejected


def gpu_summary(path: pathlib.Path, run: dict, finished_utc: str) -> dict:
  def read_rows():
    with path.open(encoding="utf-8") as handle:
      for line in handle:
        yield json.loads(line)

  peak_utilization: dict[str, float] = {}
  peak_committed = 0
  rejected_samples = 0
  sessions = [
      (dt.datetime.fromisoformat(session["runner_started_utc"]), session["pid"])
      for session in run["sessions"]
  ]
  start, end = sessions[0][0], dt.datetime.fromisoformat(finished_utc) + dt.timedelta(seconds=1)
  verified_sessions = set()
  for stamp, group in itertools.groupby(read_rows(), key=lambda row: row["t"]):
    observed = dt.datetime.fromisoformat(stamp)
    if not start <= observed < end:
      continue
    session_index = max(i for i, (began, _) in enumerate(sessions) if began <= observed)
    pid = sessions[session_index][1]
    rows = list(group)
    memory = [
        row["committed_bytes"] for row in rows
        if row["kind"] == "gpu_process_memory" and row["instance"].startswith(f"pid_{pid}_")
    ]
    if not memory or max(memory) == 0:
      continue
    peak_committed = max(peak_committed, max(memory))
    for row in rows:
      if row["kind"] == "gpu_engine":
        engine = row["engtype"]
        utilization = row["utilization"]
        if not 0 <= utilization <= 100:
          rejected_samples += 1
          continue
        peak_utilization[engine] = max(peak_utilization.get(engine, 0), utilization)
        if engine in ("Compute", "3D") and utilization > 0:
          verified_sessions.add(session_index)
  if verified_sessions != set(range(len(sessions))):
    raise ValueError("Missing matching process GPU memory and engine activity for a recorded server session")
  return {
      "peak_utilization": peak_utilization, "peak_committed_mib": round(peak_committed / 2**20, 1),
      "out_of_range_samples": rejected_samples,
  }


def format_percent(value: float | None) -> str:
  return "N/A" if value is None else f"{value:.2%}"


def render(paths: list[pathlib.Path], fixture_paths: list[pathlib.Path] | None = None) -> str:
  dataset = DATASET_DIR / DATASETS["test"]
  digest = sha256_of(dataset)
  manifest = read_json(DATASET_DIR / "dataset.manifest.json")
  cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines()]
  ids = [case["id"] for case in cases]
  if len(ids) != 500 or not any(item["path"] == dataset.name and item["sha256"] == digest for item in manifest["files"]):
    raise ValueError("The test data differs from the frozen 500-case manifest")
  (vulkan, vm, vr), (rocm, rm, rr) = [
      load_arm(path, backend, digest, ids) for path, backend in zip(paths, ("vulkan", "rocm"))
  ]
  common_keys = (
      "context_length", "parallel_slots", "modelscope_revision", "model_sha256",
      "chat_template_sha256", "launch_arguments_sha256", "gpu_layers", "reasoning_format",
  )
  q8 = read_json(ROOT / "configs/llama_cpp/launch.json")["models"]["q8"]
  engine_commit = read_json(ROOT / "configs/llama_cpp/engine.json")["build_commit"]
  if (
      any(vulkan["server"][key] != rocm["server"][key] for key in common_keys)
      or any(arm["engine"]["build_commit"] != engine_commit for arm in (vulkan, rocm))
      or any(
          arm["server"]["model_file"] != q8 or arm["server"]["gpu"]["architecture"] != "gfx1151"
          or not arm["server"]["layers_offloaded"]
          for arm in (vulkan, rocm)
      )
      or vulkan["code_sha256"] != rocm["code_sha256"]
      or vulkan["decode"] != rocm["decode"]
  ):
    raise ValueError("The two arms do not share the same model, build, harness and decoding configuration")

  lines = [
      "# IJ-0 frozen tool-calling benchmark",
      "",
      "Each arm ran the 500 frozen cases with MiniCPM5-2B Q8_0 on the physical Radeon GPU.",
      "Tools were deterministic simulators operating on synthetic data.",
      "The [IJ-0 acceptance thresholds](../docs/decisions/ADR-002-IJ0-TOOL-CALLING-ACCEPTANCE.md) were set "
      "after this benchmark began. The table is a diagnostic baseline.",
      "",
      f"- Dataset SHA256 `{digest}`",
      f"- llama.cpp `{vulkan['engine']['build_tag']}` at `{vulkan['engine']['build_commit']}`",
      f"- ModelScope revision `{vulkan['server']['modelscope_revision']}`",
      f"- Model SHA256 `{vulkan['server']['model_sha256']}`",
  ]
  for label, path, run, metrics in zip(("Vulkan", "ROCm"), paths, (vulkan, rocm), (vm, rm)):
    gpu = gpu_summary(path / "gpu.jsonl", run, metrics["finished_utc"])
    utilization = ", ".join(f"{name} {value:g}%" for name, value in sorted(gpu["peak_utilization"].items()) if value)
    lines.append(
        f"- {label} run `{run['run_id']}` at `{run['git']['commit']}` with {utilization} peak "
        f"engine activity and {gpu['peak_committed_mib']:g} MiB peak process GPU memory."
    )
    if gpu["out_of_range_samples"]:
      lines.append(f"  Excluded {gpu['out_of_range_samples']} out-of-range engine readings from the peak. Raw readings are preserved.")

  lines.extend(["", "| Metric | Vulkan | ROCm |", "|---|---:|---:|"])
  for label, key in (
      ("Frozen evaluator pass rate", "real_model_tool_calling_success"),
      ("Expected first-turn arguments correct", "tool_argument_accuracy"),
      ("Invalid tool calls", "invalid_tool_call_rate"),
  ):
    lines.append(f"| {label} | {format_percent(vm[key])} | {format_percent(rm[key])} |")
  for label, key in (
      ("Cases passed", "pass"), ("Cases failed", "fail"), ("Tool calls requested", "tool_calls_requested"),
      ("Invalid tool calls (count)", "malformed_calls"), ("Forbidden tool attempts", "forbidden_attempts"),
      ("Unauthorized tool executions", "unauthorized_executed"), ("Request errors", "request_errors"),
  ):
    lines.append(f"| {label} | {vm[key]} | {rm[key]} |")

  lines.extend(["", "| Category | Vulkan | ROCm |", "|---|---:|---:|"])
  for name, left in vm["by_category"].items():
    right = rm["by_category"][name]
    lines.append(f"| {name} | {left['pass']}/{left['cases']} | {right['pass']}/{right['cases']} |")
  lines.extend(["", "| Streaming comparison | Vulkan | ROCm |", "|---|---:|---:|"])
  parity = []
  for metrics in (vm, rm):
    stream = metrics["by_category"]["streaming_tool_call"]
    parity.append(f"{stream['stream_non_stream_identical']}/{stream['stream_non_stream_checked']}")
  lines.append(f"| Identical tool names and raw argument strings | {parity[0]} | {parity[1]} |")

  if fixture_paths:
    fixture_digest = sha256_of(DATASET_DIR.parent / "fixtures/minicpm5_parser_fixtures.json")
    lines.extend(["", "## Native parser fixtures", "", f"Fixture SHA256 `{fixture_digest}`", ""])
    for backend, path, arm in zip(("Vulkan", "ROCm"), fixture_paths, (vulkan, rocm)):
      fixture = read_json(path)
      if (
          fixture["fixture_sha256"] != fixture_digest
          or fixture["engine"] != arm["engine"] or fixture["server"] != arm["server"]
      ):
        raise ValueError(f"{backend} parser fixture identities do not match its benchmark")
      counts = ", ".join(f"{count} {status}" for status, count in sorted(fixture["counts"].items()))
      lines.append(f"- {backend} recorded {counts} in `{fixture['run_id']}`.")
      for row in fixture["results"]:
        if row["status"] != "PASS":
          lines.append(f"  - `{row['id']}` {row['status']}. {'. '.join(row['failures'])}.")
    lines.extend([
        "",
        "Assistant continuation supplies the fixed text. Successful replies carry a token trace showing that",
        "the model sampled only EOS. Known native parser rejections are recorded as such.",
    ])
  lines.extend([
      "",
      "## Scoring notes",
      "",
      "- The frozen two-order cases require a single first-turn call for a randomly chosen order.",
      "  A parallel lookup of both independent orders can fail this expectation while returning the requested facts.",
      "- Argument accuracy covers the expected first-turn arguments present in the frozen definitions,",
      "  including the loss of credit for missing calls.",
      "- The simulator enforces an allowlist and validates arguments. These runs measure protections in",
      "  the benchmark host with synthetic data.",
      "- The frozen recovery score penalizes schema rejection of the unsupported warehouse even when",
      "  the model subsequently lists supported warehouses. Report recovery and schema conformance separately.",
  ])
  lines.extend([
      "",
      "### Ticket argument trace audit (v1)",
      "",
      "The frozen scorer checks the first lookup, tool names and the final ticket ID for these cases.",
      "This separate audit checks the later ticket subject, priority and tags against the fixed prompt.",
      "",
  ])
  for backend, rows in zip(("Vulkan", "ROCm"), (vr, rr)):
    checked, mismatched = audit_ticket_arguments(cases, rows)
    lines.append(f"- {backend}: {len(mismatched)}/{checked} frozen passes had mismatched ticket arguments.")
    if mismatched:
      lines.append(f"  Case IDs `{', '.join(mismatched)}`.")
  lines.extend(["", "### Strict JSON trace audit (v1)", ""])
  for backend, rows in zip(("Vulkan", "ROCm"), (vr, rr)):
    checked, rejected = audit_argument_json(rows)
    lines.append(f"- {backend} rejected {len(rejected)}/{checked} previously decoded argument objects under strict JSON rules.")
    if rejected:
      lines.append(f"  Case IDs `{', '.join(sorted(set(rejected)))}`.")
  lines.extend(["", "## Evidence", ""])
  for backend, path in zip(("Vulkan", "ROCm"), paths):
    if path.resolve().is_relative_to(ROOT):
      relative = path.resolve().relative_to(ROOT).as_posix()
      lines.append(f"- {backend} run metadata, case traces, metrics and counters are in `{relative}/`.")
  return "\n".join(lines) + "\n"


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("vulkan", type=pathlib.Path)
  parser.add_argument("rocm", type=pathlib.Path)
  parser.add_argument("--fixtures", type=pathlib.Path, nargs=2, metavar=("VULKAN_JSON", "ROCM_JSON"))
  parser.add_argument("--output", type=pathlib.Path, required=True)
  args = parser.parse_args()
  document = render([args.vulkan, args.rocm], args.fixtures)
  with args.output.open("x", encoding="utf-8", newline="\n") as handle:
    handle.write(document)


if __name__ == "__main__":
  main()
