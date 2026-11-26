"""Seal portable, verifiable per-session bundles from the live evaluation queue."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil

from scripts.tools.scan_sensitive import CREDENTIAL_PATTERNS, identity_patterns
from .runtime import canonical, write_json

SENSITIVE = {**CREDENTIAL_PATTERNS, **identity_patterns()}


def check_text(raw):
    text = raw.decode("utf8")
    for label, pattern in SENSITIVE.items():
        if pattern.search(text):
            raise ValueError(f"publication blocked by sensitive-data check: {label}")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def export(db, state, out):
    sealed = 0
    for stamp in sorted((state / "sessions").glob("*/seal.json")):
        folder, run_id = stamp.parent, stamp.parent.name
        target = out / "sessions" / run_id
        if (target / "manifest.json").exists():
            continue
        target.mkdir(parents=True, exist_ok=True)
        metadata = json.loads((folder / "identity.json").read_bytes())
        seal = json.loads(stamp.read_bytes())
        if seal["run_id"] != run_id or metadata["run_id"] != run_id:
            raise ValueError("session identity differs")
        for name, expected in seal["sha256"].items():
            source = folder / name
            if source.parent != folder or digest(source) != expected:
                raise ValueError("session evidence hash differs")
            with gzip.open(source, "rb") as stream:
                for line in stream:
                    check_text(line)
            shutil.copyfile(source, target / name)
        write_json(target / "identity.json", metadata)
        check_text((target / "identity.json").read_bytes())
        rows = db.execute("""SELECT a.*,j.collection,j.item,j.dimension,j.role,j.candidate,j.spec,j.result FROM attempts a
                            JOIN jobs j ON a.job=j.id WHERE a.run=? AND a.ended IS NOT NULL ORDER BY a.id""", (run_id,))
        summaries = []
        with (target / "captures.jsonl.gz").open("wb") as output, gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as stream:
            for row in rows:
                raw = (state / row["evidence_path"]).read_bytes()
                if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                    raise ValueError("captured attempt hash differs")
                obj = json.loads(gzip.decompress(raw))
                if obj["job"] != row["job"] or obj["run"] != run_id:
                    raise ValueError("captured attempt identity differs")
                spec = json.loads(gzip.decompress(row["spec"]))
                record = {**obj, "spec": spec, "collection": row["collection"], "item": row["item"],
                          "role": row["role"], "candidate": row["candidate"], "dimension": row["dimension"]}
                line = canonical(record)
                check_text(line)
                stream.write(line + b"\n")
                summaries.append({k: record[k] for k in ("job","collection","item","role","candidate","dimension","evaluation","transport")})
        write_json(target / "outcomes.json", summaries)
        files = {p.name: digest(p) for p in sorted(target.iterdir()) if p.is_file()}
        write_json(target / "manifest.json", {**seal, "sha256": files, "attempts": len(summaries)})
        sealed += 1
    return sealed


def verify(out):
    jobs = set()
    for path in sorted((out / "sessions").glob("*/manifest.json")):
        manifest = json.loads(path.read_bytes())
        for name, expected in manifest["sha256"].items():
            if Path(name).name != name or digest(path.parent / name) != expected:
                raise ValueError(f"evidence mismatch in {path.parent.name}")
        outcomes = json.loads((path.parent / "outcomes.json").read_bytes())
        count = 0
        with gzip.open(path.parent / "captures.jsonl.gz", "rb") as stream:
            for count, line in enumerate(stream, 1):
                item = json.loads(line)
                outcome = outcomes[count-1]
                if item["run"] != manifest["run_id"] or any(item[k] != v for k,v in outcome.items()) or item["job"] in jobs:
                    raise ValueError("portable capture index mismatch")
                jobs.add(item["job"])
        if count != manifest["attempts"] or count != len(outcomes):
            raise ValueError("incomplete capture volume")
    return len(jobs)
