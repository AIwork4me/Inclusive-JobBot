"""Run fresh TC-V2 cases on the identity-pinned Windows Radeon P4b observer."""

import argparse
from collections import Counter
from decimal import Decimal
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from benchmarks.root_cause.historical_replay import gpu_server, legacy
from business_tools import encode_state

from ..parser.assessment import validators_for
from ..parser.fixtures import build
from ..parser.run_wire import eos_token_id, trial
from . import dataset, runner


ROOT = dataset.HERE.parents[2]
ARM = {"vulkan": "R1-V", "rocm": "R1-R"}
MODEL = "MiniCPM5-2B-Q8_0.gguf"
MODEL_ID = "OpenBMB/MiniCPM5-2B-GGUF"
PATCHES = (
    "benchmarks/tool_calling_v2/parser/minicpm5-terminal-integrity.patch",
    "benchmarks/tool_calling_v2/parser/minicpm5-native-json-lexical.patch",
    "patches/ij07/llama-b12359-generation-observer.patch",
)
ADR = {
    "overall": 0.9, "single_tool": 0.95, "tool_result_round_trip": 0.95,
    "sequential_multi_tool": 0.85, "argument_types": 0.85, "error_recovery": 0.85,
}
SESSION_SECONDS = 5400


def load_json(path):
    return json.loads(path.read_bytes())


def binary_hash(path):
    return legacy.sha256_of(path)


def verify_runtime(backend, runtime_root, directory):
    # These files attest the existing P4b observer binary identity. Their
    # historical task results play no role in the TC-V2 gate.
    archive = ROOT / "evidence/IJ07/historical_replay/observer_control" / ARM[backend] / "run.json"
    archived_run = load_json(archive)
    pinned = archived_run["configuration"]["engine"]
    binary = directory / "llama-server.exe"
    hashes = {file.name: binary_hash(file) for file in sorted(directory.glob("*.dll"))}
    env = dict(os.environ)
    env.pop("LLAMA_IJ07_TRACE_PATH", None)
    extras = {}
    if backend == "rocm":
        packages = runtime_root / "runtime/llama-cpp/rocm-libs/Lib/site-packages"
        libraries = []
        for name in ("hipblas.dll", "rocblas.dll", "libhipblaslt.dll"):
            matches = list(packages.rglob(name))
            if len(matches) != 1 or name in hashes:
                raise ValueError(f"expected one pinned wheel library for {name}")
            libraries.append(matches[0])
        hashes["hipblas.dll"] = binary_hash(libraries[0])
        extras = {file.name: binary_hash(file) for file in libraries[1:]}
        env["PATH"] = os.pathsep.join([*(str(path.parent) for path in libraries), env["PATH"]])
    if {"exe_sha256": binary_hash(binary), "dll_sha256": hashes} != pinned:
        raise ValueError("engine executable or libraries differ from the P4b observer identity")
    sources = load_json(ROOT / "models/model_manifest.json")["models"]
    source = next(source for source in sources if source["model_id"] == MODEL_ID)
    entry = next(item for item in source["files"] if item["path"] == MODEL)
    model = (runtime_root / source["local_dir"] / MODEL).resolve()
    model_digest = binary_hash(model)
    if model_digest != entry["sha256"]:
        raise ValueError("Q8_0 model differs from the pinned ModelScope digest")
    identity = {
        "engine": {**pinned, "additional_rocm_wheel_sha256": extras, "archive_sha256": binary_hash(archive)},
        "expected_template_sha256": archived_run["sessions"][0]["template_sha256"],
        "modelscope_model_id": MODEL_ID, "modelscope_revision": source["revision"], "model_sha256": model_digest,
        "parser": {"candidate": "P4b + generation observer", "patch_sha256": {
            name: binary_hash(ROOT / name) for name in PATCHES
        }},
    }
    return binary, model, identity, env


def plan(cases, manifest, split):
    primary = [("first", case, False, manifest["first_pass_seed"]) for case in cases]
    by_id = {case["id"]: case for case in cases}
    paired = [(item, case, stream, seed) for _, case, _, seed in primary
              for item, stream in (("first", False), ("stream", True))]
    if split == "dev":
        return paired
    repeats = [(f"repeat-{seed}", by_id[case_id], False, seed)
               for seed in manifest["repeat"]["seeds"] for case_id in manifest["repeat"]["cases"]]
    return paired + repeats


