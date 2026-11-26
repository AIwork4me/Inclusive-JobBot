"""Update the IJ073 gate ledger from published evidence. Formal release needs independent sign-off."""
import argparse
from collections import Counter
import json
from pathlib import Path

from .archive import verify
from .qualification import measure
from .runtime import ROOT


def snapshot():
    archive = ROOT/"evaluation/aeve/results"
    verify(archive)
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
    if counts["gold-development-robustness-v1"]:
        gates["E09"] = ("BLOCKED","Physical robustness evidence exists; the interference and bias review must close separately.")
    if gates["E08"][0] == "PASS" and counts["history-v2"]:
        from .human_review import verify_coverage
        from .history import lines, OUT
        from .runtime import REGISTRY
        families = {c:cfg["family"] for c,cfg in json.loads(REGISTRY.read_bytes())["candidates"].items()}
        summary = json.loads((OUT/"rescore_summary.json").read_bytes())
        try:
            verify_coverage(summary,lines(OUT/"rescore.jsonl.gz"),measure(archive),families)
        except ValueError:
            pass
        else:
            gates["E07"] = ("PASS","Each applicable physical and nonphysical stage has independently verified review coverage.")
            gates["E10"] = ("PASS","All required historical disagreements have a recorded independent third review.")
    return counts,history,admitted,gates


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--write",action="store_true")
    args=cli.parse_args()
    counts,history,admitted,gates=snapshot()
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
    data["remaining"]={"sealed_gold":sum(r["required"]-r["recorded"] for r in admitted.values()),
                       "expanded_planning_development":64-counts["planning-development"],
                       "robustness":224-counts["gold-development-robustness-v1"],
                       "historical_physical_primary":2*sum(history["formal_dimensions"].values())-counts["history-v2"],
                       "historical_nonphysical_primary":2*sum(extra["dimensions"].values())-counts["history-supplement-v2"],
                       "formal_core_physical":18440}
    data["evidence_gates"]={k:v for k,(v,reason) in gates.items()}
    data["gate_basis"]={k:reason for k,(v,reason) in gates.items()}
    data["qualification"].update(AEVE_IMPLEMENTATION_VERDICT="PASS",
            AEVE_FULL_SELF_EVALUATION_VERDICT=gates["E07"][0],AEVE_AI_JUDGE_QUALIFICATION_VERDICT=gates["E08"][0])
    data["next_dependency"]="Finish four sealed qualification cohorts; admit on frozen gates, then evaluate the full stage-eligible physical registry."
    data["resume_command"]="python -m evaluation.aeve resume"
    raw=(json.dumps(data,ensure_ascii=False,indent=2)+"\n").encode()
    if args.write:
        path.write_bytes(raw)
    elif raw != path.read_bytes():
        raise SystemExit("mission ledger differs from published sessions")
    print(json.dumps(data["remaining"]))


if __name__ == "__main__":
    main()
