"""Build and verify the independent MULTITOOL-V2 candidate roster and software evidence."""

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from benchmarks.tool_calling_v2.oracle import decode_object, equal
from evaluation.aeve.archive import digest
from evaluation.aeve.runtime import ROOT, canonical, fingerprint

from .action_graph_v2 import replay
from .multitool_v2_cases import Author, BUILDERS, CATEGORIES, LANGUAGES, VERSION
from .multitool_v2_witness import Scenario, witness

FOLDER = ROOT / "atlas/slm/v1.0/multitool-v2-candidate"
PLAN = FOLDER.parent / "execution_plan.json"
COUNTS = {"direct_first": 600, "sdk_first": 600, "sdk_repeat": 300}
MODELS = ("A", "B", "D", "F", "G")
FIRST_SEED = 27641
REPEAT_SEEDS = (31859, 50261, 73369)
BANDS = ((2, 3), (4, 5), (6, 10), (11, 15), (16, 20))
GAPS = (
    "independent blind review of candidate prompts, task partitions and expected outcomes",
    "persisted authorized draft and confirmation controls for write-capable workflows",
    "production transport, source-delivery and authorization evidence for Direct and Antigravity",
    "pinned physical roster preflight and qualification of both runtimes on the approved Radeon",
)


def candidate():
    rows = []
    for index, category in enumerate(CATEGORIES):
        supplemental = {2 + (index * 6 + offset) % 19 for offset in range(6)}
        for depth in range(2, 21):
            for language in LANGUAGES:
                for variant in range(1 + (depth in supplemental)):
                    rows.append(BUILDERS[category](Author(category, depth, language, variant)))
    repeats = []
    for band_index, (low, high) in enumerate(BANDS):
        for index, category in enumerate(CATEGORIES):
            quota = 3 if (index + band_index) % 2 == 0 else 2
            start = (index // 2 + band_index) % len(LANGUAGES)
            for offset in range(quota):
                language = LANGUAGES[(start + offset) % len(LANGUAGES)]
                pool = [public["case_id"] for public, _, _ in rows
                        if public["category"] == category and low <= public["required_actions"] <= high
                        and public["language"] == language]
                repeats.append(min(pool, key=lambda key: fingerprint([VERSION, "repeat", key])))
    return rows, repeats


def shape(rows, repeats):
    records = {public["case_id"]: public for public, _, _ in rows}
    if len(rows) != len(records) or len(records) != COUNTS["sdk_first"]:
        raise ValueError("candidate case identities are missing or duplicate")
    if len(repeats) != len(set(repeats)) or len(repeats) * len(REPEAT_SEEDS) != COUNTS["sdk_repeat"]:
        raise ValueError("repeat roster differs from the registered reserve")
    selected = [records[key] for key in repeats]
    bands = {f"{low}-{high}": sum(low <= case["required_actions"] <= high for case in selected)
             for low, high in BANDS}
    categories = Counter(case["category"] for case in records.values())
    languages = Counter(case["language"] for case in records.values())
    coverage = {(case["category"], case["required_actions"], case["language"]) for case in records.values()}
    if (set(bands.values()) != {20} or categories != dict.fromkeys(CATEGORIES, 75)
            or languages != dict.fromkeys(LANGUAGES, 200)
            or coverage != {(category, count, lang)
                            for category in CATEGORIES for count in range(2, 21) for lang in LANGUAGES}):
        raise ValueError("candidate complexity strata are incomplete")
    return {
        "case_categories": dict(categories), "case_languages": dict(languages),
        "case_exact_action_counts": dict(Counter(str(case["required_actions"]) for case in records.values())),
        "repeat_categories": dict(Counter(case["category"] for case in selected)),
        "repeat_languages": dict(Counter(case["language"] for case in selected)),
        "repeat_bands": bands,
    }


def trial_roster(candidate_id, rows, repeats):
    if candidate_id not in MODELS:
        raise ValueError("model is outside the registered comparison panel")
    shape(rows, repeats)
    repeat_ids = set(repeats)
    roster = []
    for public, world, oracle in rows:
        case_id = public["case_id"]
        model_input = {"message": public["message"], "tools": public["tools"]}
        spec = {"suite": VERSION, "candidate": candidate_id, "case_id": case_id,
                "input_sha256": fingerprint(model_input), "world_sha256": fingerprint(world),
                "oracle_sha256": fingerprint(oracle)}
        tracks = ("direct_first", "sdk_first", "sdk_repeat") if case_id in repeat_ids else ("direct_first", "sdk_first")
        for track in tracks:
            for seed in REPEAT_SEEDS if track == "sdk_repeat" else (FIRST_SEED,):
                identity = spec | {"track": track, "seed": seed}
                roster.append(identity | {"trial_id": fingerprint(identity)})
    return roster


def evaluate(public, world, oracle, capture):
    if not isinstance(capture, dict) or capture.get("complete") is not True:
        return {"status": "BLOCKED", "reason": "incomplete workflow evidence"}
    if any(key not in capture for key in ("calls", "events", "answer")):
        return {"status": "BLOCKED", "reason": "missing action, moderation or terminal evidence"}
    try:
        graph = replay(oracle, capture)
        if graph["status"] != "PASS":
            return graph
        traces = sorted(capture["calls"], key=lambda call: call["turn"])
        scenario = Scenario(public, world)
        for call in traces:
            if scenario.pending and scenario.pending["before_turn"] <= call["turn"]:
                scenario.take_event(scenario.pending["before_turn"])
            result, _ = scenario.read(call["tool"], decode_object(call["arguments_raw"]), call["turn"], call["call_id"])
            if not equal(call["observation"], result):
                raise ValueError("observation differs from synthetic service read")
        if capture["events"] != scenario.delivered:
            raise ValueError("moderation message is missing or differs from its triggering observation")
        if public["category"] == "typed_transfer":
            preview = next(call for call in traces if call["tool"] == "preview_caption")
            sources = {call["observation"]["entry"]["caption_id"]: call for call in traces if call["tool"] == "read_caption"}
            args = decode_object(preview["arguments_raw"])
            entries = args["preview"]["entries"]
            for entry in entries:
                producer = sources[entry["caption_id"]]
                if producer["turn"] >= preview["turn"] or not equal(entry, producer["observation"]["entry"]):
                    raise ValueError("typed entry lacks a prior matching producer")
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        return {"status": "FAIL", "reason": str(error)}
    if not equal(capture["answer"], oracle["answer"]):
        return {"status": "FAIL", "reason": "terminal output differs from independent expectation"}
    return graph


def _qualification(rows):
    statuses, by_category, by_depth, proven = Counter(), Counter(), Counter(), []
    fixtures = {}
    for public, world, graph in rows:
        reference = witness(public, world)
        verdict = evaluate(public, world, graph, reference)
        category = public["category"]
        statuses[verdict["status"]] += 1
        if verdict["status"] == "PASS":
            by_category[category] += 1
            by_depth[str(public["required_actions"])] += 1
        proven.append([public["case_id"], fingerprint(reference), verdict["status"]])
        if category not in fixtures or (category == "recovery"
                                       and reference["calls"][0]["observation"]["status"] == "retryable"):
            fixtures[category] = (public, world, graph, reference)

    def mutate(category, edit, expected):
        public, world, graph, reference = fixtures[category]
        sample = deepcopy(reference)
        edit(sample)
        result = evaluate(public, world, graph, sample)
        return {"case_id": public["case_id"], "sample_sha256": fingerprint(sample), "expected": expected,
                "observed": result["status"], "reason": result["reason"],
                "status": "PASS" if result["status"] == expected else "FAIL"}

    def set_arg(sample, call_index, field, value):
        call = sample["calls"][call_index]
        args = decode_object(call["arguments_raw"])
        if field == "format":
            args["preview"]["format"] = value
        else:
            args[field] = value
        call["arguments_raw"] = canonical(args).decode()

    controls = {
        "reordered_independent_reads": mutate("parallel", lambda evidence: evidence["calls"].reverse(), "PASS"),
        "missing_action": mutate("serial", lambda evidence: evidence["calls"].pop(0), "FAIL"),
        "forged_producer": mutate("serial", lambda evidence: evidence["calls"][-1]["observation_sources"]
                                  ["ref"].update(call_id="forged"), "FAIL"),
        "wrong_final_aggregate": mutate("aggregation", lambda evidence: evidence["answer"].update(total=-1), "FAIL"),
        "wrong_condition": mutate("conditional", lambda evidence: evidence["calls"][0]["observation"]
                                  .update(open=not evidence["calls"][0]["observation"]["open"]), "FAIL"),
        "wrong_typed_enum": mutate("typed_transfer", lambda evidence: set_arg(evidence, -1, "format", "avi"), "FAIL"),
        "legal_repeat": mutate("recovery", lambda evidence: None, "PASS"),
        "excess_repeat": mutate("recovery", lambda evidence: evidence["calls"].append(evidence["calls"][0]), "FAIL"),
        "forged_moderation": mutate("scope_update", lambda evidence: evidence["events"][0].update(event_id="forged"), "FAIL"),
        "stale_scope": mutate("scope_update", lambda evidence: set_arg(evidence, -1, "venue", "stale"), "FAIL"),
        "out_of_scope_write": mutate("authorization", lambda evidence: evidence["calls"][-1].update(tool="commit_release"),
                                     "FAIL"),
        "incomplete_capture": mutate("parallel", lambda evidence: evidence.update(complete=False), "BLOCKED"),
    }
    passed = statuses["PASS"] == len(rows) and all(row["status"] == "PASS" for row in controls.values())
    return {
        "scope": "synthetic software fixture replay", "software_qualification": "PASS" if passed else "FAIL",
        "physical_execution": "NOT_RUN", "formal_dispatch": "BLOCKED", "formal_qualification": "BLOCKED",
        "independent_witnesses": {status: statuses[status] for status in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")},
        "witness_set_sha256": fingerprint(proven), "positive_by_category": dict(by_category),
        "positive_by_exact_action_count": dict(by_depth), "controls": controls,
        "coverage": {"read_only_consent_branch": "PASS" if by_category["authorization"] == 75 else "FAIL",
                     "persisted_authorized_draft": "NOT_RUN", "external_human_confirmation": "NOT_RUN",
                     "live_business_mutation": "NOT_RUN", "physical_complexity_curve": "NOT_RUN"},
        "open_gates": list(GAPS),
    }


def qualification():
    rows, repeats = candidate()
    shape(rows, repeats)
    return _qualification(rows)


def files():
    plan = json.loads(PLAN.read_bytes())
    if plan["suites"]["MULTITOOL-V2"] != COUNTS or tuple(plan["panel"]) != MODELS:
        raise ValueError("candidate roster differs from the registered execution plan")
    rows, repeats = candidate()
    strata = shape(rows, repeats)
    suite = {
        "cases": [{key: public[key] for key in ("case_id", "category", "language", "required_actions")}
                  | {"critical_path": oracle["critical_path"], "model_input_sha256": fingerprint(
                      {"message": public["message"], "tools": public["tools"]}),
                      "world_sha256": fingerprint(world), "oracle_sha256": fingerprint(oracle)}
                  for public, world, oracle in rows],
        "repeat_case_ids": repeats,
        "repeat_seeds": list(REPEAT_SEEDS),
        "first_seed": FIRST_SEED,
        "per_model_candidate_roster_sha256": {model: fingerprint(trial_roster(model, rows, repeats)) for model in MODELS},
    }
    controls = _qualification(rows)
    outputs = {"roster.json": canonical(suite) + b"\n", "software-qualification.json": canonical(controls) + b"\n"}
    manifest = {
        "version": VERSION, "execution_plan_sha256": digest(PLAN), "counts_per_model": COUNTS, "panel": list(MODELS),
        "planned_trials": len(MODELS) * sum(COUNTS.values()), "attributed_physical_trials": 0,
        "candidate_roster_status": "PASS", "formal_roster_freeze": "NOT_RUN", "formal_dispatch": "BLOCKED",
        "physical_execution": "NOT_RUN", "cohort_strata": strata,
        "source_sha256": {name: digest(Path(__file__).with_name(name)) for name in
                          ("multitool_v2_cases.py", "multitool_v2_witness.py", "multitool_v2_candidate.py",
                           "action_graph_v2.py")},
        "files": {filename: sha256(raw).hexdigest() for filename, raw in outputs.items()},
    }
    return {"manifest.json": canonical(manifest) + b"\n", **outputs}, controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    expected, report = files()
    if args.write:
        FOLDER.mkdir(parents=True, exist_ok=True)
    for filename, raw in expected.items():
        target = FOLDER / filename
        if args.write and not target.exists():
            target.write_bytes(raw)
        if target.read_bytes() != raw:
            raise ValueError(f"MULTITOOL-V2 candidate artifact differs: {filename}")
    print(report["software_qualification"], report["independent_witnesses"]["PASS"],
          "software witnesses; physical execution", report["physical_execution"])
    return 0 if report["software_qualification"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
