"""Contain an inference subprocess in a kill-on-close Windows job."""

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import subprocess


class BasicLimits(ctypes.Structure):
    _fields_ = [
        ("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
        ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
        ("max_working_set", ctypes.c_size_t), ("active_process_count", wintypes.DWORD),
        ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
        ("scheduling_class", wintypes.DWORD),
    ]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("basic", BasicLimits), ("io_counters", ctypes.c_ulonglong * 6),
        ("process_memory_limit", ctypes.c_size_t), ("job_memory_limit", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t),
    ]


@contextmanager
def job_process(args, **options):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateJobObjectW
    create.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    create.restype = wintypes.HANDLE
    configure = kernel.SetInformationJobObject
    configure.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    configure.restype = wintypes.BOOL
    assign = kernel.AssignProcessToJobObject
    assign.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    assign.restype = wintypes.BOOL
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    resume = ctypes.WinDLL("ntdll").NtResumeProcess
    resume.argtypes = [wintypes.HANDLE]
    resume.restype = ctypes.c_long

    job = create(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    process = None
    try:
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not configure(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        # The child cannot run inference between CreateProcess and assignment.
        options["creationflags"] = options.get("creationflags", 0) | 0x4  # CREATE_SUSPENDED
        process = subprocess.Popen(args, **options)
        if not assign(job, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        status = resume(int(process._handle))
        if status != 0:
            raise OSError(f"Windows could not resume the contained inference process ({status:#x})")
        yield process
    finally:
        close(job)
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=15)
