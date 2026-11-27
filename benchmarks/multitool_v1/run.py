"""Execute MULTITOOL-V1 through the pinned local Radeon source observer."""

import argparse
from collections import Counter
from dataclasses import asdict
import http.client
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from benchmarks.competitive_slm import tc_v2_candidate
from benchmarks.root_cause import generation_capture, historical_replay
from benchmarks.root_cause.wire_profiles import decode_batched_completion, decode_batched_stream
from benchmarks.tool_calling_v2.parser.run_wire import split_sse
from benchmarks.tool_calling_v2.evaluator import Call, VALIDATOR
from benchmarks.tool_calling_v2.holdout import qualify
from benchmarks.tool_calling_v2.holdout.runner import parser_rejections
from benchmarks.tool_calling_v2.oracle import decode_object
from business_tools import encode_state
from model_gateway import GatewayError
from model_gateway.openai_protocol import decode_proposal

from .dataset import ROOT as FROZEN, canonical, load_freeze
from .runtime import Scenario, score


ROOT, legacy = historical_replay.ROOT, historical_replay.legacy
ALIAS = historical_replay.ALIAS
CANDIDATES = ("B", "D", "F", "G", "H", "J")
STATUSES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
LIMITS = {"max_turns": 24, "max_proposals": 32, "max_tokens_per_turn": 1536, "max_case_seconds": 600}
FIRST_SEED = 66007
SESSION_KEYS = ("backend", "gpu", "build", "args", "template_sha256", "layers_offloaded", "layers_total")
ENV_PREFIXES = ("LLAMA_", "GGML_", "HIP_", "ROCR_", "HSA_", "VK_")


def digest(value):
    return sha256(canonical(value)).hexdigest()


def plan(freeze, panel, selected, *, first_seed):
    if panel == "repeat":
        eligible, seeds = freeze.panel["case_ids"], freeze.panel["seeds"]
    else:
        eligible, seeds = freeze.controls if panel == "controls" else freeze.active, (first_seed,)
    if len(selected) != len(set(selected)) or set(selected) - set(eligible):
        raise ValueError("duplicate case or selection outside its frozen panel")
    return [{"key": f"{panel}--{case_id}--{seed}", "case_id": case_id, "seed": seed}
            for case_id in eligible if not selected or case_id in selected for seed in seeds]


def request(messages, tools, seed, *, alias=ALIAS, stream=False):
    body = {"model": alias, "messages": list(messages), "tools": tools, "tool_choice": "auto",
            "parallel_tool_calls": True, "seed": seed, "temperature": 0, "stream": stream,
            "cache_prompt": False, "max_tokens": LIMITS["max_tokens_per_turn"],
            "chat_template_kwargs": {"enable_thinking": False}}
    if stream:
        body["stream_options"] = {"include_usage": True}
    return body


def count_proposals(reply, validators, ids):
    choices = reply.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    proposals = message.get("tool_calls") or []
    if not isinstance(proposals, list):
        return 1, 1
    seen = set(ids)
    invalid = 0
    for item in proposals:
        try:
            proposal = decode_proposal(item)
            arguments = decode_object(proposal.arguments_raw)
            if (proposal.call_id in seen or proposal.name not in validators
                    or not validators[proposal.name].is_valid(arguments)):
                invalid += 1
            seen.add(proposal.call_id)
        except (GatewayError, ValueError):
            invalid += 1
    return len(proposals), invalid


