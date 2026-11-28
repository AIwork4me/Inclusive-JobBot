"""EA13-C — qualify the N03 Batch C cognitive primitives (C17-C24).

Per-primitive qualification for the Batch C DEVELOPMENT scope from
committed evidence only (EA03-C GT validity, Wave B-C witness rates,
production-logic fault controls). Development evidence never qualifies
protected confirmation; no Batch A/B carry-over.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
OUT = ROOT / "evidence" / "IJEVAL" / "EA13C"

PRIMS = [f"C{i:02d}" for i in range(17, 25)]

FAULT_TARGETS_C = {
    "C17": ["C-P03_truth_tokens_loose", "C-E01_truth_prefix_match"],
    "C18": ["C-P04_edges_lineform_rejected", "C-E02_edges_order_strict"],
    "C19": ["C-P05_plan_lines_rejected", "C-E03_plan_string_match"],
    "C20": ["C-E04_holding_superset"],
    "C21": ["C-P05_plan_lines_rejected", "C-E03_plan_string_match"],
    "C22": ["C-P01_duplicate_keys_accepted", "C-P02_fences_not_stripped",
            "C-E05_status_clears_error"],
    "C23": ["C-P01_duplicate_keys_accepted", "C-E06_args_subset_match"],
    "C24": ["C-P01_duplicate_keys_accepted", "C-P02_fences_not_stripped"],
}


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    gt = json.loads(
        (EVID / "ground_truth_qualification_dev160_batch_c.json")
        .read_text(encoding="utf-8"))
    wit = json.loads((EVID / "dualpath_witnesses_batch_c.json")
                     .read_text(encoding="utf-8"))["rows"]
    mut = json.loads((EVID / "production_mutation_campaign_batch_c.json")
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
        for fname in FAULT_TARGETS_C[prim]:
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
        "schema": "ijeval.ea13c.primitive_qualification.v1",
        "generated_utc": stamp,
        "scope": "N03 Batch C DEVELOPMENT (C17-C24), CPU qualification "
                 "protocol; NOT protected confirmation; no Batch A/B "
                 "carry-over; plan validity by goal-predicate simulation",
        "primitives": rows,
        "protocol": {"name": "chat-surface CPU qualification",
                     "qualified": True,
                     "note": "physical protocol parameters are the "
                             "runner lane's (IJ-NANO)"},
        "summary": {"qualified": sum(1 for r in rows
                                     if r["verdict"] == "QUALIFIED"),
                    "total": len(rows)}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "primitive_qualification_batch_c.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("qualified:", report["summary"]["qualified"], "/", len(rows))
    for r in rows:
        if r["verdict"] != "QUALIFIED":
            print("NOT QUALIFIED:", r["primitive"],
                  "witnesses", r["witnesses"], "gt", r["ground_truth"])
    return 0 if report["summary"]["qualified"] == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
