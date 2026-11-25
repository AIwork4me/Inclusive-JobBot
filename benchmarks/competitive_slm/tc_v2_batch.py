"""Execute one competitive TC-V2 roster per run with a shared Vulkan server."""

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import http.client
import json
from pathlib import Path
import re
import subprocess
import time
from uuid import uuid4

from business_tools import encode_state

from . import tc_v2_candidate as candidate
from .statistics import digest, frozen_suite


dataset, legacy, qualify, runner = candidate.dataset, candidate.legacy, candidate.qualify, candidate.runner
gpu_server = candidate.gpu_server
PANELS = {"full": ("first", "stream", "repeat"), "primary": ("first",), "stream": ("stream",), "repeat": ("repeat",)}
BATCH_CANDIDATES = ("B", "D", "F", "G")
STATUSES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
ASSESSED = frozenset(STATUSES[:2])
SESSION_IDENTITY = ("backend", "gpu", "build", "args", "template_sha256", "layers_offloaded", "layers_total")
RUNTIME_ENV_PREFIXES = ("LLAMA_", "GGML_", "HIP_", "ROCR_", "HSA_", "VK_")
RUN_SCOPE = "competitive TC-V2 frozen roster"
PC_S_SCOPE = "Atlas PC-S TC-V2 development diagnostic"
PC_S_ROSTER = Path(__file__).resolve().parents[2] / "atlas/benchmarks/pc_s_roster.json"


def pc_s_roster():
    from scripts.tools.atlas_reference_panel import create

    frozen = json.loads(PC_S_ROSTER.read_bytes())
    if frozen != create():
        raise ValueError("PC-S diagnostic roster differs from its frozen definition")
    panel = frozen["tc_v2"]
    cases, manifest = dataset.load(panel["split"])
    by_id = {case["id"]: case for case in cases}
    manifest_sha256 = legacy.sha256_of(dataset.HERE / "manifest.json")
    selected = [case_id for group in panel["selection_by_stratum"].values() for case_id in group]
    roster = [{
        "key": f"first--{case_id}", "case_id": case_id, "category": by_id[case_id]["category"],
        "split": panel["split"], "phase": "first", "stream": False, "seed": manifest["first_pass_seed"],
        "repeat_index": None, "attempt": 1, "pairing_sha256": digest(by_id[case_id]),
        "dataset_sha256": panel["dataset_sha256"], "manifest_sha256": manifest_sha256,
    } for case_id in selected]
    return {case_id: by_id[case_id] for case_id in selected}, roster


def make_roster(panel):
    if panel == "pc-s":
        return pc_s_roster()
    cases, manifest = dataset.load("holdout")
    by_id = {case["id"]: case for case in cases}
    profile = frozen_suite("TC-V2")
    pairing = {row["case_id"]: row["pairing_sha256"] for row in profile["cases"]}
    if {case_id: digest(case) for case_id, case in by_id.items()} != pairing:
        raise ValueError("roster identities differ from the frozen TC-V2 statistics suite")
    dataset_sha256 = manifest["split"]["holdout"]["sha256"]
    manifest_sha256 = legacy.sha256_of(dataset.HERE / "manifest.json")
    roster = []
    for phase in PANELS[panel]:
        repetitions = enumerate(manifest["repeat"]["seeds"], 1) if phase == "repeat" else [(None, manifest["first_pass_seed"])]
        case_ids = manifest["repeat"]["cases"] if phase == "repeat" else list(by_id)
        for index, seed in repetitions:
            tag = f"repeat-{index}" if phase == "repeat" else phase
            roster.extend({
                "key": f"{tag}--{case_id}", "case_id": case_id, "category": by_id[case_id]["category"],
                "split": "holdout", "phase": phase, "stream": phase == "stream", "seed": seed,
                "repeat_index": index, "attempt": 1, "pairing_sha256": pairing[case_id],
                "dataset_sha256": dataset_sha256, "manifest_sha256": manifest_sha256,
            } for case_id in case_ids)
    return by_id, roster


def read_checkpoint(path):
    envelope = json.loads(path.read_bytes(), parse_float=Decimal)
    row = envelope["row"]
    if dataset.sha(encode_state(row).encode("utf-8")) != envelope["sha256"]:
        raise ValueError(f"checkpoint row digest changed: {path.name}")
    return row


def _identity(run, trial, tag):
    return {
        **trial, "run_id": run["run_id"], "session": tag,
        "configuration_sha256": run["configuration_sha256"],
        "run_configuration_sha256": run["run_configuration_sha256"],
        "database": f"{trial['key']}.sqlite",
    }


