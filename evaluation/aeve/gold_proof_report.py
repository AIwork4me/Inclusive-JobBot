"""Replay the frozen Q1 discrepancy cohort against independent Gold proof obligations."""
import argparse
from collections import Counter
import json
from pathlib import Path

from .archive import check_text, digest
from .gold import iter_gold
from .gold_proof import SUPPORTED, assess, mutations, prove
from .history import lines
from .runtime import ROOT, write_json

EVIDENCE = ROOT / "evidence/IJ073/aeve"
ALTERNATIVE = "sufficient_with_different_citation_set"


def build(evidence=EVIDENCE):
    audit = evidence / "q1_source_audit.json"
    ledger = evidence / "q1_root_cause_ledger.jsonl.gz"
    original = json.loads(audit.read_bytes())
    if digest(ledger) != original["ledger_sha256"]:
        raise ValueError("Q1 ledger differs from original seal")
    frozen = evidence / "judge_qualification.json"
    if digest(frozen) != original["frozen_q1_sha256"]:
        raise ValueError("Q1 qualification differs from original seal")
    defects = set(original["gold_evidence_insufficient"])
    alternatives = [row for row in lines(ledger)
                    if row["judge"] == "J" and ALTERNATIVE in row["classification"]]
    requested = defects | {row["case_id"] for row in alternatives}
    cases = {row["case_id"]: row for row in iter_gold("qualification") if row["case_id"] in requested}
    if len(defects) != 45 or len(alternatives) != 81 or set(cases) != requested:
        raise ValueError("Q1 discrepancy cohort differs from the published inventory")
    entries = {}
    for case_id, case in sorted(cases.items()):
        packet, tag = case["packet"], case["tags"][0]
        if packet["dimension"] != SUPPORTED.get(tag):
            raise ValueError("unregistered Gold proof template")
        proof = prove(packet)
        entries[case_id] = {
            "template": tag, "packet_sha256": case["packet_sha256"], "historical_label": case["expected"],
            "historical_refs": case["required_refs"], "original_gold_defect": case_id in defects,
            "proof": proof, "mutations": mutations(tag, packet),
            "historical_gold_assessment": assess(packet, case["expected"], case["required_refs"],
                                                case["required_refs"]),
        }
    reviews = []
    for row in sorted(alternatives, key=lambda row: row["case_id"]):
        case = cases[row["case_id"]]
        if row["packet_sha256"] != case["packet_sha256"]:
            raise ValueError("Q1 alternative is bound to a different source packet")
        reviews.append({
            "case_id": row["case_id"], "job": row["job"], "run": row["run"], "judge": row["judge"],
            "verdict": row["prediction"], "citations": row["citations"],
            "historical_classification": row["classification"], "historical_exact": row["strict_exact_refs"],
            "certification": assess(case["packet"], row["prediction"], row["citations"], case["required_refs"]),
        })
    checks = [control for entry in entries.values()
              for control in [*entry["mutations"]["necessary_deletions"], entry["mutations"]["fact_reversal"]]]
    label_conflicts = sorted(cid for cid, entry in entries.items()
                             if entry["proof"]["verdict"] != entry["historical_label"])
    defects_confirmed = sum(not entries[cid]["historical_gold_assessment"]["sufficient"] for cid in defects)
    sufficient_alternatives = sum(row["certification"]["sufficient"] for row in reviews)
    controls = dict(sorted(Counter(check["status"] for check in checks).items()))
    return {
        "version": "IJ073-GOLD-PROOF-1", "scope": "Q1 discrepancy templates and archived Qwen3-14B responses",
        "source_sha256": {"audit": digest(audit), "ledger": digest(ledger), "frozen_Q1": digest(frozen),
                          "proof_implementation": digest(Path(__file__).with_name("gold_proof.py"))},
        "status": "PASS" if not label_conflicts and controls == {"PASS": len(checks)}
                            and defects_confirmed == 45 and sufficient_alternatives == 81 else "FAIL",
        "formal_router_qualification": "NOT_RUN", "legacy_free_form_rationale_qualification": "NOT_RUN",
        "gold_defects_confirmed": defects_confirmed, "sufficient_alternatives": sufficient_alternatives,
        "case_count": len(entries), "label_conflicts": label_conflicts, "mutation_controls": controls,
        "alternative_findings": dict(sorted(Counter(f for row in reviews
                                                    for f in row["certification"]["findings"]).items())),
        "cases": entries, "alternative_reviews": reviews,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    report = build()
    if args.replay and json.loads(args.replay.read_bytes()) != report:
        raise ValueError("Gold proof replay differs from archived report")
    check_text(json.dumps(report, ensure_ascii=False).encode())
    write_json(args.output, report)
    print({key: report[key] for key in ("status", "case_count", "gold_defects_confirmed",
                                        "sufficient_alternatives", "mutation_controls")})


if __name__ == "__main__":
    main()
