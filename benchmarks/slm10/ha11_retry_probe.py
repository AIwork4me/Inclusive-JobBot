"""Isolate the real Antigravity SDK output-retry effect on raw tool choice."""

import argparse
import asyncio
from importlib.metadata import version
import json
from pathlib import Path
from uuid import uuid4

from google.antigravity import Agent, LocalOpenAIAgentConfig, types
from google.antigravity.hooks import policy

from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue, wire_boundary
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import canonical, write_json

from .admission import git_head
from .ha11_extension import replay_first_reply
from .ha11_preflight import checked_runtime
from .tc_execution import adapted_sse


ALIAS = "synthetic"
PROMPT = "Use lookup_status for the synthetic reference and report the result."
SYSTEM = "Use the supplied tool when requested."
MATRIX = ((4, 768, 0, "none"), (4, 768, 1, "auto"), (3, 768, 0, "none"), (4, 1536, 0, "none"))


def lookup_status(reference: str) -> str:
    """Read synthetic status by reference."""
    raise ValueError("The scripted provider issues no tool calls")


async def run_cell(root, harness, tool_budget, token_budget, retry):
    for name in ("work", "save", "app"):
        (root / name).mkdir(parents=True)
    terminal = {"id": "ha11-retry-probe-stop", "model": ALIAS, "object": "chat.completion",
                "created": 1, "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Scripted reply."}}]}
    raw = canonical(terminal).decode()
    events = []
    with replay_first_reply({"response": raw}, ALIAS) as client:
        with wire_boundary(client.base_url, ApprovalQueue(), events, trial_id=root.name,
                           adapt_response=adapted_sse) as endpoint:
            config = LocalOpenAIAgentConfig(
                model=ALIAS, base_url=endpoint.url, system_instructions=SYSTEM,
                capabilities=types.CapabilitiesConfig(enabled_tools=[], enable_subagents=False,
                                                      agent_behavior=types.AgentBehavior.MINIMAL),
                tools=[lookup_status], policies=[policy.deny_all(), policy.allow("lookup_status")],
                workspaces=[str(root / "work")], save_dir=str(root / "save"), app_data_dir=str(root / "app"),
                mcp_servers=[], subagents=[], skills_paths=[],
                budget_config=types.BudgetConfig(max_model_calls=4, max_tool_calls=tool_budget,
                                                 max_output_tokens=token_budget),
                retry_config=types.RetryConfig(api_retry=types.ModelAPIRetryConfig(max_retries=0),
                                              model_output_retry=types.ModelOutputRetryConfig(max_retries=retry)),
                env={"ANTIGRAVITY_HARNESS_PATH": str(harness), "OTEL_SDK_DISABLED": "true",
                     "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "localhost,127.0.0.1",
                     "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "OPENAI_API_KEY": "",
                     "GOOGLE_APPLICATION_CREDENTIALS": ""},
            )
            async with asyncio.timeout(20), Agent(config) as agent:
                reply = await agent.chat(PROMPT)
                answer = "".join([chunk async for chunk in reply])
    if len(events) != 1 or events[0]["status"] != "PASS" or answer != "Scripted reply.":
        raise ValueError("Expected one complete scripted response per SDK cell")
    return events[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--local-output", type=Path, required=True)
    parser.add_argument("--publish", type=Path, required=True)
    args = parser.parse_args()
    _, _, _, _, harness = checked_runtime(args.assets.resolve(strict=True))
    root = args.local_output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    run_id = "ha11-retry-probe-" + uuid4().hex
    results = []
    for number, (tools, tokens, retry, expected) in enumerate(MATRIX):
        event = asyncio.run(run_cell(root / str(number), harness, tools, tokens, retry))
        request = json.loads(event["request"])
        names = [tool["function"]["name"] for tool in request["tools"]]
        write_json(root / f"wire-{number}.json", event)
        results.append({"configured_max_tool_calls": tools, "configured_max_output_tokens": tokens,
                        "output_retry_count": retry, "raw_tool_choice": request.get("tool_choice"),
                        "raw_max_completion_tokens": request.get("max_completion_tokens"),
                        "tool_names": names, "raw_request_sha256": event["provider_request_sha256"],
                        "status": "PASS" if request.get("tool_choice") == expected and names == ["lookup_status"]
                                  else "FAIL"})
    report = {"run_id": run_id, "git_sha": git_head(), "probe_source_sha256": digest(Path(__file__)),
              "sdk": version("google-antigravity"), "harness_sha256": digest(harness),
              "evidence_class": "real SDK with a scripted provider", "physical_trials": 0, "results": results}
    check_text(canonical(report))
    write_json(args.publish, report)
    print([row["raw_tool_choice"] for row in results], [row["status"] for row in results])


if __name__ == "__main__":
    main()
