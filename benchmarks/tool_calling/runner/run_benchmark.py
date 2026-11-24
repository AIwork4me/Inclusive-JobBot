#!/usr/bin/env python3
"""Run the frozen tool-calling benchmark against a local llama-server.

Every case is a real model interaction. The model's tool calls are parsed by
the engine's native MiniCPM5 parser, executed against deterministic stand-in
tools (never against a business system) and fed back, until the model gives a
final answer or a limit is reached. Unauthorised tools are never executed.

Per-case results are appended to ``results.jsonl`` as they finish, so an
interrupted run can be resumed with ``--resume``; a resumed run refuses to
continue if the dataset digest or the engine identity changed.

Usage:
    python benchmarks/tool_calling/runner/run_benchmark.py --dataset dev
    python benchmarks/tool_calling/runner/run_benchmark.py --dataset test --resume
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evaluate import evaluate_case  # noqa: E402
from tool_simulators import ToolHost  # noqa: E402

ROOT = HERE.parents[2]
DATASETS = {"dev": "tool_calling_dev.jsonl", "test": "tool_calling_500.jsonl"}
DATASET_DIR = HERE.parent / "datasets"


def utc_now() -> str:
  return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256_of(path: pathlib.Path) -> str:
  return hashlib.sha256(path.read_bytes()).hexdigest()


def git_state() -> dict:
  def git(*args: str) -> str:
    try:
      return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
      return ""
  return {"commit": git("rev-parse", "HEAD") or None, "dirty": bool(git("status", "--porcelain"))}


def chat(base_url: str, body: dict) -> dict:
  """POST /v1/chat/completions; streaming replies are reassembled into one message."""
  stream = bool(body.get("stream"))
  request = urllib.request.Request(
      base_url + "/v1/chat/completions",
      data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
      method="POST",
      headers={"Content-Type": "application/json"},
  )
  started = time.perf_counter()
  try:
    with urllib.request.urlopen(request, timeout=900) as response:
      if not stream:
        reply = json.loads(response.read().decode("utf-8"))
        reply["wall_ms"] = int((time.perf_counter() - started) * 1000)
        return reply
      content: list[str] = []
      reasoning: list[str] = []
      calls: dict[int, dict] = {}
      usage = timings = finish = None
      for raw_line in response:
        line = raw_line.decode("utf-8").strip()
        if not line.startswith("data:"):
          continue
        payload = line[5:].strip()
        if payload == "[DONE]":
          break
        chunk = json.loads(payload)
        usage = chunk.get("usage") or usage
        timings = chunk.get("timings") or timings
        for choice in chunk.get("choices") or []:
          finish = choice.get("finish_reason") or finish
          delta = choice.get("delta") or {}
          if delta.get("content"):
            content.append(delta["content"])
          if delta.get("reasoning_content"):
            reasoning.append(delta["reasoning_content"])
          for call in delta.get("tool_calls") or []:
            index = call.get("index", 0)
            merged = calls.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
            if call.get("id"):
              merged["id"] = call["id"]
            merged["function"]["name"] += (call.get("function") or {}).get("name") or ""
            merged["function"]["arguments"] += (call.get("function") or {}).get("arguments") or ""
      message = {"role": "assistant", "content": "".join(content), "reasoning_content": "".join(reasoning), "tool_calls": [calls[i] for i in sorted(calls)]}
      return {"choices": [{"message": message, "finish_reason": finish}], "usage": usage, "timings": timings, "wall_ms": int((time.perf_counter() - started) * 1000)}
  except (urllib.error.URLError, OSError, ValueError) as error:
    return {"error": f"{type(error).__name__}: {error}", "wall_ms": int((time.perf_counter() - started) * 1000)}


def request_body(case: dict, model: str, messages: list[dict], stream: bool) -> dict:
  options = case["options"]
  body = {
      "model": model,
      "messages": messages,
      "tools": case["tools"],
      "tool_choice": "auto",
      "parallel_tool_calls": options["parallel_tool_calls"],
      "temperature": 0,
      "max_tokens": options["max_tokens"],
      "stream": stream,
      "chat_template_kwargs": {"enable_thinking": options["thinking"]},
  }
  if stream:
    body["stream_options"] = {"include_usage": True}
  return body


def run_case(case: dict, base_url: str, model: str) -> dict:
  options = case["options"]
  host = ToolHost(case)
  messages: list[dict] = [{"role": "system", "content": case["system"]}, *case["messages"]]
  steps: list[dict] = []
  requested: list[dict] = []
  final_text = ""
  stream_matches = None
  for step_index in range(options["max_steps"]):
    reply = chat(base_url, request_body(case, model, messages, options["stream"]))
    if "error" in reply:
      steps.append({"error": reply["error"]})
      break
    choice = reply["choices"][0]
    message = choice.get("message") or {}
    calls = []
    for position, call in enumerate(message.get("tool_calls") or []):
      function = call.get("function") or {}
      raw_arguments = function.get("arguments") or ""
      try:
        parsed = json.loads(raw_arguments)
      except json.JSONDecodeError:
        parsed = None
      json_object = isinstance(parsed, dict)
      name = function.get("name") or ""
      entry = {
          "name": name,
          "arguments": parsed if json_object else None,
          "arguments_raw": raw_arguments,
          "id": call.get("id"),
          "well_formed": bool(call.get("id")) and json_object and name in host.declared,
      }
      calls.append(entry)
      requested.append(entry)
    timings = reply.get("timings") or {}
    step = {
        "tool_calls": calls,
        "content": message.get("content") or "",
        "reasoning": (message.get("reasoning_content") or "")[:2000],
        "finish_reason": choice.get("finish_reason"),
        "usage": reply.get("usage"),
        "wall_ms": reply["wall_ms"],
        "prompt_n": timings.get("prompt_n"),
        "predicted_n": timings.get("predicted_n"),
    }
    if options["stream"] and step_index == 0 and calls:
      # Protocol check: the same first turn through the non-streaming path.
      reference = chat(base_url, request_body(case, model, messages, False))
      reference_calls = ((reference.get("choices") or [{}])[0].get("message") or {}).get("tool_calls") or []
      stream_matches = (
          len(reference_calls) == len(calls)
          and all((ref.get("function") or {}).get("name") == call["name"] and (ref.get("function") or {}).get("arguments") == call["arguments_raw"] for ref, call in zip(reference_calls, calls))
      )
    step["stream_matches_non_stream"] = stream_matches
    steps.append(step)
    if not calls:
      final_text = message.get("content") or ""
      break
    replay = {"role": "assistant", "content": message.get("content") or "", "tool_calls": []}
    if message.get("reasoning_content"):
      replay["reasoning_content"] = message["reasoning_content"]
    for position, call in enumerate(calls):
      call_id = call["id"] or f"call_{step_index}_{position}"
      call["id"] = call_id
      replay["tool_calls"].append({"id": call_id, "type": "function", "function": {"name": call["name"], "arguments": call["arguments_raw"]}})
    messages.append(replay)
    for call in calls:
      result = host.dispatch(call["name"], call["arguments"] if call["arguments"] is not None else {})
      messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)})
      call["tool_result"] = result

  verdict = evaluate_case(case, steps, requested, host.executed, host.denied, final_text)
  prompt_tokens = sum((step.get("usage") or {}).get("prompt_tokens", 0) for step in steps if not step.get("error"))
  completion_tokens = sum((step.get("usage") or {}).get("completion_tokens", 0) for step in steps if not step.get("error"))
  return {
      "id": case["id"],
      "category": case["category"],
      "pass": verdict["pass"],
      "failures": verdict["failures"],
      "argument_total": verdict["argument_total"],
      "argument_correct": verdict["argument_correct"],
      "tool_calls": verdict["tool_calls"],
      "malformed_calls": verdict["malformed_calls"],
      "forbidden_attempts": verdict["forbidden_attempts"],
      "unauthorized_executed": verdict["unauthorized_executed"],
      "executed": host.executed,
      "stream_matches_non_stream": stream_matches,
      "final_text": final_text,
      "steps": steps,
      "model_turns": len([step for step in steps if not step.get("error")]),
      "error": next((step["error"] for step in steps if step.get("error")), None),
      "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
      "wall_ms": sum(step.get("wall_ms", 0) for step in steps),
  }


def summarize(results: list[dict]) -> dict:
  def rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None

  by_category: dict[str, dict] = {}
  for category in sorted({result["category"] for result in results}):
    subset = [result for result in results if result["category"] == category]
    passed = sum(1 for result in subset if result["pass"])
    entry = {"cases": len(subset), "pass": passed, "pass_rate": rate(passed, len(subset))}
    if category == "streaming_tool_call":
      checked = [result for result in subset if result["stream_matches_non_stream"] is not None]
      entry["stream_non_stream_identical"] = sum(1 for result in checked if result["stream_matches_non_stream"])
      entry["stream_non_stream_checked"] = len(checked)
    by_category[category] = entry

  argument_total = sum(result["argument_total"] for result in results)
  argument_correct = sum(result["argument_correct"] for result in results)
  calls = sum(result["tool_calls"] for result in results)
  malformed = sum(result["malformed_calls"] for result in results)
  passed = sum(1 for result in results if result["pass"])
  return {
      "cases": len(results),
      "pass": passed,
      "fail": len(results) - passed,
      "real_model_tool_calling_success": rate(passed, len(results)),
      "by_category": by_category,
      "tool_argument_accuracy": rate(argument_correct, argument_total),
      "expected_arguments": argument_total,
      "correct_arguments": argument_correct,
      "cases_with_wrong_arguments": sum(1 for result in results if result["argument_correct"] < result["argument_total"]),
      "tool_calls_requested": calls,
      "malformed_calls": malformed,
      "invalid_tool_call_rate": rate(malformed, calls),
      "forbidden_attempts": sum(len(result["forbidden_attempts"]) for result in results),
      "unauthorized_executed": sum(len(result["unauthorized_executed"]) for result in results),
      "request_errors": sum(1 for result in results if result["error"]),
      "prompt_tokens": sum(result["usage"]["prompt_tokens"] for result in results),
      "completion_tokens": sum(result["usage"]["completion_tokens"] for result in results),
      "model_turns": sum(result["model_turns"] for result in results),
  }


def failure_groups(results: list[dict]) -> dict[str, int]:
  groups: dict[str, int] = {}
  for result in results:
    for failure in result["failures"]:
      key = failure.split(":")[0].split(" ")[0] if failure else "unknown"
      groups[key] = groups.get(key, 0) + 1
  return dict(sorted(groups.items(), key=lambda item: -item[1]))


def main() -> int:
  for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding="utf-8", errors="replace")
  parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  parser.add_argument("--dataset", choices=sorted(DATASETS), default="dev")
  parser.add_argument("--base-url", default="http://127.0.0.1:8080")
  parser.add_argument("--model", default="minicpm5-2b")
  parser.add_argument("--output", help="directory for evidence; default evidence/IJ0/protocol/tool_calling_<dataset>")
  parser.add_argument("--limit", type=int, help="run only the first N cases (development use)")
  parser.add_argument("--only", help="comma-separated case ids (development use)")
  parser.add_argument("--resume", action="store_true", help="skip cases already present in results.jsonl")
  args = parser.parse_args()

  dataset_path = DATASET_DIR / DATASETS[args.dataset]
  manifest = json.loads((DATASET_DIR / "dataset.manifest.json").read_text(encoding="utf-8"))
  dataset_sha256 = sha256_of(dataset_path)
  frozen = {item["path"]: item["sha256"] for item in manifest["files"]}
  if frozen.get(dataset_path.name) != dataset_sha256:
    print(f"FAIL: {dataset_path.name} does not match the frozen manifest")
    return 2
  cases = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line]
  if args.limit:
    cases = cases[: args.limit]
  if args.only:
    wanted = set(args.only.split(","))
    cases = [case for case in cases if case["id"] in wanted]

  server_state = json.loads((ROOT / ".runtime" / "llama-server" / "server.json").read_text(encoding="utf-8"))
  engine = json.loads((ROOT / "configs" / "llama_cpp" / "engine.json").read_text(encoding="utf-8"))
  output = ROOT / (args.output or f"evidence/IJ0/protocol/tool_calling_{args.dataset}")
  output.mkdir(parents=True, exist_ok=True)
  run = {
      "schema_version": 1,
      "tool": "benchmarks/tool_calling/runner/run_benchmark.py",
      "dataset": args.dataset,
      "dataset_file": dataset_path.name,
      "dataset_sha256": dataset_sha256,
      "base_url": args.base_url,
      "engine": {"build_tag": engine["build_tag"], "build_commit": engine["build_commit"], "stable_release_tag": engine["stable_release_tag"]},
      "server": {key: server_state.get(key) for key in ("backend", "model", "model_file", "context_length", "layers_offloaded", "layers_total", "gpu_backend_libraries_present")},
      "decode": {"temperature": 0, "tool_choice": "auto"},
      "git": git_state(),
      "run_id": f"tc-{args.dataset}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
  }
  run_path, results_path = output / "run.json", output / "results.jsonl"
  done: dict[str, dict] = {}
  if args.resume and results_path.exists() and run_path.exists():
    previous = json.loads(run_path.read_text(encoding="utf-8"))
    same = previous["dataset_sha256"] == run["dataset_sha256"] and previous["engine"] == run["engine"] and previous["server"] == run["server"] and previous["decode"] == run["decode"]
    if not same:
      print("FAIL: the existing run used a different dataset, engine, server configuration or decode setting; not resuming")
      return 2
    done = {json.loads(line)["id"]: json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line}
    run["resumed_from"] = previous["run_id"]
  run["case_count_selected"] = len(cases)
  run["started_utc"] = utc_now()
  run_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")

  results = []
  with results_path.open("a" if done else "w", encoding="utf-8", newline="\n") as handle:
    for index, case in enumerate(cases, start=1):
      if case["id"] in done:
        results.append(done[case["id"]])
        continue
      result = run_case(case, args.base_url, args.model)
      handle.write(json.dumps(result, ensure_ascii=False) + "\n")
      handle.flush()
      results.append(result)
      print(f"[{index}/{len(cases)}] {case['id']} {'PASS' if result['pass'] else 'FAIL'} {result['failures'][:2]}")

  metrics = summarize(results)
  metrics["failure_groups"] = failure_groups(results)
  metrics["run_id"] = run["run_id"]
  metrics["finished_utc"] = utc_now()
  (output / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
  print(json.dumps({key: metrics[key] for key in ("cases", "pass", "real_model_tool_calling_success", "tool_argument_accuracy", "invalid_tool_call_rate", "forbidden_attempts", "unauthorized_executed", "request_errors")}, ensure_ascii=False))
  for category, entry in metrics["by_category"].items():
    print(f"  {category}: {entry['pass']}/{entry['cases']}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
