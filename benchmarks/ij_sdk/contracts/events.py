"""IJ-SDK-1.1 P4A (D07): unified event schema for wire-level capture.

Things that get observed on the way from a user task to a final business state
are different things and are labelled differently:

    what is captured                              stage
    ------------------------------------------    -------------------------
    the task handed to the adapter                task_input
    the request the SDK receives from the runner  sdk_request
    the SDK's own model-client call               sdk_model_adapter
    what is sent to the server                    server_request
    the rendered chat template                    chat_template
    raw response bytes from the server            server_response_raw
    the parsed response                           server_response_decoded
    token ids the engine actually emitted         model_generation
    the SDK's / parser's reading of the response  parser_output
    the gateway's decision                        tool_gateway
    the handler invocation                        tool_execution
    the returned payload                          tool_result
    the business world after an action            business_state
    the SDK's final output                        final_answer
    accounting                                    usage

A parsed Chat Completions body is NEVER labelled ``model_generation``: that
stage is reserved for token ids the engine returned. A stage the adapter could
not observe is written explicitly as ``not_captured`` with a reason. It is
never reconstructed and relabelled as a direct capture.

Every row carries a unique ``event_id``, a causal ``parent_id``, the tool
``call_id`` it belongs to, and a hash chain; ``seal`` freezes the file. A
missing, duplicated, reordered or edited event is therefore detectable.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from benchmarks.ij_sdk.schema import canonical_json

STAGES = (
    "task_input",
    "sdk_request",            # request the SDK receives from the runner
    "sdk_model_adapter",      # SDK -> model client call (captured when the SDK exposes it)
    "server_request",         # what is sent to the model server
    "chat_template",          # rendered template (via /apply-template when available)
    "server_response_raw",    # raw response bytes / SSE frames from the server
    "server_response_decoded",  # the parsed response (NOT raw token generation)
    "model_generation",       # token ids the engine emitted - the only thing that may carry this label
    "parser_output",          # SDK/parser interpretation (tool_calls, structured object)
    "tool_gateway",           # gateway decision (allow/deny/fault) with reasons
    "tool_execution",         # handler invocation (arguments, idempotency key)
    "tool_result",            # returned payload or error
    "business_state",         # business world digest and diff (phase: initial | step | final)
    "final_answer",           # SDK-reported final output
    "usage",                  # token / model-call accounting
)

NOT_CAPTURED = "not_captured"
GENESIS = "0" * 64


def _utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def row_hash(row: dict[str, Any]) -> str:
    body = {key: value for key, value in row.items() if key != "hash"}
    return hashlib.sha256((row.get("prev_hash", GENESIS) + canonical_json(body)).encode("utf-8")).hexdigest()


def _scan_head(path: str) -> tuple[int, str]:
    """Sequence number and chain head of an existing log, so appending resumes instead of restarting."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return 0, GENESIS
    last_seq, last_hash, count = 0, GENESIS, 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            count += 1
            try:
                row = json.loads(line)
            except ValueError:
                continue
            last_seq = max(last_seq, int(row.get("seq", 0)))
            last_hash = row.get("hash", GENESIS)
    if count == 0:
        return 0, GENESIS
    return last_seq, last_hash


