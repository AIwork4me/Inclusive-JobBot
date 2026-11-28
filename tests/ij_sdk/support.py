"""Shared helpers for the IJ-SDK regression suite. Stdlib ``unittest`` only, so the
suite runs inside every SDK environment without installing anything.

Every test module imports only modules that already existed at the audited
commit at its top level. Modules the repair added are loaded through
``RepoTestCase.import_new``, which fails the individual test with a clear
"capability absent" message when it is missing - so running the suite against
the audited tree gives a precise red picture instead of one import error.
"""

from __future__ import annotations

import importlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from benchmarks.ij_sdk.contracts.events import EventLog  # noqa: E402
from scripts.tools.ij_sdk_integrity_repro import (  # noqa: E402
    FixtureModelServer, final_response, tool_call_response)


class FakeClock:
    """Deterministic monotonic clock for budget tests."""

    def __init__(self, start: float = 1000.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def tool_call(call_id, name, args, prompt_tokens=100, completion_tokens=50, arguments=None):
    return tool_call_response(call_id, name, args, prompt_tokens, completion_tokens, arguments)


def final(text, prompt_tokens=100, completion_tokens=50, finish_reason="stop"):
    return final_response(text, prompt_tokens, completion_tokens, finish_reason)


class RepoTestCase(unittest.TestCase):
    def import_new(self, name: str):
        """Import a module the repair added; fail this test clearly when it is absent."""
        try:
            return importlib.import_module(name)
        except ImportError as exc:
            self.fail(f"capability absent: {name} ({exc})")

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="ijsdk_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def path(self, name: str) -> Path:
        return Path(self.tmp) / name

    def server(self, steps) -> FixtureModelServer:
        """A scripted model server on loopback (software fixture; never model or GPU evidence)."""
        fixture = FixtureModelServer(list(steps)).start()
        self.addCleanup(fixture.stop)
        return fixture

    def log(self, name: str = "events.jsonl") -> EventLog:
        handle = EventLog(str(self.path(name)))
        self.addCleanup(handle.close)
        return handle


def usage_dict(result) -> dict:
    """Per-trial usage as plain data, without wall time."""
    usage = result["usage"]
    data = dict(vars(usage)) if hasattr(usage, "__dict__") else dict(usage)
    data.pop("wall_seconds", None)
    return data


def read_rows(path) -> list[dict]:
    import json
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
