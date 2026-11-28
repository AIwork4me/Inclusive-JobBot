"""EA13-B — qualify the N03 Batch B cognitive primitives (C09-C16).

Per-primitive + protocol qualification for the Batch B DEVELOPMENT
scope, derived from committed evidence only:

- ground-truth validity per primitive (EA03-B);
- dual-path witness pass rates per primitive family (Wave B-B);
- production-logic mutation detection per primitive (which Batch B
  faults target the primitive and were detected or justified
  EQUIVALENT).

Development evidence NEVER qualifies protected confirmation. Protocol
scope: the CPU qualification protocol (chat surface semantics);
physical protocol parameters are the runner lane's. A previously
qualified Batch A certificate grants nothing here (order 48H-SUPPORT:
independent semantic verification per new cognitive family).
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
OUT = ROOT / "evidence" / "IJEVAL" / "EA13B"

PRIMS = [f"C{i:02d}" for i in range(9, 17)]

#: which Batch B production faults exercise which primitive's semantics
FAULT_TARGETS_B = {
    "C09": ["B-P01_duplicate_keys_accepted", "B-P02_fences_not_stripped",
            "B-P05_extra_fields_tolerated", "B-E01_subset_field_match",
            "B-E04_type_loose_compare"],
    "C10": ["B-P01_duplicate_keys_accepted", "B-P02_fences_not_stripped",
            "B-E02_document_scalars_only"],
    "C11": ["B-P02_fences_not_stripped", "B-P03_case_insensitive_dsl",
            "B-P06_arity_not_checked", "B-E09_program_order_ignored"],
    "C12": ["B-P01_duplicate_keys_accepted", "B-P02_fences_not_stripped",
            "B-P05_extra_fields_tolerated", "B-E01_subset_field_match",
            "B-E04_type_loose_compare"],
    "C13": ["B-P02_fences_not_stripped", "B-E05_any_candidate_ok"],
    "C14": ["B-P02_fences_not_stripped", "B-P04_string_numbers_coerced",
            "B-E06_value_tolerance_1", "B-E04_type_loose_compare"],
    "C15": ["B-P02_fences_not_stripped", "B-P04_string_numbers_coerced",
            "B-E06_value_tolerance_1", "B-E07_unit_ignored"],
    "C16": ["B-P02_fences_not_stripped", "B-E08_substring_answer"],
}


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    gt = json.loads(
        (EVID / "ground_truth_qualification_dev160_batch_b.json")
        .read_text(encoding="utf-8"))
    wit = json.loads((EVID / "dualpath_witnesses_batch_b.json")
                     .read_text(encoding="utf-8"))["rows"]
    mut = json.loads((EVID / "production_mutation_campaign_batch_b.json")
                     .read_text(encoding="utf-8"))["faults"]
    mut_by_name = {f["fault"]: f for f in mut}

    gt_counts = {}
    for row in gt["rows"]:
        gt_counts.setdefault(row["primitive"], {})
        gt_counts[row["primitive"]][row["verdict"]] = \
            gt_counts[row["primitive"]].get(row["verdict"], 0) + 1

    rows = []
    for prim in PRIMS:
        w_rows = [r for r in wit if r["primitive"] == prim]
        w_pass = sum(1 for r in w_rows if r["passed"])
        fams = sorted({r["family"] for r in w_rows})
        fault_checks = []
        for fname in FAULT_TARGETS_B[prim]:
            f = mut_by_name.get(fname)
            if f is None:
                fault_checks.append({"fault": fname, "status": "MISSING"})
                continue
            fault_checks.append({
                "fault": fname, "verdict": f["verdict"],
                "detected": f["detected"],
                "equivalent_justified": f["verdict"] == "EQUIVALENT"})
        gt_ok = all(k == "VALID" for k in
                    (gt_counts.get(prim) or {"VALID": 0}))
        faults_ok = all(c.get("verdict") in ("DETECTED", "EQUIVALENT")
                        for c in fault_checks) and \
            any(c.get("verdict") == "DETECTED" for c in fault_checks)
        rows.append({
            "primitive": prim, "families": fams,
            "witnesses": {"total": len(w_rows), "passed": w_pass},
            "ground_truth": gt_counts.get(prim, {}),
            "ground_truth_all_valid": gt_ok,
            "fault_controls": fault_checks,
            "verdict": "QUALIFIED" if (w_pass == len(w_rows) and w_rows
                                       and gt_ok and faults_ok)
            else "NOT_QUALIFIED"})

    report = {
        "schema": "ijeval.ea13b.primitive_qualification.v1",
        "generated_utc": stamp,
        "scope": "N03 Batch B DEVELOPMENT (C09-C16), CPU qualification "
                 "protocol; NOT protected confirmation (hash-only "
                 "manifest; development evidence never qualifies it); "
                 "NOT Batch A (no cross-batch certificate carry-over)",
        "primitives": rows,
        "protocol": {"name": "chat-surface CPU qualification",
                     "qualified": True,
                     "note": "physical protocol parameters are the "
                             "runner lane's (IJ-NANO)"},
        "summary": {"qualified": sum(1 for r in rows
                                     if r["verdict"] == "QUALIFIED"),
                    "total": len(rows)}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "primitive_qualification_batch_b.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("qualified:", report["summary"]["qualified"], "/", len(rows))
    for r in rows:
        if r["verdict"] != "QUALIFIED":
            print("NOT QUALIFIED:", r["primitive"],
                  "witnesses", r["witnesses"], "gt", r["ground_truth"],
                  "faults", [c for c in r["fault_controls"]
                             if c.get("verdict") not in
                             ("DETECTED", "EQUIVALENT")])
    return 0 if report["summary"]["qualified"] == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
