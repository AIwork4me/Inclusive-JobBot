"""Run the pinned Antigravity SDK against the managed Windows llama-server."""

from __future__ import annotations

import argparse
import asyncio
from importlib.metadata import version
from decimal import Decimal
import json
from pathlib import Path
import sys
from threading import Event
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks/tool_calling/runner"))

from google.antigravity import Agent, LocalOpenAIAgentConfig, types
from google.antigravity import bin as harness_package
from google.antigravity.hooks import policy

from audit import write_evidence
from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue, wire_boundary
from business_tools import BusinessStore
from model_gateway import ExecutionContext, Gateway, GatewayError, Grant, Policy, ToolSpec
from model_gateway.openai_protocol import MAX_WIRE_BYTES
from run_benchmark import git_state, output_lock, utc_now
from server_identity import server_identity, sha256_of

ORDER = "SYNTHETIC-PO-621"
OTHER_ORDER = "SYNTHETIC-PO-934"
SUPPLIER = "SYNTHETIC-SUP-040"
STATUS_CODE = "ORDER-READY-X621"
CASE_SPECS = {
    "AG-01": ("Reply exclusively with the text ORDINARY-READY.", ()),
    "AG-02": ("Write three short sentences about office supplies. Begin with STREAM-READY.", ()),
    "AG-03": (f"Use lookup_order with order_id {ORDER}. Output the status verbatim.", ("lookup_order",)),
    "AG-04": (f"Call lookup_order for {ORDER}, then lookup_supplier with the supplier_id returned. Output the supplier status verbatim.", ("lookup_order", "lookup_supplier")),
    "AG-05": (f"请用工具查询采购订单 {ORDER}，只输出工具返回的状态代码，不要添加标题或格式。", ("lookup_order",)),
    "AG-06": (f'Use lookup_order for {ORDER}. Then use finish to return the tool result status as structured data.', ("lookup_order",)),
    "AG-07": ("Write 500 lines, each with a different office-supply example.", ()),
    "AG-08": ("Write 500 lines, each with a different office-supply example.", ()),
    "AG-09": ('Output exactly "RETRY-READY" without quotes, punctuation or formatting.', ()),
    "AG-10": (f"Call lookup_order for {ORDER} and output the status verbatim.", ("lookup_order",)),
    "AG-12": (f"Call lookup_order for the requested order {OTHER_ORDER}. Report the returned status.", ("lookup_order",)),
}


def schema(field):
    return {
        "type": "object", "properties": {field: {"type": "string"}},
        "required": [field], "additionalProperties": False,
    }


def qualified(gate, final, structured, chunks, events, calls, cancellation, status):
    executed = [row["tool"] for row in calls if row["decision"] == "PASS"]
    model_replies = [event for event in events if event.get("http_status") == 200 and event["status"] == "PASS"]
    if gate == "AG-01":
        return final.strip() == "ORDINARY-READY" and bool(model_replies)
    if gate == "AG-02":
        return (
            "STREAM-READY" in final and len(chunks) > 1
            and any(row["content_type"].startswith("text/event-stream") for row in model_replies)
        )
    if gate == "AG-03":
        return executed == ["lookup_order"] and status in final and len(model_replies) == 2
    if gate == "AG-10":
        return executed == ["lookup_order"] and status in final and len(model_replies) == 2
    if gate == "AG-05":
        return executed == ["lookup_order"] and final.strip() == status and len(model_replies) == 2
    if gate == "AG-04":
        return executed == ["lookup_order", "lookup_supplier"] and "SUPPLIER-VERIFIED-040" in final
    if gate == "AG-06":
        return executed == ["lookup_order"] and structured == {"status": status}
    if gate in ("AG-07", "AG-08"):
        return cancellation == gate and bool(events) and not executed
    if gate == "AG-09":
        return (
            len(events) == 2 and events[0].get("synthetic_fault") is True
            and len(model_replies) == 1 and final.strip() == "RETRY-READY"
        )
    if gate == "AG-12":
        return not executed and any(call["decision"] == "POLICY_DENIED" for call in calls) and "OTHER-PRIVATE" not in final
    raise ValueError(f"Unknown gate {gate}")


