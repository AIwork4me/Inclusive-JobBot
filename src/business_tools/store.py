"""Inspectable, isolated SQLite state with atomic business and audit writes."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

BUSINESS_TABLES = (
    "purchase_orders", "suppliers", "products", "inventory", "customers",
    "tickets", "follow_ups", "review_drafts",
)
TABLES = (*BUSINESS_TABLES, "approval_records", "audit_events")


class InvalidBusinessData(ValueError):
    """The proposed operation conflicts with current business records."""


def _encode(value) -> str:
    """Persist Decimal as a JSON number without passing through a float."""
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("non-finite decimal")
        return str(value)
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("state object keys must be strings")
        return "{" + ",".join(f"{_encode(key)}:{_encode(item)}" for key, item in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _decode(raw: str):
    return json.loads(raw, parse_float=Decimal)


def _table(name: str) -> str:
    if name not in TABLES:
        raise ValueError("unknown business table")
    return name


def _get(db: sqlite3.Connection, table: str, key: str) -> dict | None:
    row = db.execute(f"SELECT body FROM {_table(table)} WHERE id = ?", (key,)).fetchone()
    return None if row is None else _decode(row[0])


def _put(db: sqlite3.Connection, table: str, key: str, row: dict) -> dict:
    if not isinstance(key, str) or not key or not isinstance(row, dict):
        raise ValueError("business row requires a key and an object body")
    raw = _encode(row)
    db.execute(f"INSERT INTO {_table(table)}(id, body) VALUES (?, ?) "
               "ON CONFLICT(id) DO UPDATE SET body = excluded.body", (key, raw))
    return _decode(raw)


class UnitOfWork:
    """Trusted handlers can read business data and write only within a transaction."""

    def __init__(self, db: sqlite3.Connection, *, writable: bool, checkpoint,
                 draft_resource: str | None = None):
        self._db = db
        self._writable = writable
        self._checkpoint = checkpoint
        self._draft_resource = draft_resource
        self.before_state: dict[str, dict] = {}
        self.proposed_state: dict[str, dict] = {}

    def get(self, table: str, key: str) -> dict | None:
        self._checkpoint()
        if table not in BUSINESS_TABLES:
            raise ValueError("handler can only access business tables")
        return _get(self._db, table, key)

    def put(self, table: str, key: str, row: dict) -> None:
        if not self._writable:
            raise PermissionError("read-only handler attempted a write")
        previous = self.get(table, key)
        if self._draft_resource is not None and (
            table != "review_drafts" or key != self._draft_resource or previous is not None
            or row.get("submitted") is not False
        ):
            raise PermissionError("draft handler may only insert an unsubmitted draft for its resource")
        stored = _put(self._db, table, key, row)
        self.before_state.setdefault(table, {}).setdefault(key, previous)
        self.proposed_state.setdefault(table, {})[key] = stored

    def result(self, result: dict) -> dict:
        if not isinstance(result, dict):
            raise ValueError("handler result must be an object")
        return _decode(_encode(result))


class BusinessStore:
    def __init__(self, path: Path | str, *, initial: dict | None = None):
        if str(path) == ":memory:":
            raise ValueError("provide a per-experiment database path")
        self._path = Path(path).resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as db:
            for table in TABLES:
                db.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS tool_call_ids (
                       actor TEXT NOT NULL, session_id TEXT NOT NULL, call_id TEXT NOT NULL,
                       PRIMARY KEY(actor, session_id, call_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS completed_operations (
                       actor TEXT NOT NULL, operation_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                       confirmation TEXT NOT NULL, receipt TEXT NOT NULL,
                       PRIMARY KEY(actor, operation_id))""")
            db.execute("CREATE TABLE IF NOT EXISTS seed_marker (id INTEGER PRIMARY KEY CHECK (id = 1))")
            if initial is not None:
                db.execute("INSERT INTO seed_marker VALUES (1)")
                for table, rows in initial.items():
                    if table not in BUSINESS_TABLES:
                        raise ValueError("initial records may only seed business tables")
                    for key, row in rows.items():
                        _put(db, table, key, row)

    @contextmanager
    def _transaction(self, *, timeout: float = 3.0):
        db = sqlite3.connect(self._path, timeout=timeout, autocommit=True)
        try:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        finally:
            db.close()

    def snapshot(self) -> dict[str, dict]:
        """Return a consistent view for a trusted auditor or benchmark oracle."""
        with self._transaction() as db:
            return {
                table: {key: _decode(raw) for key, raw in db.execute(f"SELECT id, body FROM {table} ORDER BY id")}
                for table in TABLES
            }

    @staticmethod
    def _system_row(db: sqlite3.Connection, table: str, key: str) -> dict | None:
        return _get(db, table, key)

    @staticmethod
    def _put_system_row(db: sqlite3.Connection, table: str, key: str, row: dict) -> None:
        _put(db, table, key, row)

    @staticmethod
    def _reserve_call(db: sqlite3.Connection, actor: str, session: str, call_id: str) -> bool:
        result = db.execute(
            "INSERT INTO tool_call_ids VALUES (?, ?, ?) ON CONFLICT DO NOTHING", (actor, session, call_id),
        )
        return result.rowcount == 1

    @staticmethod
    def _receipt(db: sqlite3.Connection, actor: str, operation_id: str) -> tuple[str, str, dict] | None:
        record = db.execute(
            "SELECT fingerprint, confirmation, receipt FROM completed_operations WHERE actor = ? AND operation_id = ?",
            (actor, operation_id),
        ).fetchone()
        if record is None:
            return None
        fingerprint, confirmation, receipt = record
        return fingerprint, confirmation, _decode(receipt)

    @staticmethod
    def _save_receipt(db: sqlite3.Connection, actor: str, operation_id: str,
                      fingerprint: str, confirmation: str, receipt: dict) -> None:
        db.execute("INSERT INTO completed_operations VALUES (?, ?, ?, ?, ?)",
                   (actor, operation_id, fingerprint, confirmation, _encode(receipt)))
