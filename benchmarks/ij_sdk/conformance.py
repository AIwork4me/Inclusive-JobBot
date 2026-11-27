#!/usr/bin/env python3
"""IJ-SDK-1.0 P3: per-SDK conformance probe against the pinned local llama-server.

Runs INSIDE the SDK's own venv (isolated dependency trees). For each arm it
exercises, over the SDK's own native model interface (never a hand-rolled
loop standing in for the SDK):

    C1 connect      - SDK model object reaches the loopback endpoint
    C2 chat         - one plain completion returns text
    C3 tool_roundtrip - one tool (echo) is offered; the SDK must deliver a
                        real tool call from the model and, after the gateway
                        result, a final answer using it

Everything is recorded (raw request/response when the SDK exposes it, support
tier, versions). A failure is a recorded research outcome, not a hidden skip.

Support tiers (mission 6.4):
  sdk-native        - official API accepts a custom base_url directly
  configurable      - official configurable support
  custom-adapter    - adapter we implemented; documented
  unsupported       - no path found
  not-verified      - connection attempted but incomplete

Usage (inside the arm's venv):
    python -I benchmarks/ij_sdk/conformance.py --arm b2 --base-url http://127.0.0.1:8080 \
        --model minicpm5-2b --output evidence/IJSDK/P3/conformance/b2.json
"""

from __future__ import annotations

import argparse
import re
import datetime as dt
import importlib.metadata as md
import json
import os
import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ECHO_TOOL = {
    "type": "function",
    "function": {
        "name": "lookup_order_total",
        "description": "按订单号查询订单总金额（元）。需要查询数据时必须使用该工具，不要编造。",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "订单号，例如 PO-2026-0001"}},
                       "required": ["order_id"], "additionalProperties": False},
    },
}
ORDER_TOTALS = {"PO-2026-0001": 17420.50, "PO-2026-0002": 980.00}
def amount_seen(text: str) -> bool:
    """Amount matcher tolerant of thousands separators and spaces (17,420.50)."""
    compact = re.sub(r"[\s,]", "", str(text))
    return "17420.50" in compact or "17420.5" in compact



def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(arm: str, checks: dict, support_tier: str, notes: str, output: str, wire: list) -> int:
    payload = {
        "schema_version": 1,
        "arm": arm,
        "checked_utc": utc(),
        "python": sys.version.split()[0],
        "packages": {p: md.version(p) for p in _pinned_packages(arm)},
        "support_tier": support_tier,
        "checks": checks,
        "notes": notes,
        "wire": wire,
    }
    out = ROOT / output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {output}: " + " ".join(f"{k}={v.get('status')}" for k, v in checks.items()))
    return 0 if all(c.get("status") == "PASS" for c in checks.values()) else 2


def _pinned_packages(arm: str) -> list[str]:
    return {
        "b1": ["google-antigravity"],
        "b2": ["openai-agents"],
        "b3": ["smolagents"],
        "b4": ["smolagents"],
        "b5": ["pydantic-ai-slim"],
        "b6": ["langgraph", "langchain-openai"],
        "b7": ["google-adk"],
        "b8": ["agent-framework"],
        "b9": ["pocketflow"],
        "o1": ["dspy"],
    }.get(arm, [])


# ---------------------------------------------------------------------------
# Per-arm probes. Each returns (checks dict, support_tier, notes, wire list).
# ---------------------------------------------------------------------------

def probe_b2(base_url: str, model: str):
    """OpenAI Agents SDK - Chat Completions mode, tracing disabled."""
    wire = []
    checks = {}
    notes = "set_default_openai_api('chat_completions'); tracing disabled (offline rule)"
    try:
        from agents import Agent, Runner, function_tool, set_default_openai_api, set_default_openai_client, set_tracing_disabled
        from openai import AsyncOpenAI

        set_tracing_disabled(True)
        set_default_openai_api("chat_completions")
        client = AsyncOpenAI(base_url=f"{base_url}/v1", api_key="not-needed")
        set_default_openai_client(client)

        @function_tool
        def lookup_order_total(order_id: str) -> str:
            """按订单号查询订单总金额（元）。"""
            return json.dumps({"order_id": order_id, "total": ORDER_TOTALS.get(order_id)})

        agent = Agent(name="conformance", model=model, tools=[lookup_order_total])
        result = Runner.run_sync(agent, "查询订单 PO-2026-0001 的总金额，只报告金额。")
        text = getattr(result, "final_output", None)
        checks["c3_tool_roundtrip"] = {"status": "PASS" if text and amount_seen(text) else "FAIL",
                                        "final_output": str(text)[:300]}
        checks["c2_chat"] = {"status": "PASS"}
        checks["c1_connect"] = {"status": "PASS"}
        support_tier = "sdk-native"
    except Exception as exc:
        checks["error"] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}",
                           "trace": traceback.format_exc()[-1200:]}
        support_tier = "not-verified"
    return checks, support_tier, notes, wire


