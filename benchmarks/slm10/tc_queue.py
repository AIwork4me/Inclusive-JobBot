"""Dispatch and recover the priority TC-V3 physical queue on the Radeon."""

import argparse
from collections import Counter
import gzip
from importlib.metadata import version
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from google.antigravity import bin as sdk_bin

from audit import write_evidence
from benchmarks.competitive_slm.tc_v2_candidate import server_environment, verify_launch, verify_runtime
from benchmarks.root_cause.historical_replay import gpu_server, legacy
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT, canonical
from scripts.tools.verify_ij06_evidence import verify_gpu

from .admission import archive, git_head
from .mechanical_registry import REGISTRY, assess_trial, require_registry
from .native_diagnostics import BASE_ENGINE, OBSERVER_ENGINE, OBSERVER_HASHES
from .p0_evidence import require_development
from .portable import portable
from .tc_execution import execute_trial, records
from .tc_v3 import HERE, verify_freeze

PRIORITY = ("A", "B", "D")
SOURCE_FILES = ("wire_boundary.py", "tc_execution.py", "native_diagnostics.py", "tc_queue.py")


def connect(root, roster, identity):
    db = sqlite3.connect(root / "queue.sqlite", timeout=30)
    db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=FULL;
        CREATE TABLE IF NOT EXISTS enrollment(singleton INTEGER PRIMARY KEY CHECK(singleton=1), identity TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS trials(
            trial_id TEXT PRIMARY KEY, candidate TEXT NOT NULL, ordinal INTEGER NOT NULL UNIQUE,
            session TEXT, seal_sha256 TEXT);
    """)
    with db:
        db.execute("BEGIN IMMEDIATE")
        seal = db.execute("SELECT identity FROM enrollment WHERE singleton=1").fetchone()
        payload = canonical(identity).decode()
        if seal is None:
            db.execute("INSERT INTO enrollment VALUES(1,?)", (payload,))
            db.executemany("INSERT INTO trials(trial_id,candidate,ordinal) VALUES(?,?,?)",
                           ((row["trial_id"], row["candidate"], n) for n, row in enumerate(roster)))
        elif seal[0] != payload:
            raise ValueError("queue already enrolled with a different immutable configuration")
    expected = [(row["trial_id"], row["candidate"], n) for n, row in enumerate(roster)]
    if db.execute("SELECT trial_id,candidate,ordinal FROM trials ORDER BY ordinal").fetchall() != expected:
        raise ValueError("enrolled queue roster differs from the freeze")
    return db


def seal_session(root, folder, db):
    session = folder.name
    reservations = db.execute("SELECT trial_id,seal_sha256 FROM trials WHERE session=? ORDER BY ordinal",
                              (session,)).fetchall()
    if not reservations or all(sha is not None for _, sha in reservations):
        return
    identity = json.loads((folder / "identity.json").read_bytes())
    launch = folder / "launch.json"
    if not launch.is_file():
        raise ValueError("reserved physical trial has no recoverable launch record")
    metadata = json.loads(launch.read_bytes())
    counters = folder / metadata["counter_file"]
    gpu_ok = counters.is_file() and verify_gpu({"gpu_launch": launch, "gpu_counters": counters}, "vulkan")
    published = root / "sealed" / session
    published.mkdir(parents=True, exist_ok=True)
    evidence_file = published / "trials.jsonl.gz"
    session_file = published / "manifest.json"
    if not session_file.is_file():
        rows = []
        for trial_id, _ in reservations:
            raw_file = folder / (trial_id + ".json")
            if raw_file.is_file():
                trial = json.loads(raw_file.read_bytes())
                if trial["trial_id"] != trial_id:
                    raise ValueError("trial file identity differs from its dispatch reservation")
                physically_observed = gpu_ok and any(event.get("native_evidence", {}).get("status") == "PASS"
                                                    for event in trial["wire"])
                assessment = assess_trial(trial, "holdout") if physically_observed else {}
                sealed = {"trial_id": trial_id, "physical_execution": "PASS" if physically_observed else "BLOCKED",
                          "status": "BLOCKED", "component_assessment": assessment,
                          "private_capture_sha256": digest(raw_file), "trace": portable(trial)}
            else:
                sealed = {"trial_id": trial_id, "physical_execution": "BLOCKED", "status": "BLOCKED",
                          "reason": "dispatch reserved before interruption; exact attempt requires reconciliation"}
            rows.append(canonical(sealed) + b"\n")
        payload = b"".join(rows)
        check_text(payload)
        evidence_file.write_bytes(gzip.compress(payload, mtime=0))
        manifest = {"identity": identity, "launch": portable(metadata), "gpu_execution": "PASS" if gpu_ok else "BLOCKED",
                    "artifacts": {"trials.jsonl.gz": digest(evidence_file)}, "reservations": len(reservations)}
        if counters.is_file():
            manifest["artifacts"]["gpu.jsonl.gz"] = archive(counters, published / "gpu.jsonl.gz")
        write_evidence(session_file, manifest)
    manifest = json.loads(session_file.read_bytes())
    if manifest["identity"] != identity or manifest["reservations"] != len(reservations):
        raise ValueError("sealed session identity differs from its dispatch records")
    for name, sha in manifest["artifacts"].items():
        if digest(published / name) != sha:
            raise ValueError("sealed session artifact has changed")
    rows = [json.loads(line) for line in gzip.decompress(evidence_file.read_bytes()).splitlines()]
    if [row["trial_id"] for row in rows] != [trial_id for trial_id, _ in reservations]:
        raise ValueError("sealed session roster differs from the physical reservation order")
    sha = digest(evidence_file)
    with db:
        db.executemany("UPDATE trials SET seal_sha256=? WHERE trial_id=? AND seal_sha256 IS NULL",
                       ((sha, row["trial_id"]) for row in rows))


def run_batches(root, assets, candidate, db, specs, enrollment, *, batch_size, limit, port):
    public = {row["case_id"]: row for row in records("holdout-public.jsonl")}
    worlds = {row["case_id"]: row for row in records("holdout-worlds.jsonl")}
    handoff = require_handoff(ROOT)
    record = json.loads((ROOT / "atlas/slm/v1.0/model_registry.json").read_bytes())["models"][candidate]
    model = (assets / record["local_asset"]).resolve(strict=True)
    baseline = verify_runtime(candidate, model, assets / BASE_ENGINE, require_prior_admission=False)
    if record["asset"]["expected_sha256"] != baseline["model"]["model_sha256"]:
        raise ValueError("formal model differs from the registered weights")
    engine = assets / OBSERVER_ENGINE
    actual = {file.name: digest(file) for file in engine.iterdir() if file.suffix in {".dll", ".exe"}}
    if actual != baseline["engine"]["dll_sha256"] | OBSERVER_HASHES:
        raise ValueError("formal observer runtime differs from its pinned package")
    harness = Path(sdk_bin.__file__).with_name("localharness.exe")
    if version("google-antigravity") != "0.1.24":
        raise ValueError("formal Antigravity SDK differs from its pinned version")
    alias = "ijslm-candidate-" + candidate.lower()
    dispatched = 0
    while limit is None or dispatched < limit:
        size = batch_size if limit is None else min(batch_size, limit - dispatched)
        pending = db.execute("SELECT trial_id FROM trials WHERE candidate=? AND session IS NULL "
                             "ORDER BY ordinal LIMIT ?", (candidate, size)).fetchall()
        if not pending:
            return
        session = "ijslm-tcv3-" + uuid4().hex
        folder = root / "sessions" / session
        folder.mkdir(parents=True)
        identity = {
            "run_id": session, "git_sha": git_head(), "candidate": candidate, "model": baseline["model"],
            "engine": {"build": baseline["engine"]["build"], "sha256": actual}, "backend": "vulkan",
            "sdk_version": version("google-antigravity"), "harness_sha256": digest(harness),
            "template_sha256": baseline["template"]["sha256"], "enrollment": enrollment,
        }
        write_evidence(folder / "identity.json", identity)
        try:
            with gpu_server(engine / "llama-server.exe", model, "vulkan", server_environment(), folder,
                            port, "vulkan", True, alias=alias, mission_id="IJ-SLM-1.0",
                            lease_owner="tc-v3-formal", runtime_session=session) as (client, launch):
                verify_launch(launch, baseline)
                if any(launch["gpu_lease"][key] != handoff["lease"][key]
                       for key in ("host_sha256", "gpu_physical_sha256")):
                    raise ValueError("formal physical runtime does not match the GPU handoff")
                write_evidence(folder / "launch.json", launch | {"status": "PASS"})
                for (trial_id,) in pending:
                    task = specs[trial_id]
                    case_id = task["case_id"]
                    with db:
                        reserved = db.execute("UPDATE trials SET session=? WHERE trial_id=? AND session IS NULL",
                                              (session, trial_id))
                        if reserved.rowcount != 1:
                            raise ValueError("physical trial was concurrently reserved")
                    trial = execute_trial(client, alias, public[case_id], worlds[case_id], trial_id, task["track"],
                                          folder / trial_id, harness, task["seed"])
                    write_evidence(folder / (trial_id + ".json"), trial)
                    dispatched += 1
        finally:
            seal_session(root, folder, db)
        print(candidate, session, "dispatched", dispatched, flush=True)


def progress(root, roster):
    plan = {row["trial_id"]: row for row in roster}
    counts = {candidate: Counter(planned=sum(row["candidate"] == candidate for row in roster)) for candidate in PRIORITY}
    manifests = {}
    found = set()
    for manifest_path in sorted((root / "sealed").glob("*/manifest.json")):
        doc = json.loads(manifest_path.read_bytes())
        for name, expected in doc["artifacts"].items():
            if digest(manifest_path.parent / name) != expected:
                raise ValueError("progress cannot count an unverified seal")
        candidate = doc["identity"]["candidate"]
        rows = gzip.decompress((manifest_path.parent / "trials.jsonl.gz").read_bytes()).splitlines()
        if len(rows) != doc["reservations"]:
            raise ValueError("sealed progress does not match the requested reservations")
        for line in rows:
            row = json.loads(line)
            key = row["trial_id"]
            if key in found or plan[key]["candidate"] != candidate:
                raise ValueError("duplicate or misrouted physical trial seal")
            found.add(key)
            counts[candidate]["sealed"] += 1
            counts[candidate]["executed"] += row["physical_execution"] == "PASS"
            counts[candidate][row["status"]] += 1
        manifests[manifest_path.parent.name] = digest(manifest_path)
    for count in counts.values():
        count["NOT_RUN"] = count["planned"] - count["sealed"]
    return {"models": {name: {key: count[key] for key in
                             ("planned", "executed", "sealed", "PASS", "FAIL", "BLOCKED", "NOT_RUN")}
                       for name, count in counts.items()},
            "sealed_manifests": manifests, "core_required": 36550,
            "core_remaining": 36550 - sum(count["executed"] for count in counts.values())}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--assets", type=Path, required=True)
    cli.add_argument("--candidate", choices=PRIORITY)
    cli.add_argument("--batch-size", type=int, default=24)
    cli.add_argument("--limit", type=int)
    cli.add_argument("--port", type=int, default=18754)
    cli.add_argument("--progress", action="store_true")
    args = cli.parse_args()
    if not (args.progress or args.candidate) or args.batch_size < 1 or (args.limit is not None and args.limit < 1):
        cli.error("supply a candidate or --progress and positive count limits")
    root = args.assets.resolve() / ".runtime/ij-slm-1.0/tc-v3-formal"
    roster = [row for row in records("roster.jsonl") if row["candidate"] in PRIORITY]
    if args.progress:
        print(json.dumps(progress(root, roster), indent=2))
        return
    verify_freeze()
    require_registry()
    development_sha = require_development()
    sources = {name: digest(Path(__file__).with_name(name)) for name in SOURCE_FILES if name != "wire_boundary.py"}
    sources["wire_boundary.py"] = digest(ROOT / "benchmarks/ij06_sdk/wire_boundary.py")
    enrollment = {"dataset_manifest_sha256": digest(HERE / "manifest.json"), "registry_sha256": digest(REGISTRY),
                  "development_manifest_sha256": development_sha, "gpu_handoff_sha256": digest(ROOT / HANDOFF),
                  "execution_sources": sources}
    root.mkdir(parents=True, exist_ok=True)
    with legacy.output_lock(root), connect(root, roster, enrollment) as db:
        for (session,) in db.execute("SELECT DISTINCT session FROM trials WHERE session IS NOT NULL "
                                     "AND seal_sha256 IS NULL").fetchall():
            seal_session(root, root / "sessions" / session, db)
        run_batches(root, args.assets.resolve(), args.candidate, db, {row["trial_id"]: row for row in roster},
                    enrollment, batch_size=args.batch_size, limit=args.limit, port=args.port)
        write_evidence(root / "progress.json", progress(root, roster))


if __name__ == "__main__":
    main()
