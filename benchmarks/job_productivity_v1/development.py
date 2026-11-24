"""Paired D/F development rehearsal on structured synthetic delivery notes."""

from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal
from importlib.metadata import version
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from audit import write_evidence
from benchmarks.ij06_sdk.qualify import git_state, output_lock, server_identity, sha256_of, utc_now
from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue, wire_boundary
from business_tools import BusinessStore
from google.antigravity import Agent, LocalOpenAIAgentConfig, types
from google.antigravity import bin as harness_package
from google.antigravity.hooks import policy
from model_gateway import ExecutionContext, Gateway, GatewayError, Grant, Policy, ToolSpec
from skill_engine.document_review import ID, ReviewSession, _object

CASES = (
    {
        "id": "dev-match",
        "request": "Please review this delivery note against its linked purchase order.",
        "order_id": "PO-J620", "sku": "SKU-J620", "supplier_id": "SU-J620",
        "ordered": 4, "delivered": 4, "unit_price_minor": 12345, "reported_total_minor": 49380,
        "order_unit": "box", "delivered_unit": "box", "supplier_qualified": True,
        "expected_issues": [],
    },
    {
        "id": "dev-quantity-and-amount",
        "request": "帮我审核这张送货单。请核对数量与含税总额。",
        "order_id": "PO-J621", "sku": "SKU-J621", "supplier_id": "SU-J621",
        "ordered": 7, "delivered": 6, "unit_price_minor": 3700, "reported_total_minor": 25901,
        "order_unit": "box", "delivered_unit": "box", "supplier_qualified": True,
        "expected_issues": ["SKU-J621.quantity", "total_minor"],
    },
    {
        "id": "dev-supplier-and-unit",
        "request": "Check the attached delivery note and flag problems for a supervisor.",
        "order_id": "PO-J622", "sku": "SKU-J622", "supplier_id": "SU-J622",
        "ordered": 5, "delivered": 5, "unit_price_minor": 777, "reported_total_minor": 3885,
        "order_unit": "box", "delivered_unit": "unit", "supplier_qualified": False,
        "expected_issues": ["supplier", "SKU-J622.unit", "SKU-J622.catalog_unit"],
    },
)


def initial_case(case):
    order, supplier, sku = case["order_id"], case["supplier_id"], case["sku"]
    order_line = {
        "sku": sku, "unit": case["order_unit"], "quantity": case["ordered"],
        "unit_price_minor": case["unit_price_minor"],
    }
    note = {
        "order_id": order, "supplier_id": supplier, "currency": "CNY",
        "lines": [{**order_line, "quantity": case["delivered"], "unit": case["delivered_unit"]}],
        "total_minor": case["reported_total_minor"],
    }
    world = {
        "purchase_orders": {order: {
            "order_id": order, "supplier_id": supplier, "currency": "CNY", "lines": [order_line],
            "status": "receivable", "total_minor": case["ordered"] * case["unit_price_minor"],
        }},
        "suppliers": {supplier: {"supplier_id": supplier, "qualified": case["supplier_qualified"]}},
        "products": {sku: {"sku": sku, "unit": case["order_unit"]}},
    }
    return note, world


async def intake(base_url, alias, directory, store, context, request, note, events, decisions):
    for name in ("work", "app", "save"):
        (directory / name).mkdir(parents=True)
    approvals = ApprovalQueue()
    name = "propose_review_intent"
    tool = ToolSpec(_object({"intent": {"const": "review_delivery_note"}, "order_id": ID}),
                    lambda args: args["order_id"],
                    lambda unit, args, actor: args)
    grant = Grant(context.actor, context.role, name, frozenset({note["order_id"]}), frozenset({"intake"}))
    gateway = Gateway(store, {name: tool}, Policy((grant,)))
    proposals = []

    def propose_review_intent(intent: str, order_id: str) -> str:
        """Identify the requested review and exact order ID in the supplied delivery note."""
        args = {"intent": intent, "order_id": order_id}
        try:
            proposal = approvals.claim(name, args)
            result = gateway.execute(proposal, context)
        except GatewayError as error:
            decisions.append({"status": "FAIL", "error": str(error.code)})
            return "Proposal rejected."
        except ValueError:
            decisions.append({"status": "FAIL", "error": "PROTOCOL_ERROR"})
            return "Proposal rejected."
        proposals.append(result)
        decisions.append({"status": "PASS", "call_id": proposal.call_id, "arguments": result})
        return "Intent recorded for deterministic review."

    binary = Path(harness_package.__file__).with_name("localharness.exe")
    with wire_boundary(base_url, approvals, events) as proxy:
        config = LocalOpenAIAgentConfig(
            model=alias, base_url=proxy.url,
            system_instructions=(
                "Classify the operator's request. For a delivery note review, use propose_review_intent "
                'with intent "review_delivery_note" and the exact order_id on the supplied note. '
                "The tool records a proposed intent. It does not submit a review."
            ),
            capabilities=types.CapabilitiesConfig(
                enabled_tools=[], enable_subagents=False, agent_behavior=types.AgentBehavior.MINIMAL,
            ),
            tools=[propose_review_intent], policies=[policy.deny_all(), policy.allow(name)],
            workspaces=[str(directory / "work")], app_data_dir=str(directory / "app"),
            save_dir=str(directory / "save"), mcp_servers=[], subagents=[], skills_paths=[],
            budget_config=types.BudgetConfig(max_model_calls=3, max_tool_calls=2, max_output_tokens=1536),
            retry_config=types.RetryConfig(
                api_retry=types.ModelAPIRetryConfig(max_retries=0),
                model_output_retry=types.ModelOutputRetryConfig(max_retries=1),
            ),
            env={
                "ANTIGRAVITY_HARNESS_PATH": str(binary), "OTEL_SDK_DISABLED": "true",
                "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "127.0.0.1,localhost",
                "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_APPLICATION_CREDENTIALS": "",
            },
        )
        async with asyncio.timeout(90):
            async with Agent(config) as agent:
                rendered_note = json.dumps(note, ensure_ascii=False)
                response = await agent.chat(f"{request}\n\nAttached delivery note\n{rendered_note}")
                final = await response.text()
    return proposals, final


