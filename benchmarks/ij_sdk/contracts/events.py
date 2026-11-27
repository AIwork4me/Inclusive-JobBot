"""IJ-SDK-1.0 P4: unified event schema for wire-level capture.

Every adapter must emit these events for the full observable chain:

    user task -> SDK request -> SDK model adapter -> llama-server request
      -> rendered chat template -> model generation -> parser/structured
      -> SDK interpretation -> tool gateway -> tool execution -> tool result
      -> subsequent model request -> final business state -> evaluator

Stage enumeration (STAGE) is closed; adapters record which stages were
observable. An unavailable internal representation is recorded as
`not_captured` with the reason - never reconstructed and relabeled as
directly captured evidence (mission 7.2).

Events are JSONL rows; every row carries run_id, trial_id, seq, stage.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

STAGES = (
    "task_input",
    "sdk_request",        # request the SDK receives from the runner
    "sdk_model_adapter",  # SDK -> model client call (captured when the SDK exposes it)
    "server_request",     # bytes sent to llama-server /v1/chat/completions
    "chat_template",      # rendered template (via /apply-template when available)
    "model_generation",   # raw server response (choices, finish_reason, usage)
    "parser_output",      # SDK/parser interpretation (tool_calls, structured object)
    "tool_gateway",       # gateway decision (allow/deny/fault) with reasons
    "tool_execution",     # handler invocation (arguments, idempotency key)
    "tool_result",        # returned payload or error
    "business_state",     # post-action business world state hash or diff
    "final_answer",       # SDK-reported final output
    "usage",              # token/model-call accounting from the server
)

NOT_CAPTURED = "not_captured"


def _utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class EventLog:
    """Append-only JSONL event writer with per-trial sequencing."""

    def __init__(self, path):
        self.path = str(path)
        self._seq = 0
        self._sha = hashlib.sha256()
        self._fh = open(self.path, "a", encoding="utf-8")

    def emit(self, run_id: str, trial_id: str, stage: str, payload: dict[str, Any], **meta) -> int:
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}; closed vocabulary")
        self._seq += 1
        row = {
            "seq": self._seq,
            "run_id": run_id,
            "trial_id": trial_id,
            "stage": stage,
            "ts_utc": _utc(),
            "payload": payload,
        }
        row.update(meta)
        line = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        self._sha.update(line.encode("utf-8"))
        self._fh.write(line + "\n")
        self._fh.flush()
        return self._seq

    def not_captured(self, run_id: str, trial_id: str, stage: str, reason: str) -> int:
        return self.emit(run_id, trial_id, stage, {"status": NOT_CAPTURED, "reason": reason})

    def digest(self) -> str:
        """SHA256 over the emitted JSONL bytes (evidence identity)."""
        return self._sha.hexdigest()

    def close(self) -> None:
        self._fh.close()


def read_events(path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows
