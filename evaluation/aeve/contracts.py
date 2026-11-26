"""Evidence loading, anonymous scoring views and deterministic veto."""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent
DIMENSIONS = json.loads((ROOT / "evaluator_manifest.json").read_bytes())["dimensions"]


def sha(value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf8")).hexdigest()


@lru_cache(maxsize=2)
def _validator(schema):
    return Draft202012Validator(json.loads((ROOT / f"{schema}.schema.json").read_bytes()))


def validate(schema, obj):
    validator = _validator(schema)
    error = next(validator.iter_errors(obj), None)
    if error:
        raise ValueError(f"{schema}: {error.json_path}: {error.message}")


def load_input(obj):
    validate("input", obj)
    if len({e["id"] for e in obj["events"]}) != len(obj["events"]):
        raise ValueError("duplicate evidence event")
    supplied = {e["kind"] for e in obj["events"]}
    expected = set(_validator("input").schema["properties"]["missing"]["items"]["enum"])
    if supplied & set(obj["missing"]) or supplied | set(obj["missing"]) != expected:
        raise ValueError("missing-evidence declaration incomplete or inconsistent")
    for event in obj["events"]:
        if event["kind"] in {"provenance","runtime_identity"} and event["visibility"] != "internal":
            raise ValueError("identity metadata must be withheld")
        if sha(event["value"]) != event["sha256"]:
            raise ValueError("evidence value hash mismatch")
    return obj


def load_archive_input(obj, root):
    """Verify each JSON source blob and exact RFC6901 fragment against the normalized event."""
    load_input(obj)
    root = Path(root).resolve(strict=True)
    sources = {}
    for event in obj["events"]:
        name, _, fragment = event["source"].partition("#")
        file = (root / name).resolve(strict=True)
        if not file.is_relative_to(root) or not file.is_file():
            raise ValueError("evidence reference escapes archive")
        if file not in sources:
            raw = file.read_bytes()
            sources[file] = hashlib.sha256(raw).hexdigest(), json.loads(raw)
        digest, value = sources[file]
        if digest != event.get("source_sha256"):
            raise ValueError("source bytes differ from manifest")
        if fragment and not fragment.startswith("/"):
            raise ValueError("invalid evidence fragment")
        for component in fragment.split("/")[1:]:
            name = component.replace("~1", "/").replace("~0", "~")
            if isinstance(value, list):
                if not re.fullmatch(r"0|[1-9][0-9]*", name):
                    raise ValueError("invalid sequence index")
                name = int(name)
            value = value[name]
        if sha(value) != event["sha256"]:
            raise ValueError("source fragment differs from declared evidence")
    return obj


def blind_packet(obj, dimension):
    load_input(obj)
    if dimension not in DIMENSIONS:
        raise ValueError("unknown dimension")
    events = [e for e in obj["events"] if e["visibility"] == "judge"]
    aliases = []
    for e in obj["events"]:
        if e["kind"] == "runtime_identity" and isinstance(e["value"], dict):
            aliases.extend(v for k,v in e["value"].items() if k in {"model","family","alias","model_id"}
                           and isinstance(v, str) and v.strip())
    regex = re.compile("|".join(re.escape(v) for v in sorted(set(aliases), key=len, reverse=True)), re.I) if aliases else None
    def mask(v):
        if isinstance(v, dict):
            return {k: mask(item) for k,item in v.items() if k.casefold() not in
                    {"candidate", "model", "family", "model_id", "run_id", "old_score", "old_verdict", "gold_label"}}
        if isinstance(v, list):
            return [mask(item) for item in v]
        return regex.sub("[anonymous]", v) if regex and isinstance(v,str) else v
    payload = {"dimension": dimension, "task": mask(obj["public_task"]),
               "events": [{"id": f"e{i}", "kind": e["kind"], "value": mask(e["value"])} for i, e in enumerate(events, 1)]}
    return payload, {f"e{i}": e["id"] for i, e in enumerate(events, 1)}


def validate_judgment(packet, answer):
    validate("judgment", answer)
    ids = {e["id"] for e in packet["events"]}
    if len(ids) != len(packet["events"]):
        raise ValueError("ambiguous packet reference")
    refs = answer["evidence_refs"]
    if not set(refs) <= ids:
        raise ValueError("invented evidence reference")
    if answer["verdict"] != "BLOCKED" and not refs:
        raise ValueError("uncited conclusive judgment")
    return answer


def adjudicate(packet, votes, deterministic, target_family=None):
    if deterministic not in {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}:
        raise ValueError("invalid deterministic status")
    if deterministic in {"FAIL", "BLOCKED"}:
        return {"status": deterministic, "reason": "deterministic veto"}
    families = set()
    verdicts = set()
    for vote in votes:
        if not vote.get("family") or vote["family"] == target_family or vote["family"] in families:
            continue
        try:
            answer = validate_judgment(packet, vote["answer"])
        except ValueError:
            return {"status": "BLOCKED", "reason": "invalid evidence citation or judgment"}
        families.add(vote["family"])
        verdicts.add(answer["verdict"])
    if len(families) < 2:
        return {"status": "NOT_RUN", "reason": "independent family coverage incomplete"}
    if len(verdicts) != 1 or "BLOCKED" in verdicts:
        return {"status": "BLOCKED", "reason": "third family required" if len(families) == 2 else "review required"}
    decision = verdicts.pop()
    if deterministic == "PASS" and decision == "FAIL":
        return {"status": "BLOCKED", "reason": "deterministic and semantic findings conflict"}
    return {"status": decision, "reason": "consistent independent judgments"}
