"""Compute secondary outcomes for the frozen IJ-0.7 primary planning archive."""

from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from benchmarks.atlas_validity.evaluation import planning_scores
from benchmarks.agentic_planning_v1.run import load_jsonl
from scripts.tools.atlas_progress import jsonl


def replay():
    dataset = ROOT / "benchmarks/agentic_planning_v1"
    public = {r["case_id"]: r for r in load_jsonl(dataset / "datasets/holdout.jsonl")}
    graphs = {r["case_id"]: r for r in load_jsonl(dataset / "task_graphs/holdout.jsonl")}
    archive = ROOT / "evidence/IJ07/planning/primary-vulkan-full"
    run_id = json.loads((archive / "archive_manifest.json").read_bytes())["run_id"]
    scores = defaultdict(Counter)
    seen = set()
    for file in sorted(archive.glob("planning-part-*.jsonl.gz")):
        for entry in jsonl(file):
            if not entry["name"].startswith("cases/"):
                continue
            row = json.loads(entry["raw_text"])
            case_id, track = row["case_id"], row["track"]
            if (case_id, track) in seen or row["run_id"] != run_id:
                raise ValueError("duplicate or mismatched primary planning trial")
            seen.add((case_id, track))
            outcomes = planning_scores(public[case_id], graphs[case_id], row)
            scores[track].update(f"{key}/{value}" for key, value in outcomes.items())
    if seen != {(case_id, track) for case_id in public for track in ("A", "P")}:
        raise ValueError("incomplete primary planning roster")
    return {"scope": "secondary diagnostic replay of the frozen IJ-0.7 primary outcomes",
            "run_id": run_id, "diagnostic_counts_by_track": scores}


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2, sort_keys=True))
