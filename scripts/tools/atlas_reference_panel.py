"""Freeze the stratified software-independent PC-S model trial roster."""

from argparse import ArgumentParser
from collections import defaultdict, deque
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.multitool_v1.dataset import load_freeze
from benchmarks.tool_calling_v2.holdout.dataset import load


def stable_order(case_id):
    return sha256(f"IJ071-PC-S-v1:{case_id}".encode()).digest(), case_id


def balanced(pool, count):
    groups = [deque(sorted(ids, key=stable_order)) for _, ids in sorted(pool.items())]
    if sum(map(len, groups)) < count:
        raise ValueError("insufficient cases for the diagnostic stratum")
    result = []
    while len(result) < count:
        for group in groups:
            if group:
                result.append(group.popleft())
            if len(result) == count:
                break
    return result


def create():
    tc, tc_manifest = load("dev")
    tc_groups = {language: defaultdict(list) for language in ("en", "zh")}
    for row in tc:
        tc_groups[row["language"]][row["category"]].append(row["id"])
    tc_selected = {lang: balanced(groups, 50) for lang, groups in tc_groups.items()}

    multi = load_freeze()
    multi_groups = defaultdict(lambda: defaultdict(list))
    for key, case in multi.active.items():
        oracle = case.oracle
        if oracle["language"] in ("en", "zh"):
            multi_groups[oracle["depth_bin"], oracle["language"]][oracle["category"]].append(key)
    multi_selected = {f"{depth}/{lang}": balanced(groups, 12)
                      for (depth, lang), groups in sorted(multi_groups.items())}

    planning = ROOT / "benchmarks/agentic_planning_v1"
    public = planning / "datasets/holdout.jsonl"
    private = planning / "task_graphs/holdout.jsonl"
    graphs = {r["case_id"]: r for r in load_jsonl(private)}
    plan_groups = defaultdict(lambda: defaultdict(list))
    for row in load_jsonl(public):
        case_id = row["case_id"]
        plan_groups[row["level"], row["language"]][graphs[case_id]["variant"]].append(case_id)
    plan_selected = {f"{level}/{lang}": balanced(groups, 10)
                     for (level, lang), groups in sorted(plan_groups.items())}

    def cohort(selections, planned):
        ids = [case_id for selection in selections.values() for case_id in selection]
        if len(ids) != planned or len(set(ids)) != planned:
            raise ValueError("PC-S panel roster has missing or duplicate cases")
        return {"case_count": planned, "selection_by_stratum": selections}

    return {
        "schema_version": 1,
        "scope": "PC-S diagnostic only. Exclude all selected cases from independent Atlas admission.",
        "execution_status": "NOT_RUN",
        "model_pin": "configs/qwen3_8b_reference.json",
        "tc_v2": {**cohort(tc_selected, 100), "split": "dev", "trial_count": 100,
                  "dataset_sha256": tc_manifest["split"]["dev"]["sha256"]},
        "multitool_v1": {**cohort(multi_selected, 120), "trial_count": 120,
                         "freeze_sha256": multi.manifest["freeze_sha256"]},
        "planning_v1": {**cohort(plan_selected, 160), "trial_count": 320, "tracks": ["A", "P"],
                         "dataset_sha256": sha256(public.read_bytes()).hexdigest(),
                         "oracle_sha256": sha256(private.read_bytes()).hexdigest()},
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = ROOT / "atlas/benchmarks/pc_s_roster.json"
    expected = json.dumps(create(), indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if target.read_text(encoding="utf-8") != expected:
            parser.exit(1, "PC-S diagnostic roster differs\n")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expected, encoding="utf-8", newline="\n")
    print("PC-S roster: 380 unique tasks, 540 planned trial instances")


if __name__ == "__main__":
    main()
