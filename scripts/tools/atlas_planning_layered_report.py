"""Run the expanded Planning diagnostics on a sealed Qwen3 PC-S panel."""

from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.freeze import FROZEN, verify
from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.atlas_validity.evaluation import planning_layered_scores
from scripts.tools.atlas_progress import document, jsonl
from scripts.tools.bundle_ij07_planning import verify as verify_archive


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJ072/benchmark_validity"
ARCHIVE = EVIDENCE / "pc-s-planning-full"
OUTPUT = EVIDENCE / "pc-s-planning-layered.json"
STRONG_ARCHIVE = EVIDENCE / "pc-s-j-planning-full"
STRONG_OUTPUT = EVIDENCE / "pc-s-j-planning-layered.json"
STATUSES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE")


def build(archive=ARCHIVE, model="Qwen3-8B"):
    verify_archive(archive)
    diagnostic = document(archive / "diagnostic.json")
    if (diagnostic["evidence"]["physical_execution_status"] != "PASS"
            or diagnostic["identity"]["model"]["official_model_id"] != f"Qwen/{model}"):
        raise ValueError("expanded diagnostics require the sealed PC-S archive")
    manifest = verify(FROZEN)
    cases = {row["case_id"]: row for row in load_jsonl(FROZEN / "datasets/holdout.jsonl")}
    graphs = {row["case_id"]: row for row in load_jsonl(FROZEN / "task_graphs/holdout.jsonl")}
    trials = {}
    for part in sorted(archive.glob("planning-part-*.jsonl.gz")):
        for entry in jsonl(part):
            if not entry["name"].startswith("cases/"):
                continue
            row = json.loads(entry["raw_text"])
            key, case_id = row["trial"]["trial_id"], row["case_id"]
            if key in trials or row["run_id"] != diagnostic["run_id"]:
                raise ValueError("duplicated or foreign PC-S case")
            case = cases[case_id]
            trials[key] = {"track": row["track"], "level": case["level"], "language": case["language"],
                           "dimensions": planning_layered_scores(case, graphs[case_id], row)}
    if len(trials) != diagnostic["overall"]["planned_n"]:
        raise ValueError("PC-S archive differs from its complete frozen roster")
    aggregate = {}
    for track in ("A", "P"):
        sample = [trial["dimensions"] for trial in trials.values() if trial["track"] == track]
        aggregate[track] = {}
        for name in sample[0]:
            counts = Counter(trial[name] for trial in sample)
            aggregate[track][name] = {
                "applicable": len(sample) - counts["NOT_APPLICABLE"],
                "assessed": counts["PASS"] + counts["FAIL"],
                "outcomes": {status: counts[status] for status in STATUSES},
            }
    return {
        "scope": f"{model} physical PC-S Planning secondary diagnostic",
        "dataset_sha256": manifest["artifact_sha256"]["datasets/holdout.jsonl"],
        "physical_run_id": diagnostic["run_id"],
        "original_scores": "retained in the source archive",
        "measurement_notes": {
            "tool_selection": "Relevance of observed tool names",
            "tool_arguments": "Argument equality to a scenario action, independently of its dependencies",
            "dynamic_replanning": "Recovery measured after delivery of the relevant disruption observation",
            "persisted_state": "Sandbox state check when the API exposes a write operation",
            "semantic_correctness": "Frozen structured facts with fence extraction for diagnostics",
        },
        "aggregate": aggregate, "trials": trials,
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--strong", action="store_true")
    args = parser.parse_args()
    result = build(STRONG_ARCHIVE, "Qwen3-14B") if args.strong else build()
    output = STRONG_OUTPUT if args.strong else OUTPUT
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if output.read_bytes() != raw:
            parser.error("expanded Planning diagnostics differ")
    else:
        with output.open("xb") as stream:
            stream.write(raw)
    print(f"Verified {len(result['trials'])} Planning trajectories with separate applicability denominators")


if __name__ == "__main__":
    main()
