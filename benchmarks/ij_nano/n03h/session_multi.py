"""Multi-batch dual-path session (IJ-NANO-48H adapter atlas).

The AUTH-2W roster spans all 32 primitives, so a trial's evaluation
legs are selected by its primitive's batch (C01-C08 -> a, C09-C16 ->
b, C17-C24 -> c, C25-C32 -> d) — the same per-batch leg dispatch the
EAE's adapter-scope qualification used for its canary sweep. Trial
mechanics are inherited from the pinned DualPathSession via the
per-batch LegDualPathSession adapters, each with its own sub-workdir.
"""
from __future__ import annotations

import pathlib

from benchmarks.ij_nano.n03h.session_b import make_session


def batch_of(primitive: str) -> str:
    n = int(primitive[1:]) if primitive[:1] == "C" else 0
    if 1 <= n <= 8:
        return "a"
    if 9 <= n <= 16:
        return "b"
    if 17 <= n <= 24:
        return "c"
    if 25 <= n <= 32:
        return "d"
    raise ValueError(f"primitive outside C01-C32: {primitive!r}")


class MultiLegSession:
    """Facade over four per-batch leg sessions sharing one workdir
    (subdirectories legs_a/..legs_d/). Aggregates trials, quarantine
    and canary-control views for the campaign analyzer."""

    def __init__(self, workdir: pathlib.Path):
        self.workdir = pathlib.Path(workdir)
        self._legs = {letter: make_session(letter,
                                           self.workdir / f"legs_{letter}")
                      for letter in ("a", "b", "c", "d")}

    def _session_for(self, case: dict):
        return self._legs[batch_of(case.get("primitive", ""))]

    # -- DualPathSession-compatible surface ---------------------------------
    @staticmethod
    def trial_id(case_id: str, model: str, protocol: str) -> str:
        return f"{case_id}|{model}|{protocol}"

    def run_trial(self, case: dict, expectation: dict, response,
                  model: str = "synthetic-cpu", protocol: str = "chat",
                  **kw):
        return self._session_for(case).run_trial(
            case, expectation, response, model=model, protocol=protocol,
            **kw)

    def replay(self, case: dict, expectation: dict, model: str,
               protocol: str) -> dict:
        return self._session_for(case).replay(case, expectation, model,
                                              protocol)

    def verify(self) -> list[str]:
        problems = []
        for letter, sess in self._legs.items():
            for problem in sess.verify():
                problems.append(f"[{letter}] {problem}")
        return problems

    def save(self) -> None:
        for sess in self._legs.values():
            sess.save()

    def load(self) -> bool:
        loaded = [sess.load() for sess in self._legs.values()]
        return any(loaded)

    @property
    def trials(self) -> dict:
        merged: dict = {}
        for sess in self._legs.values():
            merged.update(sess.trials)
        return merged

    @property
    def quarantine(self) -> list:
        out = []
        for sess in self._legs.values():
            out.extend(sess.quarantine)
        return out

    @property
    def canary_controls(self) -> list:
        out = []
        for sess in self._legs.values():
            out.extend(sess.canary_controls)
        return out

    def record_canary_control(self, control: dict) -> None:
        self._legs["a"].record_canary_control(control)
