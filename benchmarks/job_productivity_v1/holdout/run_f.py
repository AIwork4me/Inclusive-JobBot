"""Run JOB-V1 Arm F without inference, using shared natural inputs and business rules."""

from argparse import ArgumentParser
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time
from uuid import uuid4

from benchmarks.tool_calling.runner.run_benchmark import git_state, output_lock, sha256_of
from business_tools import BusinessStore, encode_state
from model_gateway import ExecutionContext, Gateway, GatewayError, Grant, Policy, Proposal, ToolSpec
from skill_engine.document_review import ID, NOTE, ReviewSession, _object
from skill_engine.representative import run_representative
from model_gateway.tool_validation import STRICT_SCHEMA

from .arm_f import intake
from .dataset import BUDGET, ROOT as FROZEN, canonical, digest, load
from .oracle import ACTOR, evaluate


ROOT = FROZEN.parents[3]
SKILLS = ROOT / "skills"
READ_TABLE = {"get_product": "products", "get_inventory": "inventory", "get_order": "purchase_orders",
              "get_purchase_order": "purchase_orders", "get_supplier": "suppliers"}
STATUSES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")


def stopped(reason, *, status="clarify"):
    return {"status": status, "reason": reason}


def check_order_access(store, identity, allowed, order):
    spec = ToolSpec(_object({"order_id": ID}), lambda args: args["order_id"],
                    lambda tx, args, _ctx: tx.get("purchase_orders", args["order_id"]))
    grant = Grant(ACTOR, "document-reviewer", "get_purchase_order", frozenset(allowed), frozenset({"review"}))
    direct = Gateway(store, {"get_purchase_order": spec}, Policy((grant,)))
    direct.execute(Proposal("review-access-check", "get_purchase_order", json.dumps({"order_id": order})),
                   ExecutionContext(ACTOR, "document-reviewer", identity, "review"))


def deliver(store, identity, scopes, draft_allowed, selection):
    if selection.reason:
        return stopped(selection.reason)
    workflow, fields = selection.workflow, selection.fields
    if workflow == "document-review" and not STRICT_SCHEMA(NOTE).is_valid(fields):
        return stopped("delivery_note_invalid")
    try:
        if workflow == "document-review":
            if not draft_allowed:
                check_order_access(store, identity, scopes.get("purchase_orders", ()), fields["order_id"])
                return stopped("draft_access_denied", status="refused")
            session = ReviewSession(store, SKILLS / workflow, ACTOR, identity, identity,
                                    set(scopes.get("purchase_orders", ())), set(scopes.get("suppliers", ())),
                                    set(scopes.get("products", ())))
            result = session.propose(fields)
            return {name: result[name] for name in ("order_id", "recommendation", "differences")}
        result = run_representative(SKILLS / workflow, store, ACTOR, identity, scopes, fields)
        if workflow == "customer-service":
            return {name: result[name] for name in ("order_id", "subject", "priority", "status")}
        return {"sku": result["sku"], "warehouse": fields["warehouse"],
                "unit": result["unit"], "available": result["available"]}
    except GatewayError as failure:
        # Permission denial is based on the trusted gateway decision. Other
        # errors cannot be converted to a successful completion or a commit.
        if str(failure.code) == "POLICY_DENIED":
            return stopped("product_access_denied" if workflow == "product-information" else "order_access_denied",
                           status="refused")
        return stopped("gateway_could_not_verify", status="escalate")
    except (KeyError, ValueError):
        return stopped("business_record_unverified", status="escalate")


