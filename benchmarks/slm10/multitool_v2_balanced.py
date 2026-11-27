"""Build and verify the balanced MULTITOOL-V2 synthetic candidate."""

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from evaluation.aeve.archive import digest
from evaluation.aeve.runtime import canonical, fingerprint

from . import multitool_v2_candidate as original
from .multitool_v2_cases import Author, BUILDERS, CATEGORIES, LANGUAGES
from .multitool_v2_witness import witness

VERSION = "MULTITOOL-V2/candidate-0.2"
FOLDER = original.FOLDER.with_name("multitool-v2-candidate-0.2")


class BalancedAuthor(Author):
    def __init__(self, category, depth, language, variant):
        super().__init__(category, depth, language, variant)
        self.identity = f"MT2-C02-{category}-{depth:02}-{language}-{variant}"


def candidate():
    rows, repeats = [], []
    for band_index, (low, high) in enumerate(original.BANDS):
        for category_index, category in enumerate(CATEGORIES):
            by_language = {language: [] for language in LANGUAGES}
            for language_index, language in enumerate(LANGUAGES):
                for depth in range(low, high + 1):
                    # Each category/language cell has five cases per band. Short bands
                    # split them 2/3 in alternating cells, while long bands use one per depth.
                    variants = 1 if high - low == 4 else 2 + (category_index + language_index + depth) % 2
                    for variant in range(variants):
                        row = BUILDERS[category](BalancedAuthor(category, depth, language, variant))
                        rows.append(row)
                        by_language[language].append(row[0]["case_id"])
            quota = 3 if (category_index + band_index) % 2 == 0 else 2
            start = (category_index // 2 + band_index) % len(LANGUAGES)
            for offset in range(quota):
                pool = by_language[LANGUAGES[(start + offset) % len(LANGUAGES)]]
                repeats.append(min(pool, key=lambda key: fingerprint([VERSION, "repeat", key])))
    return rows, repeats


def shape(rows, repeats):
    strata = original.shape(rows, repeats)
    if any(public["case_id"] != world["case_id"] or public["case_id"] != graph["case_id"]
           or public["required_actions"] != len(graph["actions"]) for public, world, graph in rows):
        raise ValueError("case, world, oracle or action-count identity differs")
    strata["case_bands"] = {}
    for low, high in original.BANDS:
        members = [case for case, _, _ in rows if low <= case["required_actions"] <= high]
        cells = Counter((case["category"], case["language"]) for case in members)
        if cells != {(category, language): 5 for category in CATEGORIES for language in LANGUAGES}:
            raise ValueError("first-trial band balance differs from the 120-case quota and cross strata")
        strata["case_bands"][f"{low}-{high}"] = len(members)
    if strata["case_exact_action_counts"] != {str(depth): 60 if depth <= 5 else 24 for depth in range(2, 21)}:
        raise ValueError("first-trial exact-depth balance differs from registered candidate quotas")
    return strata


def trial_roster(candidate_id, rows, repeats):
    shape(rows, repeats)
    roster = original.trial_roster(candidate_id, rows, repeats)
    for trial in roster:
        trial["suite"] = VERSION
        trial["trial_id"] = fingerprint({key: value for key, value in trial.items() if key != "trial_id"})
    return roster


def _balanced_controls(rows):
    def case_at(category, depth, *, first_observation=None):
        for public, world, oracle in rows:
            if public["category"] != category or public["required_actions"] != depth:
                continue
            sample = witness(public, world)
            if first_observation is None or all(sample["calls"][0]["observation"].get(key) == value
                                                for key, value in first_observation.items()):
                return public, world, oracle, sample
        raise ValueError(f"candidate control fixture missing for {category} at depth {depth}")

    def control(fixture, expected, edit=lambda sample: None):
        public, world, oracle, sample = fixture
        sample = deepcopy(sample)
        edit(sample)
        result = original.evaluate(public, world, oracle, sample)
        return {"case_id": public["case_id"], "sample_sha256": fingerprint(sample), "expected": expected,
                "observed": result["status"], "reason": result["reason"],
                "status": "PASS" if result["status"] == expected else "FAIL"}

    def reverse_sequential_reads(sample):
        sample["calls"].reverse()
        for turn, call in enumerate(sample["calls"]):
            call.update(turn=turn, completion_id=f"alternative-turn-{turn}")

    def reorder_updated_access_reads(sample):
        reads = sample["calls"][1:]
        for destination, call in zip(reads, reversed(deepcopy(reads)), strict=True):
            turn, completion = destination["turn"], destination["completion_id"]
            destination.update(call, turn=turn, completion_id=completion)

    parallel = case_at("parallel", 20)
    serial = case_at("serial", 20)
    retry = case_at("recovery", 2, first_observation={"status": "retryable"})
    mirror = case_at("recovery", 2, first_observation={"status": "unavailable"})
    current_scope = case_at("scope_update", 20)
    withheld = next((public, world, oracle, witness(public, world)) for public, world, oracle in rows
                    if public["category"] == "authorization" and public["required_actions"] == 2
                    and oracle["answer"]["decision"] == "withheld")
    return {
        "reordered_parallel_across_turns": control(parallel, "PASS", reverse_sequential_reads),
        "reordered_access_after_scope_update": control(current_scope, "PASS", reorder_updated_access_reads),
        "serial_depth_twenty": control(serial, "PASS"),
        "retry_same_turn": control(retry, "FAIL", lambda sample: sample["calls"][1].update(
            turn=sample["calls"][0]["turn"], completion_id=sample["calls"][0]["completion_id"])),
        "non_retryable_mirror": control(mirror, "PASS"),
        "ineligible_consent_branch": control(withheld, "FAIL", lambda sample: sample["calls"][-1].update(
            tool="read_public_excerpt")),
        "missing_scope_event": control(current_scope, "FAIL", lambda sample: sample["events"].clear()),
        "action_budget_exceeded": control(parallel, "FAIL", lambda sample: sample["calls"].extend(sample["calls"][:5])),
        "missing_call_identity": control(serial, "BLOCKED", lambda sample: sample["calls"][0].pop("call_id")),
        "invalid_argument_json": control(serial, "FAIL", lambda sample: sample["calls"][0].update(arguments_raw="{")),
    }


def files():
    plan = json.loads(original.PLAN.read_bytes())
    if plan["suites"]["MULTITOOL-V2"] != original.COUNTS or tuple(plan["panel"]) != original.MODELS:
        raise ValueError("candidate roster differs from the registered execution plan")
    rows, repeats = candidate()
    strata = shape(rows, repeats)
    roster = {
        "cases": [{key: public[key] for key in ("case_id", "category", "language", "required_actions")}
                  | {"critical_path": oracle["critical_path"], "model_input_sha256": fingerprint(
                      {"message": public["message"], "tools": public["tools"]}),
                      "world_sha256": fingerprint(world), "oracle_sha256": fingerprint(oracle)}
                  for public, world, oracle in rows],
        "repeat_case_ids": repeats, "repeat_seeds": list(original.REPEAT_SEEDS), "first_seed": original.FIRST_SEED,
        "per_model_candidate_roster_sha256": {
            model: fingerprint(trial_roster(model, rows, repeats)) for model in original.MODELS
        },
    }
    report = original._qualification(rows)
    report["balanced_controls"] = _balanced_controls(rows)
    report["coverage"]["independent_business_and_content_review"] = "NOT_RUN"
    if any(control["status"] != "PASS" for control in report["balanced_controls"].values()):
        report["software_qualification"] = "FAIL"
    outputs = {"roster.json": canonical(roster) + b"\n", "software-qualification.json": canonical(report) + b"\n"}
    manifest = {
        "version": VERSION, "execution_plan_sha256": digest(original.PLAN),
        "prior_candidate_manifest_sha256": digest(original.FOLDER / "manifest.json"),
        "counts_per_model": original.COUNTS, "panel": list(original.MODELS),
        "planned_trials": len(original.MODELS) * sum(original.COUNTS.values()), "attributed_physical_trials": 0,
        "candidate_roster_status": "PASS", "formal_roster_freeze": "NOT_RUN", "formal_dispatch": "BLOCKED",
        "physical_execution": "NOT_RUN", "cohort_strata": strata,
        "source_sha256": {name: digest(Path(__file__).with_name(name)) for name in (
            Path(__file__).name, "multitool_v2_candidate.py", "multitool_v2_cases.py", "multitool_v2_witness.py",
            "action_graph_v2.py",
        )},
        "files": {name: sha256(raw).hexdigest() for name, raw in outputs.items()},
    }
    return {"manifest.json": canonical(manifest) + b"\n", **outputs}, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    expected, report = files()
    if args.write:
        FOLDER.mkdir(parents=True, exist_ok=True)
    for name, raw in expected.items():
        target = FOLDER / name
        if args.write and not target.exists():
            target.write_bytes(raw)
        if target.read_bytes() != raw:
            raise ValueError(f"{VERSION} artifact differs: {name}")
    print(report["software_qualification"], report["independent_witnesses"]["PASS"],
          "software witnesses; physical execution", report["physical_execution"])
    return 0 if report["software_qualification"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