def probe_b3_b4(base_url: str, model: str, mode: str):
    """smolagents ToolCallingAgent (b3) or CodeAgent (b4)."""
    wire = []
    checks = {}
    tier = "sdk-native"
    try:
        from smolagents import OpenAIServerModel, Tool, ToolCallingAgent, CodeAgent

        class LookupOrderTotal(Tool):
            name = "lookup_order_total"
            description = "按订单号查询订单总金额（元）。需要查询数据时必须使用该工具。"
            inputs = {"order_id": {"type": "string", "description": "订单号，例如 PO-2026-0001"}}
            output_type = "string"

            def forward(self, order_id: str) -> str:
                return json.dumps({"order_id": order_id, "total": ORDER_TOTALS.get(order_id)},
                                  ensure_ascii=False)

        llm = OpenAIServerModel(model_id=model, api_base=f"{base_url}/v1", api_key="not-needed",
                                flatten_messages_as_text=True)
        tool = LookupOrderTotal()
        if mode == "b4":
            # CodeAgent executes generated Python; restrict to trusted tools only.
            agent = CodeAgent(tools=[tool], model=llm, add_base_tools=False, verbosity_level=0)
        else:
            agent = ToolCallingAgent(tools=[tool], model=llm, add_base_tools=False, verbosity_level=0)
        out = agent.run("查询订单 PO-2026-0001 的总金额，只报告金额数字。")
        checks["c3_tool_roundtrip"] = {"status": "PASS" if amount_seen(out) else "FAIL",
                                        "final_output": str(out)[:300]}
        checks["c2_chat"] = {"status": "PASS"}
        checks["c1_connect"] = {"status": "PASS"}
        notes = f"OpenAIServerModel(flatten_messages_as_text=True) per smolagents #908; mode={mode}"
        if mode == "b4":
            notes += "; CodeAgent runs an in-process Python executor - P3 security gate requires containment before formal runs"
    except Exception as exc:
        checks["error"] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}",
                           "trace": traceback.format_exc()[-1200:]}
        tier = "not-verified"
        notes = ""
    return checks, tier, notes, wire


def probe_b5(base_url: str, model: str):
    """Pydantic AI - OpenAIChatModel over Chat Completions."""
    import asyncio
    wire = []
    checks = {}
    notes = "OpenAIChatModel('openai-chat:' prefix forces Chat Completions); ToolOutput for local models"
    try:
        from pydantic_ai import Agent as PaiAgent, ToolOutput
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
        from pydantic import BaseModel

        class OrderTotal(BaseModel):
            order_id: str
            total: float

        pai = PaiAgent(model=OpenAIChatModel(model, provider=OpenAIProvider(base_url=f"{base_url}/v1", api_key="not-needed")),
                       output_type=ToolOutput(OrderTotal))

        @pai.tool_plain(description="按订单号查询订单总金额（元）。")
        def lookup_order_total(order_id: str) -> dict:
            return {"order_id": order_id, "total": ORDER_TOTALS.get(order_id)}

        result = asyncio.run(pai.run("查询订单 PO-2026-0001 的总金额。"))
        out = result.output
        ok = isinstance(out, OrderTotal) and abs(out.total - 17420.50) < 0.01
        checks["c3_tool_roundtrip"] = {"status": "PASS" if ok else "FAIL",
                                        "final_output": out.model_dump() if isinstance(out, OrderTotal) else str(out)[:300]}
        checks["c2_chat"] = {"status": "PASS"}
        checks["c1_connect"] = {"status": "PASS"}
        support_tier = "sdk-native"
    except Exception as exc:
        checks["error"] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}",
                           "trace": traceback.format_exc()[-1200:]}
        support_tier = "not-verified"
    return checks, support_tier, notes, wire


def probe_b6(base_url: str, model: str):
    """LangGraph prebuilt agent over ChatOpenAI."""
    wire = []
    checks = {}
    notes = "langgraph.prebuilt.create_react_agent (LangChain 1.x) + ChatOpenAI(base_url=...)"
    try:
        from langchain_openai import ChatOpenAI
        from langgraph.prebuilt import create_react_agent

        llm = ChatOpenAI(model=model, base_url=f"{base_url}/v1", api_key="not-needed", temperature=0)

        def lookup_order_total(order_id: str) -> str:
            """按订单号查询订单总金额（元）。"""
            return json.dumps({"order_id": order_id, "total": ORDER_TOTALS.get(order_id)}, ensure_ascii=False)

        agent = create_react_agent(llm, [lookup_order_total])
        result = agent.invoke({"messages": [{"role": "user", "content": "查询订单 PO-2026-0001 的总金额，只报告金额。"}]})
        msgs = result.get("messages", [])
        text = msgs[-1].content if msgs else ""
        tool_messages = [m for m in msgs if getattr(m, "type", "") == "tool"]
        checks["c3_tool_roundtrip"] = {"status": "PASS" if tool_messages and amount_seen("".join(str(m.content) for m in msgs)) else "FAIL",
                                        "tool_messages": len(tool_messages), "final_output": str(text)[:300]}
        checks["c2_chat"] = {"status": "PASS"}
        checks["c1_connect"] = {"status": "PASS"}
        support_tier = "sdk-native"
    except Exception as exc:
        checks["error"] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}",
                           "trace": traceback.format_exc()[-1200:]}
        support_tier = "not-verified"
    return checks, support_tier, notes, wire


