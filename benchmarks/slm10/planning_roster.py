"""Freeze and verify independent IJ-SLM AGENTIC-PLAN-V2 software evidence."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
from uuid import uuid4

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT, canonical, fingerprint

from .planning_controls import LEVELS, normalized_task, validate_control, validate_public

VERSION = "IJ-SLM-AGENTIC-PLAN-V2-FREEZE/1.0"
SOURCE_VERSION = "IJ-SLM-AGENTIC-PLAN-V2-INDEPENDENT-SOURCE/1.0"
SUITE = "AGENTIC-PLAN-V2"
ATLAS = ROOT / "atlas/slm/v1.0"
CORE = ATLAS / "execution_plan.json"
HISTORICAL = ROOT / "benchmarks/agentic_planning_v1/datasets/holdout.jsonl"
MODELS = ("A", "B", "D", "F", "G")
TRACKS = ("direct_plan_first", "direct_acting_first", "sdk_plan_first", "sdk_acting_first")
SDK_TRACKS = ("sdk_plan_first", "sdk_acting_first")
FIRST_SEED = 7107
REPEAT_SEEDS = (101, 211, 307)
CASE_COUNT_PER_LEVEL = 100
REPEAT_CASES_PER_LEVEL = 20
FLOORS = (.95, .95, .95, .85, .85, .80, .75, .90)
SOURCE_FILES = {"holdout-public.jsonl", "holdout-controls.jsonl"}
SOURCE_ROLES = {"public_authoring", "world_and_witness_authoring"}


def allocation():
    plan = json.loads(CORE.read_bytes())
    cases = len(LEVELS) * CASE_COUNT_PER_LEVEL
    planning = dict.fromkeys(TRACKS, cases) | {
        "sdk_repeat": len(LEVELS) * REPEAT_CASES_PER_LEVEL * len(REPEAT_SEEDS) * len(SDK_TRACKS),
    }
    suite_totals = {name: len(MODELS) * sum(tracks.values()) for name, tracks in plan["suites"].items()}
    direct = len(MODELS) * sum(n for tracks in plan["suites"].values()
                               for track, n in tracks.items() if track.startswith("direct_"))
    sdk = sum(suite_totals.values()) - direct
    if (plan["panel"] != list(MODELS) or plan["suites"][SUITE] != planning
            or suite_totals != {SUITE: 20800, "MULTITOOL-V2": 7500, "TC-V3": 8250}
            or plan["core_total"] != sum(suite_totals.values()) or tuple(plan["planning_l0_l7_floors"]) != FLOORS
            or (plan["direct_total"], plan["sdk_total"]) != (direct, sdk) or (direct, sdk) != (13500, 23050)):
        raise ValueError("independent planning allocation differs from the frozen core")
    return {"core_total": plan["core_total"], "core_direct": direct, "core_sdk": sdk, "suite_totals": suite_totals,
            "models": list(MODELS), "per_model": planning, "planning_floors": plan["planning_l0_l7_floors"]}


def repeat_panel(cases, variants):
    strata = defaultdict(lambda: defaultdict(list))
    for case in cases:
        key = case["case_id"]
        strata[case["level"]][(case["language"], variants[key])].append(key)
    chosen = set()
    for level in LEVELS:
        buckets = strata[level]
        for group in buckets.values():
            group.sort(key=lambda key: (fingerprint([VERSION, "repeat_panel", key]), key))
        ordered = [key for index in range(max(map(len, buckets.values()))) for stratum in sorted(buckets)
                   for key in buckets[stratum][index:index + 1]]
        chosen.update(ordered[:REPEAT_CASES_PER_LEVEL])
    return chosen


def allocate(cases, variants, source_manifest_sha256):
    by_level = Counter(case["level"] for case in cases)
    keys = {case["case_id"] for case in cases}
    if (by_level != dict.fromkeys(LEVELS, CASE_COUNT_PER_LEVEL) or len(keys) != len(cases)
            or keys != variants.keys() or not is_sha256(source_manifest_sha256)
            or any(not isinstance(variant, str) or not variant for variant in variants.values())):
        raise ValueError("planning allocation requires exactly 100 independent cases per level")
    repeat_ids = repeat_panel(cases, variants)
    rows = []
    for model in MODELS:
        for case in sorted(cases, key=lambda item: item["case_id"]):
            key = case["case_id"]
            planned = [(track, "first", FIRST_SEED) for track in TRACKS]
            if key in repeat_ids:
                planned += [(track, "repeat", seed) for track in SDK_TRACKS for seed in REPEAT_SEEDS]
            for track, panel, seed in planned:
                trial_id = fingerprint([VERSION, source_manifest_sha256, model, key, track, panel, seed])
                rows.append({"candidate": model, "case_id": key, "level": case["level"], "language": case["language"],
                             "track": track, "panel": panel, "seed": seed, "trial_id": trial_id})
    if len(rows) != len({row["trial_id"] for row in rows}) or len(rows) != allocation()["suite_totals"][SUITE]:
        raise ValueError("planning roster is duplicated or changes the core allocation")
    return rows


def is_sha256(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def object_json(content):
    def unique(pairs):
        obj = dict(pairs)
        if len(obj) != len(pairs):
            raise ValueError("duplicate JSON object key in Planning input")
        return obj

    def invalid_constant(value):
        raise ValueError(f"invalid JSON constant in Planning input: {value}")

    obj = json.loads(content, object_pairs_hook=unique, parse_constant=invalid_constant)
    if not isinstance(obj, dict):
        raise ValueError("Planning source rows require JSON objects")
    return obj


def historical_tasks():
    return {normalized_task(object_json(line)["prompt"]) for line in HISTORICAL.read_bytes().splitlines()}


def pinned_content(folder, name, expected):
    if not isinstance(name, str) or not is_sha256(expected):
        raise ValueError("Planning source requires a pinned relative file")
    relative = Path(name)
    path = (folder / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(folder.resolve()) or not path.is_file():
        raise ValueError("Planning source file escapes the independent bundle or is missing")
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError("Planning source file differs from its pinned SHA256")
    check_text(raw)
    return raw


def read_bundle(folder, source_manifest_sha256):
    manifest = object_json(pinned_content(folder, "manifest.json", source_manifest_sha256))
    if (set(manifest) != {"version", "mission", "suite", "partition", "origin", "artifacts", "authoring_sources"}
            or manifest["version"] != SOURCE_VERSION or manifest["mission"] != "IJ-SLM-1.0"
            or manifest["suite"] != SUITE or manifest["partition"] != "sealed_holdout"
            or manifest["origin"] != "independent_synthetic_authoring"
            or not isinstance(manifest["artifacts"], dict) or set(manifest["artifacts"]) != SOURCE_FILES
            or not isinstance(manifest["authoring_sources"], dict)
            or set(manifest["authoring_sources"]) != SOURCE_ROLES):
        raise ValueError("Planning bundle is outside the independent source contract")
    sources = []
    for value in manifest["authoring_sources"].values():
        if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
            raise ValueError("missing separate Planning authoring provenance")
        raw = pinned_content(folder, value["path"], value["sha256"])
        if not raw.strip() or Path(value["path"]).name in SOURCE_FILES | {"manifest.json"}:
            raise ValueError("Planning authoring provenance requires a separate source artifact")
        sources.append(raw)
    if sources[0] == sources[1]:
        raise ValueError("public and oracle authoring sources must be distinct")
    public, controls = [
        [object_json(line) for line in pinned_content(folder, name, manifest["artifacts"][name]).splitlines()]
        for name in ("holdout-public.jsonl", "holdout-controls.jsonl")
    ]
    return manifest, public, controls


def readiness(*, validated=False, host_checked=False):
    planned = allocation()["suite_totals"][SUITE]
    return {"planned": planned, "historical_trials_imported": 0, "formal_trials_recorded": 0,
            "independent_roster": "PASS" if validated else "BLOCKED",
            "mechanical_world_replay": "PASS" if validated else "NOT_RUN",
            "live_host_handoff_recheck": "PASS" if host_checked else "NOT_RUN",
            "formal_runtime_admission": dict.fromkeys(MODELS, "NOT_RUN"),
            "formal_matched_runner": "NOT_RUN",
            "remaining_evaluation_credentials": dict.fromkeys(("D12", "D23", "D24_affirmative", "D25"), "BLOCKED"),
            "physical_execution": "NOT_RUN", "dispatch_readiness": "BLOCKED"}


def freeze(folder, source_manifest_sha256):
    manifest, cases, worlds = read_bundle(folder, source_manifest_sha256)
    historical = historical_tasks()
    by_id, unique_tasks, controls = {}, set(), {}
    for case in cases:
        validate_public(case, historical)
        key, task = case["case_id"], normalized_task(case["task"])
        if key in by_id or task in unique_tasks:
            raise ValueError("duplicate public Planning case or task")
        by_id[key] = case
        unique_tasks.add(task)
    variants = {proof.get("case_id"): proof.get("variant") for proof in worlds}
    if by_id.keys() != variants.keys() or len(worlds) != len(variants):
        raise ValueError("independent Planning worlds must cover the exact public case roster")
    roster = allocate(cases, variants, source_manifest_sha256)
    replay = defaultdict(Counter)
    for proof in worlds:
        case_id = proof["case_id"]
        control = validate_control(by_id[case_id], proof)
        controls[case_id] = control
        counts = replay[by_id[case_id]["level"]]
        counts["cases"] += 1
        counts["worlds"] += control["worlds"]
        counts["multi_route_cases"] += control["distinct_routes"] > 1
        counts["synthetic_commit_cases"] += control["synthetic_commit"]
        counts["safe_denial_cases"] += control["approval_denial"]
        if control["distinct_routes"] > 1:
            counts.update(control["counterfactuals"])
    advanced = [replay[level] for level in ("L5", "L6", "L7")]
    if not any(row["recovery"] for row in advanced) or not any(row["scope_revision"] for row in advanced):
        raise ValueError("advanced Planning levels require independent multiroute recovery and scope controls")
    if not replay["L4"]["multi_route_cases"]:
        raise ValueError("L4 requires alternative executable paths under the same public contract")
    if not replay["L7"]["synthetic_commit_cases"] or not replay["L7"]["safe_denial_cases"]:
        raise ValueError("L7 requires both trusted synthetic approval and safe-denial controls")
    sources = [
        Path(__file__), Path(__file__).with_name("planning_controls.py"), CORE, HISTORICAL,
        *(ROOT / "benchmarks/agentic_planning_v2").glob("*.py"),
        *(ROOT / "schemas").glob("conditional_plan_v2*.json"),
    ]
    roster_raw = b"".join(canonical(row) + b"\n" for row in roster)
    report = {"version": VERSION, "suite": SUITE, "evidence_class": "independent synthetic software replay",
              "source_manifest_sha256": source_manifest_sha256, "source_bundle": manifest,
              "sources": {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(sources)},
              "allocation": allocation(), "world_replay_by_level": dict(replay), "case_controls": controls,
              "roster_sha256": sha256(roster_raw).hexdigest(), "readiness": readiness(validated=True)}
    return {"roster.jsonl": roster_raw, "manifest.json": canonical(report) + b"\n"}


def output_files(out, files, check):
    for name, content in files.items():
        check_text(content)
        target = out / name
        if ((target.exists() and (not target.is_file() or target.read_bytes() != content))
                or (check and not target.is_file())):
            raise ValueError("Planning freeze replay differs from the existing output")
    if check:
        return
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        target = out / name
        if target.exists():
            continue
        temporary = out / f".{name}-{uuid4().hex}"
        try:
            temporary.write_bytes(content)
            try:
                target.hardlink_to(temporary)
            except FileExistsError:
                if target.read_bytes() != content:
                    raise ValueError("Planning freeze changed during publication") from None
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, help="independently authored sealed holdout source directory")
    parser.add_argument("--source-manifest-sha256")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--check-host", action="store_true", help="verify the existing handoff binds the live host")
    args = parser.parse_args()
    if args.bundle:
        if not args.out or not args.source_manifest_sha256 or args.out.resolve().is_relative_to(args.bundle.resolve()):
            parser.error("a bundle requires an independently pinned digest and a separate output directory")
        files = freeze(args.bundle, args.source_manifest_sha256)
        output_files(args.out, files, args.check)
    elif args.check or args.out or args.source_manifest_sha256:
        parser.error("freeze and check require a bundle")
    if args.check_host:
        require_handoff(ROOT)
    print(json.dumps({"allocation": allocation(), "handoff_artifact_sha256": digest(ROOT / HANDOFF),
                      "readiness": readiness(validated=args.bundle is not None, host_checked=args.check_host)}))


if __name__ == "__main__":
    main()