def run_case(case, client, database, *, seed, alias=ALIAS, stream=False, require_observed_draft=False):
    sandbox = Scenario(case, database, require_observed_draft=require_observed_draft)
    before = sandbox.snapshot()
    model = case.model_input()
    messages, tools = model["messages"], model["tools"]
    validators = {tool["function"]["name"]: VALIDATOR(tool["function"]["parameters"]) for tool in tools}
    calls, events, notes, ids = [], [], [], set()
    final, completed, task_budget_reached = "", False, False
    parser_status, protocol_status, capture_status = "NOT_RUN", "NOT_RUN", "PASS"
    seen_tool_syntax = False
    proposal_count = invalid_count = 0
    prompt_tokens = completion_tokens = usage_records = 0
    started = time.monotonic()
    client.requests.clear()

    def note(code, detail):
        notes.append({"code": code, "detail": detail})

    for turn in range(LIMITS["max_turns"]):
        if time.monotonic() - started >= LIMITS["max_case_seconds"]:
            task_budget_reached = True
            note("F12_FINAL_ANSWER_ERROR", "case wall-time budget reached before a final answer")
            break
        try:
            reply = client.chat(client.base_url, request(messages, tools, seed, alias=alias, stream=stream))
        except (OSError, http.client.HTTPException, generation_capture.CaptureError) as failure:
            note("F04_TRANSPORT_ERROR", type(failure).__name__)
            capture_status = "BLOCKED"
            break
        capture = client.requests[-1]
        if capture["source_generation"].get("status") == "BLOCKED" or capture["render_status"] != 200:
            note("F15_INSUFFICIENT_EVIDENCE", "generation observer or rendered prompt missing")
            capture_status = "BLOCKED"
        usage = reply.get("usage") or {}
        if all(type(usage.get(key)) is int and usage[key] >= 0 for key in ("prompt_tokens", "completion_tokens")):
            prompt_tokens += usage["prompt_tokens"]
            completion_tokens += usage["completion_tokens"]
            usage_records += 1
        if time.monotonic() - started >= LIMITS["max_case_seconds"]:
            task_budget_reached = True
            note("F12_FINAL_ANSWER_ERROR", "case wall-time budget exceeded during model response")
            break
        if reply.get("parser_rejected"):
            rejected = parser_rejections(capture)
            proposal_count += rejected
            invalid_count += rejected
            parser_status = "FAIL"
            note("F06_NATIVE_PARSER_ERROR", "native parser rejected generated output")
            break
        if capture["http_status"] != 200:
            note("F04_TRANSPORT_ERROR", f"HTTP {capture['http_status']}")
            capture_status = "BLOCKED"
            break
        choices = reply.get("choices") or []
        if choices and choices[0].get("finish_reason") == "length":
            task_budget_reached = True
            note("F12_FINAL_ANSWER_ERROR", "model hit response token budget")
            break
        proposed, invalid = count_proposals(reply, validators, ids)
        proposal_count += proposed
        invalid_count += invalid
        try:
            raw = capture["raw_response"]
            max_calls = LIMITS["max_proposals"]
            if stream:
                answer = decode_batched_stream(split_sse(raw.encode("utf-8")), max_calls=max_calls)
            else:
                answer = decode_batched_completion(raw, max_calls=max_calls)
            if any(call.call_id in ids for call in answer.calls):
                raise ValueError("tool call ID was reused across assistant turns")
        except (GatewayError, ValueError) as failure:
            protocol_status = "FAIL"
            capture_failed = capture.get("gateway_protocol", {}).get("status")
            if capture_failed == "FAIL" and not choices:
                note("F05_PROTOCOL_ERROR", "completion envelope missing or malformed")
            else:
                note("F05_PROTOCOL_ERROR", str(failure))
            break
        protocol_status = "PASS"
        if not answer.calls:
            completed, final = True, answer.content
            break
        seen_tool_syntax = True
        if proposal_count > LIMITS["max_proposals"]:
            task_budget_reached = True
            note("F02_MODEL_TOOL_SELECTION_ERROR", "tool proposal budget exceeded")
            break
        assistant = {"role": "assistant", "content": answer.content, "tool_calls": [
            {"type": "function", "id": call.call_id,
             "function": {"name": call.name, "arguments": call.arguments_raw}} for call in answer.calls
        ]}
        if answer.reasoning:
            assistant["reasoning_content"] = answer.reasoning
        messages.append(assistant)
        for call in answer.calls:
            ids.add(call.call_id)
            observed = sandbox.call(call.call_id, call.name, call.arguments_raw, turn=turn)
            calls.append(Call(turn, call.call_id, call.name, call.arguments_raw, observed))
            messages.append({"role": "tool", "tool_call_id": call.call_id, "content": encode_state(observed)})
        for event_id, event in sandbox.take_events():
            events.append((turn, event_id))
            messages.append(event)
    else:
        task_budget_reached = True
        note("F12_FINAL_ANSWER_ERROR", "assistant turn budget exhausted")

    after = sandbox.snapshot()
    verdict = score(case, calls, final, before=before, after=after, delivered_events=events)
    verdict["findings"].extend(notes)
    if capture_status == "BLOCKED":
        verdict["status"] = "BLOCKED"
    elif notes:
        verdict.update(status="FAIL", trace_status="FAIL")
    if seen_tool_syntax and parser_status == "NOT_RUN":
        parser_status = "PASS"
    model_turns = len(client.requests)
    required = case.oracle["nodes"]
    eligible_first = {node["tool"] for node in required if not node["depends_on"]}
    return {**verdict, "case_id": case.case_id, "category": case.oracle["category"],
            "depth_bin": case.oracle["depth_bin"], "required_tool_steps": len(required), "seed": seed,
            "native_parser_status": parser_status, "wire_protocol_status": protocol_status,
            "source_evidence_status": capture_status, "completed": completed, "budget_reached": task_budget_reached,
            "first_call_correct": bool(calls and calls[0].name in eligible_first) if eligible_first else None,
            "model_calls": model_turns, "usage_records": usage_records,
            "prompt_tokens": prompt_tokens if model_turns and usage_records == model_turns else None,
            "completion_tokens": completion_tokens if model_turns and usage_records == model_turns else None,
            "proposal_count": proposal_count, "invalid_proposal_count": invalid_count,
            "wall_ms": round((time.monotonic() - started) * 1000), "final": final,
            "calls": [asdict(call) for call in calls], "delivered_events": events,
            "before_sqlite": before, "after_sqlite": after, "requests": list(client.requests)}