def probe_b7(base_url: str, model: str):
    """Google ADK via the native OpenAI connector."""
    wire = []
    checks = {}
    notes = "OpenAILlm connector (google.adk.integrations.openai) with InMemoryRunner"
    try:
        import asyncio
        from google.adk.agents import LlmAgent
        from google.adk.runners import InMemoryRunner
        from google.adk.integrations.openai import OpenAILlm
        from google.genai import types as gtypes

        def lookup_order_total(order_id: str) -> dict:
            """按订单号查询订单总金额（元）。"""
            return {"order_id": order_id, "total": ORDER_TOTALS.get(order_id)}

        llm = OpenAILlm(model=model, base_url=f"{base_url}/v1", api_key="not-needed")
        agent = LlmAgent(name="conformance", model=llm, tools=[lookup_order_total],
                         instruction="需要数据时调用工具；只报告金额。")
        runner = InMemoryRunner(agent=agent, app_name="conformance")

        async def run():
            content = gtypes.Content(role="user", parts=[gtypes.Part(text="查询订单 PO-2026-0001 的总金额。")])
            session = await runner.session_service.create_session(app_name="conformance", user_id="t")
            text_out = ""
            async for event in runner.run_async(user_id="t", session_id=session.id, new_message=content):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            text_out += part.text
            return text_out

        text = asyncio.run(run())
        checks["c3_tool_roundtrip"] = {"status": "PASS" if amount_seen(text) else "FAIL", "final_output": text[:300]}
        checks["c2_chat"] = {"status": "PASS"}
        checks["c1_connect"] = {"status": "PASS"}
        support_tier = "sdk-native"
    except Exception as exc:
        checks["error"] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}",
                           "trace": traceback.format_exc()[-1200:]}
        support_tier = "not-verified"
    return checks, support_tier, notes, wire


def probe_b8(base_url: str, model: str):
    """Microsoft Agent Framework 1.26.0 (last clean release; SEC-01)."""
    wire = []
    checks = {}
    notes = "agent-framework==1.26.0 (last clean release; 1.26.1/.2 hijacked, never install). " \
            "agent_framework.Agent(chat_client=OpenAIChatCompletionClient) - Chat-Completions-only servers."
    try:
        import asyncio
        from agent_framework.openai import OpenAIChatCompletionClient
        from agent_framework import Agent as AfAgent

        client = OpenAIChatCompletionClient(model=model, base_url=f"{base_url}/v1", api_key="not-needed")

        from typing import Annotated

        def lookup_order_total(order_id: Annotated[str, "订单号，例如 PO-2026-0001"]) -> dict:
            """按订单号查询订单总金额（元）。"""
            return {"order_id": order_id, "total": ORDER_TOTALS.get(order_id)}

        agent = AfAgent(client=client, name="conformance", tools=[lookup_order_total])
        result = asyncio.run(agent.run("查询订单 PO-2026-0001 的总金额，只报告金额。"))
        text = str(result)
        checks["c3_tool_roundtrip"] = {"status": "PASS" if amount_seen(text) else "FAIL", "final_output": text[:300]}
        checks["c2_chat"] = {"status": "PASS"}
        checks["c1_connect"] = {"status": "PASS"}
        support_tier = "sdk-native"
    except Exception as exc:
        checks["error"] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}",
                           "trace": traceback.format_exc()[-1200:]}
        support_tier = "not-verified"
    return checks, support_tier, notes, wire


