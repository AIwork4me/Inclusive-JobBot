"""OS-owned cooperative lease shared across Windows sessions and worktrees."""

from contextlib import contextmanager
from functools import lru_cache
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import threading
from uuid import uuid4


NAME = "InclusiveJobBotPhysicalGPU"
_held = threading.Lock()


def fingerprint(value):
    return sha256(value.strip().casefold().encode("utf-8")).hexdigest()


def windows_query(script):
    return subprocess.check_output(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        encoding="utf-8", errors="strict", timeout=25, creationflags=subprocess.CREATE_NO_WINDOW,
    ).strip()


@lru_cache(maxsize=1)
def identities():
    if os.name == "nt":
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                           access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            host = winreg.QueryValueEx(key, "MachineGuid")[0]
        gpu = json.loads(windows_query(
            "$ErrorActionPreference='Stop'; "
            "$ids=@((Get-CimInstance Win32_VideoController | "
            "Where-Object PNPDeviceID -Like 'PCI\\*').PNPDeviceID); "
            "ConvertTo-Json -InputObject $ids -Compress"
        ))
    else:
        host = Path("/etc/machine-id").read_text(encoding="ascii")
        gpu = [str(device.resolve()) for device in Path("/sys/class/drm").glob("card*/device")
               if device.exists()]
    if not host.strip() or len(gpu) != 1 or not gpu[0]:
        raise RuntimeError("a single physical GPU could not be bound to the lease")
    return fingerprint(host), fingerprint(gpu[0])


@contextmanager
def physical_gpu(*, mission_id="IJ-0", runtime_session=None, lease_owner="historical-replay",
                 require_idle=True):
    if not mission_id or not lease_owner or runtime_session == "":
        raise ValueError("GPU lease requires mission, runtime session and owner")
    # Win32 mutex ownership is recursive on the same thread. Reject accidental
    # nested acquisitions in this process too.
    if not _held.acquire(blocking=False):
        raise BlockingIOError("this process already has a physical GPU lease")
    try:
        with _named_lease(NAME) as abandoned:
            host, gpu = identities()
            if require_idle and os.name == "nt":
                active = windows_query(
                    "$ErrorActionPreference='Stop'; (Get-CimInstance Win32_Process "
                    "-Filter \"Name LIKE 'llama-server%' OR Name LIKE 'ollama%'\").ProcessId"
                )
                if active:
                    raise BlockingIOError("an existing inference process holds the physical GPU slot")
            yield {"host_sha256": host, "gpu_physical_sha256": gpu, "mission_id": mission_id,
                   "process_id": os.getpid(), "runtime_session": runtime_session or uuid4().hex,
                   "lease_owner": lease_owner, "abandoned": abandoned}
    finally:
        _held.release()


@contextmanager
def _named_lease(name):
    if not name.isalnum():
        raise ValueError("invalid lease name")
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        api = ctypes.WinDLL("kernel32", use_last_error=True)
        create = api.CreateMutexW
        create.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        create.restype = wintypes.HANDLE
        wait = api.WaitForSingleObject
        wait.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        wait.restype = wintypes.DWORD
        for function in (api.CloseHandle, api.ReleaseMutex):
            function.argtypes = [wintypes.HANDLE]
            function.restype = wintypes.BOOL
        handle = create(None, False, "Global\\" + name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            result = wait(handle, 0)
            if result == 258:
                raise BlockingIOError("another physical inference session owns the GPU")
            if result not in (0, 128):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                yield result == 128
            finally:
                if not api.ReleaseMutex(handle):
                    raise ctypes.WinError(ctypes.get_last_error())
        finally:
            api.CloseHandle(handle)
    else:
        import fcntl

        lockfile = "/tmp/inclusive-jobbot-physical-gpu.lock" if name == NAME else f"/tmp/{name}.lock"
        fd = os.open(lockfile, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield False
        finally:
            os.close(fd)
