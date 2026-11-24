#!/usr/bin/env python3
"""Exercise a read-only Antigravity tool loop against the managed llama-server."""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import pathlib
import sys
import uuid

from google.antigravity import Agent, LocalOpenAIAgentConfig, types
from google.antigravity import bin as harness_package
from google.antigravity.hooks import policy

from run_benchmark import git_state, utc_now, write_json
from server_identity import ROOT, server_identity, sha256_of

ORDER_ID = "PO-2026-0470"
ORDER_STATUS = "ZX-APPROVED-47"
PROMPT = f"请用工具查询采购订单 {ORDER_ID}，只输出工具返回的状态代码。"


async def smoke(base_url: str, alias: str, directory: pathlib.Path, binary: pathlib.Path) -> dict:
  for name in ("work", "save", "app"):
    (directory / name).mkdir(parents=True)
  calls = []

  def get_order_status(order_id: str) -> str:
    """Look up the status of a synthetic purchase order by its exact order ID."""
    result = ORDER_STATUS if order_id == ORDER_ID else "ORDER_NOT_FOUND"
    calls.append({"name": "get_order_status", "order_id": order_id, "result": result})
    return result

  config = LocalOpenAIAgentConfig(
      model=alias,
      base_url=base_url + "/v1",
      system_instructions="You are a read-only order assistant. Look up orders with get_order_status and output only the exact status code.",
      capabilities=types.CapabilitiesConfig(
          enabled_tools=[], enable_subagents=False, agent_behavior=types.AgentBehavior.MINIMAL,
      ),
      tools=[get_order_status],
      policies=[policy.deny_all(), policy.allow(get_order_status.__name__)],
      mcp_servers=[], subagents=[], skills_paths=[],
      workspaces=[str(directory / "work")],
      save_dir=str(directory / "save"),
      app_data_dir=str(directory / "app"),
      budget_config=types.BudgetConfig(max_model_calls=4, max_tool_calls=3, max_output_tokens=2048),
      env={
          "ANTIGRAVITY_HARNESS_PATH": str(binary),
          "OTEL_SDK_DISABLED": "true",
          "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "",
          "NO_PROXY": "127.0.0.1,localhost",
          "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_APPLICATION_CREDENTIALS": "",
      },
  )
  async with asyncio.timeout(120):
    async with Agent(config) as agent:
      response = await agent.chat(PROMPT)
      final_text = await response.text()
      conversation_id = agent.conversation_id

  transcript = directory / "app" / "brain" / conversation_id / ".system_generated/logs/transcript_full.jsonl"
  entries = [json.loads(line) for line in transcript.read_text(encoding="utf-8").splitlines()]
  trace = [
      {key: entry[key] for key in ("step_index", "type", "model", "tool_calls", "input_tokens", "output_tokens") if key in entry}
      for entry in entries
  ]
  wanted = {"name": "get_order_status", "order_id": ORDER_ID, "result": ORDER_STATUS}
  observed_calls = [call for entry in trace for call in entry.get("tool_calls", [])]
  checks = {
      "sdk_transcript_requested_expected_tool": observed_calls == [{"name": "get_order_status", "args": {"order_id": ORDER_ID}}],
      "host_executed_expected_synthetic_lookup": calls == [wanted],
      "model_returned_only_tool_status": final_text.strip() == ORDER_STATUS,
      "sdk_transcript_records_model_tool_model": [entry["type"] for entry in trace] == [
          "USER_INPUT", "PLANNER_RESPONSE", "AGENCY_TOOL_CALL", "PLANNER_RESPONSE",
      ],
  }
  return {
      "status": "PASS" if all(checks.values()) else "FAIL",
      "prompt": PROMPT,
      "checks": checks,
      "host_executions": calls,
      "final_text": final_text,
      "sdk_transcript": trace,
      "capabilities": {"builtins": [], "subagents": False, "mcp_servers": [], "allowed_business_tools": [get_order_status.__name__]},
  }


def main() -> int:
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--base-url", default="http://127.0.0.1:8080")
  parser.add_argument("--model", default="minicpm5-2b")
  parser.add_argument("--output", default="evidence/IJ0/antigravity/local_tool_smoke.json")
  args = parser.parse_args()
  output = ROOT / args.output
  if output.exists():
    parser.error("Smoke evidence already exists. Choose a new output file.")
  engine, server, session = server_identity(args.base_url, args.model)
  run_id = f"ag-smoke-{uuid.uuid4().hex}"
  directory = ROOT / ".runtime/tool-calling" / run_id
  binary = pathlib.Path(harness_package.__file__).with_name("localharness.exe")
  run = {
      "schema_version": 1,
      "run_id": run_id,
      "started_utc": utc_now(),
      "evidence_type": "real model and SDK, synthetic read-only tool",
      "engine": engine, "server": server, "session": session, "git": git_state(),
      "runner_sha256": sha256_of(pathlib.Path(__file__)),
      "sdk": {
          "name": "google-antigravity",
          "version": importlib.metadata.version("google-antigravity"),
          "harness_sha256": sha256_of(binary),
      },
  }
  try:
    run.update(asyncio.run(smoke(args.base_url, args.model, directory, binary)))
  except Exception as error:
    run.update(status="BLOCKED", checks={}, error_type=type(error).__name__)
  run["finished_utc"] = utc_now()
  output.parent.mkdir(parents=True, exist_ok=True)
  write_json(output, run)
  print(run["status"], json.dumps(run["checks"]))
  return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[run["status"]]


if __name__ == "__main__":
  sys.exit(main())