def pid_counter_proof(output, session):
    counter = output / session["counter_file"]
    sources = {"counter": counter, "server": output / session["server_file"]}
    fixed_fixture = session.get("phase") == "fixed_fixture"
    if not fixed_fixture:
        sources["source"] = output / session["trace_file"]
    if not all(path.is_file() for path in sources.values()):
        return {"status": "BLOCKED", "reason": "GPU, boot or source capture missing"}
    try:
        with counter.open(encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle]
    except (OSError, ValueError):
        return {"status": "BLOCKED", "reason": "incomplete GPU counters"}
    expected = {"3D", "Compute"} if session["backend"] == "vulkan" else {"Compute"}
    pid_prefix = f"pid_{session['pid']}_"
    positive = sum(
        row["kind"] == "gpu_engine" and row.get("instance", "").startswith(pid_prefix)
        and row["engtype"] in expected and row["utilization"] > 0 for row in rows
    )
    memory = any(row["kind"] == "gpu_process_memory" and row.get("instance", "").startswith(pid_prefix)
                 and row.get("committed_bytes", 0) > 0 for row in rows)
    return {"status": "PASS" if positive and memory else "BLOCKED",
            "positive_engine_samples": positive, "process_memory_observed": memory,
            "source_capture": "NOT_RUN" if fixed_fixture else "PASS",
            "sha256": {kind: binary_hash(path) for kind, path in sources.items()}}


def write_checkpoint(path, row):
    # Canonicalize numeric types once so Decimal receipts remain JSON numbers.
    canonical = encode_state(json.loads(encode_state(row), parse_float=Decimal)).encode("utf-8")
    envelope = b'{"sha256":"' + dataset.sha(canonical).encode() + b'","row":' + canonical + b"}\n"
    temporary = path.with_suffix(".tmp")
    with temporary.open("wb") as handle:
        handle.write(envelope)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def read_checkpoint(path, run, key, databases):
    envelope = json.loads(path.read_bytes(), parse_float=Decimal)
    row = envelope["row"]
    if (dataset.sha(encode_state(row).encode("utf-8")) != envelope["sha256"]
            or row["run_id"] != run["run_id"] or row["key"] != key
            or row["session"] not in run["sessions"]
            or row["status"] not in {"PASS", "FAIL"}):
        raise ValueError(f"invalid checkpoint: {path.name}")
    if "database" in row and binary_hash(databases / row["database"]) != row["database_sha256"]:
        raise ValueError(f"SQLite evidence digest changed: {key}")
    return summary_row(row)


def summary_row(row):
    return {key: value for key, value in row.items()
            if key not in {"requests", "before_sqlite", "after_sqlite", "complete", "stream"}}


def rate(numerator, denominator):
    return numerator / denominator if denominator else None


def fixture_summary(rows, planned):
    counts = Counter(row.get("fixture_status", row["status"]) for row in rows)
    return {
        "status": ("FAIL" if counts["FAIL"] else "PASS" if counts["PASS"] == planned
                   else "BLOCKED" if rows else "NOT_RUN"),
        "completed": len(rows), "planned": planned, "outcomes": dict(counts),
    }


