import json
import os
from pathlib import Path
import subprocess
import sys

from benchmarks.root_cause.gpu_lease import _named_lease
from evaluation.aeve import controller
from evaluation.aeve.qualification import require_freeze, seed
from evaluation.aeve.runtime import ROOT


def test_entrypoints_and_all_frozen_qualification_jobs(tmp_path):
    env = {**os.environ,"PYTHONPATH":os.pathsep.join((str(ROOT),str(ROOT/"src")))}
    for action in ("seed-oracle","seed-gold"):
        subprocess.run([sys.executable,"-m","evaluation.aeve.controller",action,"--state",str(tmp_path)],
                       env=env,check=True,capture_output=True)
    db = controller.connect(tmp_path)
    assert db.execute("SELECT count(*) FROM jobs WHERE collection='clarification'").fetchone()[0] == 10
    assert db.execute("SELECT count(*) FROM jobs WHERE collection='planning-development'").fetchone()[0] == 64
    assert require_freeze()
    seed(db)
    seed(db)
    counts = db.execute("SELECT candidate,count(*) FROM jobs WHERE collection='gold-qualification' GROUP BY candidate")
    assert dict(counts) == dict.fromkeys("BGFJ",807)
    db.close()


def test_gpu_lease_excludes_another_process_across_directories(tmp_path):
    from uuid import uuid4
    name = "AEVEUnitTest" + uuid4().hex
    child = ("from benchmarks.root_cause.gpu_lease import _named_lease\n"
             f"try:\n with _named_lease({name!r}): pass\nexcept BlockingIOError: raise SystemExit(3)")
    env = {**os.environ,"PYTHONPATH":str(ROOT)}
    with _named_lease(name):
        assert subprocess.run([sys.executable,"-c",child],cwd=tmp_path,env=env).returncode == 3
    assert subprocess.run([sys.executable,"-c",child],cwd=tmp_path,env=env).returncode == 0


def test_unsealed_generation_is_requeued_with_original_judgment_preserved(tmp_path):
    db = controller.connect(tmp_path)
    with db:
        controller.add(db,"gold-qualification","case","J","D01","semantic",{"example":True})
        db.execute("UPDATE jobs SET status='RECORDED',run='unsealed',result='{}'")
    with controller.gpu_lock(tmp_path):
        controller.quarantine_unsealed(db,tmp_path)
        controller.quarantine_unsealed(db,tmp_path)
    assert db.execute("SELECT status FROM jobs").fetchone()[0] == "PENDING"
    assert [tuple(row) for row in db.execute("SELECT run,result FROM quarantined")] == [("unsealed","{}")]
    db.close()


def test_rehashed_case_cannot_claim_another_native_generation(tmp_path):
    import gzip
    import shutil
    import pytest
    from evaluation.aeve.archive import verify, digest
    from evaluation.aeve.runtime import canonical
    source = next((ROOT/"evaluation/aeve/results/sessions").glob("*/manifest.json")).parent
    volume = tmp_path/"sessions"/source.name
    shutil.copytree(source,volume)
    captures = volume/"captures.jsonl.gz"
    rows = [json.loads(line) for line in gzip.decompress(captures.read_bytes()).splitlines()]
    sample = next(r for r in rows if r["transport"] == "PASS")
    response = json.loads(sample["capture"]["raw_response"])
    response["id"] = "software-negative-control"
    sample["capture"]["raw_response"] = json.dumps(response)
    captures.write_bytes(gzip.compress(b"".join(canonical(r)+b"\n" for r in rows),mtime=0))
    file = volume/"manifest.json"
    stamp = json.loads(file.read_bytes())
    stamp["sha256"][captures.name] = digest(captures)
    file.write_bytes(canonical(stamp))
    with pytest.raises(ValueError,match="independent native token capture"):
        verify(tmp_path)