def resolve_runtime(args):
    engine = args.engine_dir.resolve()
    if args.candidate is None:
        if args.runtime_root is None or args.model is not None:
            raise ValueError("the default MiniCPM5 profile requires --runtime-root and its pinned model path")
        return qualify.verify_runtime(args.backend, args.runtime_root.resolve(), engine)
    if args.backend != "vulkan" or args.candidate not in CANDIDATES:
        raise ValueError("strict MULTITOOL candidates use the verified Vulkan profile")
    if args.model is None:
        raise ValueError("strict candidate profile requires --model with the exact admitted Q8_0 GGUF")
    model = args.model.resolve(strict=True)
    verified = tc_v2_candidate.verify_runtime(args.candidate, model, engine)
    # The admission verifier also supplies the TC-V2 workload limits, which
    # are not the MULTITOOL limits. Only its runtime identity applies here.
    identity = {key: value for key, value in verified.items() if key != "budgets"}
    identity["expected_template_sha256"] = verified["template"]["sha256"]
    identity["model_alias"] = f"ij07-candidate-{args.candidate.lower()}"
    identity["context_tokens"] = verified["budgets"]["context_tokens"]
    return engine / "llama-server.exe", model, identity, tc_v2_candidate.server_environment()


def configuration(args, freeze, roster, identity, env):
    inventory = [*Path(__file__).parent.glob("*.py"),
                 *(ROOT / "benchmarks/tool_calling_v2").glob("*.py"),
                 *(ROOT / "benchmarks/tool_calling_v2/holdout").glob("*.py"),
                 *(ROOT / "benchmarks/tool_calling_v2/parser").glob("*.py"),
                 ROOT / "benchmarks/root_cause/generation_capture.py", ROOT / "benchmarks/root_cause/historical_replay.py",
                 ROOT / "benchmarks/root_cause/wire_profiles.py",
                 ROOT / "benchmarks/tool_calling/runner/run_benchmark.py", ROOT / "scripts/windows/sample_gpu_counters.ps1",
                 ROOT / "scripts/windows/common.ps1", *(ROOT / "src/business_tools").glob("*.py"),
                 *(ROOT / "src/model_gateway").glob("*.py")]
    if "candidate" in identity:
        inventory.append(Path(tc_v2_candidate.__file__))
    environment = {key.upper(): value for key, value in env.items() if key.upper().startswith(ENV_PREFIXES)}
    config = {"git": legacy.git_state(), **identity, "backend": args.backend, "port": args.port,
            "stream": bool(getattr(args, "stream", False)),
            "freeze_sha256": freeze.manifest["freeze_sha256"], "panel": args.panel,
            "scope": "diagnostic" if args.case or args.panel == "controls" else "full_panel", "roster": roster,
            "manifest_sha256": legacy.sha256_of(FROZEN / "manifest.json"), "sdk_installed": version("google-antigravity"),
            "sdk_used": False, "limits": LIMITS, "environment_sha256": digest(environment),
            "source_sha256": {path.relative_to(ROOT).as_posix(): legacy.sha256_of(path) for path in sorted(inventory)}}
    if getattr(args, "require_observed_draft", False):
        config["require_observed_draft"] = True
    return config


