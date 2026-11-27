"""Local, synthetic business transactions for MULTITOOL-V2 software qualification."""

from collections.abc import Iterable
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from model_gateway.errors import GatewayError
from model_gateway.strict_json import strict_object


_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS sessions (
           session_id TEXT PRIMARY KEY, instance_id TEXT NOT NULL UNIQUE,
           scope_version INTEGER NOT NULL CHECK (scope_version > 0))""",
    """CREATE TABLE IF NOT EXISTS scope_entities (
           session_id TEXT NOT NULL REFERENCES sessions, entity_id TEXT NOT NULL,
           PRIMARY KEY (session_id, entity_id))""",
    """CREATE TABLE IF NOT EXISTS drafts (
           session_id TEXT NOT NULL REFERENCES sessions, draft_id TEXT NOT NULL,
           draft_version INTEGER NOT NULL, entity_id TEXT NOT NULL, scope_version INTEGER NOT NULL,
           text TEXT NOT NULL, PRIMARY KEY (session_id, draft_id, draft_version))""",
    """CREATE TABLE IF NOT EXISTS decisions (
           session_id TEXT NOT NULL, draft_id TEXT NOT NULL, draft_version INTEGER NOT NULL,
           entity_id TEXT NOT NULL, scope_version INTEGER NOT NULL, event_id TEXT NOT NULL UNIQUE,
           decision TEXT NOT NULL CHECK (decision IN ('APPROVED', 'DENIED')),
           PRIMARY KEY (session_id, draft_id, draft_version),
           FOREIGN KEY (session_id, draft_id, draft_version) REFERENCES drafts)""",
    """CREATE TABLE IF NOT EXISTS releases (
           session_id TEXT NOT NULL, draft_id TEXT NOT NULL, draft_version INTEGER NOT NULL,
           entity_id TEXT NOT NULL, scope_version INTEGER NOT NULL,
           event_id TEXT NOT NULL REFERENCES decisions(event_id), text TEXT NOT NULL,
           PRIMARY KEY (session_id, draft_id),
           FOREIGN KEY (session_id, draft_id, draft_version) REFERENCES drafts)""",
    """CREATE TABLE IF NOT EXISTS audit (
           sequence INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions,
           event TEXT NOT NULL, outcome TEXT NOT NULL, scope_version INTEGER NOT NULL,
           draft_id TEXT, draft_version INTEGER, entity_id TEXT, event_id TEXT)""",
)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_TARGET_FIELDS = {"entity_id", "draft_id", "draft_version"}
_ARGUMENTS = {
    "create_draft": {"entity_id", "draft_id", "text"},
    "revise_draft": _TARGET_FIELDS | {"text"},
    "read_draft": _TARGET_FIELDS,
    "commit_draft": _TARGET_FIELDS,
}


def _valid_id(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _valid_version(value):
    return type(value) is int and 0 < value < 2**63


def _scope(entities):
    if isinstance(entities, (str, bytes)) or not isinstance(entities, Iterable):
        raise ValueError("scope must be a collection of entity IDs")
    result = set()
    for entity in entities:
        if not _valid_id(entity):
            raise ValueError("scope contains an invalid entity ID")
        result.add(entity)
    return result


def _arguments(tool, raw):
    if type(tool) is not str or tool not in _ARGUMENTS:
        return None
    try:
        args = strict_object(raw)
    except GatewayError:
        return None
    if (args.keys() != _ARGUMENTS[tool] or not _valid_id(args["entity_id"]) or not _valid_id(args["draft_id"])
            or ("draft_version" in args and not _valid_version(args["draft_version"]))):
        return None
    if "text" in args:
        text = args["text"]
        if type(text) is not str or len(text) > 2000 or not text.strip() or "\0" in text:
            return None
    return args


@dataclass(frozen=True, slots=True)
class DraftReview:
    """Exact persisted draft displayed by the host before accepting a decision."""

    session_id: str
    session_instance_id: str
    entity_id: str
    draft_id: str
    draft_version: int
    scope_version: int
    text: str


class SQLiteSandbox:
    """Expose only invoke to the model. Session grants and decisions enter through the host."""

    def __init__(self, path: Path | str, *, session_id: str, initial_scope: Iterable[str] | None = None):
        if not _valid_id(session_id) or str(path) == ":memory:":
            raise ValueError("a valid session ID and file-backed database are required")
        self._session = session_id
        self._path = Path(path).resolve()
        scope = None if initial_scope is None else _scope(initial_scope)
        with self._transaction() as db:
            for statement in _SCHEMA:
                db.execute(statement)
            existing = db.execute("SELECT 1 FROM sessions WHERE session_id = ?", (self._session,)).fetchone()
            if existing:
                if scope is not None and scope != self._grants(db):
                    raise ValueError("use the host scope update for an existing session")
            else:
                if scope is None:
                    raise ValueError("a new session requires explicit host scope")
                db.execute("INSERT INTO sessions VALUES (?, ?, 1)", (self._session, uuid4().hex))
                self._replace_grants(db, scope)

    @contextmanager
    def _transaction(self):
        with closing(sqlite3.connect(self._path, autocommit=True)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.execute("COMMIT")
            finally:
                if db.in_transaction:
                    db.execute("ROLLBACK")

    def _scope_version(self, db):
        return db.execute("SELECT scope_version FROM sessions WHERE session_id = ?", (self._session,)).fetchone()[0]

    def _grants(self, db):
        return {row[0] for row in db.execute("SELECT entity_id FROM scope_entities WHERE session_id = ?",
                                              (self._session,))}

    def _replace_grants(self, db, scope):
        db.execute("DELETE FROM scope_entities WHERE session_id = ?", (self._session,))
        db.executemany("INSERT INTO scope_entities VALUES (?, ?)", ((self._session, entity) for entity in scope))

    def _audit(self, db, event, outcome, scope_version, target, event_id=None):
        db.execute("""INSERT INTO audit (session_id, event, outcome, scope_version, draft_id, draft_version,
                                        entity_id, event_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                   (self._session, event, outcome, scope_version, target.get("draft_id"), target.get("draft_version"),
                    target.get("entity_id"), event_id))

    def update_scope(self, entities: Iterable[str]) -> int:
        """Apply a host scope update and invalidate earlier uncommitted reviews."""
        scope = _scope(entities)
        with self._transaction() as db:
            version = self._scope_version(db) + 1
            db.execute("UPDATE sessions SET scope_version = ? WHERE session_id = ?", (version, self._session))
            self._replace_grants(db, scope)
            self._audit(db, "scope_update", "SCOPE_INVALIDATED", version, {})
        return version

    def _latest(self, db, draft_id):
        return db.execute("""SELECT draft_version, entity_id, drafts.scope_version, text, instance_id
                              FROM drafts JOIN sessions USING (session_id)
                             WHERE session_id = ? AND draft_id = ? ORDER BY draft_version DESC LIMIT 1""",
                          (self._session, draft_id)).fetchone()

    def _review(self, db, entity_id, draft_id, draft_version, scope_version):
        current = self._latest(db, draft_id)
        if (entity_id in self._grants(db) and current is not None and current["entity_id"] == entity_id
                and current["draft_version"] == draft_version and current["scope_version"] == scope_version):
            return DraftReview(self._session, current["instance_id"], entity_id, draft_id, draft_version,
                               scope_version, current["text"])
        return None

    def review_draft(self, *, entity_id: str, draft_id: str, draft_version: int) -> DraftReview | None:
        """Return a reviewable draft to the trusted host for display and confirmation."""
        if not _valid_id(entity_id) or not _valid_id(draft_id) or not _valid_version(draft_version):
            return None
        with self._transaction() as db:
            return self._review(db, entity_id, draft_id, draft_version, self._scope_version(db))

    def _decision(self, db, draft_id, draft_version):
        return db.execute("""SELECT entity_id, scope_version, event_id, decision FROM decisions
                             WHERE session_id = ? AND draft_id = ? AND draft_version = ?""",
                          (self._session, draft_id, draft_version)).fetchone()

    def record_decision(self, review: DraftReview, *, event_id: str, approved: bool) -> bool:
        """Persist a trusted host event for exactly the reviewed draft and permission scope."""
        if (type(review) is not DraftReview or review.session_id != self._session or not _valid_id(event_id)
                or type(approved) is not bool or not _valid_id(review.entity_id) or not _valid_id(review.draft_id)
                or not _valid_version(review.draft_version) or not _valid_version(review.scope_version)
                or type(review.text) is not str):
            return False
        decision = "APPROVED" if approved else "DENIED"
        target = {field: getattr(review, field) for field in _TARGET_FIELDS}
        with self._transaction() as db:
            scope_version = self._scope_version(db)
            current = self._review(db, **target, scope_version=scope_version)
            outcome = "REJECTED"
            if current == review:
                prior = self._decision(db, review.draft_id, review.draft_version)
                if prior is not None and (prior["event_id"], prior["decision"]) == (event_id, decision):
                    outcome = "REPLAYED"
                elif prior is None:
                    inserted = db.execute("""INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?)
                                             ON CONFLICT (event_id) DO NOTHING""",
                                          (self._session, review.draft_id, review.draft_version, review.entity_id,
                                           scope_version, event_id, decision))
                    if inserted.rowcount == 1:
                        outcome = decision
            self._audit(db, "external_decision", outcome, scope_version, target, event_id)
        return outcome != "REJECTED"

    def invoke(self, tool: str, arguments_raw: str | bytes) -> dict:
        """Execute only a schema-checked model tool proposal for this host-selected session."""
        args = _arguments(tool, arguments_raw)
        event = tool if type(tool) is str and tool in _ARGUMENTS else "unknown_tool"
        target = {} if args is None else {field: args[field] for field in _TARGET_FIELDS if field in args}
        try:
            with self._transaction() as db:
                scope_version = self._scope_version(db)
                db.execute("SAVEPOINT tool_proposal")
                event_id = None
                try:
                    if args is None:
                        code, data, outcome = "invalid_call", {}, "INVALID_CALL"
                    else:
                        code, data, outcome, event_id = self._execute(db, tool, args, scope_version)
                    self._audit(db, event, outcome, scope_version, target | data, event_id)
                except sqlite3.Error:
                    db.execute("ROLLBACK TO tool_proposal")
                    self._audit(db, event, "ROLLED_BACK", scope_version, target, event_id)
                    code, data = "transaction_failed", {}
                db.execute("RELEASE tool_proposal")
        except sqlite3.Error:
            return {"code": "transaction_failed", "data": {}}
        return {"code": code, "data": data}

    def _execute(self, db, tool, args, scope_version):
        entity_id, draft_id = args["entity_id"], args["draft_id"]
        denied = "permission_denied", {}, "OUT_OF_SCOPE", None
        if entity_id not in self._grants(db):
            return denied
        current = self._latest(db, draft_id)
        if tool == "create_draft":
            if current is not None:
                return denied
            return self._stage(db, args, scope_version, 1)
        if current is None or current["entity_id"] != entity_id or current["draft_version"] != args["draft_version"]:
            return denied
        release = db.execute("SELECT event_id FROM releases WHERE session_id = ? AND draft_id = ?",
                             (self._session, draft_id)).fetchone()
        if tool == "revise_draft":
            if release is not None:
                return denied
            return self._stage(db, args, scope_version, current["draft_version"] + 1)
        if current["scope_version"] != scope_version:
            return denied
        data = {field: args[field] for field in _TARGET_FIELDS} | {"scope_version": scope_version}
        if tool == "read_draft":
            return "ok", data | {"text": current["text"]}, "READ", None
        decision = self._decision(db, draft_id, current["draft_version"])
        if decision is None or (decision["entity_id"], decision["scope_version"]) != (entity_id, scope_version):
            return "permission_denied", {}, "APPROVAL_REQUIRED", None
        event_id = decision["event_id"]
        if decision["decision"] == "DENIED":
            return "permission_denied", {}, "APPROVAL_DENIED", event_id
        if release is not None:
            if event_id != release["event_id"]:
                return denied
            return "committed", data, "REPLAYED", event_id
        db.execute("INSERT INTO releases VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (self._session, draft_id, current["draft_version"], entity_id, scope_version, event_id, current["text"]))
        return "committed", data, "COMMITTED", event_id

    def _stage(self, db, args, scope_version, version):
        draft_id, entity_id = args["draft_id"], args["entity_id"]
        db.execute("INSERT INTO drafts VALUES (?, ?, ?, ?, ?, ?)",
                   (self._session, draft_id, version, entity_id, scope_version, args["text"]))
        data = {"entity_id": entity_id, "draft_id": draft_id, "draft_version": version, "scope_version": scope_version}
        return "drafted", data, "DRAFTED", None

    def snapshot(self) -> dict:
        """Read a consistent, session-bound account for independent software witnesses."""
        with self._transaction() as db:
            snapshot = {"scope_version": self._scope_version(db), "scope": sorted(self._grants(db))}
            for table, order in (("drafts", "draft_id, draft_version"), ("decisions", "draft_id, draft_version"),
                                 ("releases", "draft_id"), ("audit", "sequence")):
                rows = db.execute(f"SELECT * FROM {table} WHERE session_id = ? ORDER BY {order}", (self._session,))
                snapshot[table] = [{key: row[key] for key in row.keys() if key != "session_id"} for row in rows]
        return snapshot