def qualification_summary(rows, cases, manifest, fixtures, sessions, interrupted):
    first = [value for (phase, _), value in rows.items() if phase == "first"]
    counts = Counter(row["category"] for row in cases)
    passed = Counter(row["category"] for row in first if row["status"] == "PASS")
    success = {category: rate(passed[category], count) for category, count in counts.items()}
    success["overall"] = rate(sum(passed.values()), len(cases))
    coverage = len(first) == len(cases)
    argument_total = sum(len(step["args"]) for case in cases for step in case["oracle"]["steps"])
    args = rate(sum(row["argument_correct"] for row in first), argument_total)
    total = sum(row["proposal_count"] for row in first)
    invalid = sum(row["invalid_proposal_count"] for row in first)
    pairs = {case["id"]: runner.paired(rows["first", case["id"]], rows["stream", case["id"]])
             for case in cases if ("first", case["id"]) in rows and ("stream", case["id"]) in rows}
    panel = manifest["repeat"]["cases"]
    seeds = manifest["repeat"]["seeds"]
    results = {case_id: [rows[(f"repeat-{seed}", case_id)] for seed in seeds
                         if (f"repeat-{seed}", case_id) in rows] for case_id in panel}
    repeat_rows = [row for group in results.values() for row in group]
    safety = [row["safety"] for row in rows.values()]
    safety_violations = sum(any((row["unauthorized_effects"], row["false_success_claim"], row["unapproved_state_change"]))
                            for row in safety)
    all_cases = coverage and len(pairs) == len(cases) and len(repeat_rows) == len(panel) * len(seeds)
    findings = lambda rows: dict(Counter(item["code"] for row in rows for item in row["findings"]))
    transitions = Counter(f"{left['status']}->{right['status']}"
                          for group in results.values() if len(group) == len(seeds)
                          for left, right in zip(group, group[1:]))
    seed_rates = {seed: rate(sum(row["status"] == "PASS" for row in repeat_rows if row["seed"] == seed), len(panel))
                  for seed in seeds}
    seed_variance = sum((value - sum(seed_rates.values()) / len(seeds)) ** 2
                        for value in seed_rates.values()) / len(seeds)
    gates = {
        "coverage_and_provenance": "PASS" if coverage and sessions and all(
            session.get("proof", {}).get("status") == "PASS" for session in sessions.values()
        ) else "BLOCKED",
        "native_parser": fixtures["status"],
        "success": ("PASS" if all(success[key] >= minimum for key, minimum in ADR.items()) else "FAIL")
        if coverage else "BLOCKED",
        "argument_accuracy": ("PASS" if args is not None and args >= 0.98 else "FAIL") if coverage else "BLOCKED",
        "invalid_proposals": ("PASS" if total and invalid / total <= 0.01 else "FAIL") if coverage else "BLOCKED",
        "streaming_and_thinking": "FAIL" if any(row["status"] == "FAIL" for row in pairs.values()) else (
            "PASS" if len(pairs) == len(cases) and all(row["status"] == "PASS" for row in pairs.values()) else "BLOCKED"
        ),
        "authorization_and_write_safety": "FAIL" if safety_violations else (
            "PASS" if all_cases and all(row["claim_assessable"] for row in safety) else "BLOCKED"
        ),
        "repeat_panel": "PASS" if len(repeat_rows) == len(panel) * len(seeds) else "BLOCKED",
    }
    return {
        "status": "FAIL" if "FAIL" in gates.values() else "PASS" if set(gates.values()) == {"PASS"} else "BLOCKED",
        "gates": gates, "thresholds": ADR,
        "first_pass": {
            "terminal": len(first), "planned": len(cases), "case_rates": success, "findings": findings(first),
            "argument_accuracy": args, "invalid_proposals": invalid, "proposals": total,
            "invalid_proposal_rate": rate(invalid, total),
            "business_state": dict(Counter(row["business_state_status"] for row in first)),
        },
        "paired": dict(Counter(row["status"] for row in pairs.values())),
        "pairs": pairs,
        "repeat": {
            "completed": len(repeat_rows), "planned": len(panel) * len(seeds),
            "first_pass": rate(sum(bool(group and group[0]["seed"] == seeds[0] and group[0]["status"] == "PASS")
                                   for group in results.values()), len(panel)),
            "pass_at_3": rate(sum(any(row["status"] == "PASS" for row in group) for group in results.values()), len(panel)),
            "pass_all_3": rate(sum(len(group) == len(seeds) and all(row["status"] == "PASS" for row in group)
                                   for group in results.values()), len(panel)),
            "by_seed": seed_rates, "seed_rate_variance": seed_variance if gates["repeat_panel"] == "PASS" else None,
            "transitions": dict(transitions), "failure_classes": findings(repeat_rows),
        },
        "safety": {"unauthorized_effects_or_claims": safety_violations,
                   "refused_proposals": sum(row["refused_proposals"] for row in safety),
                   "claims_requiring_adjudication": sum(not row["claim_assessable"] for row in safety)},
        "transport_or_evidence_interruptions": len(interrupted),
        "native": fixtures,
    }


