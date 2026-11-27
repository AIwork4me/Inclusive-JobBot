"""Index immutable evidence by full experiment identity and physical origin."""

from hashlib import file_digest
import re

from evaluation.aeve.runtime import fingerprint


class MatchConflict(ValueError):
    """An existing identity is bound to different evidence."""


class TrialIdentity:
    HASH_FIELDS = {
        "model_sha256", "dataset_sha256", "runtime_sha256", "sdk_sha256", "prompt_sha256",
        "template_sha256", "tools_sha256", "permissions_sha256", "evaluation_sha256",
        "gpu_sha256", "host_sha256", "configuration_sha256",
    }
    LABEL_FIELDS = {"case_id", "track", "attempt_slot"}

    def __call__(self, spec):
        if set(spec) != self.HASH_FIELDS | self.LABEL_FIELDS:
            raise ValueError("incomplete experiment identity")
        if any(not isinstance(spec[field], str) or not re.fullmatch("[0-9a-f]{64}", spec[field])
               for field in self.HASH_FIELDS):
            raise ValueError("experiment fields require SHA256")
        if any(not isinstance(spec[field], str) or not spec[field].strip() for field in self.LABEL_FIELDS):
            raise ValueError("experiment labels must be nonempty")
        return fingerprint(spec)


identity = TrialIdentity()


class Registry:
    def __init__(self, db):
        self.db = db
        self.db.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS trials(
                signature TEXT PRIMARY KEY, physical_id TEXT NOT NULL UNIQUE,
                git_sha TEXT NOT NULL, runtime_session TEXT NOT NULL,
                physical_ordinal INTEGER NOT NULL, evidence_sha256 TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS references_by_mission(
                mission TEXT NOT NULL, signature TEXT NOT NULL REFERENCES trials(signature),
                PRIMARY KEY(mission, signature));
        """)

    def lookup(self, spec):
        fields = ("physical_id", "git_sha", "runtime_session", "physical_ordinal", "evidence_sha256")
        row = self.db.execute(
            "SELECT physical_id,git_sha,runtime_session,physical_ordinal,evidence_sha256 "
            "FROM trials WHERE signature=?", (identity(spec),)).fetchone()
        return dict(zip(fields, row, strict=True)) if row else None

    def add(self, mission, spec, origin, evidence, expected_sha256):
        if not isinstance(mission, str) or not mission.strip():
            raise ValueError("missing source mission")
        if set(origin) != {"git_sha", "runtime_session", "physical_ordinal"}:
            raise ValueError("incomplete physical origin")
        sha, session, ordinal = (origin[key] for key in ("git_sha", "runtime_session", "physical_ordinal"))
        if (not isinstance(sha, str) or not re.fullmatch("[0-9a-f]{40}", sha)
                or not isinstance(session, str) or not session.strip()
                or type(ordinal) is not int or ordinal < 0):
            raise ValueError("invalid physical origin")
        with evidence.open("rb") as source:
            observed = file_digest(source, "sha256").hexdigest()
        if observed != expected_sha256:
            raise ValueError("evidence sha256 differs from its seal")
        signature = identity(spec)
        physical = fingerprint([spec["host_sha256"], session, ordinal])
        record = (signature, physical, sha, session, ordinal, observed)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            existing = self.db.execute(
                "SELECT * FROM trials WHERE signature=? OR physical_id=?", record[:2]).fetchall()
            if existing and existing != [record]:
                raise MatchConflict("physical trial or experiment identity already bound")
            if not existing:
                self.db.execute("INSERT INTO trials VALUES (?,?,?,?,?,?)", record)
            self.db.execute("INSERT OR IGNORE INTO references_by_mission VALUES (?,?)", (mission, signature))
        return not existing

    def count(self):
        return self.db.execute("SELECT count(*) FROM trials").fetchone()[0]
