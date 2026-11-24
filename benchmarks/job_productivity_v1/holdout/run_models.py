"""Run one JOB-V1 model treatment on the pinned local Radeon Vulkan stack."""

from argparse import ArgumentParser
from collections import Counter
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from benchmarks.root_cause import historical_replay
from benchmarks.tool_calling_v2.holdout import qualify

from .dataset import BUDGET, TREATMENTS, digest, load
from .model_arms import ARMS, FIRST_SEED, run_case
from .run_f import ROOT, create_plan


legacy = historical_replay.legacy
SESSION_FIELDS = ("backend", "gpu", "build", "args", "template_sha256", "layers_offloaded", "layers_total")
STATUS = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
QWEN_CONFIG = ROOT / "configs/qwen3_8b_reference.json"
QWEN_ADMISSION = ROOT / "evidence/IJ07/model_identity/admission_strict/H/report.json"


def runtime(args):
    root = args.runtime_root.resolve()
    binary, model, pinned, env = qualify.verify_runtime("vulkan", root, args.engine_dir.resolve())
    alias = historical_replay.ALIAS
    if args.arm == "E":
        config = qualify.load_json(QWEN_CONFIG)
        previous = qualify.load_json(QWEN_ADMISSION)
        model = (root / ".tools/models/Qwen3-8B-GGUF" / config["filename"]).resolve()
        if model.stat().st_size != config["size"] or legacy.sha256_of(model) != config["sha256"]:
            raise ValueError("Qwen3-8B model file differs from its exact Q8_0 pin")
        if previous["gpu"]["backend"] != "vulkan":
            raise ValueError("Qwen3-8B template evidence is missing its admitted Vulkan identity")
        pinned = {**pinned, "expected_template_sha256": previous["gpu"]["template_sha256"],
                  "modelscope_model_id": config["modelscope_id"], "modelscope_revision": config["modelscope_revision"],
                  "model_sha256": config["sha256"], "model_admission_sha256": legacy.sha256_of(QWEN_ADMISSION),
                  "config_sha256": legacy.sha256_of(QWEN_CONFIG)}
        alias = config["alias"]
    return binary, model, alias, pinned, env


def configuration(args, freeze, roster, pinned, alias, env):
    inventory = [*Path(__file__).parent.glob("*.py"), *(ROOT / "src/model_gateway").glob("*.py"),
                 *(ROOT / "src/business_tools").glob("*.py"), *(ROOT / "src/skill_engine").glob("*.py"),
                 *(ROOT / "src/sop_engine").glob("*.py"), *(ROOT / "src/audit").glob("*.py"),
                 *(ROOT / "skills").glob("*/*.yaml"), *(ROOT / "skills").glob("*/SKILL.md"),
                 ROOT / "benchmarks/tool_calling_v2/holdout/qualify.py", ROOT / "benchmarks/tool_calling_v2/oracle.py",
                 ROOT / "benchmarks/root_cause/historical_replay.py", ROOT / "benchmarks/root_cause/generation_capture.py",
                 ROOT / "scripts/windows/sample_gpu_counters.ps1", ROOT / "benchmarks/tool_calling/runner/run_benchmark.py"]
    env_select = ("LLAMA_", "GGML_", "VK_")
    return {**pinned, "arm": args.arm, "treatment": TREATMENTS[args.arm], "model_alias": alias, "backend": "vulkan",
            "scope": "diagnostic" if args.case else "complete_panel", "panel": args.panel, "port": args.port,
            "freeze_sha256": freeze.manifest["freeze_sha256"], "roster": roster, "first_seed": FIRST_SEED,
            "limits": BUDGET, "git": legacy.git_state(), "sdk_installed": version("google-antigravity"), "sdk_used": False,
            "runtime_environment_sha256": digest({key: value for key, value in env.items()
                                                   if key.upper().startswith(env_select)}),
            "source_sha256": {path.relative_to(ROOT).as_posix(): legacy.sha256_of(path) for path in sorted(inventory)}}


def summarize(run, rows, blocked):
    config = run["configuration"]
    roster = config["roster"]
    counts = Counter(dict.fromkeys(STATUS, 0))
    for key in roster:
        counts[rows[key]["status"] if key in rows else "BLOCKED" if key in blocked else "NOT_RUN"] += 1
    proof = all(run["sessions"][row["session"]].get("proof", {}).get("status") == "PASS" for row in rows.values())
    physics = "PASS" if rows and proof else "BLOCKED" if rows or blocked else "NOT_RUN"
    status = ("BLOCKED" if physics == "BLOCKED" or counts["BLOCKED"] or counts["NOT_RUN"]
              else "FAIL" if counts["FAIL"] else "PASS")
    return {"status": status, "run_id": run["run_id"], "configuration_sha256": run["fingerprint"],
            "arm": config["arm"], "scope": config["scope"], "panel": config["panel"], "outcomes": dict(counts),
            "physical_evidence_status": physics, "synthetic_world": True, "sdk_used": False,
            "terminal_rows": len(rows), "planned_rows": len(roster),
            "completed_business_tasks": sum(row["completed"] for row in rows.values()),
            "first_pass_successes": sum(row["first_pass_success"] for row in rows.values()),
            "recovered_successes": sum(row["recovered_after_rejection"] for row in rows.values()),
            "model_requests": sum(row["model_calls"] for row in rows.values())}