class EventLog:
    """Append-only JSONL event writer with resume-safe sequencing and a hash chain."""

    def __init__(self, path, *, run_id: str = "run"):
        self.path = str(path)
        self.run_id = run_id
        self._seq, self._last_hash = _scan_head(self.path)
        self._last_event_id: str | None = None
        if self._seq:
            # resume: the id of the row we are appending after
            self._last_event_id = f"{run_id}#{self._seq:08d}"
        self._sealed = False
        self._fh = open(self.path, "a", encoding="utf-8")

    @staticmethod
    def _check_generation_label(stage: str, payload: dict[str, Any]) -> None:
        """``model_generation`` is reserved for token ids the engine returned. A parsed
        response, or anything else, is refused here rather than mislabelled downstream."""
        if stage != "model_generation":
            return
        declared_missing = payload.get("status") == NOT_CAPTURED and bool(payload.get("reason"))
        token_ids = payload.get("token_ids")
        real_tokens = isinstance(token_ids, list) and all(isinstance(t, int) and not isinstance(t, bool) for t in token_ids)
        if not (declared_missing or real_tokens):
            raise ValueError("model_generation may carry only token ids the engine returned ('token_ids'), "
                             "or status not_captured with a reason; a parsed response belongs to "
                             "server_response_decoded")

    def emit(self, run_id: str, trial_id: str, stage: str, payload: dict[str, Any], *,
             parent_id: str | None = None, call_id: str | None = None, **meta) -> int:
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}; closed vocabulary {STAGES}")
        self._check_generation_label(stage, payload)
        self._seq += 1
        row = {
            "event_id": f"{run_id}#{self._seq:08d}",
            "parent_id": parent_id,
            "run_id": run_id,
            "trial_id": trial_id,
            "call_id": call_id,
            "seq": self._seq,
            "stage": stage,
            "ts_utc": _utc(),
            "payload": payload,
            "prev_hash": self._last_hash,
        }
        row.update(meta)
        row["hash"] = row_hash(row)
        line = canonical_json(row)
        self._fh.write(line + "\n")
        self._fh.flush()
        self._last_hash = row["hash"]
        self._last_event_id = row["event_id"]
        return self._seq

    def not_captured(self, run_id: str, trial_id: str, stage: str, reason: str, **kw) -> int:
        """Declare that a stage could not be observed, and why."""
        return self.emit(run_id, trial_id, stage, {"status": NOT_CAPTURED, "reason": reason}, **kw)

    def digest(self) -> str:
        """Chain head: SHA256 over every emitted row so far (evidence identity)."""
        return self._last_hash

    def seal(self) -> dict[str, Any]:
        """Freeze the log: write a sidecar seal with row count, chain head and file digest."""
        self._fh.flush()
        self._sealed = True
        path = Path(self.path)
        text = path.read_bytes()
        seal = {
            "schema_version": 1,
            "file": path.name,
            "rows": self._seq,
            "sha256": hashlib.sha256(text).hexdigest(),
            "last_hash": self._last_hash,
            "sealed_utc": _utc(),
        }
        Path(self.path + ".seal.json").write_text(json.dumps(seal, indent=1) + "\n", encoding="utf-8")
        return seal

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    # information for callers
    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def last_event_id(self) -> str | None:
        return self._last_event_id


def read_events(path, *, trial_id: str | None = None) -> list[dict[str, Any]]:
    """Parse a JSONL event log. Raises ``ValueError`` on a line that is not a JSON object."""
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for number, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise ValueError(f"{Path(path).name}:{number}: not JSON ({exc})") from None
            if not isinstance(row, dict):
                raise ValueError(f"{Path(path).name}:{number}: event row must be a JSON object")
            if trial_id is None or row.get("trial_id") == trial_id:
                rows.append(row)
    return rows


def verify(path, seal: dict[str, Any] | str | None = None) -> dict[str, Any]:
    """Check a sealed log. Verifies every row's hash, the chain (each prev_hash equals the
    previous row's hash), strictly increasing sequence numbers, and - when a seal or an
    expected chain head is given - the row count, the head and the whole-file digest.

    Returns {"ok": bool, "problems": [...], "rows": n, "last_hash": ...}.
    """
    problems: list[str] = []
    rows: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for number, line in enumerate(fh, start=1):
                if not line.strip():
                    problems.append(f"line {number}: blank line inside the log")
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    problems.append(f"line {number}: not JSON")
                    continue
                rows.append(row)
    except OSError as exc:
        return {"ok": False, "problems": [f"cannot read log: {type(exc).__name__}"], "rows": 0, "last_hash": None}

    expected_prev = GENESIS
    previous_seq = 0
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if row.get("prev_hash") != expected_prev:
            problems.append(f"row {index}: chain broken (prev_hash does not match the previous row's hash)")
        if row_hash(row) != row.get("hash"):
            problems.append(f"row {index}: hash mismatch (row content was modified)")
        seq = row.get("seq")
        if not isinstance(seq, int) or seq <= previous_seq:
            problems.append(f"row {index}: sequence number {seq!r} is not greater than the previous one")
        else:
            previous_seq = seq
        event_id = row.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            problems.append(f"row {index}: missing event_id")
        elif event_id in seen_ids:
            problems.append(f"row {index}: duplicate event_id {event_id}")
        else:
            seen_ids.add(event_id)
        if row.get("stage") not in STAGES:
            problems.append(f"row {index}: unknown stage {row.get('stage')!r}")
        expected_prev = row.get("hash")
    last_hash = rows[-1].get("hash") if rows else None

    if isinstance(seal, str):                      # an expected chain head
        if last_hash != seal:
            problems.append("chain head differs from the expected digest (rows were added, removed or altered)")
    elif isinstance(seal, dict):
        if seal.get("rows") != len(rows):
            problems.append(f"row count {len(rows)} differs from the seal ({seal.get('rows')})")
        if seal.get("last_hash") != last_hash:
            problems.append("chain head differs from the seal")
        file_digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if seal.get("sha256") != file_digest:
            problems.append("file digest differs from the seal (bytes were modified after sealing)")
    return {"ok": not problems and bool(rows), "problems": problems, "rows": len(rows), "last_hash": last_hash}


def load_seal(path) -> dict[str, Any] | None:
    seal_path = Path(str(path) + ".seal.json")
    if not seal_path.exists():
        return None
    return json.loads(seal_path.read_text(encoding="utf-8"))