def telemetry(case, selection, verdict, events, followups, machine_ms):
    valid_intake = case.expected["native_input"] or {}
    selected = selection.fields or {}
    effects = [row for row in events if row["status"] in {"COMMITTED", "DRAFTED"}]
    commit_keys = [(row["tool"], row["resource"], row["idempotency_key"]) for row in effects if row["status"] == "COMMITTED"]
    return {
        "model_calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
        "machine_ms": machine_ms, "tool_calls": len(events), "first_pass_success": verdict["status"] == "PASS",
        "user_interaction_turns": 1 + len(followups), "agent_decision_steps": 0,
        "host_intake_decisions": 1, "host_gateway_transactions": len(events),
        "automatic_recovery_attempts": sum(max(0, event["attempts"] - 1) for event in events),
        "human_interventions": 0, "argument_unit": "normalized_intake_top_level_field",
        "argument_correct": sum(key in selected and selected[key] == value for key, value in valid_intake.items()),
        "argument_total": len(valid_intake),
        "invalid_calls": sum(row["error_code"] in {"PROTOCOL_ERROR", "SCHEMA_ERROR", "BUSINESS_VALIDATION_ERROR"} for row in events),
        "unauthorized_effects": sum(row["authorization"] != "ALLOW" for row in effects),
        "unconfirmed_commits": sum(row["status"] == "COMMITTED" and row["confirmation_state"] != "CONFIRMED" for row in effects),
        "duplicate_commits": len(commit_keys) - len(set(commit_keys)),
        "false_approvals": sum(row["status"] == "COMMITTED" for row in effects),
        "business_writes": len(effects),
        "correct_business_writes": len(effects) if verdict["business_state_status"] == "PASS" else 0,
    }


def run_case(case, database):
    identity = case.plan["case_id"]
    store = BusinessStore(database, initial=case.world["state"])
    before = store.snapshot()
    started = time.perf_counter()
    raw = case.input_initial()
    followups = case.task["followups"]
    if len(followups) > BUDGET["user_followups"] or any(event["release"] != "before_final_delivery" for event in followups):
        raise ValueError("unsupported frozen follow-up schedule")
    selection = intake(raw, [event["text"] for event in followups])
    answer = deliver(store, identity, case.world["permitted_reads"], case.world["draft_allowed"], selection)
    machine_ms = round((time.perf_counter() - started) * 1000, 3)
    after = store.snapshot()
    events = list(after["audit_events"].values())
    reads = [(READ_TABLE[row["tool"]], row["resource"], row["result"]) for row in events if row["status"] == "READ"]
    delivered = [event["id"] for event in followups]
    verdict = evaluate(case, answer=answer, reads=reads, before=before, after=after, delivered_followups=delivered)
    if machine_ms > BUDGET["machine_ms"] or len(events) > BUDGET["tool_proposals"]:
        verdict.update(status="FAIL", completed=False, correct_escalations=0,
                       correct_refusal=False, correct_clarification=False)
        verdict["findings"].append("case exceeded the shared budget")
    return {**case.plan, **verdict, **telemetry(case, selection, verdict, events, followups, machine_ms),
            "arm": "F", "facet": case.task["facet"], "language": case.task["language"],
            "initial_input": raw, "followups": followups, "delivered_followups": delivered,
            "intake": asdict(selection), "answer": answer, "reads": reads,
            "before_sqlite": before, "after_sqlite": after}


def state_bytes(data):
    return encode_state(data).encode("utf-8") + b"\n"


def atomic(path, data, *, encode=canonical):
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.part")
    with temporary.open("xb") as handle:
        handle.write(encode(data))
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def load_rows(records, databases, planned, run_id):
    rows = {}
    for path in records.glob("*.json"):
        trial = planned.get(path.stem)
        row = json.loads(path.read_bytes(), parse_float=Decimal)
        identity = row.get("database")
        if (trial is None or row.get("trial") != trial or row.get("run_id") != run_id
                or row.get("status") not in STATUSES[:3]
                or row.get("artifact_sha256") != sha256(state_bytes({name: item for name, item in row.items()
                                                                  if name != "artifact_sha256"})).hexdigest()
                or not isinstance(identity, str) or not re.fullmatch(rf"{re.escape(path.stem)}--[0-9a-f]{{32}}\.sqlite", identity)
                or row.get("database_sha256") != sha256_of(databases / identity)):
            raise ValueError("checkpoint identity, contents, or SQLite hash differs")
        rows[path.stem] = row
    return rows


def create_plan(freeze, panel, selected):
    population = freeze.cases if panel == "primary" else {row["case_id"] for row in freeze.repeat["cases"]}
    if len(selected) != len(set(selected)) or set(selected) - set(population):
        raise ValueError("duplicate case or case outside the selected frozen panel")
    seeds = [None] if panel == "primary" else freeze.repeat["trial_seeds"]
    return {f"{key}--{seed}" if seed is not None else key: {"case_id": key, "trial_seed": seed}
            for key in sorted(population) if not selected or key in selected for seed in seeds}


