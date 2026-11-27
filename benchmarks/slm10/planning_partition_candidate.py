"""Build a Planning candidate with disjoint level fixtures and a proposed matched roster."""

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from evaluation.aeve.archive import digest
from evaluation.aeve.runtime import canonical, fingerprint

from .planning_l5_candidate import OUT as PARENT, repair
from .planning_roster import ATLAS, allocate, historical_tasks, output_files, read_bundle, validate_public
from .planning_source_candidate import json_line
from .planning_source_controls import LEVELS, business_fixture
from .planning_source_release import validate_release_control
from .planning_world_allocation import EVALUATION_CONTRACT, SOURCE, SOURCE_SHA256

OUT = ATLAS / "planning-v2-source-candidate-0.4"
STATUSES = {
    "L1": ("intake receipt filed", "intake receipt awaiting label", "intake receipt acknowledged"),
    "L2": ("handling review scheduled", "handling constraints verified", "handling review pending"),
    "L3": ("indexed record found", "indexed record awaiting update", "indexed record moved to archive"),
    "L4": ("source comparison open", "source comparison completed", "source comparison awaiting reconciliation"),
    "L5": ("original registry available", "standby registry current", "revised registry confirmed"),
}
OLD_PREDICTOR = {
    "primary": "primary", "changed_limit": "primary", "changed_index": "different_status",
    "alternate_source": "different_status",
}


def public_identity(case):
    case = deepcopy(case)
    for field in ("reference", "subject"):
        if field in case["public"]:
            original = case["public"][field]
            domain = original.partition("-")[0]
            reference = f"{domain}-{fingerprint(['PL2 public identity 0.4', case['case_id']])[:14].upper()}"
            case["public"][field] = reference
            case["task"] = case["task"].replace(original, reference)
    return case