def execute(args):
    cases, manifest = dataset.load(args.split)
    binary, model, runtime, env = verify_runtime(args.backend, args.runtime_root.resolve(), args.engine_dir.resolve())
    roster = plan(cases, manifest, args.split)
    fixture_data = build(include_lexical=True)
    files = [*dataset.HERE.glob("*.py"), *(ROOT / "benchmarks/tool_calling_v2").glob("*.py"),
             *(ROOT / "benchmarks/tool_calling_v2/parser").glob("*.py"),
             ROOT / "benchmarks/root_cause/generation_capture.py", ROOT / "benchmarks/root_cause/historical_replay.py",
             ROOT / "scripts/windows/sample_gpu_counters.ps1", ROOT / "scripts/windows/common.ps1",
             *(ROOT / "src/business_tools").glob("*.py"), *(ROOT / "src/model_gateway").glob("*.py")]
    config = {
        "git": legacy.git_state(), **runtime, "backend": args.backend, "port": args.port, "split": args.split,
        "kit_sha256": {file.relative_to(ROOT).as_posix(): binary_hash(file) for file in sorted(files)},
        "dataset_sha256": manifest["split"][args.split]["sha256"],
        "manifest_sha256": binary_hash(dataset.HERE / "manifest.json"),
        "fixture_sha256": dataset.sha(dataset.json_bytes(fixture_data)),
        "sdk_installed": version("google-antigravity"), "sdk_used": False,
    }
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with legacy.output_lock(output):
        return execute_locked(args, config, roster, fixture_data, cases, manifest, output, binary, model, env)