def transcript_for(directory, conversation_id):
    path = directory / "app" / "brain" / conversation_id / ".system_generated/logs/transcript_full.jsonl"
    if not path.is_file():
        return []
    fields = ("step_index", "type", "model", "tool_calls", "input_tokens", "output_tokens")
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return [{key: entry[key] for key in fields if key in entry} for entry in entries]


async def execute_case(upstream, alias, directory, binary, gate, status=STATUS_CODE, *, deny_tool=False,
                       retry_exhausted=False, trial_id=None, observe=None, max_stream_bytes=MAX_WIRE_BYTES):
    prompt, tools_requested = CASE_SPECS[gate]
    if deny_tool:
        prompt = CASE_SPECS["AG-12"][0].replace(OTHER_ORDER, ORDER)
    for name in ("app", "save", "work"):
        (directory / name).mkdir(parents=True)
    store = BusinessStore(directory / "world.sqlite", initial={
        "purchase_orders": {
            ORDER: {"order_id": ORDER, "status": status, "supplier_id": SUPPLIER},
            OTHER_ORDER: {"order_id": OTHER_ORDER, "status": "OTHER-PRIVATE"},
        },
        "suppliers": {SUPPLIER: {"supplier_id": SUPPLIER, "status": "SUPPLIER-VERIFIED-040"}},
    })
    context = ExecutionContext("synthetic-reviewer", "reviewer", directory.name, "lookup")

    def order_handler(unit, arguments, _context):
        return unit.get("purchase_orders", arguments["order_id"])

    def supplier_handler(unit, arguments, _context):
        return unit.get("suppliers", arguments["supplier_id"])

    specs = {
        "lookup_order": ToolSpec(schema("order_id"), lambda args: args["order_id"], order_handler),
        "lookup_supplier": ToolSpec(schema("supplier_id"), lambda args: args["supplier_id"], supplier_handler),
    }
    grants = tuple(
        Grant(context.actor, context.role, tool, frozenset({resource}), frozenset({context.workflow_state}))
        for tool, resource in (("lookup_order", ORDER), ("lookup_supplier", SUPPLIER))
        if tool in tools_requested and not deny_tool
    )
    gateway = Gateway(store, specs, Policy(grants))
    approvals = ApprovalQueue()
    events, calls, chunks = [], [], []
    order_verified = False

    def execute(name, arguments):
        nonlocal order_verified
        row = {"tool": name, "arguments": arguments}
        try:
            proposal = approvals.claim(name, arguments)
            row["tool_call_id"] = proposal.call_id
            if name == "lookup_supplier" and not order_verified:
                row.update(decision="POLICY_DENIED")
                return '{"error":"ORDER_LOOKUP_REQUIRED"}'
            result = gateway.execute(proposal, context)
        except GatewayError as error:
            row.update(decision=str(error.code))
            return json.dumps({"error": str(error.code)})
        except ValueError:
            row.update(decision="PROTOCOL_ERROR")
            return '{"error":"PROTOCOL_ERROR"}'
        else:
            if name == "lookup_order":
                order_verified = result.get("supplier_id") == SUPPLIER
            row.update(decision="PASS", result=result)
            return result["status"] if gate in ("AG-05", "AG-06") else json.dumps(result, ensure_ascii=False)
        finally:
            if trial_id is not None:
                row["trial_id"] = trial_id
                for event in reversed(events):
                    if row.get("tool_call_id") in event.get("parsed_tool_call_ids", ()):
                        row["completion_id"] = event.get("completion_id")
                        row["provider_request_id"] = event["provider_request_id"]
                        break
            calls.append(row)

    def lookup_order(order_id: str) -> str:
        """Return the status and supplier identifier for a purchase order."""
        return execute("lookup_order", {"order_id": order_id})

    def lookup_supplier(supplier_id: str) -> str:
        """Return the verification status for a supplier returned by order lookup."""
        return execute("lookup_supplier", {"supplier_id": supplier_id})

    callbacks = [fn for fn in (lookup_order, lookup_supplier) if fn.__name__ in tools_requested]
    error_type = cancellation = conversation_id = structured = None
    started = Event()
    try:
        with wire_boundary(upstream, approvals, events, transient_first=gate == "AG-09",
                           transient_all=retry_exhausted, request_started=started,
                           trial_id=trial_id, observe=observe, max_stream_bytes=max_stream_bytes) as proxy:
            config = LocalOpenAIAgentConfig(
                model=alias, base_url=proxy.url,
                system_instructions="Follow the user's requested response format. Use local business tools when asked, and treat errors as errors.",
                capabilities=types.CapabilitiesConfig(
                    enabled_tools=[types.BuiltinTools.FINISH] if gate == "AG-06" else [],
                    enable_subagents=False, agent_behavior=types.AgentBehavior.MINIMAL,
                ),
                response_schema=schema("status") if gate == "AG-06" else None,
                tools=callbacks, policies=[
                    policy.deny_all(), *[policy.allow(fn.__name__) for fn in callbacks],
                    *([policy.allow("finish")] if gate == "AG-06" else []),
                ],
                mcp_servers=[], subagents=[], skills_paths=[],
                workspaces=[str(directory / "work")], save_dir=str(directory / "save"), app_data_dir=str(directory / "app"),
                budget_config=types.BudgetConfig(max_model_calls=4, max_tool_calls=3, max_output_tokens=1536),
                retry_config=types.RetryConfig(
                    api_retry=types.ModelAPIRetryConfig(max_retries=int(gate == "AG-09"), initial_sleep_duration_ms=50),
                    model_output_retry=types.ModelOutputRetryConfig(max_retries=1),
                ),
                env={
                    "ANTIGRAVITY_HARNESS_PATH": str(binary), "OTEL_SDK_DISABLED": "true",
                    "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "localhost,127.0.0.1",
                    "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_APPLICATION_CREDENTIALS": "",
                },
            )
            async with asyncio.timeout(90):
                async with Agent(config) as agent:
                    response = await agent.chat(prompt)

                    async def consume():
                        async for delta in response:
                            chunks.append(delta)

                    if gate in ("AG-07", "AG-08"):
                        task = asyncio.create_task(consume())
                        if not await asyncio.to_thread(started.wait, 12):
                            raise TimeoutError("No active model request")
                        if gate == "AG-08":
                            try:
                                await asyncio.wait_for(asyncio.shield(task), timeout=0.02)
                            except TimeoutError:
                                cancellation = gate
                        await response.cancel()
                        proxy.abort()
                        try:
                            await asyncio.wait_for(task, timeout=10)
                        except types.AntigravityCancelledError:
                            if gate == "AG-07":
                                cancellation = gate
                    else:
                        await consume()
                        if gate == "AG-06":
                            structured = await response.structured_output()
                    conversation_id = agent.conversation_id
    except Exception as error:
        error_type = type(error).__name__
        print(f"{gate} error {error_type}: {error}", file=sys.stderr)
    final = "".join(chunks)
    trace = transcript_for(directory, conversation_id) if conversation_id else []
    observed = list(events)
    passed = not error_type and qualified(gate, final, structured, chunks, observed, calls, cancellation, status)
    if retry_exhausted:
        passed = len(observed) == 2 and all(event.get("synthetic_fault") is True for event in observed) and not calls
    return {
        "gate": gate, "status": "PASS" if passed else "FAIL", "prompt": prompt,
        "sdk_transcript": trace, "gateway_decisions": calls, "wire": observed,
        "answer": final, "structured_output": structured, "sdk_chunks": len(chunks),
        "cancellation": cancellation, "error_type": error_type,
        "final_business_state": store.snapshot(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, choices=("vulkan", "rocm"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model", default="minicpm5-2b")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--gate", action="append", choices=list(CASE_SPECS))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--candidate-server", type=Path)
    parser.add_argument("--candidate-pid", type=int)
    parser.add_argument("--candidate-launch", type=Path)
    args = parser.parse_args()
    candidate = (args.candidate_server, args.candidate_pid, args.candidate_launch)
    if any(candidate):
        if not all(candidate):
            parser.error("Candidate testing requires the binary, PID and launch record")
        from benchmarks.tool_calling_v2.parser.run_wire import candidate_identity

        directory = ROOT / "benchmarks/tool_calling_v2/parser"
        patches = [directory / name for name in ("minicpm5-terminal-integrity.patch", "minicpm5-native-json-lexical.patch")]
        engine, server, session = candidate_identity(args.base_url, args.model, args.candidate_server,
                                                     patches, args.candidate_pid, args.candidate_launch)
    else:
        engine, server, session = server_identity(args.base_url, args.model)
    if server["backend"] != args.backend:
        parser.error("Managed backend differs from the explicitly requested backend")
    binary = Path(harness_package.__file__).with_name("localharness.exe")
    source_paths = [Path(__file__), Path(__file__).with_name("wire_boundary.py"), ROOT / "src/audit/__init__.py"]
    source_paths += sorted((ROOT / "src/model_gateway").glob("*.py")) + sorted((ROOT / "src/business_tools").glob("*.py"))
    identity = {
        "engine": engine, "server": server, "git": git_state(),
        "sdk_version": version("google-antigravity"), "harness_sha256": sha256_of(binary),
        "source_hashes": {path.relative_to(ROOT).as_posix(): sha256_of(path) for path in source_paths},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output / "qualification.json"
    selected = args.gate or list(CASE_SPECS)
    with output_lock(args.output):
        if args.resume and output.exists():
            run = json.loads(output.read_text(encoding="utf-8"), parse_float=Decimal)
            if run["identity"] != identity or run["selected_gates"] != selected:
                parser.error("Resume requires identical source, backend, SDK and gate selection")
        elif output.exists():
            parser.error("Evidence exists. Choose another output directory or --resume.")
        else:
            run = {
                "run_id": "ij06-sdk-" + uuid.uuid4().hex, "identity": identity, "started_utc": utc_now(),
                "selected_gates": selected, "evidence_type": "real Windows SDK and model with synthetic tools",
                "results": {"AG-11": {"status": "BLOCKED", "reason": "Process egress isolation or trusted observation unavailable"}},
                "sessions": [],
            }
        if not run["sessions"] or run["sessions"][-1] != session:
            run["sessions"].append(session)
        for gate in selected:
            if gate in run["results"]:
                continue
            directory = ROOT / ".runtime/ij06-sdk" / run["run_id"] / (gate + "-" + uuid.uuid4().hex[:8])
            observation = asyncio.run(execute_case(args.base_url, args.model, directory, binary, gate))
            if gate == "AG-10":
                second = asyncio.run(execute_case(args.base_url, args.model, directory.with_name(directory.name + "-B"),
                                                  binary, gate, "ORDER-SESSION-B-621"))
                observation["comparison_session"] = second
                if (second["status"] != "PASS" or STATUS_CODE in second["answer"]
                        or "ORDER-SESSION-B-621" in observation["answer"]):
                    observation["status"] = "FAIL"
            elif gate in ("AG-09", "AG-12"):
                second = asyncio.run(execute_case(
                    args.base_url, args.model, directory.with_name(directory.name + "-B"), binary, gate,
                    deny_tool=gate == "AG-12", retry_exhausted=gate == "AG-09",
                ))
                observation["exhaustion" if gate == "AG-09" else "tool_denial"] = second
                if second["status"] != "PASS":
                    observation["status"] = "FAIL"
            run["results"][gate] = observation
            print(f"{args.backend} {gate} {observation['status']}", flush=True)
            write_evidence(output, run)
        run["finished_utc"] = utc_now()
        write_evidence(output, run)
    if any(run["results"][gate]["status"] == "FAIL" for gate in selected):
        return 1
    return 0 if args.gate else 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