def configuration(freeze, panel, planned, limited):
    paths = [*Path(__file__).parent.glob("*.py"), *(ROOT / "src/business_tools").glob("*.py"),
             *(ROOT / "src/model_gateway").glob("*.py"), *(ROOT / "src/skill_engine").glob("*.py"),
             *(ROOT / "src/audit").glob("*.py"), *SKILLS.glob("*/*.yaml"),
             ROOT / "benchmarks/tool_calling_v2/oracle.py", ROOT / "benchmarks/tool_calling/runner/run_benchmark.py"]
    return {"arm": "F", "input": "frozen_extracted_text", "scope": "diagnostic" if limited else "panel",
            "model": None, "gpu": None, "sdk_used": False, "panel": panel, "git": git_state(),
            "python": platform.python_version(), "freeze_sha256": freeze.manifest["freeze_sha256"],
            "planned": planned, "budget": BUDGET,
            "sources": {name.relative_to(ROOT).as_posix(): sha256_of(name) for name in sorted(paths)}}


def execute(output, freeze, config, *, resume=False):
    output.mkdir(parents=True, exist_ok=True)
    with output_lock(output):
        run_file = output / "run.json"
        fingerprint = digest(config)
        if run_file.exists():
            run = json.loads(run_file.read_bytes())
            if not resume or run["fingerprint"] != fingerprint or digest(run["configuration"]) != fingerprint:
                raise ValueError("resume requires the same frozen experiment and code identity")
        else:
            if resume or any(path.name != ".writer.lock" for path in output.iterdir()):
                raise ValueError("a fresh output directory is required")
            run = {"run_id": "ij07-job-f-" + uuid4().hex, "configuration": config, "fingerprint": fingerprint,
                   "started_utc": datetime.now(timezone.utc).isoformat()}
            atomic(run_file, run)
        records, databases = output / "cases", output / "sqlite"
        records.mkdir(exist_ok=True)
        databases.mkdir(exist_ok=True)
        planned = config["planned"]
        rows = load_rows(records, databases, planned, run["run_id"])
        for key, trial in planned.items():
            if key in rows:
                continue
            database = databases / f"{key}--{uuid4().hex}.sqlite"
            row = run_case(freeze.cases[trial["case_id"]], database)
            if trial["trial_seed"] is not None:
                row["trial_seed"] = trial["trial_seed"]
            row.update(run_id=run["run_id"], trial=trial, database=database.name, database_sha256=sha256_of(database))
            row["artifact_sha256"] = sha256(state_bytes(row)).hexdigest()
            atomic(records / f"{key}.json", row, encode=state_bytes)
            rows[key] = row
        summary = summarize(run, rows)
        atomic(output / "summary.json", summary)
        return summary


def summarize(run, rows):
    config = run["configuration"]
    outcomes = Counter({**dict.fromkeys(STATUSES, 0), **dict(Counter(row["status"] for row in rows.values()))})
    outcomes["NOT_RUN"] = len(config["planned"]) - len(rows)
    by_facet = {}
    for row in rows.values():
        by_facet.setdefault(row["facet"], Counter())[row["status"]] += 1
    status = "FAIL" if outcomes["FAIL"] else "BLOCKED" if outcomes["BLOCKED"] or outcomes["NOT_RUN"] else "PASS"
    return {"status": status, "arm": "F", "scope": config["scope"], "panel": config["panel"],
            "run_id": run["run_id"], "configuration_sha256": run["fingerprint"],
            "freeze_sha256": config["freeze_sha256"], "cases": len(rows), "outcomes": dict(outcomes), "by_facet": by_facet,
            "completed_business_tasks": sum(row["completed"] for row in rows.values()),
            "correct_escalations": sum(row["correct_escalations"] for row in rows.values()),
            "correct_clarifications": sum(row["correct_clarification"] for row in rows.values()),
            "correct_refusals": sum(row["correct_refusal"] for row in rows.values()),
            "model_calls": sum(row["model_calls"] for row in rows.values()),
            "other_arms_status": {arm: "NOT_RUN" for arm in "ABCDE"}}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--panel", choices=("primary", "repeat"), default="primary")
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    try:
        freeze = load()
        plan = create_plan(freeze, args.panel, args.case)
        result = execute(args.output, freeze, configuration(freeze, args.panel, plan, bool(args.case)), resume=args.resume)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(2, f"BLOCKED: {error}\n")
    print(canonical(result).decode("utf-8"), end="")
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