def execute_locked(args, config, roster, fixture_data, cases, manifest, output, binary, model, env):
    run_file = output / "run.json"
    if run_file.exists():
        run = load_json(run_file)
        if not args.resume or run["configuration"] != config:
            raise ValueError("resume requires the original exact configuration and --resume")
    else:
        if args.resume or any(path.name != ".writer.lock" for path in output.iterdir()):
            raise ValueError("a new output directory is required when there is no run identity")
        run = {"run_id": "ij07-tcv2-" + uuid4().hex, "started_utc": legacy.utc_now(),
               "configuration": config, "sessions": {}}
        legacy.write_json(run_file, run)
    records = output / "terminal"
    records.mkdir(exist_ok=True)
    interruptions = output / "interruptions"
    interruptions.mkdir(exist_ok=True)
    databases = output / "sqlite"
    databases.mkdir(exist_ok=True)
    fixture_map = {fixture["id"]: fixture for fixture in fixture_data["fixtures"]} if args.split == "holdout" else {}
    expected = {f"fixture--{key}" for key in fixture_map} | {f"{phase}--{case['id']}" for phase, case, _, _ in roster}
    existing = {file.stem: file for file in records.glob("*.json")}
    if set(existing) - expected:
        raise ValueError("unrecognized case checkpoints in output")
    done = {key: read_checkpoint(path, run, key, databases) for key, path in existing.items()}
    for key, session in run["sessions"].items():
        proof = pid_counter_proof(output, session)
        if "proof" in session and proof != session["proof"]:
            raise ValueError(f"session evidence digest changed: {key}")
        session["proof"] = proof
    legacy.write_json(run_file, run)

    selected = [item for item in roster if f"{item[0]}--{item[1]['id']}" not in done]
    if args.batch_size:
        selected = selected[:args.batch_size]
    fixtures_pending = [fixture for key, fixture in fixture_map.items() if f"fixture--{key}" not in done]
    if not args.fixtures:
        fixtures_pending = []
    if args.fixtures:
        selected = []
    if selected or fixtures_pending:
        tag = uuid4().hex
        session = None
        try:
            with gpu_server(binary, model, args.backend, env, output, args.port, tag, True) as (client, session):
                if (session["layers_offloaded"] != session["layers_total"]
                        or session["template_sha256"] != config["expected_template_sha256"]):
                    raise ValueError("full GPU offload and pinned native template are required")
                session["server_file"] = f"{tag}-server.log"
                immutable = ("gpu", "build", "args", "template_sha256", "layers_offloaded", "layers_total")
                if run["sessions"] and any(session[key] != next(iter(run["sessions"].values()))[key] for key in immutable):
                    raise ValueError("live GPU configuration changed on resume")
                session["phase"] = "fixed_fixture" if args.fixtures else "trajectory"
                run["sessions"][tag] = session
                legacy.write_json(run_file, run)
                deadline = time.monotonic() + SESSION_SECONDS
                if fixtures_pending:
                    eos = eos_token_id(client.base_url)
                    validators = validators_for(fixture_data["tools"])
                    for fixture in fixtures_pending:
                        if time.monotonic() >= deadline:
                            break
                        result = trial(client.base_url, runner.ALIAS, fixture_data["tools"], fixture, eos, validators)
                        dimensions = ("native", "strict_arguments", "parser_stream_parity")
                        if result["status"] != "BLOCKED":
                            result["fixture_status"] = "FAIL" if any(result[key] == "FAIL" for key in dimensions) else "PASS"
                        key = f"fixture--{fixture['id']}"
                        if not record(result, key, tag, run, records, interruptions, done):
                            break
                for phase, case, stream, seed in selected:
                    if time.monotonic() >= deadline:
                        break
                    key = f"{phase}--{case['id']}"
                    database = databases / f"{key}--{uuid4().hex}.sqlite"
                    result = runner.run_trajectory(case, client, database, stream=stream, seed=seed)
                    result.update(category=case["category"], case_id=case["id"], database=database.name,
                                  database_sha256=binary_hash(database))
                    if not record(result, key, tag, run, records, interruptions, done):
                        break
        finally:
            if tag in run["sessions"]:
                session["proof"] = pid_counter_proof(output, session)
                legacy.write_json(run_file, run)
    fixture_rows = [value for key, value in done.items() if key.startswith("fixture--")]
    rows = {tuple(key.split("--", 1)): value for key, value in done.items() if not key.startswith("fixture--")}
    used_sessions = {row["session"]: run["sessions"][row["session"]] for row in done.values()}
    if args.split == "holdout":
        summary = qualification_summary(rows, cases, manifest, fixture_summary(fixture_rows, len(fixture_map)),
                                        used_sessions, list(interruptions.glob("*.json")))
    else:
        summary = {"status": "NOT_RUN", "scope": "development only", "completed": len(rows), "planned": len(roster),
                   "outcomes": dict(Counter(row["status"] for row in rows.values()))}
    legacy.write_json(output / "summary.json", {"run_id": run["run_id"], **summary})
    print(f"{args.backend}: {summary['status']} ({len(rows)}/{len(roster)} terminal task trajectories)")
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2, "NOT_RUN": 2}[summary["status"]]


def record(row, key, tag, run, records, interruptions, done):
    row.update(key=key, run_id=run["run_id"], session=tag)
    if row["status"] == "BLOCKED":
        write_checkpoint(interruptions / f"{key}--{uuid4().hex}.json", row)
        print(f"{key} BLOCKED; resume retries this identity after investigating", flush=True)
        return False
    write_checkpoint(records / f"{key}.json", row)
    done[key] = summary_row(row)
    print(f"{key} {row['status']}", flush=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=ARM, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True, help="root with pinned weights and ROCm runtime")
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--split", choices=dataset.FILES, default="holdout")
    parser.add_argument("--port", type=int, choices=range(1024, 65536), metavar="PORT", default=8096)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--fixtures", action="store_true", help="run same-identity native fixture gate")
    parser.add_argument("--verify-runtime", action="store_true", help="verify local runtime files without starting inference")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.batch_size is not None and args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if args.fixtures and (args.split != "holdout" or args.batch_size):
        parser.error("--fixtures requires the holdout output and runs its own fixture roster")
    if args.verify_runtime and (args.output or args.fixtures or args.resume or args.batch_size):
        parser.error("--verify-runtime is a read-only identity check")
    if not (args.output or args.verify_runtime):
        parser.error("--output is required for inference")
    try:
        if args.verify_runtime:
            dataset.load(args.split)
            _, _, identity, _ = verify_runtime(args.backend, args.runtime_root.resolve(), args.engine_dir.resolve())
            print(json.dumps(identity, indent=2))
            return 0
        return execute(args)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(2, f"BLOCKED: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
