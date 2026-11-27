"""Update the IJ073 gate ledger from published evidence. Formal release needs independent sign-off."""
import argparse
from collections import Counter
import json
from pathlib import Path

from .archive import digest
from .qualification import measure
from .history import lines
from .history_routing import route_matrix
from .meta_evaluation import snapshot as sealed_snapshot
from .q2_closure import FROZEN, build as build_q2, scan
from .q2_qualification import COLLECTION, roster
from .runtime import ROOT, write_json

EVIDENCE = ROOT / "evidence/IJ073/aeve"


def coverage_summary(seen, cases, candidates, manifests):
    by_candidate = {code: len(seen.get(code, ())) for code in candidates}
    if set(seen) - set(candidates) or any(items - cases for items in seen.values()):
        raise ValueError("sealed Q2 assessment is outside the frozen roster")
    recorded = sum(by_candidate.values())
    required = len(cases) * len(candidates)
    return {"version": "IJ073-Q2-SEALED-COVERAGE-2", "recorded": recorded, "required": required,
            "remaining": required - recorded, "by_candidate": by_candidate, "session_manifests": manifests,
            "roster_status": "PASS" if recorded == required else "NOT_RUN", "status": "NOT_RUN"}



def attach_q2_admission(coverage, closure, closure_sha256):
    statuses = {code: row["status"] for code, row in closure["models"].items()}
    if (coverage["roster_status"] != "PASS" or coverage["recorded"] != closure["recorded"]
            or set(statuses) != set(coverage["by_candidate"])
            or set(statuses.values()) - {"PASS", "FAIL", "BLOCKED"}):
        raise ValueError("Q2 admission requires a complete sealed roster")
    return {**coverage, "status": "PASS" if list(statuses.values()).count("PASS") >= 2 else "FAIL",
            "candidate_admission": statuses, "closure_sha256": closure_sha256}

def q2_coverage(view, hashes):
    protocol = json.loads(FROZEN.read_bytes())
    sessions, seen = scan(view)
    return {**coverage_summary(seen, set(roster()), tuple(protocol["arms"]),
                               {p.parent.name: hashes[p.parent.name] for p in sessions}),
            "protocol_file_sha256": digest(FROZEN)}


