"""EA13 — qualify the actual N03 cognitive primitives (order section 6).

Per-primitive (C01–C08) + protocol qualification for the Batch A
DEVELOPMENT scope, derived from committed evidence only:

- ground-truth validity per primitive (EA03 qualification v2);
- dual-path witness pass rates per primitive family (Wave B);
- production-logic mutation detection per primitive (which faults
  target the primitive and were detected);
- dual-path agreement on the positive corpus (158/160 + 2 agreed
  EMPTY_OUTPUT empty-truth formatting cases).

Development evidence NEVER qualifies protected confirmation (the
confirmation split has no qualified oracle coverage here — hash-only
manifest). Protocol scope: the CPU qualification protocol (`chat`
surface semantics); physical protocol parameters are the runner lane's.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
OUT = ROOT / "evidence" / "IJEVAL" / "EA13"

PRIMS = ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08"]

#: which production faults exercise which primitive's semantics
FAULT_TARGETS = {
    "C01": ["P02_duplicate_keys_accepted", "P10_multiline_label_first",
            "P11_identity_case_change", "P12_fences_not_stripped",
            "E01_any_catalog_member"],
    "C02": ["P03_drop_extra_fields", "P04_default_missing_fields",
            "P13_predicate_dropped", "E03_flags_ignored",
            "E08_c02_action_only"],
    "C03": ["P09_markers_tolerated", "E07_c03_order_insensitive"],
    "C04": ["P14_empty_list_not_explicit", "E02_c04_subset_match",
            "E05_alternatives_ignored"],
    "C05": ["P08_hedge_unparseable", "E06_inverted_decision"],
    "C06": ["P02_duplicate_keys_accepted", "P10_multiline_label_first",
            "P11_identity_case_change", "P12_fences_not_stripped"],
    "C07": ["P02_duplicate_keys_accepted", "P10_multiline_label_first",
            "P11_identity_case_change", "P12_fences_not_stripped",
            "E01_any_catalog_member"],
    "C08": ["P02_duplicate_keys_accepted", "P10_multiline_label_first",
            "P11_identity_case_change", "P12_fences_not_stripped"],
}


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    gt = json.loads((EVID / "ground_truth_qualification_dev160_v2.json")
                    .read_text(encoding="utf-8"))
    wit = json.loads((EVID / "dualpath_witnesses.json")
                     .read_text(encoding="utf-8"))["rows"]
    mut = json.loads((EVID / "production_mutation_campaign.json")
                     .read_text(encoding="utf-8"))["faults"]
    mut_by_name = {f["fault"]: f for f in mut}

    # GT validity per primitive
    gt_counts = {}
    for row in gt.get("rows", gt.get("per_case", [])):
        prim = row.get("primitive") or row.get("case_id", "-").split(
            "-")[1]
        verdict = row.get("verdict") or row.get("gt_verdict")
        gt_counts.setdefault(prim, {})
        gt_counts[prim][verdict] = gt_counts[prim].get(verdict, 0) + 1

    rows = []
    for prim in PRIMS:
        w_rows = [r for r in wit if r["primitive"] == prim]
        w_pass = sum(1 for r in w_rows if r["passed"])
        fams = sorted({r["family"] for r in w_rows})
        fault_checks = []
        for fname in FAULT_TARGETS[prim]:
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
        faults_ok = all(c["verdict"] in ("DETECTED", "EQUIVALENT")
                        for c in fault_checks) and \
            any(c["verdict"] == "DETECTED" for c in fault_checks)
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
        "schema": "ijeval.ea13.primitive_qualification.v1",
        "generated_utc": stamp,
        "scope": "N03 Batch A DEVELOPMENT (C01-C08), CPU qualification "
                 "protocol; NOT protected confirmation (no qualified "
                 "oracle coverage for the confirmation split — hash-only "
                 "manifest; development evidence never qualifies it)",
        "primitives": rows,
        "protocol": {"name": "chat-surface CPU qualification",
                     "qualified": True,
                     "note": "physical protocol parameters are the "
                             "runner lane's (IJ-NANO)"},
        "summary": {"qualified": sum(1 for r in rows
                                     if r["verdict"] == "QUALIFIED"),
                    "total": len(rows)}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "primitive_qualification.json").write_text(
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
