"""Validate the independent software-history roster and its derived-source links."""
from collections import Counter
import gzip
import hashlib
import json

from .history import lines

ELIGIBLE = "eligible_independent_software_evidence"
REUSED = {"reuse_source_semantic_evaluation", "reuse_identical_captured_software_evidence"}
COLLECTION = "history-supplement-v2"
INPUT = "judge_inputs_nonphysical_v2.jsonl.gz"
INVENTORY = "nonphysical_evaluability.jsonl.gz"
MANIFEST = "nonphysical_coverage.json"


def inventory(folder):
    required = (INPUT, INVENTORY, MANIFEST)
    missing = [name for name in required if not (folder / name).is_file()]
    if missing:
        return {}, {"status": "BLOCKED", "reason": "supplemental inventory incomplete", "missing": missing}
    manifest = json.loads((folder / MANIFEST).read_bytes())
    if manifest["version"] != 2:
        raise ValueError("unknown nonphysical coverage contract")
    for name, key in ((INPUT, "inputs"), (INVENTORY, "registry")):
        with gzip.open(folder / name, "rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != manifest["sha256_uncompressed"][key]:
                raise ValueError("supplemental input or registry integrity mismatch")
    registry = {}
    eligible = set()
    derived = set()
    classes = Counter()
    for row in lines(folder / INVENTORY):
        tid = row["trial_id"]
        reason = row["semantic_disposition"]
        if tid in registry or row["record_class"] == "physical_trial":
            raise ValueError("duplicate or physical trial in supplemental registry")
        if reason == ELIGIBLE:
            eligible.add(tid)
        if bool(row["source_trial_id"]) != (reason in REUSED) or row["source_trial_id"] == tid:
            raise ValueError("inconsistent derived source link")
        if row["source_trial_id"]:
            derived.add(tid)
        classes[row["record_class"], reason] += 1
        registry[tid] = row
    unique = set()
    dims = Counter()
    for packet in lines(folder / INPUT):
        tid = packet["trial_id"]
        row = registry.get(tid, {})
        if (tid not in eligible or tid in unique or packet["record_class"] != row["record_class"] or
                packet["source_family"] != row["subject_family"] or packet["source_sha256"] != row["source"][2]):
            raise ValueError("supplemental packet lacks a distinct registered source")
        if len(set(packet["dimensions"])) != len(packet["dimensions"]):
            raise ValueError("duplicate supplemental dimension")
        unique.add(tid)
        dims.update(packet["dimensions"])
    expected = {(k, reason): n for k, counts in manifest["denominators"].items() for reason,n in counts.items()}
    if (unique != eligible or len(registry) != manifest["registered"] or len(unique) != manifest["unique_semantic_packets"]
            or dims != manifest["dimensions"] or len(derived) != manifest["linked_source_records"] or classes != expected):
        raise ValueError("supplemental coverage denominators differ")
    return registry, {"status": "PASS", "registered": len(registry), "independent_inputs": len(eligible),
                      "linked_source_records": len(derived), "by_class": manifest["denominators"],
                      "sha256_uncompressed": manifest["sha256_uncompressed"]}


def bind(trial, registry, present):
    if not present or trial["class"] == "physical_trial":
        if trial["trial_id"] in registry:
            raise ValueError("physical record in supplemental denominator")
        return None
    row = registry.get(trial["trial_id"])
    if not row or row["record_class"] != trial["class"] or row["source"] not in trial["sources"]:
        raise ValueError("supplemental record does not bind to historical source")
    for dim, value in trial["deterministic"].items():
        if row["deterministic"].get(dim) != value:
            raise ValueError("supplemental record changed a deterministic fact")
    return row


def require_independent_review(result, admitted, families, subject):
    votes = result["votes"]
    if (result["status"] not in {"PASS","FAIL","BLOCKED"} or result["primary_recorded"] != 2 or result["invalid"]
            or (result["disputed"] and (not result["third_recorded"] or len(votes) < 3))):
        raise ValueError("unverified formal historical review")
    if not set(votes) <= admitted or len({families[c] for c in votes}) != len(votes):
        raise ValueError("unqualified or duplicate judge family")
    if any(families[c].casefold() == subject.casefold() for c in votes):
        raise ValueError("self-family review")
    if any((v not in {"PASS","FAIL","BLOCKED"} or
            result["citation_support"].get(c) != ("abstention" if v == "BLOCKED" else "supported"))
           for c,v in votes.items()) or len(votes) < 2:
        raise ValueError("citation support or abstention missing")
