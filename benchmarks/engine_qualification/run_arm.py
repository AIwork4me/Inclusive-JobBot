#!/usr/bin/env python3
"""Run the frozen engine-qualification workload against llama-server arms.

For each arm the script starts the pinned server through the verified launch
script, waits until the GPU counter sampler is live, sends the frozen
workload, then stops the sampler and the server. It writes per-request results
(``results.jsonl``), a ``summary.json``, the launch evidence (``launch.json``)
and the counter rows (``counters.jsonl``) under ``<output-root>/<arm>/``.

Arms (ECO-01 IJ-0.5):

    A  llama.cpp CPU        F16        E  llama.cpp CPU        Q8_0
    B  llama.cpp Vulkan     F16        F-vulkan  Vulkan Q4_K_M
    C  llama.cpp Vulkan     Q8_0       F-rocm    ROCm/HIP Q4_K_M
    D  llama.cpp ROCm/HIP   Q8_0

Arm G (Ollama) is optional and is not run by this script.

Usage:
    python benchmarks/engine_qualification/run_arm.py --arms A,B,C,D,E
    python benchmarks/engine_qualification/run_arm.py --compare-only
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import counters  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
WORKLOAD = HERE / "workload.json"
STATE_DIR = ROOT / ".runtime" / "llama-server"
LOG_DIR = ROOT / ".runtime" / "logs"

ARMS = {
    "A": {"backend": "cpu", "model": "f16", "label": "llama.cpp CPU, F16", "gpu": False},
    "B": {"backend": "vulkan", "model": "f16", "label": "llama.cpp GPU Vulkan, F16", "gpu": True},
    "C": {"backend": "vulkan", "model": "q8", "label": "llama.cpp GPU Vulkan, Q8_0", "gpu": True},
    "D": {"backend": "rocm", "model": "q8", "label": "llama.cpp GPU ROCm/HIP, Q8_0", "gpu": True},
    "E": {"backend": "cpu", "model": "q8", "label": "llama.cpp CPU, Q8_0", "gpu": False},
    "F-vulkan": {"backend": "vulkan", "model": "q4", "label": "llama.cpp GPU Vulkan, Q4_K_M", "gpu": True},
    "F-rocm": {"backend": "rocm", "model": "q4", "label": "llama.cpp GPU ROCm/HIP, Q4_K_M", "gpu": True},
}
# Same weights, different backend: the pair isolates the backend difference.
COMPARISONS = [("A", "B"), ("E", "C"), ("E", "D"), ("C", "D"), ("C", "F-vulkan"), ("D", "F-rocm")]


def utc_now() -> str:
  return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def powershell(script: str, args: list[str], log_name: str | None = None, timeout: int = 3600) -> int:
  command = [
      "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
      str(ROOT / "scripts" / "windows" / script), *args,
  ]
  # Output goes to a file, never to a pipe: the server inherits the parent's
  # handles and a pipe reader would wait forever for end-of-file.
  log = open(LOG_DIR / (log_name or f"{script}.out"), "wb") if log_name else subprocess.DEVNULL
  try:
    return subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=timeout).returncode
  finally:
    if log is not subprocess.DEVNULL:
      log.close()


def start_server(arm_id: str, arm: dict, port: int, context_length: int) -> dict:
  code = powershell(
      "start_llama_server.ps1",
      ["-Backend", arm["backend"], "-Model", arm["model"], "-Port", str(port), "-ContextLength", str(context_length),
       # 0 for CPU arms: a CPU-only build would otherwise log "offloaded N/N layers".
       "-GpuLayers", "99" if arm["gpu"] else "0"],
      log_name=f"start-{arm_id}.out",
  )
  state_path = STATE_DIR / "server.json"
  if code != 0 or not state_path.exists():
    raise RuntimeError(f"launch of arm {arm_id} failed with exit code {code}; see .runtime/logs/start-{arm_id}.out")
  return json.loads(state_path.read_text(encoding="utf-8"))


def start_sampler(pid: int, output: pathlib.Path, stop_file: pathlib.Path) -> subprocess.Popen:
  output.parent.mkdir(parents=True, exist_ok=True)
  ready = pathlib.Path(str(stop_file) + ".ready")
  for stale in (stop_file, ready):
    if stale.exists():
      stale.unlink()
  process = subprocess.Popen(
      [
          "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
          str(ROOT / "scripts" / "windows" / "sample_gpu_counters.ps1"),
          "-TargetProcessId", str(pid), "-OutputPath", str(output), "-StopFile", str(stop_file),
      ],
      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
  )
  deadline = time.time() + 120
  while not ready.exists():
    if process.poll() is not None:
      raise RuntimeError("the counter sampler exited before it was ready")
    if time.time() > deadline:
      raise RuntimeError("the counter sampler did not become ready within 120 seconds")
    time.sleep(0.25)
  return process


def stop_sampler(process: subprocess.Popen, stop_file: pathlib.Path) -> None:
  stop_file.touch()
  try:
    process.wait(timeout=30)
  except subprocess.TimeoutExpired:
    process.kill()


def stream_chat(base_url: str, model: str, messages: list[dict], max_tokens: int, thinking: bool, timeout: int = 1800) -> dict:
  body = {
      "model": model,
      "messages": messages,
      "stream": True,
      "temperature": 0,
      "max_tokens": max_tokens,
      "stream_options": {"include_usage": True},
      "chat_template_kwargs": {"enable_thinking": thinking},
  }
  request = urllib.request.Request(
      base_url + "/v1/chat/completions",
      data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
      method="POST",
      headers={"Content-Type": "application/json"},
  )
  started = time.perf_counter()
  first_token = None
  text: list[str] = []
  reasoning: list[str] = []
  usage = timings = finish_reason = None
  chunks = 0
  try:
    with urllib.request.urlopen(request, timeout=timeout) as response:
      for raw_line in response:
        line = raw_line.decode("utf-8").strip()
        if not line.startswith("data:"):
          continue
        payload = line[5:].strip()
        if payload == "[DONE]":
          break
        chunk = json.loads(payload)
        chunks += 1
        if chunk.get("usage"):
          usage = chunk["usage"]
        if chunk.get("timings"):
          timings = chunk["timings"]
        for choice in chunk.get("choices") or []:
          if choice.get("finish_reason"):
            finish_reason = choice["finish_reason"]
          delta = choice.get("delta") or {}
          if delta.get("content"):
            if first_token is None:
              first_token = time.perf_counter()
            text.append(delta["content"])
          if delta.get("reasoning_content"):
            if first_token is None:
              first_token = time.perf_counter()
            reasoning.append(delta["reasoning_content"])
  except (urllib.error.URLError, OSError, ValueError) as error:
    return {
        "error": f"{type(error).__name__}: {error}",
        "wall_ms": int((time.perf_counter() - started) * 1000),
    }
  ended = time.perf_counter()
  return {
      "content": "".join(text),
      "reasoning": "".join(reasoning),
      "ttft_ms": None if first_token is None else int((first_token - started) * 1000),
      "wall_ms": int((ended - started) * 1000),
      "chunks": chunks,
      "usage": usage,
      "timings": timings,
      "finish_reason": finish_reason,
  }


def normalize(text: str) -> str:
  value = unicodedata.normalize("NFKC", text).strip()
  value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.DOTALL).strip()
  value = re.sub(r"[。．.]+$", "", value)
  return re.sub(r"\s+", "", value).lower()


def json_object_of(text: str):
  match = re.search(r"\{.*\}", text, re.DOTALL)
  if not match:
    return None
  try:
    value = json.loads(match.group(0))
  except json.JSONDecodeError:
    return None
  return value if isinstance(value, dict) else None


def grade(item: dict, content: str) -> tuple[bool, str]:
  """Returns (correct, reason)."""
  if "json_expect" in item or "expect_keys" in item:
    expected = item.get("json_expect") or item.get("expect_values") or {}
    expected_keys = item.get("expect_keys") or sorted(expected)
    parsed = json_object_of(content)
    if parsed is None:
      return False, "not a JSON object"
    missing = [key for key in expected_keys if key not in parsed]
    if missing:
      return False, f"missing keys {missing}"
    for key, want in expected.items():
      got = parsed.get(key)
      got_text = "null" if got is None else str(got)
      if isinstance(want, str):
        want = unicodedata.normalize("NFKC", want)
      if normalize(got_text) != normalize(str(want)):
        return False, f"{key}: expected {want!r}, got {got!r}"
    return True, "ok"
  wanted = [normalize(option) for option in item["expected"]]
  return normalize(content) in wanted, "ok" if normalize(content) in wanted else f"got {content.strip()[:80]!r}"


def check_manifest() -> str:
  manifest = json.loads((WORKLOAD.parent / "workload.json.manifest.json").read_text(encoding="utf-8"))
  digest = hashlib.sha256(WORKLOAD.read_bytes()).hexdigest()
  frozen = {item["path"]: item["sha256"] for item in manifest["files"]}
  if frozen.get(WORKLOAD.name) != digest:
    raise SystemExit("workload.json does not match its frozen manifest; rerun scripts/tools/freeze_dataset.py")
  return digest


def run_arm(arm_id: str, port: int, context_length: int, output_root: pathlib.Path, workload_sha256: str) -> dict:
  arm = ARMS[arm_id]
  workload = json.loads(WORKLOAD.read_text(encoding="utf-8"))
  arm_dir = output_root / arm_id
  arm_dir.mkdir(parents=True, exist_ok=True)
  state = start_server(arm_id, arm, port, context_length)
  base_url = f"http://{state['host']}:{state['port']}"
  model_alias = state["arguments"][state["arguments"].index("-a") + 1]
  results_path = arm_dir / "results.jsonl"
  results_handle = results_path.open("w", encoding="utf-8", newline="\n")
  stop_file = ROOT / ".runtime" / f"stop-sampler-{arm_id}"
  sampler = None
  started_utc = utc_now()
  try:
    if arm["gpu"] and not state.get("layers_offloaded"):
      raise RuntimeError("GPU arm started without any layer offloaded")
    if arm["gpu"] and not state.get("gpu_backend_libraries_present", True):
      raise RuntimeError("GPU arm started from a build without GPU backend libraries")
    probe_messages = [{"role": "user", "content": "用一句话说明什么是采购订单。"}]

    cold = stream_chat(base_url, model_alias, probe_messages, 48, False)

    sampler = start_sampler(state["pid"], arm_dir / "counters.jsonl", stop_file)
    stream_chat(base_url, model_alias, probe_messages, 48, False)  # warm-up, not recorded
    records = []
    for section in ("chat", "structured", "tasks"):
      for item in workload[section]:
        if section == "chat":
          messages, thinking, max_tokens = item["messages"], item.get("thinking", False), item["max_tokens"]
        else:
          messages, thinking, max_tokens = [{"role": "user", "content": item["prompt"]}], item.get("thinking", False), item["max_tokens"]
        reply = stream_chat(base_url, model_alias, messages, max_tokens, thinking)
        content = reply.get("content", "")
        if section == "chat":
          # Thinking items are judged on "produced output"; a think block that
          # runs out of budget is reported as truncated, not as an engine failure.
          produced = bool((content + reply.get("reasoning", "")).strip())
          ok = produced
          reason = "ok" if produced else "empty"
        else:
          ok, reason = grade(item, content) if "error" not in reply else (False, reply["error"])
        timings = reply.get("timings") or {}
        record = {
            "arm": arm_id,
            "section": section,
            "id": item["id"],
            "thinking": thinking,
            "ok": ok,
            "reason": reason,
            "content": content,
            "reasoning": reply.get("reasoning", ""),
            "ttft_ms": reply.get("ttft_ms"),
            "wall_ms": reply.get("wall_ms"),
            "finish_reason": reply.get("finish_reason"),
            "truncated": reply.get("finish_reason") == "length",
            "usage": reply.get("usage"),
            "prompt_n": timings.get("prompt_n"),
            "prompt_ms": timings.get("prompt_ms"),
            "predicted_n": timings.get("predicted_n"),
            "predicted_ms": timings.get("predicted_ms"),
            "error": reply.get("error"),
        }
        records.append(record)
        results_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        results_handle.flush()
        print(f"{arm_id} {section} {item['id']} {'PASS' if ok else 'FAIL'} {reply.get('wall_ms')} ms")
  finally:
    results_handle.close()
    if sampler is not None:
      stop_sampler(sampler, stop_file)
    powershell("stop_llama_server.ps1", [], log_name=f"stop-{arm_id}.out")

  rows = counters.load(arm_dir / "counters.jsonl") if (arm_dir / "counters.jsonl").exists() else []
  sections = {}
  for section in ("chat", "structured", "tasks"):
    subset = [r for r in records if r["section"] == section]
    sections[section] = {
        "count": len(subset),
        "pass": sum(1 for r in subset if r["ok"]),
        "pass_rate": round(sum(1 for r in subset if r["ok"]) / len(subset), 4) if subset else None,
        "failures": [{"id": r["id"], "reason": r["reason"]} for r in subset if not r["ok"]],
        "truncated_by_token_budget": sorted(r["id"] for r in subset if r["truncated"]),
    }
  measured = [r for r in records if r["predicted_n"] and r["predicted_ms"] and not r["error"]]
  wall = sorted(r["wall_ms"] for r in records if not r["error"])
  ttft = sorted(r["ttft_ms"] for r in measured if r["ttft_ms"] is not None)
  summary = {
      "schema_version": 1,
      "arm": arm_id,
      "label": arm["label"],
      "backend": arm["backend"],
      "model": arm["model"],
      "context_length": context_length,
      "gpu_arm": arm["gpu"],
      "started_utc": started_utc,
      "finished_utc": utc_now(),
      "workload_sha256": workload_sha256,
      "request_count": len(records),
      "request_errors": sum(1 for r in records if r["error"]),
      "execution_status": "PASS" if not any(r["error"] for r in records) else "FAIL",
      "cold_first_request": {key: cold.get(key) for key in ("wall_ms", "ttft_ms", "finish_reason", "error")},
      "sections": sections,
      "performance": {
          "prompt_tokens": sum(r["prompt_n"] for r in measured),
          "predicted_tokens": sum(r["predicted_n"] for r in measured),
          "prompt_ms_total": round(sum(r["prompt_ms"] for r in measured), 1),
          "predicted_ms_total": round(sum(r["predicted_ms"] for r in measured), 1),
          "prompt_tokens_per_second": round(sum(r["prompt_n"] for r in measured) / (sum(r["prompt_ms"] for r in measured) / 1000), 2) if measured else None,
          "decode_tokens_per_second": round(sum(r["predicted_n"] for r in measured) / (sum(r["predicted_ms"] for r in measured) / 1000), 2) if measured else None,
          "ttft_ms_mean": round(sum(ttft) / len(ttft)) if ttft else None,
          "ttft_ms_p95": ttft[min(len(ttft) - 1, int(len(ttft) * 0.95))] if ttft else None,
          "wall_ms_p50": wall[len(wall) // 2] if wall else None,
          "wall_ms_p95": wall[min(len(wall) - 1, int(len(wall) * 0.95))] if wall else None,
      },
      "counters": counters.summarize(rows) if rows else None,
  }
  (arm_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
  launch = {key: state.get(key) for key in (
      "backend", "model", "context_length", "gpu_layers", "layers_offloaded", "layers_total",
      "offload_log_line", "allocation_log_lines", "startup_seconds", "owns_port", "port",
      "gpu_backend_libraries_present",
  )}
  launch["arguments"] = [
      re.sub(r"(?i)Users[\\/]+[^\\/\"'\s]+", "Users/<REDACTED>", arg) for arg in state["arguments"]
  ]
  launch["state_status"] = state.get("status")
  (arm_dir / "launch.json").write_text(json.dumps(launch, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
  print(f"{arm_id}: execution {summary['execution_status']}, tasks {sections['tasks']['pass']}/{sections['tasks']['count']}, "
        f"structured {sections['structured']['pass']}/{sections['structured']['count']}, "
        f"decode {summary['performance']['decode_tokens_per_second']} tok/s")
  return summary


def write_comparison(output_root: pathlib.Path) -> None:
  comparison = {"schema_version": 1, "generated_utc": utc_now(), "method": "greedy decoding, same frozen workload; text equality is checked after normalisation", "pairs": []}
  for cpu_arm, gpu_arm in COMPARISONS:
    cpu_dir, gpu_dir = output_root / cpu_arm, output_root / gpu_arm
    if not (cpu_dir / "results.jsonl").exists() or not (gpu_dir / "results.jsonl").exists():
      continue

    def load(directory: pathlib.Path) -> dict[str, dict]:
      return {json.loads(line)["id"]: json.loads(line) for line in (directory / "results.jsonl").read_text(encoding="utf-8").splitlines() if line}

    cpu, gpu = load(cpu_dir), load(gpu_dir)
    pair = {"cpu_arm": cpu_arm, "gpu_arm": gpu_arm, "weights": ARMS[cpu_arm]["model"], "sections": {}}
    for section in ("chat", "structured", "tasks"):
      ids = [key for key in cpu if cpu[key]["section"] == section]
      identical = [key for key in ids if normalize(cpu[key]["content"]) == normalize(gpu[key]["content"])]
      cpu_pass = [key for key in ids if cpu[key]["ok"]]
      gpu_pass = [key for key in ids if gpu[key]["ok"]]
      pair["sections"][section] = {
          "count": len(ids),
          "identical_text": len(identical),
          "identical_text_rate": round(len(identical) / len(ids), 4) if ids else None,
          "cpu_pass": len(cpu_pass),
          "gpu_pass": len(gpu_pass),
          "pass_only_on_cpu": sorted(set(cpu_pass) - set(gpu_pass)),
          "pass_only_on_gpu": sorted(set(gpu_pass) - set(cpu_pass)),
          "different_text": sorted(key for key in ids if key not in identical),
          "truncated_cpu": sorted(key for key in ids if cpu[key]["truncated"]),
          "truncated_gpu": sorted(key for key in ids if gpu[key]["truncated"]),
      }
    cpu_summary = json.loads((cpu_dir / "summary.json").read_text(encoding="utf-8"))
    gpu_summary = json.loads((gpu_dir / "summary.json").read_text(encoding="utf-8"))
    pair["decode_tokens_per_second"] = {"cpu": cpu_summary["performance"]["decode_tokens_per_second"], "gpu": gpu_summary["performance"]["decode_tokens_per_second"]}
    comparison["pairs"].append(pair)
  (output_root / "comparison.json").write_text(json.dumps(comparison, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
  print(f"comparison written for {len(comparison['pairs'])} pair(s) -> {output_root / 'comparison.json'}")


def resummarize(output_root: pathlib.Path) -> None:
  """Recompute the counter part of each finished arm's summary from its raw rows."""
  for arm_dir in sorted(output_root.iterdir()):
    summary_path = arm_dir / "summary.json"
    if not (summary_path.exists() and (arm_dir / "counters.jsonl").exists()):
      continue
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["counters"] = counters.summarize(counters.load(arm_dir / "counters.jsonl"))
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + chr(10), encoding="utf-8")
    counters_summary = summary["counters"]
    print(f"{arm_dir.name}: {counters_summary['counter_quality']}, invalid samples {counters_summary['invalid_utilization_samples']}, "
          f"compute median {counters_summary['engine_utilization'].get('Compute', {}).get('median_percent')}%")