def substitute(value, old, new):
    if isinstance(value, dict):
        return {key: substitute(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [substitute(item, old, new) for item in value]
    return new if value == old else value


def control(case):
    level, public = case["level"], case["public"]
    fixture = business_fixture(case)
    if level in STATUSES:
        statuses = STATUSES[level]
        for index, key in enumerate(("current", "alternate", "revision")):
            serial = fingerprint(["PL2 private observation 0.4", case["case_id"], key])[:10]
            fixture[key] = f"{statuses[index]} ({serial})"
        if level == "L2":
            fixture["limit"] = "handling limit " + fixture["limit"]
            fixture["other_limit"] = "handling limit " + fixture["other_limit"]
    if level in ("L6", "L7"):
        label = "Checklist" if level == "L6" else "Release audit"
        fixture["review"] = f"{label} assessment {fingerprint(['PL2 audit 0.4', case['case_id']])[:14]}"
    variant, actions, stops, worlds = LEVELS[level](case, fixture)
    if level == "L7":
        old = f"synthetic-grant-{public['subject']}"
        new = f"synthetic-event-{fingerprint(['PL2 external grant 0.4', case['case_id']])[:24]}"
        worlds = substitute(worlds, old, new)
    return {
        "case_id": case["case_id"], "variant": variant,
        "witness": {"version": 2, "goal": case["contract"]["goal"], "actions": actions, "stops": stops},
        "worlds": worlds,
    }


def candidate():
    _, old_cases, old_proofs = read_bundle(SOURCE, SOURCE_SHA256)
    old_by_id = {proof["case_id"]: proof for proof in old_proofs}
    old_by_reference = {
        (case["public"]["reference"], world["world_id"]): world["facts"]["value"]
        for case in old_cases if case["level"] == "L1" for world in old_by_id[case["case_id"]]["worlds"]
    }
    public, controls, prediction = [], [], Counter()
    references, task_families = set(), Counter()
    historical = historical_tasks()
    for old in old_cases:
        case = public_identity(old)
        proof = control(case)
        if case["level"] == "L5":
            case, proof, _ = repair(case, proof)
        validate_public(case, historical)
        validate_release_control(case, proof)
        public.append(case)
        controls.append(proof)
        new_ref = case["public"].get("reference", case["public"].get("subject"))
        if new_ref:
            if new_ref in references:
                raise ValueError("reference crossed a Planning task or level")
            references.add(new_ref)
        task_families[case["level"], proof["variant"]] += 1
        if case["level"] not in ("L2", "L3", "L4", "L5"):
            continue
        for world in proof["worlds"]:
            alias = OLD_PREDICTOR.get(world["world_id"])
            if alias is None:
                continue
            prediction["opportunities"] += 1
            exact = (new_ref, alias)
            prediction["exact_reference_hits"] += exact in old_by_reference
            # Give the old predictor the historical reference even though the new task never exposes it.
            prior = old_by_reference[old["public"]["reference"], alias]
            prediction["historical_crosswalk_hits"] += prior == world["facts"]["value"]
    if len(public) != 800 or len(references) != 750 or prediction != {
        "opportunities": 800, "exact_reference_hits": 0, "historical_crosswalk_hits": 0,
    }:
        raise ValueError("partition control coverage or leakage changed")
    assessment = {
        "prior_reference_predictor": dict(prediction), "public_unique_references": len(references),
        "model_leakage_experiment": "NOT_RUN",
        "semantic_review": "NOT_RUN",
        "template_families": [{"level": level, "workflow": variant, "cases": count}
                              for (level, variant), count in sorted(task_families.items())],
        "inference_scope": "These families instantiate a small set of shared workflows. "
                           "Treat instances as clustered and require independent semantic duplicate review.",
    }
    return public, controls, assessment


def make_roster(public, controls, source_digest):
    by_case = {proof["case_id"]: proof for proof in controls}
    strata = defaultdict(list)
    for case in public:
        key = case["case_id"]
        world_ids = tuple(sorted(world["world_id"] for world in by_case[key]["worlds"]))
        strata[case["level"], world_ids].append(key)
    selected = {}
    for (_, names), keys in sorted(strata.items()):
        order = sorted(keys, key=lambda key: fingerprint(["PL2 world allocation 0.4", source_digest, key]))
        for index, key in enumerate(order):
            name = names[index % len(names)]
            world = next(world for world in by_case[key]["worlds"] if world["world_id"] == name)
            selected[key] = {"world_id": name, "world_sha256": fingerprint(world)}
    rows = allocate(public, {key: proof["variant"] for key, proof in by_case.items()}, source_digest)
    contract = digest(EVALUATION_CONTRACT)
    return [{**row, **selected[row["case_id"]], "evaluation_contract_sha256": contract} for row in rows]


def bundle():
    public, controls, assessment = candidate()
    sources = {"holdout-public.jsonl": b"".join(map(json_line, public)),
               "holdout-controls.jsonl": b"".join(map(json_line, controls))}
    source_pins = {name: sha256(data).hexdigest() for name, data in sources.items()}
    source_digest = fingerprint(source_pins)
    trials = make_roster(public, controls, source_digest)
    roster_bytes = b"".join(map(json_line, trials))
    files = sources | {"candidate-roster.jsonl": roster_bytes,
                       "partition-controls.json": json_line(assessment)}
    manifest = {
        "version": "IJ-SLM-AGENTIC-PLAN-V2-SOURCE-CANDIDATE/0.4",
        "parent_manifest_sha256": digest(PARENT / "manifest.json"),
        "source_identity_sha256": source_digest,
        "authorship": "Public identity isolation and synthetic observation reauthoring are automated project work.",
        "source_module_sha256": digest(Path(__file__)),
        "artifacts": {name: sha256(data).hexdigest() for name, data in files.items()},
        "cases": len(public), "software_worlds": sum(len(p["worlds"]) for p in controls),
        "worlds_selected": len(public), "proposed_trial_slots": len(trials),
        "roster_uncompressed_sha256": sha256(roster_bytes).hexdigest(),
        "physical_execution": "NOT_RUN", "formal_freeze": "NOT_RUN", "formal_dispatch": "BLOCKED",
        "independent_human_review": "NOT_RUN",
    }
    return files | {"manifest.json": json_line(manifest)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    output_files(OUT, bundle(), not args.write)
    print("Verified 800 Planning cases, 2,500 software worlds and 20,800 proposed slots. Formal dispatch remains BLOCKED.")


if __name__ == "__main__":
    main()
