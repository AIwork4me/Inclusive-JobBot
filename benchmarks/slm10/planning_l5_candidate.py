"""Build the versioned Planning V2 alternate-denial software candidate."""

import argparse
from copy import deepcopy
from hashlib import sha256

from evaluation.aeve.archive import digest
from evaluation.aeve.runtime import ROOT

from .planning_controls import validate_control
from .planning_roster import ATLAS, output_files, read_bundle
from .planning_source_candidate import json_line
from .planning_world_allocation import SOURCE, SOURCE_SHA256

OUT = ATLAS / "planning-v2-source-candidate-0.3"
ALTERNATE_WORLDS = {"alternate_source", "revised_primary_unavailable"}


def repair(case, proof):
    case, proof = deepcopy(case), deepcopy(proof)
    alternate = case["contract"]["tools"]["alternate"]
    alternate["outputs"].append("code")
    alternate["description"] += " If access is denied, its code is permission_denied."
    for node in proof["witness"]["actions"]:
        if node["tool"] == "alternate":
            code = {"from": node["id"], "field": "code"}
            proof["witness"]["stops"].append({
                "when": {"op": "eq", "left": code, "right": "permission_denied"},
                "disposition": "escalate", "facts": {"reason": code},
            })
    denial_worlds = []
    for world in proof["worlds"]:
        if world["world_id"] in ALTERNATE_WORLDS:
            denied = deepcopy(world)
            if denied["steps"][-1]["tool"] != "alternate":
                raise ValueError("statutory denial requires a terminal alternate service call")
            denied["steps"][-1]["result"] = {"code": "permission_denied"}
            denied.update(world_id=world["world_id"] + "_denied", disposition="escalate",
                          facts={"reason": "permission_denied"})
            denial_worlds.append(denied)
    if len(denial_worlds) != len(ALTERNATE_WORLDS):
        raise ValueError("L5 case lacks both required alternate denial controls")
    proof["worlds"].extend(denial_worlds)
    return case, proof, validate_control(case, proof)


def candidate():
    _, cases, proofs = read_bundle(SOURCE, SOURCE_SHA256)
    by_id = {proof["case_id"]: proof for proof in proofs}
    public, controls = [], []
    original_l5 = new_l5 = 0
    for case in cases:
        proof = by_id[case["case_id"]]
        if case["level"] == "L5":
            original_l5 += len(proof["worlds"])
            case, proof, result = repair(case, proof)
            new_l5 += result["worlds"] - len(by_id[case["case_id"]]["worlds"])
        public.append(case)
        controls.append(proof)
    if (len(public), original_l5, new_l5) != (800, 500, 200):
        raise ValueError("unexpected Planning L5 repair coverage")
    return public, controls


def bundle():
    public, controls = candidate()
    artifacts = {
        "holdout-public.jsonl": b"".join(map(json_line, public)),
        "holdout-controls.jsonl": b"".join(map(json_line, controls)),
    }
    manifest = {
        "version": "IJ-SLM-AGENTIC-PLAN-V2-SOURCE-CANDIDATE/0.3",
        "parent_manifest_sha256": SOURCE_SHA256,
        "repair_source": {"path": "benchmarks/slm10/planning_l5_candidate.py",
                          "sha256": digest(ROOT / "benchmarks/slm10/planning_l5_candidate.py")},
        "artifacts": {name: sha256(body).hexdigest() for name, body in artifacts.items()},
        "cases": len(public), "software_worlds": sum(len(p["worlds"]) for p in controls),
        "original_l5_worlds_replayed": 500, "new_l5_denial_worlds_replayed": 200,
        "independent_review": "NOT_RUN", "formal_freeze": "NOT_RUN", "formal_dispatch": "BLOCKED",
        "attributed_physical_trials": 0,
    }
    return artifacts | {"manifest.json": json_line(manifest)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    output_files(OUT, bundle(), not args.write)
    print("Replayed 500 original L5 worlds and 200 alternate denial worlds. Formal release remains BLOCKED.")


if __name__ == "__main__":
    main()
