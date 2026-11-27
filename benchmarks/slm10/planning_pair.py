"""Matched plan-first diagnostics through Direct llama.cpp and Antigravity."""

import asyncio
from dataclasses import dataclass

from google.antigravity import Agent, LocalOpenAIAgentConfig, types
from google.antigravity.hooks import policy

from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue, wire_boundary
from evaluation.aeve.controller import grade
from evaluation.aeve.oracle_panel import panel
from evaluation.aeve.runtime import fingerprint


@dataclass(frozen=True)
class Endpoint:
    answer: str
    wire: list
    error_type: str | None = None


async def sdk_plan(client, body, target, harness):
    system, user = body["messages"]
    wire = []
    for name in ("work", "save", "app"):
        (target / name).mkdir(parents=True)
    with wire_boundary(client.base_url, ApprovalQueue(), wire) as endpoint:
        config = LocalOpenAIAgentConfig(
            model=body["model"], base_url=endpoint.url, system_instructions=system["content"],
            capabilities=types.CapabilitiesConfig(
                enabled_tools=[], enable_subagents=False, agent_behavior=types.AgentBehavior.MINIMAL),
            tools=[], mcp_servers=[], subagents=[], skills_paths=[], policies=[policy.deny_all()],
            workspaces=[str(target / "work")], save_dir=str(target / "save"), app_data_dir=str(target / "app"),
            budget_config=types.BudgetConfig(max_model_calls=1, max_output_tokens=body["max_tokens"]),
            retry_config=types.RetryConfig(api_retry=types.ModelAPIRetryConfig(max_retries=0),
                                          model_output_retry=types.ModelOutputRetryConfig(max_retries=0)),
            env={
                "ANTIGRAVITY_HARNESS_PATH": str(harness), "OTEL_SDK_DISABLED": "true",
                "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "localhost,127.0.0.1",
                "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_APPLICATION_CREDENTIALS": "",
            },
        )
        chunks = []
        try:
            async with asyncio.timeout(90):
                async with Agent(config) as agent:
                    response = await agent.chat(user["content"])
                    async for chunk in response:
                        chunks.append(chunk)
        except (OSError, ValueError, types.AntigravityCancelledError, types.AntigravityConnectionError,
                types.AntigravityExecutionError, types.AntigravityValidationError) as error:
            return Endpoint("".join(chunks), wire, type(error).__name__)
    return Endpoint("".join(chunks), wire)


def replay(spec, observed):
    if not observed.wire or observed.error_type:
        return {"status": "BLOCKED", "reason": "no complete runtime response"}
    try:
        return grade(spec, observed.answer)
    except (KeyError, TypeError, ValueError):
        return {"status": "FAIL", "reason": "invalid model planning output"}


def diagnostic_panel():
    chosen = set()
    for spec in panel():
        if spec["mode"] != "native":
            continue
        if spec["suite"] == "clarification":
            if spec["arm"] == "combined":
                yield spec
        elif spec["track"] == "inferred" and spec["language"] == "en" and spec["level"] in (2, 4, 6):
            if spec["level"] not in chosen:
                chosen.add(spec["level"])
                yield spec


def matched_plan(client, alias, target, harness):
    results = []
    for spec in diagnostic_panel():
        body = {**spec["body"], "model": alias}
        client.requests.clear()
        client.read_trace()
        try:
            decoded = client.chat(client.base_url, body)
            choice = decoded["choices"][0]
            answer = choice["message"].get("content") or ""
            source = client.requests[-1]["source_generation"]
            error_type = None if choice["finish_reason"] == "stop" and source.get("truncated") is False else "IncompleteGeneration"
            direct = Endpoint(answer, list(client.requests), error_type)
        except (OSError, ValueError, KeyError) as error:
            direct = Endpoint("", list(client.requests), type(error).__name__)
        sdk = asyncio.run(sdk_plan(client, body, target / spec["case"], harness))
        results.append({
            "case": spec["case"], "suite": spec["suite"], "case_sha256": fingerprint(spec),
            "formal_qualification": "NOT_RUN", "evidence_class": "legacy-roster diagnostic",
            "common_visible_task_sha256": fingerprint(body["messages"]),
            "direct": {**vars(direct), "mechanical_replay": replay(spec, direct)},
            "sdk": {**vars(sdk), "mechanical_replay": replay(spec, sdk)},
        })
    return results