def summary(run, done, interruptions):
    config = run["configuration"]
    roster = config["roster"]
    counts = Counter({status: 0 for status in STATUSES})
    by_depth = {}
    blocked_keys = {path.stem.rsplit("--", 1)[0] for path in interruptions}
    for item in roster:
        row = done.get(item["key"])
        status = row["status"] if row else "BLOCKED" if item["key"] in blocked_keys else "NOT_RUN"
        counts[status] += 1
        if row:
            by_depth.setdefault(row["depth_bin"] or "0", Counter())[row["status"]] += 1
    sessions_used = {row["session"] for row in done.values()}
    gpu_status = "NOT_RUN"
    if sessions_used:
        gpu_status = "PASS" if all(run["sessions"][tag].get("proof", {}).get("status") == "PASS"
                                   for tag in sessions_used) else "BLOCKED"
    elif interruptions:
        gpu_status = "BLOCKED"
    task_status = ("BLOCKED" if gpu_status == "BLOCKED" or len(done) != len(roster)
                   else "FAIL" if counts["FAIL"] else "PASS")
    if not (done or interruptions):
        task_status = "NOT_RUN"
    metrics = {"status": task_status, "scope": config["scope"], "panel": config["panel"],
               "run_id": run["run_id"], "configuration_sha256": run["fingerprint"],
               "planned": len(roster), "terminal": len(done), "tasks": dict(counts), "by_depth_observed": by_depth,
               "physical_evidence_status": gpu_status, "runtime_interruptions": len(interruptions),
               "synthetic_services": True, "sdk_used": False}
    if "candidate" in config:
        metrics["candidate"] = config["candidate"]
    if config["panel"] == "repeat":
        groups = {}
        for trial in roster:
            groups.setdefault(trial["case_id"], []).append(done.get(trial["key"], {}).get("status", "NOT_RUN"))
        assessed = [statuses for statuses in groups.values() if "NOT_RUN" not in statuses]
        complete = bool(groups) and len(assessed) == len(groups)
        metrics["repeats"] = {"complete_groups": len(assessed), "planned_groups": len(groups),
                              "pass_at_3": sum("PASS" in row for row in assessed) / len(groups) if complete else None,
                              "pass_all_3": sum(all(status == "PASS" for status in row) for row in assessed) / len(groups)
                              if complete else None}
    return metrics