def main() -> int:
  # Windows console code pages cannot represent every model output.
  for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding="utf-8", errors="replace")
  parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  parser.add_argument("--arms", default="C,D,B,F-vulkan,F-rocm,E,A", help="comma-separated arm ids")
  parser.add_argument("--port", type=int, default=8080)
  parser.add_argument("--context-length", type=int, default=8192)
  parser.add_argument("--output-root", default="evidence/IJ0/gpu")
  parser.add_argument("--compare-only", action="store_true")
  parser.add_argument("--resummarize", action="store_true", help="recompute counter summaries from stored raw rows")
  args = parser.parse_args()
  output_root = ROOT / args.output_root
  output_root.mkdir(parents=True, exist_ok=True)

  if args.resummarize:
    resummarize(output_root)
    write_comparison(output_root)
    return 0
  if not args.compare_only:
    workload_sha256 = check_manifest()
    for arm_id in [item.strip() for item in args.arms.split(",") if item.strip()]:
      if arm_id not in ARMS:
        raise SystemExit(f"unknown arm {arm_id}; choose from {sorted(ARMS)}")
      try:
        run_arm(arm_id, args.port, args.context_length, output_root, workload_sha256)
      except Exception as error:  # keep going: one broken arm must not hide the others
        print(f"{arm_id}: BLOCKED {type(error).__name__}: {error}")
        (output_root / arm_id).mkdir(parents=True, exist_ok=True)
        (output_root / arm_id / "blocked.json").write_text(
            json.dumps({"arm": arm_id, "status": "BLOCKED", "reason": f"{type(error).__name__}: {error}", "time_utc": utc_now()}, indent=2) + "\n",
            encoding="utf-8",
        )
        powershell("stop_llama_server.ps1", [], log_name=f"stop-{arm_id}.out")
      time.sleep(3)
  write_comparison(output_root)
  return 0


if __name__ == "__main__":
  sys.exit(main())
