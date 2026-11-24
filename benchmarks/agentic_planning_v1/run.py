"""Run AGENTIC-PLAN-V1 on the pinned local llama.cpp source observer."""

import argparse
from collections import Counter
from contextlib import contextmanager
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import json
import math
import os
import platform
import re
from uuid import uuid4

from benchmarks.competitive_slm import tc_v2_candidate
from benchmarks.root_cause import generation_capture, historical_replay
from benchmarks.tool_calling_v2.parser import run_wire
from model_gateway import openai_protocol, streaming, strict_json

from . import runner
from .freeze import FROZEN, encode, verify

legacy = historical_replay.legacy
ROOT = historical_replay.ROOT
ALIAS = historical_replay.ALIAS
STATUSES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
SESSION_KEYS = ("backend", "gpu", "layers_offloaded", "layers_total", "build", "args", "template_sha256")
RUNTIME_ENV_PREFIXES = ("LLAMA_", "GGML_", "HIP_", "ROCR_", "HSA_", "VK_")
PLANNING_CANDIDATES = ("B", "D", "F", "G")


def digest(value):
    return sha256(encode(value)).hexdigest()


def write_json(path, value):
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.part")
    with temporary.open("xb") as handle:
        handle.write(encode(value))
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def read_json(path):
    return json.loads(path.read_bytes())


def roster(cases, panel, mode, tracks, selected, seed):
    case_ids = [case["case_id"] for case in (panel["cases"] if mode == "repeat" else cases)]
    if selected and (len(set(selected)) != len(selected) or not set(selected).issubset(case_ids)):
        raise ValueError("case selection has duplicates or falls outside the selected panel")
    tracks = sorted(set(tracks))
    indices = panel["seeds"] if mode == "repeat" else [seed]
    return [
        {"trial_id": f"{case_id}-{track}-{index + 1:02}", "case_id": case_id,
         "track": track, "repeat_index": index + 1, "seed": value}
        for case_id in case_ids if not selected or case_id in selected
        for track in tracks for index, value in enumerate(indices)
    ]


class Attempt:
    def __init__(self, path, handle):
        self.path = path
        self.handle = handle

    def write(self, event):
        self.handle.write(encode(event))
        self.handle.flush()
        os.fsync(self.handle.fileno())


class Checkpoint:
    """One durable terminal result per trial, backed by an immutable attempt journal."""

    def __init__(self, output, configuration, *, resume):
        self.output = output
        self.path = output / "run.json"
        self.results = output / "cases"
        self.attempts = output / "attempts"
        self.fingerprint = digest(configuration)
        if self.path.exists():
            self.run = read_json(self.path)
            if (not resume or self.run.get("fingerprint") != self.fingerprint
                    or digest(self.run.get("configuration")) != self.fingerprint):
                raise ValueError("resume requires the exact original run identity")
        else:
            if resume or self.results.exists() or self.attempts.exists() or (output / "summary.json").exists():
                raise ValueError("cannot recover attempts without their original run identity")
            self.run = {"run_id": "ij07-plan-" + uuid4().hex, "fingerprint": self.fingerprint,
                        "configuration": configuration, "sessions": [], "created_utc": legacy.utc_now()}
            write_json(self.path, self.run)
        self.results.mkdir(exist_ok=True)
        self.attempts.mkdir(exist_ok=True)
        self.done = {}
        trials = {trial["trial_id"]: trial for trial in configuration["trials"]}
        for path in self.results.glob("*.json"):
            trial = trials.get(path.stem)
            result = read_json(path)
            self.check_result(trial, result)
            self.done[trial["trial_id"]] = result

    def check_result(self, trial, result):
        payload = {key: value for key, value in result.items() if key != "artifact_sha256"}
        session = result.get("server_session")
        if (trial is None or result.get("trial") != trial or result.get("status") not in STATUSES[:3]
                or result.get("run_id") != self.run["run_id"] or result.get("run_fingerprint") != self.fingerprint
                or type(session) is not int or not 1 <= session <= len(self.run["sessions"])
                or result.get("artifact_sha256") != digest(payload)):
            raise ValueError("invalid trial identity or terminal artifact digest")
        journal = result.get("journal")
        if not isinstance(journal, str) or not re.fullmatch(rf"attempts/{trial['trial_id']}\.[0-9a-f]{{32}}\.jsonl", journal):
            raise ValueError("invalid attempt journal name")
        path = self.output / journal
        if not path.is_file() or result.get("journal_sha256") != legacy.sha256_of(path):
            raise ValueError("invalid attempt journal digest")

    def session(self, launch):
        sessions = self.run["sessions"]
        if sessions and any(launch.get(key) != sessions[0].get(key) for key in SESSION_KEYS):
            raise ValueError("live llama.cpp identity changed across resume")
        sessions.append(launch)
        write_json(self.path, self.run)

    @contextmanager
    def attempt(self, trial):
        path = self.attempts / f"{trial['trial_id']}.{uuid4().hex}.jsonl"
        with path.open("xb") as handle:
            attempt = Attempt(path, handle)
            attempt.write({"kind": "attempt", "trial": trial, "run_id": self.run["run_id"],
                           "configuration_sha256": self.fingerprint, "server_session": len(self.run["sessions"])})
            yield attempt

    def record(self, trial, result, attempt):
        if trial["trial_id"] in self.done:
            raise ValueError("trial already has a terminal record")
        path = self.results / f"{trial['trial_id']}.json"
        if path.exists():
            raise ValueError("terminal artifact already exists")
        row = {**result, "trial": trial, "run_id": self.run["run_id"], "run_fingerprint": self.fingerprint,
               "server_session": len(self.run["sessions"]), "journal": attempt.path.relative_to(self.output).as_posix(),
               "journal_sha256": legacy.sha256_of(attempt.path)}
        row["artifact_sha256"] = digest(row)
        self.check_result(trial, row)
        write_json(path, row)
        self.done[trial["trial_id"]] = row

    def summarize(self):
        trials = self.run["configuration"]["trials"]
        counts = Counter({status: 0 for status in STATUSES})
        by_track = {track: Counter({status: 0 for status in STATUSES}) for track in ("A", "P")}
        for trial in trials:
            result = self.done.get(trial["trial_id"])
            status = result["status"] if result else "NOT_RUN"
            counts[status] += 1
            by_track[trial["track"]][status] += 1
        qualified_launch = bool(self.run["sessions"]) and all(
            session.get("owns_port") is True and session.get("layers_offloaded", 0) > 0
            and isinstance(session.get("gpu"), dict) and session["gpu"].get("architecture") == "gfx1151"
            for session in self.run["sessions"]
        )
        physical_status = "NOT_RUN"
        if qualified_launch and counts["BLOCKED"]:
            physical_status = "BLOCKED"
        elif qualified_launch and not counts["NOT_RUN"]:
            physical_status = "PASS"
        summary = {"run_id": self.run["run_id"], "fingerprint": self.fingerprint,
                   "planned_trials": len(trials), "counts": counts, "by_track": by_track,
                   "physical_execution_status": physical_status}
        write_json(self.output / "summary.json", summary)
        return summary


