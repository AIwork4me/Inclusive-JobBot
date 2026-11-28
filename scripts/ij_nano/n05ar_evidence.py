#!/usr/bin/env python3
"""N05A-R evidence generator: comparator-level mutation results and the
v2 coverage matrix (declared/reachable/tested reconciliation)."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.eval.contracts import (CONTRACT_VERSION, FAMILIES,
                                       REASON_CODES, REASON_CODE_DISPOSITIONS)
from nanoagent.eval.controls import TRUTH_CONTROLS, battery
from nanoagent.eval.evaluator import CognitiveEvaluator
from nanoagent.eval.qualification import (mutation_gate, reason_coverage,
                                          validate_control_battery)

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main() -> int:
    cases = battery()
    validate_control_battery(cases)
    ev = CognitiveEvaluator(cases)

    # battery execution evidence: positives pass, negatives fail exactly
    battery_exec = {"positives": 0, "negatives": 0, "negative_exact": 0}
    for c in cases:
        r = ev.evaluate(c.case_id, c.response)
        if c.control_class == "positive":
            battery_exec["positives"] += 1
            assert r.passed, (c.case_id, r.reasons)
        else:
            battery_exec["negatives"] += 1
            intended = c.control_class.split(":", 1)[1]
            assert r.reasons == (intended,), (c.case_id, r.reasons, intended)
            battery_exec["negative_exact"] += 1

    truth_exec = {"controls": len(TRUTH_CONTROLS), "agreeing": 0}
    from nanoagent.eval.comparators import predicate_truth
    for tc in TRUTH_CONTROLS:
        got = predicate_truth(tc["pred"], tc["world"])
        assert got == tc["expect"], (tc["name"], got, tc["expect"])
        truth_exec["agreeing"] += 1

    mut_report = mutation_gate(cases, TRUTH_CONTROLS)
    undetected = sorted(m for m, r in mut_report.items() if not r["detected"])

    # retained v1-style mutants (post-evaluation reason-code drops) mapped
    # onto the v2 rule set: every rule still load-bearing
    from nanoagent.eval import contracts as _c

    class _DropRuleEvaluator(CognitiveEvaluator):
        dropped = ""

        def evaluate(self, case_id, response):  # type: ignore[override]
            r = super().evaluate(case_id, response)
            if r.passed or self.dropped not in r.reasons:
                return r
            kept = tuple(x for x in r.reasons if x != self.dropped)
            return _c.EvaluationResult(r.case_id, r.family, not kept, kept)

    retained = {}
    rules = sorted({c.control_class.split(":", 1)[1] for c in cases
                    if c.control_class.startswith("negative:")})
    for rule in rules:
        mut = type("M", (_DropRuleEvaluator,), {"dropped": rule})()
        witness = None
        for c in cases:
            if c.control_class != f"negative:{rule}":
                continue
            true_r = ev.evaluate(c.case_id, c.response)
            mut_r = mut.evaluate(c.case_id, c.response)
            if true_r.reasons == (rule,) and mut_r.passed:
                witness = c.case_id
                break
        retained[rule] = witness
    retained_missing = {r: w for r, w in retained.items() if w is None}

    cov = ev.coverage()
    rec = reason_coverage(cases)

    matrix = {
        "schema": "ij_nano.n05ar.coverage_matrix",
        "generated_utc": __import__("datetime").datetime
                             .now(__import__("datetime").timezone.utc)
                             .isoformat(timespec="seconds"),
        "contract_version": CONTRACT_VERSION,
        "gate": "N05AR_COGNITIVE_EVALUATOR_INTEGRITY_GO",
        "battery": {
            "cases": len(cases),
            "positives": battery_exec["positives"],
            "negatives": battery_exec["negatives"],
            "negatives_failing_for_exactly_their_reason":
                battery_exec["negative_exact"],
        },
        "truth_controls": truth_exec,
        "families": {fam: {
            "positives": cov[fam]["positives"],
            "negatives": cov[fam]["negatives"],
            "reason_codes": cov[fam]["reason_codes"],
        } for fam in FAMILIES},
        "reason_reconciliation": rec,
        "obsolete_codes": REASON_CODE_DISPOSITIONS,
        "comparator_mutants": {
            "classes": sorted(mut_report),
            "detected": {m: r["detected"] for m, r in mut_report.items()},
            "witnesses": {m: r["witness"] for m, r in mut_report.items()},
            "channels": {m: r["channel"] for m, r in mut_report.items()},
            "undetected": undetected,
        },
        "retained_rule_drop_mutants": {
            "rules": rules,
            "witnesses": retained,
            "undetected": sorted(retained_missing),
        },
        "verdict": {
            "battery_green": battery_exec["negative_exact"]
                             == battery_exec["negatives"],
            "truth_controls_green": truth_exec["agreeing"]
                                    == truth_exec["controls"],
            "comparator_mutants_all_detected": not undetected,
            "rule_drop_mutants_all_detected": not retained_missing,
            "reason_codes_reconciled": rec["reconciled"],
        },
    }
    ok = all(matrix["verdict"].values())
    matrix["verdict"]["N05AR_COGNITIVE_EVALUATOR_INTEGRITY_GO"] = \
        "PASS" if ok else "FAIL"

    out = ROOT / "evidence" / "IJNANO" / "N05AR"
    out.mkdir(parents=True, exist_ok=True)
    (out / "coverage_matrix.json").write_text(
        json.dumps(matrix, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps(matrix["verdict"], indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
