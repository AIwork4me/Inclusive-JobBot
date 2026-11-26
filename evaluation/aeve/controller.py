"""Restartable single-GPU queue. Run from the repository root with PYTHONPATH=.;src."""
import argparse
from contextlib import contextmanager
from functools import lru_cache
import gzip
import json
import os
from pathlib import Path
import sqlite3
import time

from .local_judge import body_for, check, role_for
from .runtime import ROOT, canonical, fingerprint, infer, selected_judges, session, write_json

DEFAULT = ROOT / ".runtime/aeve-ij073"


def connect(folder):
    folder.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(folder / "queue.sqlite", timeout=60)
    db.row_factory = sqlite3.Row
    db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS jobs(
            id TEXT PRIMARY KEY, collection TEXT NOT NULL, item TEXT NOT NULL, candidate TEXT NOT NULL,
            dimension TEXT NOT NULL, role TEXT NOT NULL, spec BLOB NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
            result TEXT, run TEXT, created INTEGER NOT NULL, UNIQUE(collection,item,candidate,dimension,role)
        );
        CREATE INDEX IF NOT EXISTS pending ON jobs(status,candidate,collection,created);
        CREATE TABLE IF NOT EXISTS attempts(
            id INTEGER PRIMARY KEY, job TEXT NOT NULL, run TEXT NOT NULL, started REAL NOT NULL, ended REAL,
            transport TEXT, evidence_path TEXT, sha256 TEXT
        );
    """)
    return db


@contextmanager
def gpu_lock(folder):
    # The OS releases this lock on process exit, including abnormal termination.
    lock = (folder / "gpu.lock").open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            if lock.tell() == 0:
                lock.write(b"1")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        lock.close()


def add(db, collection, item, candidate, dimension, role, spec):
    key = fingerprint([collection, item, candidate, dimension, role, spec])
    args = (collection, item, candidate, dimension, role)
    old = db.execute("SELECT id FROM jobs WHERE collection=? AND item=? AND candidate=? AND dimension=? AND role=?", args).fetchone()
    if old:
        if old["id"] != key:
            raise ValueError(f"input changed for frozen job {item}/{candidate}/{dimension}; version the collection")
        return
    db.execute("INSERT INTO jobs(id,collection,item,candidate,dimension,role,spec,created) VALUES(?,?,?,?,?,?,?,?)",
               (key, *args, gzip.compress(canonical(spec), compresslevel=1, mtime=0), time.time_ns()))


def judge_job(db, collection, item, candidate, packet, role=None):
    dimension = packet["dimension"]
    role = role or role_for(dimension)
    spec = {"packet": packet, "body": body_for(candidate, packet, role)}
    add(db, collection, item, candidate, dimension, role, spec)


def seed_oracle(db):
    from .oracle_panel import panel
    with db:
        for row in panel():
            item = "/".join((row["case"], row["arm"], row["mode"], row["track"]))
            add(db, row["suite"], item, "J", "plan", "candidate", row)


def seed_gold(db, split):
    from .gold import iter_gold
    rubrics = json.loads(Path(__file__).with_name("evaluator_manifest.json").read_bytes())["dimensions"]
    with db:
        for case in iter_gold(split):
            for candidate in ("J", "G", "F"):
                packet = case["packet"]
                dim = packet["dimension"]
                role = role_for(dim)
                body = body_for(candidate, packet, role)
                body["messages"][0]["content"] += " Evaluation criterion: " + rubrics[dim]["rubric"]
                add(db, "gold-" + split, case["case_id"], candidate, dim, role, {"packet": packet, "body": body})


@lru_cache(maxsize=1)
def worlds():
    path = ROOT / "benchmarks/agentic_planning_v1/task_graphs/holdout.jsonl"
    return {r["case_id"]: r for r in (json.loads(line) for line in path.read_bytes().splitlines())}


def grade(spec, raw):
    if "packet" in spec:
        return check(spec["packet"], raw)
    from benchmarks.agentic_planning_v2.oracle import validate
    from benchmarks.agentic_planning_v2.execution import execute
    from benchmarks.agentic_planning_v2.runner import evaluate_raw
    from benchmarks.agentic_planning_v1.sandbox import SyntheticSandbox
    from benchmarks.tool_calling_v2.oracle import decode_object, equal
    if "world" in spec:
        return evaluate_raw(raw, spec["contract"], [spec["world"]])
    plan = decode_object(raw)
    errors = validate(plan, spec["contract"])
    if errors:
        return {"status": "FAIL", "errors": errors}
    graph = worlds()[spec["case"]]
    sandbox = SyntheticSandbox(graph["world"])
    execution = execute(plan, spec["public"], spec["contract"]["action_budget"], sandbox.invoke)
    matched = equal(execution["final"], graph["final"]) and equal(sandbox.snapshot(), graph["goal_state"])
    return {"status": "PASS" if matched else "FAIL", "reason": execution["reason"], "records": execution["records"],
            "final": execution["final"], "after_state": sandbox.snapshot()}


def archive(db, folder, job, aid, run, transport, capture, evaluation):
    from hashlib import sha256
    payload = canonical({"job": job["id"], "run": run, "attempt": aid, "transport": transport,
                         "evaluation": evaluation, "capture": capture})
    packed = gzip.compress(payload, compresslevel=6, mtime=0)
    relative = Path("captures") / run / f"{aid:08d}.json.gz"
    dst = folder / relative
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp")
    tmp.write_bytes(packed)
    tmp.replace(dst)
    with db:
        db.execute("UPDATE attempts SET ended=?,transport=?,evidence_path=?,sha256=? WHERE id=?",
                   (time.time(), transport, relative.as_posix(), sha256(packed).hexdigest(), aid))
        db.execute("UPDATE jobs SET status='RECORDED',result=?,run=? WHERE id=?", (canonical(evaluation).decode(), run, job["id"]))


def quarantine_unsealed(db, folder):
    """Call only while holding the state lock. Preserve failed attempts for audit."""
    db.execute("""CREATE TABLE IF NOT EXISTS quarantined(
                  job TEXT,run TEXT,result TEXT,reason TEXT NOT NULL,PRIMARY KEY(job,run))""")
    with db:
        for row in db.execute("SELECT DISTINCT run FROM jobs WHERE status='RECORDED'").fetchall():
            run = row["run"]
            stamp = folder / "sessions" / run / "seal.json"
            if stamp.is_file():
                seal = json.loads(stamp.read_bytes())
                if seal["run_id"] != run:
                    raise ValueError("seal names a different run")
                if seal["gpu_evidence"] == "PASS" and seal["active_pid_counter_samples"] > 0:
                    continue
            reason = "session lacks a valid PID-bound GPU seal"
            db.execute("""INSERT OR IGNORE INTO quarantined SELECT id,run,result,? FROM jobs
                          WHERE run=? AND status='RECORDED'""",(reason,run))
            db.execute("UPDATE jobs SET status='PENDING',result=NULL,run=NULL WHERE run=? AND status='RECORDED'",(run,))
        db.execute("""UPDATE attempts SET transport='BLOCKED' WHERE ended IS NULL AND transport IS NULL""")


def work(db, folder, assets, port, candidate, collections, limit):
    slots = ",".join("?" for _ in collections)
    sql = f"SELECT * FROM jobs WHERE status='PENDING' AND candidate=? AND collection IN ({slots}) ORDER BY created LIMIT ?"
    with gpu_lock(folder):
        quarantine_unsealed(db, folder)
        jobs = db.execute(sql, (candidate, *collections, limit)).fetchall()
        if not jobs:
            return 0
        with session(candidate, assets, folder, port) as (run, client):
            started = time.monotonic()
            recorded = 0
            for job in jobs:
                if time.monotonic() - started > 5400:
                    break
                spec = json.loads(gzip.decompress(job["spec"]))
                with db:
                    aid = db.execute("INSERT INTO attempts(job,run,started) VALUES(?,?,?)",
                                     (job["id"], run, time.time())).lastrowid
                transport, raw, capture = infer(client, spec["body"])
                if transport == "PASS":
                    try:
                        result = grade(spec, raw)
                    except (ValueError, TypeError, KeyError, RecursionError) as exc:
                        result = {"status": "FAIL", "reason": "invalid_output", "detail": str(exc)[:240]}
                else:
                    result = {"status": transport, "reason": "incomplete_generation_or_transport"}
                archive(db, folder, job, aid, run, transport, capture, result)
                recorded += 1
        return recorded


def status(db):
    return [dict(r) for r in db.execute("SELECT collection,candidate,status,count(*) AS n FROM jobs GROUP BY 1,2,3 ORDER BY 1,2,3")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["seed-oracle", "seed-gold", "work", "status"])
    parser.add_argument("--state", type=Path, default=DEFAULT)
    parser.add_argument("--assets", type=Path, default=ROOT.parent.parent)
    parser.add_argument("--candidate", choices=["J", "G", "F", "B"], default="J")
    parser.add_argument("--collections", nargs="+", default=["clarification", "planning-development"])
    parser.add_argument("--limit", type=int, default=128)
    parser.add_argument("--port", type=int, default=18744)
    parser.add_argument("--split", choices=["development","calibration"], default="development")
    args = parser.parse_args()
    folder = args.state.resolve()
    db = connect(folder)
    if args.action == "seed-oracle":
        seed_oracle(db)
    elif args.action == "seed-gold":
        seed_gold(db, args.split)
    elif args.action == "work":
        work(db, folder, args.assets.resolve(), args.port, args.candidate, args.collections, args.limit)
    print(json.dumps(status(db), ensure_ascii=False))
    db.close()


if __name__ == "__main__":
    main()