def _session_artifacts(output, tag, launch):
    names = {"launch": f"{tag}-launch.json", "boot": f"{tag}-server.log",
             "trace": launch["trace_file"], "counters": launch["counter_file"]}
    if any(not isinstance(name, str) or Path(name).name != name or not name.startswith(tag + "-")
           for name in names.values()):
        raise ValueError("unsafe or unexpected live-session artifact filename")
    paths = {key: output / name for key, name in names.items()}
    hashes = {key: legacy.sha256_of(path) for key, path in paths.items() if path.is_file()}
    return paths, hashes


def _complete_session(output, tag, launch, uninterrupted):
    paths, hashes = _session_artifacts(output, tag, launch)
    gpu_observed = False
    if uninterrupted and paths["counters"].is_file():
        try:
            gpu_observed = candidate.verify_gpu({"gpu_launch": paths["launch"], "gpu_counters": paths["counters"]}, "vulkan")
        except (OSError, ValueError, KeyError):
            pass
    return {"status": "PASS" if gpu_observed and hashes.keys() == paths.keys() else "BLOCKED",
            "artifacts_sha256": hashes}


def _checkpoint_hashes(attempt, trajectory):
    result = {"attempt": legacy.sha256_of(attempt)}
    if trajectory.is_file():
        result["trajectory"] = legacy.sha256_of(trajectory)
    return result


def read_attempts(output, run):
    attempts = {file.stem: file for file in (output / "attempts").glob("*.json")}
    records = {file.stem: file for file in (output / "trajectories").glob("*.json")}
    roster = {trial["key"]: trial for trial in run["run_configuration"]["roster"]}
    if set(attempts) - roster.keys() or set(records) - attempts.keys():
        raise ValueError("unplanned attempt or trajectory without its first-attempt journal")
    for tag, launch in run["sessions"].items():
        if re.fullmatch("[0-9a-f]{32}", tag) is None:
            raise ValueError("invalid stored session identity")
        candidate.verify_launch(launch, run["configuration"])
        proof = launch.get("proof")
        if proof is not None:
            _, hashes = _session_artifacts(output, tag, launch)
            if proof["artifacts_sha256"] != hashes:
                raise ValueError(f"session artifact digest changed: {tag}")

    rows, checkpoint_hashes = {}, defaultdict(dict)
    for key, path in attempts.items():
        intent = read_checkpoint(path)
        tag = intent["session"]
        if tag not in run["sessions"] or any(intent.get(field) != value for field, value in
                                             _identity(run, roster[key], tag).items()):
            raise ValueError(f"first-attempt journal differs from run and roster: {key}")
        hashes = _checkpoint_hashes(path, output / "trajectories" / f"{key}.json")
        checkpoint_hashes[tag][key] = hashes
        if key not in records:
            rows[key] = {**roster[key], "status": "BLOCKED", "reason": "no durable first-attempt trajectory"}
            continue
        row = read_checkpoint(records[key])
        if (any(row.get(field) != value for field, value in _identity(run, roster[key], tag).items())
                or row["attempt_sha256"] != hashes["attempt"]
                or row["trajectory_status"] not in (*ASSESSED, "BLOCKED")):
            raise ValueError(f"trajectory identity differs from first-attempt journal: {key}")
        if legacy.sha256_of(output / "sqlite" / intent["database"]) != row["database_sha256"]:
            raise ValueError(f"SQLite checkpoint digest changed: {key}")
        saved = {field: value for field, value in row.items() if field not in ("requests", "before_sqlite", "after_sqlite")}
        source_proved = saved["source_capture_status"] == "PASS"
        session_proved = run["sessions"][tag].get("proof", {}).get("status") == "PASS"
        rows[key] = {**saved, "status": saved["trajectory_status"] if source_proved and session_proved else "BLOCKED"}
    for tag, launch in run["sessions"].items():
        if "proof" in launch and checkpoint_hashes[tag] != launch["proof"]["checkpoints_sha256"]:
            raise ValueError(f"sealed session checkpoint inventory changed: {tag}")
    return rows


def _count(outcomes):
    measured = Counter(outcomes)
    total = sum(measured.values())
    passes = measured["PASS"]
    unresolved = measured["BLOCKED"] + measured["NOT_RUN"]
    return {
        "planned": total, "assessed": total - unresolved,
        "status_counts": {status: measured[status] for status in STATUSES},
        "pass_rate": passes / total if not unresolved else None,
        "pass_rate_bounds": [passes / total, (passes + unresolved) / total],
    }