def snapshot(archive):
    counts = Counter()
    for stamp in (archive/"sessions").glob("*/manifest.json"):
        for r in json.loads((stamp.parent/"outcomes.json").read_bytes()):
            counts[r["collection"]] += 1
    history = json.loads((ROOT/"evidence/IJ073/aeve/history/coverage.json").read_bytes())
    admitted = measure(archive)["admission"]
    gates = {
        "E00":("PASS","Versioned bounded planning DSL, public and observed state, invalidation and typed tool contracts."),
        "E01":("PASS","Three source-level corrections and 235 case-level legacy divergence explanations."),
        "E02":("PASS","800 frozen executable witnesses and 29 public-equivalent cases."),
        "E03":("PASS","602 archived paired mutations and independent external-event controls."),
        "E04":("PASS","Bounded graph, authorization and post-state checks in the frozen software worlds."),
        "E05":("PASS","25-dimension software contract, stage-specific exhibits, blinded roles and deterministic veto."),
        "E06":("PASS","Independent local families physically evaluated the same anonymized pilot evidence."),
        "E07":("BLOCKED","Formal physical-trial reviews require admitted families and independent semantic citation checks."),
        "E08":("NOT_RUN","See each family's recorded count and formal decision below."),
        "E09":("NOT_RUN","224 paired development interventions have a separate denominator."),
        "E10":("BLOCKED","Third-family development decisions recorded. Formal disagreement closure requires applicable historical reviews."),
        "E11":("BLOCKED","Pinned assets are indexed. Missing observations and unsupported historical stages constrain assessability."),
        "E12":("BLOCKED","Original 22 retained; freeze the expanded representative and challenge panel after qualification and historical coverage."),
        "E13":("BLOCKED","Independent human review requires E07, E08 and E12."),
        "E14":("BLOCKED","AI-human calibration requires actual blinded submissions."),
        "E15":("BLOCKED","Independent revalidation requires the calibrated evaluator."),
        "E16":("BLOCKED","Benchmark validity and the new benchmark freeze depend on preceding gates."),
        "E17":("BLOCKED","At least 18,440 core trials await benchmark release (4,610 per model); additional runnable candidates retain full coverage."),
        "E18":("BLOCKED","The certified model, job and hardware joint matrix requires the new physical runs."),
        "E19":("BLOCKED","Final remote and fresh-clone delivery audit follows the unified Atlas.")}
    if any(r["recorded"] for r in admitted.values()):
        if all(r["recorded"] == r["required"] for r in admitted.values()):
            passed = sum(r["status"] == "PASS" for r in admitted.values())
            gates["E08"] = ("PASS" if passed >= 2 else "FAIL",f"{passed} independent families admitted on complete gold cohorts.")
        else:
            gates["E08"] = ("BLOCKED","Independent qualification in progress; at least one frozen cohort is incomplete.")
    if counts["gold-development-robustness-v1"] == 224:
        gates["E09"] = ("BLOCKED","All 224 paired interventions ran; retest bias and interference on independently qualified revised configurations.")
    elif counts["gold-development-robustness-v1"]:
        gates["E09"] = ("BLOCKED","Physical robustness evidence exists; the interference and bias review must close separately.")
    return counts,history,admitted,gates


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--write",action="store_true")
    cli.add_argument("--archive", type=Path, default=ROOT / "evaluation/aeve/results")
    args=cli.parse_args()
    with sealed_snapshot(args.archive) as (view, hashes):
        counts,history,admitted,gates=snapshot(view)
        coverage=q2_coverage(view, hashes)
        closure_path = EVIDENCE / "q2_closure.json"
        if closure_path.is_file():
            sealed = json.loads(closure_path.read_bytes())
            if build_q2(view, sealed["session_manifests"]) != sealed:
                raise ValueError("published Q2 closure does not replay")
            coverage = attach_q2_admission(coverage, sealed, digest(closure_path))
    path=ROOT/"atlas/ij073/progress.json"
    data=json.loads(path.read_bytes())
    data["evidence_class"]="deterministic software controls, historical archive replay and sealed local Radeon sessions"
    data["experiment_coverage"].update(
        new_physical_trials=4+counts["clarification"]+counts["planning-development"],
        new_ai_judgments=sum(v for k,v in counts.items() if k not in {"clarification","planning-development"}),
        registered_historical_physical_trials=history["class_counts"]["physical_trial"],
        applicable_historical_physical_trials=history["formal_physical_packets"],
        completed_human_reviews=0)
    extra=json.loads((ROOT/"evidence/IJ073/aeve/history/nonphysical_coverage.json").read_bytes())
    data["experiment_coverage"]["applicable_nonphysical_packets"] = extra["unique_semantic_packets"]
    data["sealed_gpu_by_collection"]=dict(sorted(counts.items()))
    data["qualification_by_judge"]=admitted
    addendum_path=ROOT/"evidence/IJ073/aeve/history/physical_addendum.json"
    extra_physical=sum(json.loads(addendum_path.read_bytes())["added_semantic_dimensions"].values()) if addendum_path.is_file() else 0
    data["remaining"]={"sealed_gold":sum(r["required"]-r["recorded"] for r in admitted.values()),
                       "expanded_planning_development":64-counts["planning-development"],
                       "robustness":224-counts["gold-development-robustness-v1"],
                       "historical_physical_primary":2*(sum(history["formal_dimensions"].values())+extra_physical)-counts["history-v2"],
                       "historical_nonphysical_primary":2*sum(extra["dimensions"].values())-counts["history-supplement-v2"],
                       "formal_core_physical":18440}
    data["remaining"]["q2_qualification"]=coverage["remaining"]
    if counts[COLLECTION] != coverage["recorded"]:
        raise ValueError("Q2 snapshot counts disagree")
    data["q2_qualification"] = {k: coverage[k] for k in ("status", "roster_status", "recorded", "required")}
    data["formal_q3_qualification"] = "NOT_RUN"
    identity = json.loads((EVIDENCE / "history_identity_reverify.json").read_bytes())
    data["experiment_coverage"].update(
        registered_historical_identities=identity["registered_trials"],
        applicable_historical_dimensions=identity["physical_dimensions"] + identity["nonphysical_dimensions"],
        unassessable_historical_physical_trials=identity["unassessable_physical_trials"],
    )
    data["evidence_gates"]={k:v for k,(v,reason) in gates.items()}
    data["gate_basis"]={k:reason for k,(v,reason) in gates.items()}
    data["qualification"].update(AEVE_IMPLEMENTATION_VERDICT="PASS",
            AEVE_FULL_SELF_EVALUATION_VERDICT=gates["E07"][0],AEVE_AI_JUDGE_QUALIFICATION_VERDICT=gates["E08"][0])
    data["next_dependency"]=(
        "Complete and replay the frozen Q2 roster, then verify the GPU handoff."
        if coverage["remaining"] else "Publish the complete Q2 closure and verify the GPU handoff."
        if coverage["status"] == "NOT_RUN" else "Resume paired runtime development and independent Q3 qualification when the GPU is returned to IJ-0.7.3."
    )
    coverage_path = EVIDENCE / "q2_sealed_coverage.json"
    mission_path = ROOT / "MISSION_STATE.json"
    mission = json.loads(mission_path.read_bytes())["q2_sealed_coverage"]
    mission_fields = {k: coverage[k] for k in ("status", "roster_status", "recorded", "required", "remaining")}
    replacement = {**mission, **mission_fields}
    matrix_path = EVIDENCE / "historical_route_matrix.json"
    family_index = EVIDENCE / "history/coverage.json"
    supplement = EVIDENCE / "history/judge_inputs_nonphysical_v2.jsonl.gz"
    subjects = set(history["source_families"])
    subjects.update(row["source_family"] for row in lines(supplement))
    matrix = {"version": "IJ073-ROUTE-MATRIX-1", "formal_history": "BLOCKED",
              "q3_credentials": "NOT_RUN",
              "source_sha256": {"physical": digest(family_index), "nonphysical": digest(supplement)},
              **route_matrix([], subjects)}
    data["resume_command"]="python -m evaluation.aeve resume"
    raw=(json.dumps(data,ensure_ascii=False,indent=2)+"\n").encode()
    if args.write:
        path.write_bytes(raw)
        write_json(coverage_path, coverage)
        write_json(matrix_path, matrix)
        # Preserve the existing layout outside the synchronized Q2 entry.
        lines_before = mission_path.read_bytes()
        old_field = next(line for line in lines_before.splitlines() if b'"q2_sealed_coverage":' in line)
        new_field = ('  "q2_sealed_coverage": ' + json.dumps(replacement, ensure_ascii=False) + ',').encode()
        mission_path.write_bytes(lines_before.replace(old_field, new_field, 1))
    elif (raw != path.read_bytes() or json.loads(coverage_path.read_bytes()) != coverage
          or mission != replacement or json.loads(matrix_path.read_bytes()) != matrix):
        raise SystemExit("mission ledger differs from published sessions")
    print(json.dumps(data["remaining"]))


if __name__ == "__main__":
    main()
