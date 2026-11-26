"""Resume the local single-GPU evaluation from immutable inputs and recorded attempts."""
import argparse
import json
from pathlib import Path
import time

from .adjudication import assess
from .archive import digest, export
from .controller import DEFAULT, connect, gpu_lock, quarantine_unsealed, seed_gold, seed_oracle, status, work
from .history import OUT
from .intake import seed_history
from .runtime import ROOT, write_json


FORMAL_INPUTS = {"history-v2":"judge_inputs_v2.jsonl.gz",
                 "history-supplement-v2":"judge_inputs_nonphysical_v2.jsonl.gz"}


def schedule(db, batch, formal=False):
    # Fewer completed batches run first. Paired reviewers and the planning panel have bounded latency.
    collections = tuple(c + suffix for c in FORMAL_INPUTS for suffix in ("-dispute","-citations","")) if formal else (
        "gold-qualification","gold-development-robustness-v1","planning-development","clarification","gold-development","gold-calibration")
    rows = db.execute("""SELECT collection,candidate,sum(status='RECORDED') AS done,
                         sum(status='PENDING') AS waiting FROM jobs
                         GROUP BY collection,candidate HAVING waiting>0""")
    choices = [r for r in rows if r["collection"] in collections]
    if not choices:
        return None
    pick = min(choices, key=lambda r: (r["done"] // batch, collections.index(r["collection"]), r["candidate"]))
    return pick["candidate"], pick["collection"]


def prepare(db):
    db.execute("CREATE TABLE IF NOT EXISTS seeded (name TEXT PRIMARY KEY, digest TEXT NOT NULL)")
    def once(name, identity, seed):
        row = db.execute("SELECT digest FROM seeded WHERE name=?", (name,)).fetchone()
        if row:
            if row[0] != identity:
                raise ValueError("sealed queue input changed: " + name)
            return
        seed()
        with db:
            db.execute("INSERT INTO seeded VALUES (?,?)", (name,identity))
    db.executescript("""
        CREATE TABLE IF NOT EXISTS review_changed(item TEXT PRIMARY KEY);
        CREATE TRIGGER IF NOT EXISTS mark_review_changed AFTER UPDATE OF status ON jobs
        WHEN NEW.status='RECORDED' AND NEW.collection IN ('history-v2','history-v2-dispute','history-v2-citations',
            'history-supplement-v2','history-supplement-v2-dispute','history-supplement-v2-citations')
        BEGIN
            INSERT OR IGNORE INTO review_changed SELECT CASE WHEN NEW.collection LIKE '%-citations'
                THEN (SELECT item FROM jobs WHERE id=NEW.item) ELSE NEW.item END;
        END;
    """)
    seed_oracle(db)
    for split in ("development","calibration"):
        from .gold import FOLDER
        once("gold-four-families-"+split, digest(FOLDER/"manifest.json"), lambda: seed_gold(db,split))
    from .qualification import require_freeze, seed
    once("gold-qualification",require_freeze(),lambda:seed(db))
    from .robustness import seed as seed_robustness
    seed_robustness(db)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--state",type=Path,default=DEFAULT)
    cli.add_argument("--assets",type=Path,default=ROOT.parent.parent)
    cli.add_argument("--history",type=Path,default=ROOT/OUT)
    cli.add_argument("--out",type=Path,default=ROOT/"evaluation/aeve/results")
    cli.add_argument("--batch",type=int,default=96)
    cli.add_argument("--port",type=int,default=18744)
    args = cli.parse_args()
    if args.batch < 1:
        cli.error("batch must be positive")
    folder = args.state.resolve()
    db = connect(folder)
    try:
        with gpu_lock(folder,"controller.lock"):
            drive(db, folder, args)
    finally:
        db.close()


def drive(db, folder, args):
    from .restore import restore
    from .archive import verify
    while True:
        try:
            with gpu_lock(folder):
                quarantine_unsealed(db,folder)
            break
        except BlockingIOError:
            time.sleep(15)
    verify(args.out)
    for stamp in (args.out/"sessions").glob("*/manifest.json"):
        archive = json.loads(stamp.read_bytes())
        existing = db.execute("SELECT count(*) FROM jobs WHERE run=? AND status='RECORDED'",(archive["run_id"],)).fetchone()[0]
        if existing != archive["attempts"]:
            restore(db,folder,args.out)
            break
    prepare(db)
    retries = 0
    admitted = None
    while True:
        export(db,folder,args.out)
        if admitted is None:
            next_job = schedule(db,args.batch)
        else:
            changed = [row[0] for row in db.execute("SELECT item FROM review_changed")]
            if changed:
                for collection in FORMAL_INPUTS:
                    assess(db,args.history/"registry.jsonl.gz",enqueue=True,collection=collection,admitted=admitted,items=changed)
                with db:
                    db.executemany("DELETE FROM review_changed WHERE item=?",((item,) for item in changed))
            next_job = schedule(db,args.batch,formal=True)
        write_json(folder/"progress.json", {"queue":status(db),"next":next_job,
                   "formal_physical_remaining":18440,"formal_freeze":"BLOCKED"})
        if not next_job:
            if admitted is not None:
                print("Routable historical jobs drained. Inspect case coverage, citation checks and admission gaps.",flush=True)
                break
            from .qualification import measure
            report = measure(args.out)
            write_json(folder/"qualification.json",report)
            admitted = [c for c,r in report["admission"].items() if r["status"] == "PASS"]
            if len(admitted) < 2:
                print("Independent admission gate BLOCKED: fewer than two qualified families.",flush=True)
                break
            from .runtime import fingerprint
            for collection, name in FORMAL_INPUTS.items():
                packets = args.history/name
                if not packets.is_file():
                    print(f"Missing {name}; {collection} remains blocked",flush=True)
                    continue
                identity = fingerprint([digest(packets),admitted,report["protocol_sha256"]])
                old = db.execute("SELECT digest FROM seeded WHERE name=?",(collection,)).fetchone()
                if old and old[0] != identity:
                    raise ValueError("formal admission or evidence changed; a new collection version is required")
                if not old:
                    seed_history(db,packets,admitted=admitted,collection=collection)
                    with db:
                        db.execute("INSERT INTO seeded VALUES (?,?)",(collection,identity))
                with db:
                    db.execute("""INSERT OR IGNORE INTO review_changed SELECT DISTINCT item FROM jobs
                                  WHERE collection=? AND status='RECORDED'""",(collection,))
            continue
        candidate, collection = next_job
        try:
            completed = work(db,folder,args.assets.resolve(),args.port,candidate,[collection],args.batch)
        except BlockingIOError:
            time.sleep(20)
            continue
        except (OSError, TimeoutError, ConnectionError) as error:
            retries += 1
            if retries > 3:
                raise
            print(f"Recoverable runtime error ({type(error).__name__}), retry {retries}/3",flush=True)
            time.sleep(15 * retries)
            continue
        retries = 0
        print(f"{candidate} {collection} recorded {completed}",flush=True)


if __name__ == "__main__":
    main()