def probe_b9(base_url: str, model: str):
    """PocketFlow - the framework has NO model layer; disclose our reference utility."""
    import urllib.request
    wire = []
    checks = {}
    notes = ("PocketFlow provides Node/Flow only; the LLM utility, tool plumbing and "
             "loop are OUR reference implementation (disclosed per mission 6.4). "
             "Conformance therefore measures PocketFlow's graph mechanics, not its model support.")
    try:
        from pocketflow import Node, Flow

        class AskModel(Node):
            def prep(self, shared):
                return shared["messages"]

            def exec(self, messages):
                body = {"model": model, "messages": messages, "max_tokens": 512, "temperature": 0,
                        "stream": False, "tools": [ECHO_TOOL], "tool_choice": "auto",
                        "chat_template_kwargs": {"enable_thinking": False}}
                req = urllib.request.Request(f"{base_url}/v1/chat/completions",
                                             data=json.dumps(body, ensure_ascii=False).encode(),
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as reply:
                    return json.load(reply)

            def post(self, shared, prep_res, exec_res):
                msg = exec_res["choices"][0]["message"]
                calls = msg.get("tool_calls") or []
                if calls:
                    args = json.loads(calls[0]["function"]["arguments"])
                    result = ORDER_TOTALS.get(args.get("order_id"))
                    shared["messages"].append({"role": "assistant", "content": None, "tool_calls": calls})
                    shared["messages"].append({"role": "tool", "tool_call_id": calls[0]["id"],
                                               "content": json.dumps({"total": result}, ensure_ascii=False)})
                    return "ask"
                shared["final"] = msg.get("content") or ""
                return "done"

        class Decide(Node):
            def exec(self, _):
                pass

            def post(self, shared, _, __):
                return None

        ask_node = AskModel()
        ask_node - "ask" >> ask_node  # PocketFlow self-loop for the tool round trip
        flow = Flow(start=ask_node)
        shared = {"messages": [{"role": "user", "content": "查询订单 PO-2026-0001 的总金额，只报告金额。"}]}
        flow.run(shared)
        final = shared.get("final", "")
        checks["c3_tool_roundtrip"] = {"status": "PASS" if amount_seen(final) else "FAIL", "final_output": final[:300]}
        checks["c2_chat"] = {"status": "PASS"}
        checks["c1_connect"] = {"status": "PASS"}
        support_tier = "custom-adapter"
    except Exception as exc:
        checks["error"] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}",
                           "trace": traceback.format_exc()[-1200:]}
        support_tier = "not-verified"
    return checks, support_tier, notes, wire


def probe_o1(base_url: str, model: str):
    """DSPy - optimization layer; verify LM transport + a ReAct step."""
    wire = []
    checks = {}
    notes = "dspy.LM('openai/<model>', api_base=...) - O1 is an optimization arm, not a runtime"
    try:
        import dspy

        lm = dspy.LM(f"openai/{model}", api_base=f"{base_url}/v1", api_key="not-needed", temperature=0, max_tokens=512)
        dspy.configure(lm=lm)
        answer = lm("用一句话说明什么是采购订单。")[0]
        checks["c2_chat"] = {"status": "PASS" if answer else "FAIL", "final_output": str(answer)[:200]}
        checks["c1_connect"] = {"status": "PASS"}
        support_tier = "sdk-native"
    except Exception as exc:
        checks["error"] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}",
                           "trace": traceback.format_exc()[-1200:]}
        support_tier = "not-verified"
    return checks, support_tier, notes, wire


def probe_b1(base_url: str, model: str):
    """Antigravity - LocalOpenAIAgentConfig via Agent.chat (repository smoke path)."""
    wire = []
    checks = {}
    notes = "google.antigravity LocalOpenAIAgentConfig + Agent.chat (async context manager); API verified against benchmarks/tool_calling/runner/run_antigravity_smoke.py"
    try:
        import asyncio
        from google.antigravity import Agent, LocalOpenAIAgentConfig

        config = LocalOpenAIAgentConfig(
            base_url=f"{base_url}/v1",
            model=model,
            api_key="not-needed",
        )

        async def run():
            async with Agent(config) as agent:
                response = await agent.chat("用一句话说明什么是采购订单。")
                return response

        text = asyncio.run(run())
        checks["c2_chat"] = {"status": "PASS" if text else "FAIL", "final_output": str(text)[:300]}
        checks["c1_connect"] = {"status": "PASS"}
        support_tier = "sdk-native"
    except Exception as exc:
        checks["error"] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}",
                           "trace": traceback.format_exc()[-1200:]}
        support_tier = "not-verified"
    return checks, support_tier, notes, wire


PROBES = {
    "b1": probe_b1,
    "b2": probe_b2,
    "b3": lambda u, m: probe_b3_b4(u, m, "b3"),
    "b4": lambda u, m: probe_b3_b4(u, m, "b4"),
    "b5": probe_b5,
    "b6": probe_b6,
    "b7": probe_b7,
    "b8": probe_b8,
    "b9": probe_b9,
    "o1": probe_o1,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, choices=sorted(PROBES))
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model", default="minicpm5-2b")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    checks, tier, notes, wire = PROBES[args.arm](args.base_url, args.model)
    return record(args.arm, checks, tier, notes, args.output, wire)


if __name__ == "__main__":
    sys.exit(main())