def summarize(run, records):
    roster = run["run_configuration"]["roster"]
    by_phase = defaultdict(list)
    selected_by_case = defaultdict(dict)
    for trial in roster:
        row = records.get(trial["key"], trial | {"status": "NOT_RUN"})
        by_phase[trial["phase"]].append(row)
        selected_by_case[trial["case_id"]][trial["phase"], trial["repeat_index"]] = row
    phase_summary = {}
    for phase, rows in by_phase.items():
        categories = defaultdict(list)
        for row in rows:
            categories[row["category"]].append(row["status"])
        phase_summary[phase] = {**_count(row["status"] for row in rows),
                                "categories": {key: _count(values) for key, values in sorted(categories.items())}}
    paired = []
    repeated = []
    for phases in selected_by_case.values():
        primary, stream = phases.get(("first", None)), phases.get(("stream", None))
        if primary is not None and stream is not None:
            statuses = (primary["status"], stream["status"])
            if "BLOCKED" in statuses:
                paired.append("BLOCKED")
            elif "NOT_RUN" in statuses:
                paired.append("NOT_RUN")
            else:
                paired.append(runner.paired(primary, stream)["status"])
        if ("repeat", 1) in phases:
            repeated.append([phases["repeat", index]["status"] for index in range(1, 4)])
    repeat_summary = None
    if repeated:
        complete = [group for group in repeated if set(group) <= ASSESSED]
        repeat_summary = {
            "planned_groups": len(repeated), "assessed_groups": len(complete),
            "pass_at_3": sum("PASS" in group for group in complete) / len(repeated) if len(complete) == len(repeated) else None,
            "pass_all_3": sum(set(group) == {"PASS"} for group in complete) / len(repeated) if len(complete) == len(repeated) else None,
        }
    coverage = _count(row["status"] for rows in by_phase.values() for row in rows)
    return {
        "run_id": run["run_id"], "run_configuration_sha256": run["run_configuration_sha256"],
        "configuration_sha256": run["configuration_sha256"], "scope": run["scope"],
        "coverage_status": ("PASS" if coverage["planned"] == coverage["assessed"] else
                            "NOT_RUN" if not records and not run["sessions"] else "BLOCKED"),
        **coverage, "phases": phase_summary, "streaming_pairs": _count(paired) if paired else None,
        "repeat": repeat_summary,
    }


def _run_pending(args, run, pending, cases, output, engine_dir, model, env):
    tag = uuid4().hex
    alias = f"ij07-candidate-{run['configuration']['candidate'].lower()}"
    launch = None
    uninterrupted = False
    attempted = []
    stop = None
    try:
        with gpu_server(engine_dir / "llama-server.exe", model, "vulkan", env, output, args.port,
                        tag, True, alias=alias) as (client, live):
            candidate.verify_launch(live, run["configuration"])
            if run["sessions"] and any(live[key] != next(iter(run["sessions"].values()))[key] for key in SESSION_IDENTITY):
                raise ValueError("live server identity changed across resume")
            wire = candidate.BudgetedCapture(args.port, client.trace_path, alias)
            launch = {**live, "status": "PASS"}
            _session_artifacts(output, tag, launch)
            legacy.write_json(output / f"{tag}-launch.json", launch)
            run["sessions"][tag] = launch
            legacy.write_json(output / "run.json", run)
            deadline = time.monotonic() + qualify.SESSION_SECONDS - candidate.BUDGETS["wall_clock_seconds_per_case"]
            try:
                for trial in pending:
                    if time.monotonic() >= deadline:
                        break
                    attempted.append(trial["key"])
                    if not _run_trial(run, trial, tag, cases, wire, output):
                        break
            except KeyboardInterrupt as failure:
                stop = failure
        uninterrupted = True
    finally:
        if tag in run["sessions"]:
            proof = _complete_session(output, tag, launch, uninterrupted)
            proof["checkpoints_sha256"] = {
                key: _checkpoint_hashes(output / "attempts" / f"{key}.json", output / "trajectories" / f"{key}.json")
                for key in attempted if (output / "attempts" / f"{key}.json").is_file()
            }
            launch["proof"] = proof
            legacy.write_json(output / "run.json", run)
    if stop is not None:
        raise stop


def _run_trial(run, trial, tag, cases, wire, output):
    fields = _identity(run, trial, tag)
    key = trial["key"]
    attempt_file = output / "attempts" / f"{key}.json"
    trajectory_file = output / "trajectories" / f"{key}.json"
    database = output / "sqlite" / fields["database"]
    if attempt_file.exists() or trajectory_file.exists() or database.exists():
        raise ValueError(f"prior attempt or SQLite state exists: {key}")
    qualify.write_checkpoint(attempt_file, {**fields, "started_utc": legacy.utc_now()})
    wire.begin_trial()
    result = runner.run_trajectory(cases[trial["case_id"]], wire, database, stream=trial["stream"], seed=trial["seed"])
    captured = (
        not result.get("transport_failure") and not result.get("source_evidence_missing") and bool(result["requests"])
        and all(row["source_generation"].get("status") != "BLOCKED" for row in result["requests"])
    )
    trajectory_status = result.pop("status")
    qualify.write_checkpoint(trajectory_file, {
        **result, **fields, "trajectory_status": trajectory_status, "budget_error": wire.budget_error,
        "source_capture_status": "PASS" if captured else "BLOCKED",
        "attempt_sha256": legacy.sha256_of(attempt_file), "database_sha256": legacy.sha256_of(database),
        "native_proposal_count_scope": ("requires independent native trace audit" if result["native_parser_rejected"]
                                        else "observed wire proposals"),
    })
    print(f"{key}: trajectory {trajectory_status}; session proof pending", flush=True)
    return trajectory_status in ASSESSED and captured