def execute_locked(args, output, cases, config, binary, model, alias, env):
    run_path = output / "run.json"
    roster = config["roster"]
    fingerprint = digest(config)
    if run_path.exists():
        run = qualify.load_json(run_path)
        if not args.resume or run["fingerprint"] != fingerprint or digest(run["configuration"]) != fingerprint:
            raise ValueError("resume requires the exact original JOB-V1 model identity")
    else:
        if args.resume or any(path.name != ".writer.lock" for path in output.iterdir()):
            raise ValueError("a fresh output directory is required for a new run")
        run = {"run_id": "ij07-job-" + args.arm.lower() + "-" + uuid4().hex, "configuration": config,
               "fingerprint": fingerprint, "sessions": {}, "started_utc": legacy.utc_now()}
        legacy.write_json(run_path, run)
    records, interruptions, databases = (output / name for name in ("cases", "interruptions", "sqlite"))
    for directory in (records, interruptions, databases):
        directory.mkdir(exist_ok=True)
    if any(path.stem not in roster for path in records.glob("*.json")):
        raise ValueError("terminal artifact is outside the requested frozen roster")
    rows = {path.stem: qualify.read_checkpoint(path, run, path.stem, databases) for path in records.glob("*.json")}
    for key, row in rows.items():
        case = cases[roster[key]["case_id"]]
        if (row["arm"] != args.arm or row["pairing_sha256"] != case.plan["pairing_sha256"]
                or row["case_id"] != case.plan["case_id"] or row["trial"] != roster[key]):
            raise ValueError("terminal pairing identity differs from frozen roster")
    for tag, session in run["sessions"].items():
        verified = qualify.pid_counter_proof(output, session)
        if "proof" in session and session["proof"] != verified:
            raise ValueError(f"physical evidence changed: {tag}")
        session["proof"] = verified

    pending = [key for key in roster if key not in rows]
    if args.batch_size:
        pending = pending[:args.batch_size]
    if pending:
        tag = uuid4().hex
        try:
            with historical_replay.gpu_server(binary, model, "vulkan", env, output, args.port, tag, True, alias=alias) as (client, launch):
                if (launch["layers_offloaded"] != launch["layers_total"]
                        or launch["template_sha256"] != config["expected_template_sha256"]):
                    raise ValueError("live full offload or native template differs from the runtime pin")
                if run["sessions"] and any(launch[key] != next(iter(run["sessions"].values()))[key] for key in SESSION_FIELDS):
                    raise ValueError("live runtime changed on resume")
                launch["server_file"] = f"{tag}-server.log"
                run["sessions"][tag] = launch
                legacy.write_json(run_path, run)
                for key in pending:
                    trial = roster[key]
                    seed = trial["trial_seed"] if trial["trial_seed"] is not None else FIRST_SEED
                    database = databases / f"{key}--{uuid4().hex}.sqlite"
                    row = run_case(cases[trial["case_id"]], database, args.arm, alias, client, seed=seed)
                    row.update(trial=trial, database=database.name, database_sha256=legacy.sha256_of(database))
                    if trial["trial_seed"] is not None:
                        row["trial_seed"] = trial["trial_seed"]
                    if not qualify.record(row, key, tag, run, records, interruptions, rows):
                        break
        finally:
            if tag in run["sessions"]:
                launch["proof"] = qualify.pid_counter_proof(output, launch)
                legacy.write_json(run_path, run)
    blocked = {path.stem.rsplit("--", 1)[0] for path in interruptions.glob("*.json")}
    summary = summarize(run, rows, blocked)
    legacy.write_json(output / "summary.json", summary)
    return summary


def execute(args):
    freeze = load()
    roster = create_plan(freeze, args.panel, args.case)
    binary, model, alias, pinned, env = runtime(args)
    config = configuration(args, freeze, roster, pinned, alias, env)
    if args.preflight_only:
        return {"status": "PASS", "physical_evidence_status": "NOT_RUN", "planned_rows": len(roster),
                "arm": args.arm, "alias": alias, "model_sha256": pinned["model_sha256"],
                "modelscope_revision": pinned["modelscope_revision"], "configuration_sha256": digest(config)}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with legacy.output_lock(output):
        return execute_locked(args, output, freeze.cases, config, binary, model, alias, env)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, choices=ARMS)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--engine-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--port", type=int, choices=range(1024, 65536), metavar="PORT", default=18719)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--panel", choices=("primary", "repeat"), default="primary")
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.batch_size is not None and args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if (args.preflight_only and (args.output or args.resume or args.batch_size)) or not (args.output or args.preflight_only):
        parser.error("give an output path for inference or use --preflight-only for a read-only check")
    try:
        result = execute(args)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(2, f"BLOCKED: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2, "NOT_RUN": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