def execute_locked(args, config, cases, output, binary, model, env):
    run_path = output / "run.json"
    fingerprint = digest(config)
    if run_path.exists():
        run = qualify.load_json(run_path)
        if not args.resume or run["fingerprint"] != fingerprint or digest(run["configuration"]) != fingerprint:
            raise ValueError("resume requires the exact original run configuration")
    else:
        if args.resume or any(path.name != ".writer.lock" for path in output.iterdir()):
            raise ValueError("a fresh output directory is required for a new run")
        run = {"run_id": "ij07-multitool-" + uuid4().hex, "configuration": config,
               "fingerprint": fingerprint, "sessions": {}, "started_utc": legacy.utc_now()}
        legacy.write_json(run_path, run)
    records, interruptions, databases = (output / name for name in ("cases", "interruptions", "sqlite"))
    for directory in (records, interruptions, databases):
        directory.mkdir(exist_ok=True)
    roster = config["roster"]
    expected = {trial["key"] for trial in roster}
    if any(file.stem not in expected for file in records.glob("*.json")):
        raise ValueError("unexpected terminal checkpoint")
    done = {file.stem: qualify.read_checkpoint(file, run, file.stem, databases) for file in records.glob("*.json")}
    for tag, session in run["sessions"].items():
        proof = qualify.pid_counter_proof(output, session)
        if "proof" in session and proof != session["proof"]:
            raise ValueError(f"session source or physical proof changed: {tag}")
        session["proof"] = proof
    pending = [trial for trial in roster if trial["key"] not in done]
    if args.batch_size:
        pending = pending[:args.batch_size]
    if pending:
        tag = uuid4().hex
        alias = config.get("model_alias", ALIAS)
        try:
            with historical_replay.gpu_server(binary, model, args.backend, env, output, args.port, tag, True,
                                              alias=alias, max_nonstream_calls=LIMITS["max_proposals"]) as (client, launch):
                if "candidate" in config:
                    tc_v2_candidate.verify_launch(launch, config)
                if (launch["layers_offloaded"] != launch["layers_total"]
                        or launch["template_sha256"] != config["expected_template_sha256"]):
                    raise ValueError("live full offload or model template differs from pin")
                if run["sessions"] and any(launch[key] != next(iter(run["sessions"].values()))[key] for key in SESSION_KEYS):
                    raise ValueError("live server identity changed on resume")
                launch["server_file"] = f"{tag}-server.log"
                run["sessions"][tag] = launch
                legacy.write_json(run_path, run)
                for trial in pending:
                    case = cases[trial["case_id"]]
                    key = trial["key"]
                    database = databases / f"{key}--{uuid4().hex}.sqlite" if case.oracle["state"] is not None else None
                    result = run_case(case, client, database, seed=trial["seed"], alias=alias,
                                      stream=config.get("stream", False),
                                      require_observed_draft=config.get("require_observed_draft", False))
                    if database is not None:
                        result.update(database=database.name, database_sha256=legacy.sha256_of(database))
                    if not qualify.record(result, key, tag, run, records, interruptions, done):
                        break
        finally:
            if tag in run["sessions"]:
                launch["proof"] = qualify.pid_counter_proof(output, launch)
                legacy.write_json(run_path, run)
    result = summary(run, done, list(interruptions.glob("*.json")))
    legacy.write_json(output / "summary.json", result)
    return result


def execute(args):
    freeze = load_freeze()
    roster = plan(freeze, args.panel, args.case, first_seed=FIRST_SEED)
    binary, model, identity, env = resolve_runtime(args)
    config = configuration(args, freeze, roster, identity, env)
    if args.preflight_only:
        return {"status": "PASS", "physical_evidence_status": "NOT_RUN", "backend": args.backend,
                "configuration_sha256": digest(config), "freeze_sha256": config["freeze_sha256"],
                "planned": len(roster), "scope": config["scope"], "runtime": identity}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with legacy.output_lock(output):
        return execute_locked(args, config, {**freeze.active, **freeze.controls}, output, binary, model, env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=qualify.ARM, required=True)
    parser.add_argument("--runtime-root", type=Path, help="root with the default MiniCPM5 and backend runtime")
    parser.add_argument("--candidate", choices=CANDIDATES, help="opt into the strict-admission Vulkan profile")
    parser.add_argument("--model", type=Path, help="explicit pinned Q8_0 GGUF for --candidate")
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--port", type=int, choices=range(1024, 65536), metavar="PORT", default=18718)
    parser.add_argument("--panel", choices=("primary", "repeat", "controls"), default="primary")
    parser.add_argument("--case", action="append", default=[], help="limit a diagnostic to explicit frozen IDs")
    parser.add_argument("--batch-size", type=int, help="limit additional case attempts per launch")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stream", action="store_true", help="use the shared proposal budget with streaming")
    parser.add_argument("--require-observed-draft", action="store_true",
                        help="require a prior-turn trusted review before a synthetic draft")
    parser.add_argument("--preflight-only", action="store_true", help="verify identities without launching inference")
    args = parser.parse_args()
    if args.batch_size is not None and args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if args.preflight_only and (args.resume or args.output or args.batch_size):
        parser.error("--preflight-only is read-only")
    if not (args.output or args.preflight_only):
        parser.error("an output directory is required for inference")
    try:
        result = execute(args)
    except (ImportError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(2, f"BLOCKED: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2, "NOT_RUN": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
