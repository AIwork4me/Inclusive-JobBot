"""Restore recorded jobs from verified portable sessions, retaining their original attempt IDs."""
import gzip
import json
import shutil

from .archive import digest, verify
from .controller import add, gpu_lock
from .runtime import canonical


def restore(db, state, results):
    total = verify(results)
    with gpu_lock(state):
        db.execute("""CREATE TABLE IF NOT EXISTS imported(job TEXT PRIMARY KEY,run TEXT NOT NULL,
                      original_attempt INTEGER NOT NULL,manifest_sha256 TEXT NOT NULL)""")
        for stamp in sorted((results/"sessions").glob("*/manifest.json")):
            manifest = json.loads(stamp.read_bytes())
            run = manifest["run_id"]
            copy = state/"imported"/run
            copy.mkdir(parents=True,exist_ok=True)
            for name, expected in manifest["sha256"].items():
                target = copy/name
                if not target.exists() or digest(target) != expected:
                    shutil.copyfile(stamp.parent/name,target)
            shutil.copyfile(stamp,copy/"manifest.json")
            seal_hash = digest(stamp)
            with db, gzip.open(copy/"captures.jsonl.gz","rb") as stream:
                for line in stream:
                    row = json.loads(line)
                    add(db,*(row[k] for k in ("collection","item","candidate","dimension","role","spec")))
                    job = db.execute("SELECT * FROM jobs WHERE id=?",(row["job"],)).fetchone()
                    if job["status"] == "RECORDED" and (job["run"] != run or json.loads(job["result"]) != row["evaluation"]):
                        raise ValueError("restored judgment conflicts with an existing observation")
                    db.execute("INSERT OR IGNORE INTO imported VALUES(?,?,?,?)",(row["job"],run,row["attempt"],seal_hash))
                    db.execute("UPDATE jobs SET status='RECORDED', result=?,run=? WHERE id=?",
                               (canonical(row["evaluation"]).decode(),run,row["job"]))
    return total
