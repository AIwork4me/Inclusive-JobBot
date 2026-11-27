"""Rebuild the historical registry in scratch space and rebind its stage rosters."""
import argparse
from collections import Counter
from filecmp import cmp
import json
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

from . import history
from .archive import digest
from .history_dimensions import apply_facts, read_addendum
from .history_supplement_report import bind, inventory
from .runtime import write_json


def build():
    original = history.OUT
    with TemporaryDirectory(prefix="aeve-history-identity-") as directory:
        scratch = Path(directory)
        for name in ("sealed_projections.jsonl.gz", "judge_inputs.jsonl.gz"):
            copyfile(original / name, scratch / name)
        history.main([], output=scratch)
        for name in ("assets.json", "coverage.json", "registry.jsonl.gz", "judge_inputs_v2.jsonl.gz",
                     "sealed_projections.jsonl.gz"):
            if not cmp(original / name, scratch / name, shallow=False):
                raise ValueError(f"rebuilt history differs from archive: {name}")
    supplemental, report = inventory(original)
    addendum, facts = read_addendum(original)
    if report["status"] != "PASS" or addendum is None:
        raise ValueError("history supplements are incomplete")
    registry = {}
    for trial in history.lines(original / "registry.jsonl.gz"):
        tid = trial["trial_id"]
        if tid in registry or tid != history.sid(trial["run_id"], trial["case_id"], trial["attempt_id"]):
            raise ValueError("duplicate or inconsistent historical trial identity")
        bind(trial, supplemental, True)
        apply_facts(trial, facts)
        registry[tid] = trial
    physical = {tid for tid, row in registry.items() if row["class"] == "physical_trial"}
    packets = {"physical": set(), "nonphysical": set()}
    for source, group in ((original / "judge_inputs_v2.jsonl.gz", "physical"), (addendum, "physical"),
                          (original / "judge_inputs_nonphysical_v2.jsonl.gz", "nonphysical")):
        for row in history.lines(source):
            tid = row["trial_id"]
            trial = registry[tid]
            if ((tid in physical) != (group == "physical") or row["source_family"] != trial["source_family"]
                    or row["source_sha256"] not in {item[2] for item in trial["sources"]}):
                raise ValueError("historical packet is not bound to its trial")
            exhibits = {event["id"] for event in row["events"]}
            if len(exhibits) != len(row["events"]):
                raise ValueError("historical packet has duplicate evidence IDs")
            for dim in row["dimensions"]:
                key = tid, dim
                scoped = row["dimension_event_ids"][dim]
                if key in packets[group] or not scoped or len(scoped) != len(set(scoped)) or set(scoped) - exhibits:
                    raise ValueError("repeated dimension or invalid stage evidence")
                packets[group].add(key)
    evaluable = {tid for tid, _ in packets["physical"]}
    missing = physical - evaluable
    if any(registry[tid]["semantic_eligibility"] != "insufficient_citable_decision_evidence" for tid in missing):
        raise ValueError("missing physical projection lacks a recorded evidence disposition")
    return {"status": "PASS", "scope": "historical registry and stage identity replay",
            "source_baseline_git_sha": history.BASE, "registered_trials": len(registry),
            "physical_trials": len(physical), "evaluable_physical_trials": len(evaluable),
            "unassessable_physical_trials": len(missing), "physical_dimensions": len(packets["physical"]),
            "nonphysical_packets": report["independent_inputs"], "nonphysical_dimensions": len(packets["nonphysical"]),
            "double_primary_reviews": 2 * sum(map(len, packets.values())),
            "physical_source_families": dict(Counter(registry[tid]["source_family"] for tid in physical)),
            "missing_physical_trial_ids": sorted(missing),
            "assets": {name: digest(original / name) for name in ("coverage.json", "physical_addendum.json",
                                                                   "nonphysical_coverage.json", "registry.jsonl.gz")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay", type=Path)
    options = parser.parse_args()
    result = build()
    if options.replay is not None and json.loads(options.replay.read_bytes()) != result:
        raise ValueError("historical identity evidence differs from its replay")
    write_json(options.output, result)
    print(result["registered_trials"], "registered trial identities verified")


if __name__ == "__main__":
    main()
