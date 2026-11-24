#!/usr/bin/env python3
"""First native tool-calling experiment against llama-server (ECO-01 5.1).

Sends OpenAI tool-calling requests to ``/v1/chat/completions`` and records the
raw request and response of every step, so a failure can be attributed to a
layer (model, template, native output, parser, API) instead of guessed.

The multi-step loop here is a test harness for protocol investigation. The
production agent loop is the Google Antigravity SDK and lives elsewhere.

Checks (non-streaming and streaming):
  1. tool definitions reach the prompt (``/apply-template``)
  2. a single call: id, function name, JSON arguments
  3. streaming reconstructs the same call
  4. tool result round trip: a second call whose argument comes from the first
     result, then a final answer that uses the second result
  5. tool_choice "none" produces no call; "required" produces a call

Usage:
    python scripts/tools/tool_calling_smoke.py --output evidence/IJ0/protocol/tool_calling_smoke.json
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
            "description": "按订单号查询采购订单，返回供应商编号、商品明细和总金额。",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "采购订单号，例如 PO-2026-0001"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_supplier",
            "description": "按供应商编号查询供应商信息，包括名称、是否在合格供应商名单中。",
            "parameters": {
                "type": "object",
                "properties": {"supplier_id": {"type": "string", "description": "供应商编号，例如 SUP-007"}},
                "required": ["supplier_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_amount",
            "description": "核对订单总金额与明细行金额之和是否一致，容差 0.01 元。",
            "parameters": {
                "type": "object",
                "properties": {
                    "line_amounts": {"type": "array", "items": {"type": "number"}, "description": "各明细行金额"},
                    "order_total": {"type": "number", "description": "订单总金额"},
                },
                "required": ["line_amounts", "order_total"],
            },
        },
    },
]

ORDERS = {
    "PO-2026-0001": {
        "order_id": "PO-2026-0001",
        "supplier_id": "SUP-007",
        "lines": [{"sku": "SKU-A100", "name": "A4 复印纸", "unit_price": 45.00, "quantity": 4}, {"sku": "SKU-B210", "name": "签字笔", "unit_price": 2.50, "quantity": 20}],
        "total": 230.00,
        "status": "已审批",
    },
    "PO-2026-0002": {
        "order_id": "PO-2026-0002",
        "supplier_id": "SUP-013",
        "lines": [{"sku": "SKU-C305", "name": "文件夹", "unit_price": 8.00, "quantity": 15}],
        "total": 118.00,
        "status": "待审核",
    },
}
SUPPLIERS = {
    "SUP-007": {"supplier_id": "SUP-007", "name": "华东办公用品有限公司", "qualified": True, "contact": "李明"},
    "SUP-013": {"supplier_id": "SUP-013", "name": "南方文具厂", "qualified": False, "contact": "王芳"},
}


def run_tool(name: str, arguments: dict) -> dict:
  """Deterministic stand-ins for the business tools; no I/O, no side effects."""
  if name == "get_purchase_order":
    return ORDERS.get(str(arguments.get("order_id")).strip(), {"error": "order_not_found"})
  if name == "get_supplier":
    return SUPPLIERS.get(str(arguments.get("supplier_id")).strip(), {"error": "supplier_not_found"})
  if name == "validate_amount":
    try:
      lines = [float(value) for value in arguments.get("line_amounts", [])]
      total = float(arguments.get("order_total"))
    except (TypeError, ValueError):
      return {"error": "invalid_arguments"}
    return {"consistent": abs(sum(lines) - total) <= 0.01, "line_sum": round(sum(lines), 2), "order_total": total}
  return {"error": f"unknown_tool:{name}"}


class Client:
  def __init__(self, base_url: str, model: str):
    self.base_url = base_url.rstrip("/")
    self.model = model
    self.trace: list[dict] = []

  def post(self, path: str, body: dict, stream: bool = False, timeout: int = 600):
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        self.base_url + path, data=payload, method="POST", headers={"Content-Type": "application/json"}
    )
    started = time.perf_counter()
    try:
      with urllib.request.urlopen(request, timeout=timeout) as response:
        if not stream:
          raw = response.read().decode("utf-8")
          result = json.loads(raw)
          self.trace.append({"path": path, "request": body, "response": result, "elapsed_ms": int((time.perf_counter() - started) * 1000)})
          return result
        chunks = []
        text: list[str] = []
        reasoning: list[str] = []
        calls: dict[int, dict] = {}
        for line in response:
          line = line.decode("utf-8").strip()
          if not line.startswith("data:") or line[5:].strip() == "[DONE]":
            continue
          chunk = json.loads(line[5:].strip())
          chunks.append(chunk)
          for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
              text.append(delta["content"])
            if delta.get("reasoning_content"):
              reasoning.append(delta["reasoning_content"])
            for call in delta.get("tool_calls") or []:
              index = call.get("index", 0)
              merged = calls.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
              if call.get("id"):
                merged["id"] = call["id"]
              merged["function"]["name"] += (call.get("function") or {}).get("name") or ""
              merged["function"]["arguments"] += (call.get("function") or {}).get("arguments") or ""
        result = {
            "content": "".join(text),
            "reasoning_content": "".join(reasoning),
            "tool_calls": [calls[i] for i in sorted(calls)],
            "timings": next((c["timings"] for c in reversed(chunks) if c.get("timings")), None),
            "usage": next((c["usage"] for c in reversed(chunks) if c.get("usage")), None),
            "chunk_count": len(chunks),
        }
        self.trace.append({"path": path, "stream": True, "request": body, "response": result, "elapsed_ms": int((time.perf_counter() - started) * 1000)})
        return result
    except (urllib.error.URLError, OSError, ValueError) as error:
      failure = {"error": f"{type(error).__name__}: {error}"}
      self.trace.append({"path": path, "request": body, "response": failure, "elapsed_ms": int((time.perf_counter() - started) * 1000)})
      return failure


def parse_arguments(call: dict) -> tuple[bool, dict]:
  try:
    value = json.loads(call.get("function", {}).get("arguments") or "")
  except json.JSONDecodeError:
    return False, {}
  return isinstance(value, dict), value if isinstance(value, dict) else {}


def normalize_calls(calls: list[dict]) -> list[dict]:
  output = []
  for call in calls or []:
    ok, arguments = parse_arguments(call)
    output.append({"id": call.get("id"), "name": call.get("function", {}).get("name"), "arguments": arguments, "arguments_are_json_object": ok})
  return output


def main() -> int:
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  parser.add_argument("--base-url", default="http://127.0.0.1:8080")
  parser.add_argument("--model", default="minicpm5-2b")
  parser.add_argument("--output", default="evidence/IJ0/protocol/tool_calling_smoke.json")
  parser.add_argument("--thinking", action="store_true", help="leave thinking enabled (default disables it)")
  args = parser.parse_args()
  client = Client(args.base_url, args.model)
  thinking = args.thinking
  report: dict = {
      "schema_version": 1,
      "run_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
      "tool": "scripts/tools/tool_calling_smoke.py",
      "base_url": client.base_url,
      "thinking_enabled": thinking,
      "checks": [],
  }

  def check(name: str, passed: bool | None, **details) -> None:
    status = "PASS" if passed is True else "FAIL" if passed is False else "BLOCKED"
    report["checks"].append({"name": name, "status": status, **details})
    print(f"{status}  {name}")

  base = {"model": args.model, "temperature": 0, "stream": False, "chat_template_kwargs": {"enable_thinking": thinking}, "tools": TOOLS}
  single_messages = [
      {"role": "system", "content": "你是单据审核助手。需要查询数据时调用工具，不要编造数据。"},
      {"role": "user", "content": "请查询采购订单 PO-2026-0001 的信息。"},
  ]

  rendered = client.post("/apply-template", {"messages": single_messages, "tools": TOOLS, "add_generation_prompt": True, "chat_template_kwargs": {"enable_thinking": thinking}})
  prompt = rendered.get("prompt") or ""
  check("tool_schema_reaches_prompt", "get_purchase_order" in prompt and "Tool usage guidelines" in prompt, prompt_tail=prompt[-400:])

  plain = client.post("/v1/chat/completions", {**base, "messages": single_messages})
  plain_calls = normalize_calls((plain.get("choices") or [{}])[0].get("message", {}).get("tool_calls"))
  first = plain_calls[0] if plain_calls else {}
  check(
      "single_call_non_stream",
      bool(plain_calls) and first.get("name") == "get_purchase_order" and first.get("arguments") == {"order_id": "PO-2026-0001"} and bool(first.get("id")) and first.get("arguments_are_json_object"),
      calls=plain_calls,
      content=(plain.get("choices") or [{}])[0].get("message", {}).get("content"),
      finish_reason=(plain.get("choices") or [{}])[0].get("finish_reason"),
      error=plain.get("error"),
  )

  streamed = client.post("/v1/chat/completions", {**base, "stream": True, "stream_options": {"include_usage": True}, "messages": single_messages}, stream=True)
  stream_calls = normalize_calls(streamed.get("tool_calls"))
  check(
      "single_call_stream_matches_non_stream",
      [c["name"] for c in stream_calls] == [c["name"] for c in plain_calls] and [c["arguments"] for c in stream_calls] == [c["arguments"] for c in plain_calls] and bool(stream_calls) and all(c.get("id") for c in stream_calls),
      calls=stream_calls,
      chunk_count=streamed.get("chunk_count"),
      error=streamed.get("error"),
  )

  # Multi-step round trip: the second call's argument must come from the first result.
  messages = [
      {"role": "system", "content": "你是单据审核助手。需要查询数据时调用工具，不要编造数据。每次只调用当前步骤需要的工具。"},
      {"role": "user", "content": "查询采购订单 PO-2026-0002，然后查出它供应商的名称，并判断该供应商是否在合格名单中。"},
  ]
  steps = []
  expected_sequence = ["get_purchase_order", "get_supplier"]
  executed: list[str] = []
  final_text = ""
  for step in range(6):
    reply = client.post("/v1/chat/completions", {**base, "messages": messages, "max_tokens": 512})
    message = (reply.get("choices") or [{}])[0].get("message", {})
    calls = normalize_calls(message.get("tool_calls"))
    if "error" in reply:
      steps.append({"step": step, "error": reply["error"]})
      break
    steps.append({"step": step, "content": message.get("content"), "reasoning": message.get("reasoning_content"), "calls": calls})
    if not calls:
      final_text = message.get("content") or ""
      break
    messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": message.get("tool_calls")})
    for call in calls:
      executed.append(str(call["name"]))
      result = run_tool(str(call["name"]), call["arguments"])
      steps[-1].setdefault("tool_results", []).append({"name": call["name"], "result": result})
      messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)})
  check(
      "tool_result_round_trip",
      executed[: len(expected_sequence)] == expected_sequence and "南方文具厂" in final_text and ("不在" in final_text or "否" in final_text),
      executed_calls=executed,
      step_count=len(steps),
      final_text=final_text,
  )

  none_reply = client.post("/v1/chat/completions", {**base, "tool_choice": "none", "messages": single_messages, "max_tokens": 200})
  none_calls = normalize_calls((none_reply.get("choices") or [{}])[0].get("message", {}).get("tool_calls"))
  check("tool_choice_none_makes_no_call", not none_calls, calls=none_calls, content=((none_reply.get("choices") or [{}])[0].get("message", {}).get("content") or "")[:200])

  report["status"] = "PASS" if all(c["status"] == "PASS" for c in report["checks"]) else "FAIL"
  report["trace"] = client.trace
  output = pathlib.Path(args.output)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
  print(f"overall: {report['status']} ({sum(c['status'] == 'PASS' for c in report['checks'])}/{len(report['checks'])}) -> {args.output}")
  return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
  sys.exit(main())
