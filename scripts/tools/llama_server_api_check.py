#!/usr/bin/env python3
"""Exercise the llama-server API surface that the JobBot Model Gateway relies on.

Checks, against a running local llama-server:

* ``GET /health``, ``GET /props``, ``GET /v1/models``
* ``POST /tokenize`` and ``POST /detokenize`` round trip
* ``POST /apply-template`` with tools, to see the rendered prompt
* ``POST /v1/chat/completions`` non-streaming and streaming (SSE)
* that greedy decoding gives the same text through both paths
* ``GET /metrics``

Stdlib only. Writes a JSON record and exits non-zero when a required check
fails. Token counts and speeds are taken from the server's own ``timings``.

Usage:
    python scripts/tools/llama_server_api_check.py --base-url http://127.0.0.1:8080 \
        --output evidence/IJ0/server_api_check.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_purchase_order",
            "description": "按订单号查询采购订单。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "采购订单号"},
                },
                "required": ["order_id"],
            },
        },
    }
]
MESSAGES = [{"role": "user", "content": "请查询订单号 PO-2026-0001 的采购订单。"}]
COMPARE_MESSAGES = [{"role": "user", "content": "用一句话说明什么是采购订单。"}]


class Client:
  def __init__(self, base_url: str):
    self.base_url = base_url.rstrip("/")

  def call(self, method: str, path: str, body: dict | None = None, timeout: int = 300):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        self.base_url + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
      raw = response.read()
      elapsed_ms = int((time.perf_counter() - started) * 1000)
      content_type = response.headers.get("Content-Type", "")
      payload = json.loads(raw.decode("utf-8")) if "json" in content_type else raw.decode("utf-8")
      return response.status, payload, elapsed_ms

  def stream(self, path: str, body: dict, timeout: int = 300):
    """Returns (chunks, text, reasoning, tool_calls, elapsed_ms) from an SSE stream."""
    request = urllib.request.Request(
        self.base_url + path,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    chunks: list[dict] = []
    text: list[str] = []
    reasoning: list[str] = []
    tool_calls: dict[int, dict] = {}
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
      for line in response:
        line = line.decode("utf-8").strip()
        if not line.startswith("data:"):
          continue
        payload = line[5:].strip()
        if payload == "[DONE]":
          break
        chunk = json.loads(payload)
        chunks.append(chunk)
        for choice in chunk.get("choices") or []:
          delta = choice.get("delta") or {}
          if delta.get("content"):
            text.append(delta["content"])
          if delta.get("reasoning_content"):
            reasoning.append(delta["reasoning_content"])
          for call in delta.get("tool_calls") or []:
            index = call.get("index", 0)
            merged = tool_calls.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
            if call.get("id"):
              merged["id"] = call["id"]
            function = call.get("function") or {}
            merged["function"]["name"] += function.get("name") or ""
            merged["function"]["arguments"] += function.get("arguments") or ""
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return chunks, "".join(text), "".join(reasoning), [tool_calls[i] for i in sorted(tool_calls)], elapsed_ms


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  parser.add_argument("--base-url", default="http://127.0.0.1:8080")
  parser.add_argument("--model", default="minicpm5-2b")
  parser.add_argument("--output", default="evidence/IJ0/server_api_check.json")
  args = parser.parse_args()
  client = Client(args.base_url)

  checks: list[dict] = []
  record: dict = {
      "schema_version": 1,
      "run_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
      "tool": "scripts/tools/llama_server_api_check.py",
      "base_url": client.base_url,
      "checks": checks,
  }

  def check(name: str, passed: bool, **details) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", **details})
    print(f"{checks[-1]['status']}  {name}")

  status, health, ms = client.call("GET", "/health")
  check("health", status == 200 and health.get("status") == "ok", http_status=status, body=health, elapsed_ms=ms)

  status, props, ms = client.call("GET", "/props")
  caps = props.get("chat_template_caps") or {}
  check(
      "props",
      status == 200 and bool(props.get("build_info")) and caps.get("supports_tools") is True,
      http_status=status,
      build_info=props.get("build_info"),
      model_ftype=props.get("model_ftype"),
      chat_template_caps=caps,
      chat_template_length=len(props.get("chat_template") or ""),
      total_slots=props.get("total_slots"),
      elapsed_ms=ms,
  )

  status, models, ms = client.call("GET", "/v1/models")
  listed = [m.get("id") for m in models.get("data") or []] if isinstance(models, dict) else []
  check("v1/models", status == 200 and args.model in listed, http_status=status, models=listed, elapsed_ms=ms)

  sentence = "采购订单 PO-2026-0001，含税金额 ¥12,345.67。"
  status, tokens, ms = client.call("POST", "/tokenize", {"content": sentence, "add_special": True})
  token_ids = tokens.get("tokens") or []
  status2, detokenized, _ = client.call("POST", "/detokenize", {"tokens": token_ids})
  check(
      "tokenize_detokenize_round_trip",
      status == 200 and status2 == 200 and detokenized.get("content") == sentence,
      token_count=len(token_ids),
      http_status=status,
      elapsed_ms=ms,
  )

  status, rendered, ms = client.call(
      "POST",
      "/apply-template",
      {"messages": MESSAGES, "tools": TOOLS, "add_generation_prompt": True},
  )
  prompt = rendered.get("prompt") or ""
  check(
      "apply_template_with_tools",
      status == 200 and "get_purchase_order" in prompt and "<tools>" in prompt and "<|im_start|>assistant" in prompt,
      http_status=status,
      rendered_prompt=prompt,
      elapsed_ms=ms,
  )

  greedy = {"temperature": 0, "max_tokens": 60, "chat_template_kwargs": {"enable_thinking": False}}
  status, plain, ms = client.call("POST", "/v1/chat/completions", {"model": args.model, "messages": COMPARE_MESSAGES, "stream": False, **greedy})
  plain_text = ((plain.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
  plain_timings = plain.get("timings") or {}
  check(
      "chat_completions_non_stream",
      status == 200 and bool(plain_text.strip()),
      http_status=status,
      content=plain_text,
      usage=plain.get("usage"),
      prompt_ms=plain_timings.get("prompt_ms"),
      predicted_ms=plain_timings.get("predicted_ms"),
      elapsed_ms=ms,
  )

  chunks, stream_text, reasoning, tool_calls, ms = client.stream(
      "/v1/chat/completions", {"model": args.model, "messages": COMPARE_MESSAGES, "stream": True, **greedy}
  )
  final = next((c for c in reversed(chunks) if (c.get("choices") or [{}])[0].get("finish_reason")), {})
  check(
      "chat_completions_stream",
      bool(chunks) and bool(stream_text.strip()),
      chunk_count=len(chunks),
      finish_reason=(final.get("choices") or [{}])[0].get("finish_reason"),
      content=stream_text,
      elapsed_ms=ms,
  )
  check(
      "stream_matches_non_stream_under_greedy_decoding",
      stream_text == plain_text,
      non_stream=plain_text,
      stream=stream_text,
  )

  status, metrics, ms = client.call("GET", "/metrics")
  metric_names = [line.split(" ")[0] for line in metrics.splitlines() if line and not line.startswith("#")]
  check(
      "metrics",
      status == 200 and "llamacpp:prompt_tokens_total" in metric_names and "llamacpp:tokens_predicted_total" in metric_names,
      http_status=status,
      metric_count=len(metric_names),
      elapsed_ms=ms,
  )

  record["status"] = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"
  output = pathlib.Path(args.output)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
  print(f"overall: {record['status']} ({sum(c['status'] == 'PASS' for c in checks)}/{len(checks)}) -> {args.output}")
  return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
  sys.exit(main())
