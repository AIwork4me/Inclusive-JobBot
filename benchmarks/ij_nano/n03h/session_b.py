"""Batch B dual-path session adapter (IJ-NANO-48H).

The pinned EAE ships ``dualpath_b.evaluate_dual`` (the qualified Batch B
evaluation legs) but no session class. This adapter reuses the pinned
``DualPathSession`` trial mechanics (content-addressed artifacts,
duplicate rejection, quarantine, crash-safe persistence) and routes
EVALUATION through ``dualpath_b`` — the only behavior difference, and
only for Batch B scopes. Validated against the qualified Batch B
witness battery in tests (134 rows).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time

from eval_assurance import dualpath_b
from eval_assurance.dualpath import (MISSING, MISSING_EVIDENCE,
                                     DUPLICATE_TRIAL, DualPathResult,
                                     DualPathSession, capture_artifact)


class BatchBDualPathSession(DualPathSession):

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
        result = dualpath_b.evaluate_dual(case, expectation, response)
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
        result = dualpath_b.evaluate_dual(case, expectation, content)
        return {"trial_id": tid,
                "replay_classification": result.classification,
                "recorded_classification": rec["classification"],
                "matches_recorded":
                    result.classification == rec["classification"]}


def make_session(legs: str, workdir: pathlib.Path) -> DualPathSession:
    """Session factory: Batch A legs -> pinned DualPathSession; Batch B
    legs -> the dualpath_b-routing adapter above."""
    if legs == "b":
        return BatchBDualPathSession(workdir)
    return DualPathSession(workdir)
