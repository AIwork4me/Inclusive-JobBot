"""Freeze the Q3 sample roster and configuration while checking cohort leakage."""
import argparse
from collections import Counter
import json
from pathlib import Path

from .archive import digest
from .contracts import DIMENSIONS
from .history import OUT, lines
from .history_routing import HEX256, RISKS
from .runtime import ROOT, write_json

PARTITIONS = ("development", "calibration", "sealed_qualification")
CONFIGURATION = {"judge_profiles", "prompt_bundle", "proof_adapters", "router", "skill_compiler",
                 "request_schema", "judgment_schema", "physical_runner", "dispute_policy"}


def bind(groups, key, partition, label):
    if groups.setdefault(key, partition) != partition:
        raise ValueError(f"{label} crosses Q3 partitions")


def is_sha(value):
    return isinstance(value, str) and HEX256.fullmatch(value) is not None


def validate(rows, historical):
    counts, seen, episodes, templates, packets = Counter(), set(), {}, {}, {}
    new, physical = set(), set()
    for row in rows:
        partition = row["partition"]
        family, episode = row["template_family"], row["episode"]
        key = (row["case_id"], row["dimension"], row["risk"])
        if (partition not in PARTITIONS or not family or not episode or not key[0]
                or key[1] not in DIMENSIONS or key[2] not in RISKS or key in seen):
            raise ValueError("invalid or repeated Q3 evaluation unit")
        seen.add(key)
        if not is_sha(row.get("business_proof_sha256")):
            raise ValueError("independent business proof is missing")
        if not all(is_sha(row.get(field)) for field in ("source_sha256", "packet_sha256")):
            raise ValueError("Q3 source or packet is not pinned")
        counts[partition] += 1
        bind(templates, family, partition, "template family")
        bind(packets, row["packet_sha256"], partition, "packet")
        trial_id = row.get("source_trial_id")
        if trial_id:
            trace = historical.get(trial_id, {})
            if (trace.get("class") != "physical_trial"
                    or row["source_sha256"] not in {source[2] for source in trace["sources"]}):
                raise ValueError("Q3 physical episode is not bound to its archived trial")
            # Use the archive's case identity to keep repetitions and candidate arms together.
            group = ("archived", trace["case_id"])
            if partition == "sealed_qualification":
                physical.add(group)
        else:
            group = ("new", family, episode)
            if partition == "sealed_qualification":
                new.add(family)
        bind(episodes, group, partition, "episode")
    if not new or not physical:
        raise ValueError("Q3 requires new template families and archived physical episodes")
    # Calibration can tune the operating point. Qualification stays sealed.
    return {**{p: counts[p] for p in PARTITIONS}, "qualification_physical_episodes": len(physical),
            "qualification_new_template_families": len(new)}


def checked_file(root, item):
    file = (root / item["path"]).resolve()
    if not file.is_relative_to(root.resolve()) or digest(file) != item["sha256"]:
        raise ValueError("Q3 input differs from its pinned bytes")
    return file


def freeze(bundle, registry):
    rows_path = bundle / "roster.jsonl"
    configurations = json.loads((bundle / "configuration.json").read_bytes())
    if set(configurations) != CONFIGURATION:
        raise ValueError("incomplete Q3 evaluation configuration")
    for item in configurations.values():
        checked_file(bundle, item)
    cases = list(lines(rows_path))
    history = {row["trial_id"]: row for row in lines(registry)}
    totals = validate(cases, history)
    for case in cases:
        for field in ("source_sha256", "packet_sha256", "business_proof_sha256"):
            sha = case[field]
            checked_file(bundle, {"path": f"objects/{sha}", "sha256": sha})
    metrics = ROOT / "evaluation/aeve/q3_metric_preregistration.json"
    legacy = ROOT / "evaluation/aeve/qualification_freeze.json"
    return {"version": "IJ073-Q3-COHORT-1", "physical_status": "NOT_RUN",
            "roster_sha256": digest(rows_path), "historical_registry_sha256": digest(registry),
            "metrics_sha256": digest(metrics), "legacy_thresholds_sha256": digest(legacy),
            "validator_sha256": digest(Path(__file__)), "configuration": configurations, "totals": totals}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--registry", type=Path, default=ROOT / OUT / "registry.jsonl.gz")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    data = freeze(args.bundle, args.registry)
    if args.replay and data != json.loads(args.replay.read_bytes()):
        raise ValueError("Q3 freeze differs from the archived manifest")
    write_json(args.output, data)
    print(data["totals"])


if __name__ == "__main__":
    main()
