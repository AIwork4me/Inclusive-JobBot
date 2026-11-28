"""Per-batch dual-path session adapters (IJ-NANO-48H).

The pinned EAE ships per-batch ``evaluate_dual`` legs (``dualpath_b``,
``dualpath_c``, ...) but session classes only for the Batch A core.
This module reuses the pinned ``DualPathSession`` trial mechanics
(content-addressed artifacts, duplicate rejection, quarantine,
crash-safe persistence) and routes EVALUATION through the correct
per-batch legs — the only behavioral difference, validated against
each batch's qualified witness battery in tests.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import pathlib
import time

from eval_assurance.dualpath import (MISSING, MISSING_EVIDENCE,
                                     DUPLICATE_TRIAL, DualPathResult,
                                     DualPathSession, capture_artifact)


class LegDualPathSession(DualPathSession):
    """DualPathSession whose evaluation leg is a per-batch
    ``evaluate_dual`` from the pinned EAE. The overridden ``run_trial``
    mirrors the pinned implementation's trial mechanics exactly; only
    the evaluation call differs."""

    def __init__(self, workdir: pathlib.Path, evaluate_dual_leg):
        super().__init__(workdir)
        self._evaluate_dual_leg = evaluate_dual_leg

    def run_trial(self, case: dict, expectation: dict, response,
                  model: str = "synthetic-cpu", protocol: str = "chat",
                  artifact_bytes: bytes | None = None,
                  receipt=None, production_parser=None,
                  production_evaluator=None):
        tid = self.trial_id(case.get("case_id", ""), model, protocol)
        if tid in self.trials:
            self.quarantine.append({"trial_id": tid,
                                    "reason": DUPLICATE_TRIAL})
            return DualPathResult(
                case.get("case_id", ""), case.get("primitive", ""),
                DUPLICATE_TRIAL, "—", "—", False, True,
                reasons=("duplicate trial identity",))
        if response is MISSING:
            self.quarantine.append({"trial_id": tid,
                                    "reason": MISSING_EVIDENCE})
            self.trials[tid] = {"trial_id": tid,
                                "classification": MISSING_EVIDENCE}
            return DualPathResult(
                case.get("case_id", ""), case.get("primitive", ""),
                MISSING_EVIDENCE, "—", "—", False, True,
                reasons=("no raw artifact exists for this trial",))
        if artifact_bytes is not None:
            digest = hashlib.sha256(artifact_bytes).hexdigest()
            payload = artifact_bytes.decode("utf-8", "replace")
        else:
            art = capture_artifact(case.get("case_id", ""), model,
                                   protocol, response
                                   if isinstance(response, str)
                                   else str(response))
            digest = art["artifact_sha256"]
            payload = art["payload"]
        (self.workdir / "artifacts" / f"{digest[:24]}.json").write_text(
            payload, encoding="utf-8")
        result = self._evaluate_dual_leg(case, expectation, response)
        self.trials[tid] = {
            "trial_id": tid, "case_id": case.get("case_id", ""),
            "model": model, "protocol": protocol,
            "classification": result.classification,
            "artifact_sha256": digest,
            "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                          time.gmtime())}
        if result.quarantine:
            self.quarantine.append({"trial_id": tid,
                                    "reason": result.classification})
        return result

    def replay(self, case: dict, expectation: dict, model: str,
               protocol: str) -> dict:
        tid = self.trial_id(case.get("case_id", ""), model, protocol)
        rec = self.trials[tid]
        raw = json.loads(self._artifact_payload(rec["artifact_sha256"]))
        content = raw["content"] if isinstance(raw, dict) else str(raw)
        result = self._evaluate_dual_leg(case, expectation, content)
        return {"trial_id": tid,
                "replay_classification": result.classification,
                "recorded_classification": rec["classification"],
                "matches_recorded":
                    result.classification == rec["classification"]}


#: batch letter -> dualpath module suffix ("" is the Batch A core)
_LEG_SUFFIX = {"a": "", "b": "_b", "c": "_c", "d": "_d"}


def make_session(legs: str, workdir: pathlib.Path) -> DualPathSession:
    """Session factory: Batch A core legs -> pinned DualPathSession;
    per-batch legs -> the LegDualPathSession routing adapter above."""
    suffix = _LEG_SUFFIX.get(legs)
    if suffix is None:
        raise ValueError(f"unknown legs {legs!r}")
    if suffix == "":
        return DualPathSession(workdir)
    mod = importlib.import_module("eval_assurance.dualpath" + suffix)
    return LegDualPathSession(workdir, mod.evaluate_dual)


#: backwards-compatible alias (Batch B was the first adapter)
BatchBDualPathSession = LegDualPathSession
