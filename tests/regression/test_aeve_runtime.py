import json
import os
from pathlib import Path
import subprocess
import sys

from benchmarks.root_cause.gpu_lease import physical_gpu
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
    child = ("from benchmarks.root_cause.gpu_lease import physical_gpu\n"
             "try:\n with physical_gpu(): pass\nexcept BlockingIOError: raise SystemExit(3)")
    env = {**os.environ,"PYTHONPATH":str(ROOT)}
    with physical_gpu():
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
