"""Compare P0/P1 on the twenty frozen Qwen3-8B L0 Plan-first trials."""

from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.freeze import FROZEN
from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.atlas_validity.evaluation import planning_scores_v2
from benchmarks.job_productivity_v1.statistics import exact_mcnemar, wilson_interval
from scripts.tools.atlas_progress import document, jsonl
from scripts.tools.bundle_ij07_planning import verify

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJ072/benchmark_validity"
OUTPUT = EVIDENCE / "pc-p-qwen3-l0-p0-p1.json"


def selected_archive(archive, selected):
    verify(archive)
    diagnostic = document(archive / "diagnostic.json")
    if diagnostic["evidence"]["physical_execution_status"] != "PASS":
        raise ValueError("pilot results require PID and source evidence")
    cases, run = {}, None
    for part in sorted(archive.glob("planning-part-*.jsonl.gz")):
        for entry in jsonl(part):
            if entry["name"] == "run.json":
                run = json.loads(entry["raw_text"])
            elif entry["name"].startswith("cases/AP1-L0-"):
                row = json.loads(entry["raw_text"])
                if row["track"] == "P" and row["case_id"] in selected:
                    if row["case_id"] in cases or row["run_id"] != diagnostic["run_id"]:
                        raise ValueError("duplicate or mismatched matched pilot trial")
                    cases[row["case_id"]] = row
    if cases.keys() != selected or run is None:
        raise ValueError("incomplete PC-P comparison roster")
    return run, cases


def compare():
    roster = document(ROOT / "atlas/benchmarks/pc_s_roster.json")["planning_v1"]["selection_by_stratum"]
    selected = set(roster["L0/en"] + roster["L0/zh"])
    p0, original = selected_archive(EVIDENCE / "pc-s-planning-checkpoint", selected)
    p1, revised = selected_archive(EVIDENCE / "pc-p-qwen3-l0-p1", selected)
    left, right = p0["configuration"], p1["configuration"]
    omit = {"trials", "settings"}
    if (any(left[key] != right[key] for key in left.keys() - omit)
            or left["settings"] | {"prompt_contract": "p1"} != right["settings"]
            or left["model"]["official_model_id"] != "Qwen/Qwen3-8B"):
        raise ValueError("paired pilot changed an input other than the planned prompt treatment or scope")
    public = {row["case_id"]: row for row in load_jsonl(FROZEN / "datasets/holdout.jsonl")}
    oracle = {row["case_id"]: row for row in load_jsonl(FROZEN / "task_graphs/holdout.jsonl")}
    pairs = []
    counts = {"p0": Counter(), "p1": Counter()}
    for case_id in sorted(selected):
        a, b = original[case_id], revised[case_id]
        if a["trial"] != b["trial"]:
            raise ValueError("pilot seed or case identity differs")
        pair = {"case_id": case_id, "language": public[case_id]["language"]}
        for arm, row in (("p0", a), ("p1", b)):
            scores = planning_scores_v2(public[case_id], oracle[case_id], row)
            counts[arm].update(f"{name}/{status}" for name, status in scores.items())
            pair[arm] = scores
        pairs.append(pair)
    endpoints = {}
    for dimension in ("initial_plan_protocol", "strict_end_to_end"):
        old_only = sum(pair["p0"][dimension] == "PASS" and pair["p1"][dimension] == "FAIL" for pair in pairs)
        new_only = sum(pair["p0"][dimension] == "FAIL" and pair["p1"][dimension] == "PASS" for pair in pairs)
        endpoints[dimension] = {
            "p0_only": old_only, "p1_only": new_only,
            "mcnemar_exact_two_sided_descriptive": exact_mcnemar(old_only, new_only),
            "wilson95": {arm: wilson_interval(counts[arm][f"{dimension}/PASS"], len(pairs))
                         for arm in counts},
        }
    return {"scope": "paired physical L0 Plan-first diagnostic, single reference model",
            "planned_pairs": len(pairs), "p0_run_id": p0["run_id"], "p1_run_id": p1["run_id"],
            "source_commit": left["git"]["commit"], "counts": counts, "endpoints": endpoints, "pairs": pairs}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = compare()
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if OUTPUT.read_bytes() != raw:
            parser.error("PC-P paired evidence differs")
    else:
        with OUTPUT.open("xb") as handle:
            handle.write(raw)
    for arm, counts in result["counts"].items():
        print(arm, counts)


if __name__ == "__main__":
    main()
