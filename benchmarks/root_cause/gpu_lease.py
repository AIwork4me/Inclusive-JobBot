"""Exclusive cooperative lease for physical inference across checkouts, ports and queues."""
from contextlib import contextmanager
import os


@contextmanager
def physical_gpu():
    with _named_lease("InclusiveJobBotPhysicalGPU"):
        yield


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
        for name in ("CloseHandle", "ReleaseMutex"):
            getattr(api, name).argtypes = [wintypes.HANDLE]
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
                yield
            finally:
                api.ReleaseMutex(handle)
        finally:
            api.CloseHandle(handle)
    else:
        import fcntl
        # A fixed machine path keeps different TMPDIR values on the same lease.
        lockfile = "/tmp/inclusive-jobbot-physical-gpu.lock" if name == "InclusiveJobBotPhysicalGPU" else f"/tmp/{name}.lock"
        fd = os.open(lockfile, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)