def usage(events):
    result = {"prompt_tokens": 0, "completion_tokens": 0, "usage_records": 0}
    for event in events:
        for line in event.get("response", "").splitlines():
            if not line.startswith("data: {"):
                continue
            obj = json.loads(line[6:])
            if token_usage := obj.get("usage"):
                for key in ("prompt_tokens", "completion_tokens"):
                    result[key] += token_usage.get(key, 0)
                result["usage_records"] += 1
    return result


def execute(case, arm, args, run_id):
    note, world = initial_case(case)
    started = time.perf_counter()
    directory = ROOT / ".runtime/ij06-job-development" / run_id / f'{case["id"]}-{arm}'
    directory.mkdir(parents=True)
    store = BusinessStore(directory / "world.sqlite", initial=world)
    actor = "development-employee"
    context = ExecutionContext(actor, "document-reviewer", f'{case["id"]}-{arm}', "intake")
    events, decisions = [], []
    draft = final = error = None
    try:
        if arm == "D":
            proposals, final = asyncio.run(intake(args.base_url, args.model, directory, store, context,
                                                  case["request"], note, events, decisions))
            if proposals != [{"intent": "review_delivery_note", "order_id": note["order_id"]}]:
                raise ValueError("Expected one verified intake proposal")
        review = ReviewSession(
            store, ROOT / "skills/document-review", actor, context.session_id, case["id"],
            {note["order_id"]}, {note["supplier_id"]}, {case["sku"]},
        )
        draft = review.propose(note)
    except (GatewayError, ValueError, TimeoutError) as exc:
        error = getattr(exc, "code", type(exc).__name__)
    snapshot = store.snapshot()
    expected_issues = case["expected_issues"]
    expected_recommendation = "ESCALATE" if expected_issues else "MATCH"
    passes = (
        error is None and draft is not None
        and draft["recommendation"] == expected_recommendation
        and draft["differences"] == expected_issues
        and snapshot["review_drafts"] == {case["id"]: draft} and draft["submitted"] is False
        and snapshot["approval_records"] == {}
        and snapshot["purchase_orders"] == world["purchase_orders"]
        and snapshot["suppliers"] == world["suppliers"]
        and snapshot["products"] == world["products"]
        and not (snapshot["tickets"] or snapshot["follow_ups"])
    )
    return {
        "id": case["id"], "arm": arm, "status": "PASS" if passes else "FAIL",
        "business_state": snapshot, "model_calls": len(events), **usage(events),
        "machine_ms": round((time.perf_counter() - started) * 1000, 2),
        "expected_issues": expected_issues, "wire": events,
        "gateway_decisions": decisions, "model_intake_text": final, "error": error,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, choices=("vulkan", "rocm"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model", default="minicpm5-2b")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    engine, server, session = server_identity(args.base_url, args.model)
    if server["backend"] != args.backend:
        parser.error("Wrong live backend")
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output / "development.json"
    paths = [Path(__file__)]
    for directory in ("benchmarks/ij06_sdk", "src/model_gateway", "src/business_tools", "src/skill_engine",
                      "src/sop_engine", "src/audit", "skills/document-review"):
        paths.extend(path for path in (ROOT / directory).glob("*") if path.is_file())
    identity = {
        "git": git_state(), "engine": engine, "server": server,
        "sdk": version("google-antigravity"),
        "sources": {path.relative_to(ROOT).as_posix(): sha256_of(path) for path in sorted(paths)},
    }
    with output_lock(args.output):
        if output.exists():
            if not args.resume:
                parser.error("Evidence already exists. Use --resume or choose a different directory.")
            run = json.loads(output.read_text(encoding="utf-8"), parse_float=Decimal)
            if run["identity"] != identity:
                parser.error("Resume requires identical source, SDK and backend")
        else:
            run = {
                "run_id": "job-dev-" + uuid.uuid4().hex,
                "started_utc": utc_now(), "identity": identity, "sessions": [],
                "classification": "PAIR_D_F_DEVELOPMENT_REHEARSAL",
                "results": [],
            }
        if session not in run["sessions"]:
            run["sessions"].append(session)
        done = {(row["id"], row["arm"]) for row in run["results"]}
        for case in CASES:
            for arm in ("D", "F"):
                if (case["id"], arm) in done:
                    continue
                result = execute(case, arm, args, run["run_id"])
                run["results"].append(result)
                print(f'{args.backend} {arm} {case["id"]} {result["status"]}', flush=True)
                write_evidence(output, run)
        run["finished_utc"] = utc_now()
        write_evidence(output, run)
    return int(any(row["status"] != "PASS" for row in run["results"]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
