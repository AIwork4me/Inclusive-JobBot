"""Pin one Planning world per case across the matched roster."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re

from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT, canonical, fingerprint

from . import planning_roster as roster


VERSION = "IJ-SLM-PLANNING-WORLD-ALLOCATION/1.0"
SOURCE = roster.ATLAS / "planning-v2-source-candidate-0.2"
SOURCE_SHA256 = "72eb98bdf99268dcc53da8c2753f4b76308f4b23c33cd08d65ab0ab7c0ec6f45"
OUTPUT = roster.ATLAS / "planning-v2-world-allocation"
EVALUATION_CONTRACT = roster.ATLAS / "evaluation_contract.json"
CREDENTIALS = ("release_review", "matched_runner", "runtime_admission", "hardware_handoff", "evaluation")
DIMENSIONS = ("D12", "D23", "D24_affirmative", "D25")
STRICT = "STRICT"
READ_ONLY_MECHANICAL = "READ_ONLY_MECHANICAL"
READ_ONLY_LEVELS = ("L0", "L1", "L2", "L3", "L4", "L5")
READ_ONLY_MECHANICS = ("public_contract", "provider_tool_linkage", "actual_call_path", "business_facts", "read_only_scope")
READ_ONLY_DIMENSIONS = {"D12": "BLOCKED", "D23": "NOT_RUN", "D24_affirmative": "NOT_RUN", "D25": "BLOCKED"}


def jsonl(rows):
    return b"".join(canonical(row) + b"\n" for row in rows)


def build_allocation():
    _, public, controls = roster.read_bundle(SOURCE, SOURCE_SHA256)
    by_id = {row["case_id"]: row for row in public}
    variants = {row["case_id"]: row["variant"] for row in controls}
    trials = roster.allocate(public, variants, SOURCE_SHA256)
    repeats = {trial["case_id"] for trial in trials if trial["panel"] == "repeat"}
    groups = defaultdict(list)
    for proof in controls:
        case = by_id[proof["case_id"]]
        world_ids = tuple(sorted(world["world_id"] for world in proof["worlds"]))
        groups[case["level"], world_ids].append(proof)
    cases, coverage = {}, defaultdict(Counter)
    for (level, world_ids), members in sorted(groups.items()):
        # Fill each authored world type evenly without depending on corpus row order.
        order = sorted(members, key=lambda row: (fingerprint([VERSION, SOURCE_SHA256, row["case_id"]]), row["case_id"]))
        for index, proof in enumerate(order):
            case_id = proof["case_id"]
            selected = world_ids[index % len(world_ids)]
            worlds = {world["world_id"]: fingerprint(world) for world in proof["worlds"]}
            cases[case_id] = {
                "level": level, "language": by_id[case_id]["language"],
                "public_sha256": fingerprint(by_id[case_id]), "repeat_panel": case_id in repeats,
                "selected_world_id": selected, "selected_world_sha256": worlds[selected],
                "unselected_worlds": [{"world_id": name, "world_sha256": worlds[name], "physical_execution": "NOT_RUN"}
                                      for name in world_ids if name != selected],
            }
            coverage[level][selected] += 1
    world_count = sum(len(row["worlds"]) for row in controls)
    unselected_count = sum(len(row["unselected_worlds"]) for row in cases.values())
    if len(cases) != 800 or world_count != 2300 or unselected_count != 1500:
        raise ValueError("supplemental allocation must preserve the pinned Planning corpus")
    return {
        "version": VERSION, "source_manifest_sha256": SOURCE_SHA256,
        "source_roster_sha256": sha256(jsonl(trials)).hexdigest(),
        "allocator_sha256": digest(Path(__file__)), "evaluation_contract_sha256": digest(EVALUATION_CONTRACT),
        "planned_trials": len(trials), "source_world_count": world_count, "unselected_world_count": unselected_count,
        "selection_rule": "rank cases by digest within level and world vocabulary, cycle sorted world IDs",
        "selected_by_level": dict(coverage), "cases": cases, "evidence_class": "software allocation",
        "dispatch_scope_contract": {
            STRICT: {"levels": list(roster.LEVELS), "dimensions": dict.fromkeys(DIMENSIONS, "PASS")},
            READ_ONLY_MECHANICAL: {"levels": list(READ_ONLY_LEVELS), "dimensions": READ_ONLY_DIMENSIONS,
                                   "mechanics": dict.fromkeys(READ_ONLY_MECHANICS, "PASS")},
        },
        "formal_release": "NOT_RUN", "formal_dispatch": "BLOCKED", "physical_execution": "NOT_RUN",
    }


def bind_trial(allocation, trial):
    case = allocation["cases"].get(trial.get("case_id"))
    candidate, track, panel, seed = (trial.get(field) for field in ("candidate", "track", "panel", "seed"))
    if (case is None or trial.get("level") != case["level"] or trial.get("language") != case["language"]
            or candidate not in roster.MODELS or track not in roster.TRACKS or type(seed) is not int):
        raise ValueError("Planning trial identity is outside the paired roster")
    if panel == "first":
        valid_seed = seed == roster.FIRST_SEED
    else:
        valid_seed = panel == "repeat" and case["repeat_panel"] and track in roster.SDK_TRACKS and seed in roster.REPEAT_SEEDS
    expected = fingerprint([roster.VERSION, SOURCE_SHA256, candidate, trial["case_id"], track, panel, seed])
    if not valid_seed or trial.get("trial_id") != expected:
        raise ValueError("Planning trial identity differs from the pinned roster")
    selected = {"source_manifest_sha256": SOURCE_SHA256, "public_sha256": case["public_sha256"],
                "world_id": case["selected_world_id"], "world_sha256": case["selected_world_sha256"],
                "evaluation_contract_sha256": allocation["evaluation_contract_sha256"]}
    if any(field in trial and trial[field] != expected for field, expected in selected.items()):
        raise ValueError("Planning trial identity attempts to override its selected world or contract")
    return trial | selected


def require_dispatch_binding(allocation, trial, runtime, credential_pins, credential_folder, *, release_scope=STRICT):
    """Check identity and all externally registered credentials before a future launch."""
    if credential_pins.keys() != set(CREDENTIALS):
        raise ValueError("Planning dispatch requires independent credential pins")
    if allocation != build_allocation():
        raise ValueError("Planning dispatch allocation differs from the pinned candidate")
    binding = bind_trial(allocation, trial)
    scopes = allocation["dispatch_scope_contract"]
    if release_scope not in scopes:
        raise ValueError("Planning dispatch requires a recognized evidence-bound release scope")
    scope = scopes[release_scope]
    if binding["level"] not in scope["levels"]:
        raise ValueError("Planning read-only scope cannot authorize stateful levels")
    digests = ("engine_binary_sha256", "model_sha256", "sdk_binary_sha256", "host_sha256", "gpu_physical_sha256",
               "runner_sha256")
    identifiers = ("engine_build", "model_revision", "sdk_version", "runtime_session_id", "run_id")
    profile = "SDK_NATIVE" if binding["track"].startswith("sdk_") else "DIRECT_NATIVE"
    if (not re.fullmatch(r"[0-9a-f]{40}", str(runtime.get("git_sha")))
            or any(not roster.is_sha256(runtime.get(name)) for name in digests)
            or any(not isinstance(runtime.get(name), str) or not runtime[name] for name in identifiers)
            or runtime.get("backend") != "vulkan" or runtime.get("profile") != profile):
        raise ValueError("Planning dispatch requires exact runtime, SDK and hardware identities")
    source = {"source_manifest_sha256": SOURCE_SHA256, "release_scope": release_scope,
              "world_allocation_sha256": sha256(canonical(allocation) + b"\n").hexdigest()}
    runtime_fields = ("candidate", *digests, *identifiers, "backend", "profile", "git_sha")
    identity = {name: (binding[name] if name == "candidate" else runtime[name]) for name in runtime_fields}
    hardware = {name: runtime[name] for name in ("host_sha256", "gpu_physical_sha256")}
    evaluation = {"evaluation_contract_sha256": binding["evaluation_contract_sha256"], "dimensions": scope["dimensions"]}
    if release_scope == READ_ONLY_MECHANICAL:
        evaluation["mechanics"] = scope["mechanics"]
    requirements = {
        "release_review": source,
        "matched_runner": source | {"runner_sha256": runtime["runner_sha256"], "profile": profile},
        "runtime_admission": source | identity,
        "hardware_handoff": hardware | {"handoff_sha256": digest(ROOT / HANDOFF)},
        "evaluation": source | evaluation,
    }
    for name, expected in requirements.items():
        record = roster.object_json(roster.pinned_content(Path(credential_folder), f"{name}.json", credential_pins[name]))
        if (record.get("credential") != name or record.get("status") != "PASS"
                or record.get("bindings") != expected or not roster.is_sha256(record.get("evidence_sha256"))):
            raise ValueError(f"Planning dispatch credential does not establish {name}")
    handoff = require_handoff(ROOT)
    if any(handoff["lease"][key] != value for key, value in hardware.items()):
        raise ValueError("Planning dispatch hardware differs from the verified live handoff")
    return binding | source | identity | {"credential_sha256": dict(credential_pins),
                                           "strict_e2e": "NOT_RUN" if release_scope == STRICT else "BLOCKED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    allocation = build_allocation()
    raw = canonical(allocation) + b"\n"
    roster.output_files(args.output, {"manifest.json": raw}, not args.write)
    print(json.dumps({key: allocation[key] for key in ("planned_trials", "source_world_count",
                     "unselected_world_count", "formal_dispatch")} | {"world_allocation_sha256": sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
