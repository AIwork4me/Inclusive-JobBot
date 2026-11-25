"""Check the frozen archive and replay only observed V1 actions and final states."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from benchmarks.agentic_planning_v2.trace import assess
from scripts.tools.ij073_baseline import digest, read, records


def verified_cases(directory):
    bundle = read(directory / "bundle.json")
    manifest = directory / "archive_manifest.json"
    if digest(manifest) != bundle["archive_manifest_sha256"]:
        raise ValueError("manifest hash mismatch")
    members = read(manifest)["sha256"]
    seen = set()
    for name, entry in bundle["parts"].items():
        part = directory / name
        if digest(part) != entry["sha256"]:
            raise ValueError(f"damaged part {name}")
        for obj in records(part):
            member, raw = obj["name"], obj["raw_text"]
            if member in seen or hashlib.sha256(raw.encode()).hexdigest() != members[member]:
                raise ValueError(f"damaged or duplicate member {member}")
            seen.add(member)
            if member.startswith("cases/"):
                trial = json.loads(raw)
                if trial["run_id"] != bundle["run_id"] or member != f"cases/{trial['trial']['trial_id']}.json":
                    raise ValueError("trial identity mismatch")
                yield members[member], trial
    if seen != members.keys():
        raise ValueError("incomplete bundle")


def audit():
    frozen = Path("benchmarks/agentic_planning_v1")
    cases, graphs = ({r["case_id"]: r for r in records(frozen / p / "holdout.jsonl")}
                     for p in ("datasets", "task_graphs"))
    rows = []
    for panel in ("primary", "repeat"):
        directory = Path("evidence/IJ07/planning") / (panel + "-vulkan-full")
        for sha, trial in verified_cases(directory):
            case_id = trial["case_id"]
            rows.append({"panel": panel, "run_id": trial["run_id"], "trial": trial["trial"], "track": trial["track"],
                         "member_sha256": sha, "old_status": trial["status"],
                         **assess(cases[case_id], graphs[case_id], trial)})
    counts = Counter((r["panel"], r["track"]) for r in rows)
    if counts != {("primary", "A"): 800, ("primary", "P"): 800, ("repeat", "A"): 480, ("repeat", "P"): 480}:
        raise ValueError("unexpected archived coverage")
    return {"scope": "offline replay of observed actions, external approvals, final object and business state",
            "summary": {k: dict(Counter(r[k] for r in rows)) for k in ("trace_replay", "commit_authorization", "final_and_state")},
            "trials": rows}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
