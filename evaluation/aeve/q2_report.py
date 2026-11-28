"""Verify and summarize the matched Q2 development arms from original model captures."""
import argparse
from collections import Counter
import json
from pathlib import Path

from .meta_evaluation import snapshot
from .q2_development import COLLECTION, ARMS, config, grade, roster, summarize
from .history import lines
from .runtime import ROOT, write_json


def build(archive, manifests=None):
    with snapshot(archive,manifests) as (view, hashes):
        report = summarize(view)
        for volume in sorted((view/"sessions").glob("*/captures.jsonl.gz")):
            outcomes = json.loads(volume.with_name("outcomes.json").read_bytes())
            if not any(r["collection"] == COLLECTION for r in outcomes):
                continue
            for row in lines(volume):
                if row["collection"] != COLLECTION or row["transport"] != "PASS":
                    continue
                content = json.loads(row["capture"]["raw_response"])["choices"][0]["message"]["content"]
                try:
                    replay = grade(row["spec"],content)
                except (ValueError,TypeError,KeyError):
                    replay = None
                if replay != row["evaluation"] and (replay is not None or "verdict" in row["evaluation"]):
                    raise ValueError("development judgment differs from the raw GPU response")
    observed = {(r["candidate"],r["case_id"],r["arm"]):r for r in report["cases"]}
    gold = {case["case_id"]:case for case in roster()}
    pairs = {}
    for candidate in config()["order"]:
        for arm in ARMS[1:]:
            matched = Counter()
            for case_id, case in gold.items():
                base = observed.get((candidate,case_id,"baseline"))
                repair = observed.get((candidate,case_id,arm))
                if not base or not repair:
                    continue
                matched["pairs"] += 1
                for metric, evaluator in (
                    ("decision",lambda r:r["verdict"] == case["expected"]),
                    ("citation",lambda r:r["correct_citations"]),
                ):
                    old,new = evaluator(base),evaluator(repair)
                    if old != new:
                        matched[f"{metric}_{'improved' if new else 'degraded'}"] += 1
            pairs[f"{candidate}/{arm}"] = dict(matched)
    return {**report,"session_manifests":hashes,"paired_changes":pairs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive",type=Path,default=ROOT/"evaluation/aeve/results")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--replay",type=Path)
    args = parser.parse_args()
    frozen = json.loads(args.replay.read_bytes()) if args.replay else None
    report = build(args.archive,frozen["session_manifests"] if frozen else None)
    if frozen is not None and report != frozen:
        raise ValueError("development replay differs from its pinned result")
    write_json(args.output,report)
    print(f"{len(report['cases'])}/360 assessments")
    for group, stats in sorted(report["groups"].items()):
        print(group,stats.get("recorded",0),stats.get("correct",0),stats.get("citations",0))


if __name__ == "__main__":
    main()