def execute_locked(args, configuration, cases, roster, output, engine_dir, model, env, *, scope=RUN_SCOPE):
    run_file = output / "run.json"
    config_sha = digest(configuration)
    run_configuration = {
        "scope": scope, "arm_configuration_sha256": config_sha, "port": args.port, "roster": roster,
        "environment_sha256": digest({key.upper(): value for key, value in env.items()
                                      if key.upper().startswith(RUNTIME_ENV_PREFIXES)}),
    }
    fingerprint = digest(run_configuration)
    if run_file.exists():
        run = candidate.read_json(run_file)
        if (not args.resume or run.get("scope") != scope or run.get("configuration_sha256") != config_sha
                or run.get("configuration") != configuration or run.get("run_configuration_sha256") != fingerprint
                or run.get("run_configuration") != run_configuration):
            raise ValueError("resume requires the exact original competitive roster configuration")
    else:
        if args.resume or any(path.name != ".writer.lock" for path in output.iterdir()):
            raise ValueError("batch starts in a fresh output directory")
        run = {
            "run_id": "ij07-competitive-tcv2-roster-" + uuid4().hex, "started_utc": legacy.utc_now(),
            "scope": scope, "evidence_class": "local_model", "configuration": configuration,
            "configuration_sha256": config_sha, "run_configuration": run_configuration,
            "run_configuration_sha256": fingerprint, "sessions": {},
        }
        legacy.write_json(run_file, run)
    for name in ("attempts", "trajectories", "sqlite"):
        (output / name).mkdir(exist_ok=True)
    measured = read_attempts(output, run)
    pending = [trial for trial in roster if trial["key"] not in measured]
    if args.batch_size is not None:
        pending = pending[:args.batch_size]
    if pending:
        _run_pending(args, run, pending, cases, output, engine_dir, model, env)
        measured = read_attempts(output, run)
    result = summarize(run, measured)
    legacy.write_json(output / "summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=(*BATCH_CANDIDATES, "H"), required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--panel", choices=(*PANELS, "pc-s"), default="full")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--batch-size", type=int, help="additional first attempts per server invocation")
    parser.add_argument("--verify-runtime", action="store_true", help="verify identities and roster without inference")
    parser.add_argument("--port", type=int, choices=range(1024, 65536), default=8102, metavar="PORT")
    args = parser.parse_args()
    diagnostic = args.panel == "pc-s"
    if diagnostic != (args.candidate == "H"):
        parser.error("candidate H is reserved for the pc-s panel, which requires H")
    scope = PC_S_SCOPE if diagnostic else RUN_SCOPE
    if args.batch_size is not None and args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if args.verify_runtime and (args.output or args.resume or args.batch_size is not None):
        parser.error("--verify-runtime is read-only")
    if not (args.verify_runtime or args.output):
        parser.error("inference requires an output directory")
    try:
        candidate.check_shared_limits()
        model, engine = args.model.resolve(strict=True), args.engine_dir.resolve(strict=True)
        runtime = candidate.verify_runtime(args.candidate, model, engine)
        cases, roster = make_roster(args.panel)
        extra_files = (Path(__file__), PC_S_ROSTER) if diagnostic else (Path(__file__),)
        configuration = candidate.build_configuration(
            runtime, roster[0]["dataset_sha256"], roster[0]["manifest_sha256"], extra_files=extra_files,
        )
        if args.verify_runtime:
            print(json.dumps({"identity_check": "PASS", "inference": "NOT_RUN",
                              "scope": scope, "candidate": args.candidate, "planned": len(roster),
                              "roster_sha256": digest(roster), "configuration_sha256": digest(configuration)}, indent=2))
            return 0
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        with legacy.output_lock(output):
            result = execute_locked(
                args, configuration, cases, roster, output, engine, model, candidate.server_environment(), scope=scope,
            )
    except (OSError, ValueError, KeyError, ImportError, http.client.HTTPException, subprocess.SubprocessError) as failure:
        parser.exit(2, f"BLOCKED: {failure}\n")
    print(f"{args.candidate} {args.panel}: {result['coverage_status']} ({result['assessed']}/{result['planned']} assessed)")
    return 0 if result["coverage_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
