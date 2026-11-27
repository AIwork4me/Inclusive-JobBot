import ctypes
from ctypes import wintypes
from pathlib import Path
import os
import subprocess
import sys

import pytest


def test_live_mutex_contends_across_worktrees_and_recovers_abandoned_owner():
    other = os.environ.get("JOBBOT_LEASE_OTHER_WORKTREE")
    if os.name != "nt" or not other:
        pytest.skip("requires Windows and a second worktree")
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": ""}
    probe = """
from benchmarks.root_cause.gpu_lease import physical_gpu
import sys
try:
    with physical_gpu(mission_id=sys.argv[1], runtime_session='lease-test', lease_owner='test',
                      require_idle=False) as lease:
        print(lease['mission_id'], lease['process_id'], lease['host_sha256'],
              lease['gpu_physical_sha256'], lease['abandoned'], flush=True)
        if sys.argv[1]=='holder':
            sys.stdin.read()
except BlockingIOError:
    sys.exit(23)
"""
    with subprocess.Popen([sys._base_executable, "-c", probe, "holder"], cwd=root, env=env,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True) as holder:
        try:
            owning = holder.stdout.readline().split()
            assert owning[:2] == ["holder", str(holder.pid)]
            denied = subprocess.run([sys._base_executable, "-c", probe, "contender"], cwd=other,
                                    env=env, capture_output=True, text=True, timeout=30)
            assert denied.returncode == 23, denied.stderr
        finally:
            holder.kill()
            holder.communicate(timeout=10)
    recovered = subprocess.run([sys._base_executable, "-c", probe, "recovered"], cwd=other,
                               env=env, capture_output=True, text=True, timeout=30, check=True)
    assert recovered.stdout.split()[2:4] == owning[2:4]
    assert recovered.stdout.split()[0] == "recovered"
@pytest.mark.skipif(os.name != "nt", reason="requires Windows")
def test_inference_subprocess_ends_when_its_controller_is_killed():
    root = Path(__file__).resolve().parents[2]
    probe = """
from benchmarks.root_cause.windows_job import job_process
import sys
with job_process([sys.executable, '-c', 'import time; time.sleep(60)']) as child:
    print(child.pid, flush=True)
    sys.stdin.read()
"""
    with subprocess.Popen([sys._base_executable, "-c", probe], cwd=root,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True) as holder:
        pid = int(holder.stdout.readline())
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        child = kernel.OpenProcess(0x100000, False, pid)
        try:
            assert child and kernel.WaitForSingleObject(child, 0) == 258
            holder.kill()
            holder.communicate(timeout=10)
            assert kernel.WaitForSingleObject(child, 10000) == 0
        finally:
            if child:
                kernel.CloseHandle(child)