def load_jsonl(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def model_identity():
    source = next(model for model in read_json(ROOT / "models/model_manifest.json")["models"]
                  if model["model_id"] == "OpenBMB/MiniCPM5-2B-GGUF")
    file = next(file for file in source["files"] if file["path"] == "MiniCPM5-2B-Q8_0.gguf")
    model_path = (ROOT / source["local_dir"] / file["path"]).resolve()
    if not model_path.is_file() or legacy.sha256_of(model_path) != file["sha256"]:
        raise ValueError("MiniCPM5 Q8_0 model file is missing or differs from its ModelScope pin")
    return model_path, {"alias": ALIAS, "repo_id": source["model_id"], "revision": source["revision"],
                        "sha256": file["sha256"], "quantization": "Q8_0"}


def prepare_runtime(args):
    candidate = getattr(args, "candidate", None)
    selected_model = getattr(args, "model", None)
    engine_dir = args.engine_dir.resolve()
    if candidate is None:
        if selected_model is not None:
            raise ValueError("--model requires a strict-admission candidate profile")
        model, identity = model_identity()
        binary, engine, env = historical_replay.engine_runtime(engine_dir, args.backend)
        return model, identity, binary, engine, env, None
    if candidate not in PLANNING_CANDIDATES or selected_model is None or args.backend != "vulkan":
        raise ValueError("strict-admission candidate B, D, F or G requires --model and the Vulkan backend")
    model = selected_model.resolve(strict=True)
    runtime = tc_v2_candidate.verify_runtime(candidate, model, engine_dir)
    artifact = runtime["model"]
    identity = {**artifact, "alias": f"ij07-candidate-{candidate.lower()}",
                "repo_id": artifact["runtime_repo"], "revision": artifact["runtime_revision"],
                "sha256": artifact["model_sha256"]}
    # The admission profile supplies identity and launch checks. Planning retains its own frozen limits.
    profile = {key: value for key, value in runtime.items() if key != "budgets"}
    return model, identity, engine_dir / "llama-server.exe", runtime["engine"], tc_v2_candidate.server_environment(), profile


def source_identity(candidate=False):
    modules = (runner, historical_replay, generation_capture, legacy, run_wire, openai_protocol, streaming, strict_json)
    sources = (Path(__file__), *(Path(module.__file__) for module in modules))
    if candidate:
        sources += (Path(tc_v2_candidate.__file__), *(ROOT / name for name in tc_v2_candidate.SOURCE_PATCHES))
    return {path.resolve().relative_to(ROOT).as_posix(): legacy.sha256_of(path) for path in sources}


def run_benchmark(args):
    manifest = verify(FROZEN)
    cases = load_jsonl(FROZEN / "datasets/holdout.jsonl")
    graphs = {graph["case_id"]: graph for graph in load_jsonl(FROZEN / "task_graphs/holdout.jsonl")}
    public = {case["case_id"]: case for case in cases}
    panel = read_json(FROZEN / "datasets/repeat_panel.json")
    trials = roster(cases, panel, args.panel, list(args.tracks), args.case, args.seed)
    model, identity, binary, engine, env, candidate = prepare_runtime(args)
    alias = identity.get("alias", ALIAS)
    if args.engine_sha256 and engine["exe_sha256"] != args.engine_sha256:
        raise ValueError("llama-server binary digest differs from --engine-sha256")
    try:
        sdk = version("google-antigravity")
    except PackageNotFoundError:
        sdk = None
    settings = {"stream": args.stream, "thinking": args.thinking, "temperature": args.temperature,
                "max_tokens": args.max_tokens}
    environment = {key.upper(): value for key, value in env.items() if key.upper().startswith(RUNTIME_ENV_PREFIXES)}
    configuration = {"engine": engine, "model": identity, "backend": args.backend, "port": args.port,
                     "git": legacy.git_state(), "sources": source_identity(candidate is not None), "python": platform.python_version(),
                     "manifest": manifest, "sdk_installed": sdk, "sdk_used": False, "panel": args.panel,
                     "runtime_environment_sha256": digest(environment),
                     "selection": "diagnostic" if args.case else "complete_panel", "settings": settings, "trials": trials}
    if candidate is not None:
        configuration["candidate_profile"] = candidate
    if args.preflight_only:
        preview = {"configuration_sha256": digest(configuration), "planned_trials": len(trials),
                   "first_trial": trials[0], "engine": engine, "model": identity, "backend": args.backend,
                   "physical_execution_status": "NOT_RUN"}
        if candidate is not None:
            preview["candidate_profile"] = candidate
        return preview
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with legacy.output_lock(output):
        checkpoint = Checkpoint(output, configuration, resume=args.resume)
        pending = [trial for trial in trials if trial["trial_id"] not in checkpoint.done]
        if args.batch_size:
            pending = pending[:args.batch_size]
        if pending:
            tag = uuid4().hex
            with historical_replay.gpu_server(binary, model, args.backend, env, output, args.port, tag, True, alias) as (client, launch):
                if candidate is not None:
                    tc_v2_candidate.verify_launch(launch, candidate)
                checkpoint.session(launch)
                for trial in pending:
                    case = public[trial["case_id"]]
                    with checkpoint.attempt(trial) as attempt:
                        result = runner.run_trajectory(case, graphs[case["case_id"]], client, track=trial["track"],
                                                       seed=trial["seed"], alias=alias, journal=attempt.write, **settings)
                        checkpoint.record(trial, result, attempt)
                    print(f"{trial['trial_id']} {result['status']}", flush=True)
        return checkpoint.summarize()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-dir", required=True, type=Path)
    parser.add_argument("--engine-sha256", help="Require this exact launcher SHA-256 at initial launch and resume")
    parser.add_argument("--backend", required=True, choices=("vulkan", "rocm"))
    parser.add_argument("--candidate", choices=PLANNING_CANDIDATES, help="Use a strict-admission Vulkan candidate instead of MiniCPM5")
    parser.add_argument("--model", type=Path, help="Local Q8_0 GGUF path for --candidate")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18717)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--preflight-only", action="store_true", help="Verify frozen inputs and binary pins without launching")
    parser.add_argument("--batch-size", type=int, default=0, help="Process at most this many pending trials per launch")
    parser.add_argument("--tracks", choices=("A", "P", "AP"), default="AP")
    parser.add_argument("--panel", choices=("primary", "repeat"), default="primary")
    parser.add_argument("--case", action="append", default=[], help="Limit a diagnostic to specified case IDs")
    parser.add_argument("--seed", type=int, default=41909, help="Seed for the primary panel")
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--thinking", action="store_true")
    parser.add_argument("--stream", action="store_true")
    args = parser.parse_args()
    if (not 1 <= args.port <= 65535 or args.batch_size < 0 or not 1 <= args.max_tokens <= 2048
            or not 0 <= args.seed < 2**32 - 1 or not math.isfinite(args.temperature) or not 0 <= args.temperature <= 2):
        parser.error("invalid port, batch limit, seed, token limit or temperature")
    try:
        print(json.dumps(run_benchmark(args), indent=2, ensure_ascii=False))
    except (ImportError, OSError, KeyError, ValueError) as failure:
        parser.exit(2, f"BLOCKED: {failure}\n")


if __name__ == "__main__":
    main()
