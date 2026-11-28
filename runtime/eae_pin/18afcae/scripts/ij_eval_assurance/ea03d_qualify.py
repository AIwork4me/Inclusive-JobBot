"""EA03-D — Batch D ground-truth qualification + GT mutation battery.

Obligation A for C25-C32 over the PINNED full roster (development
split): 160/160 VALID target; handoff critical mutation targets
applied per applicable case, fail-closed on escapes.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)

from eval_assurance.reference import oracle_d  # noqa: E402

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
PIN_FULL = EVID / "pinned_full"
PRIMS = list(oracle_d.BATCH_D)


def _load():
    rows = [json.loads(l) for l in
            (PIN_FULL / "n03_cases.public.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()]
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PIN_FULL / "n03_dev_expectations.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip())}
    return rows, exps


def _mut_c25(exp):
    m = copy.deepcopy(exp)
    m["decision"] = "STOP" if exp["decision"] == "CONTINUE" else "CONTINUE"
    return [("flipped_decision", m)]


def _mut_c26(exp):
    out = []
    m = copy.deepcopy(exp)                        # clarification flip
    if exp["decision"] == "ASK":
        m["decision"] = "ACT"
        m["missing"] = []
    else:
        m["decision"] = "ASK"
        m["missing"] = ["__optional__"]
    out.append(("clarification_flip", m))
    if exp.get("missing"):
        m = copy.deepcopy(exp)                    # missing-set drift
        m["missing"] = list(exp["missing"]) + ["__extra__"]
        out.append(("missing_set_drift", m))
    return out


def _mut_c27(exp):
    out = []
    m = copy.deepcopy(exp)                        # decision flip
    m["decision"] = "PROCEED" if exp["decision"] == "ESCALATE" \
        else "ESCALATE"
    m["rules"] = [] if m["decision"] == "PROCEED" else ["R-SPURIOUS"]
    out.append(("decision_flip", m))
    if exp.get("rules"):
        m = copy.deepcopy(exp)                    # rule omission
        m["rules"] = exp["rules"][:-1]
        out.append(("rule_omission", m))
        m = copy.deepcopy(exp)                    # spurious escalation
        m["rules"] = list(exp["rules"]) + ["R-SPURIOUS"]
        out.append(("spurious_rule", m))
    return out


def _mut_c28(case, exp):
    con = exp.get("construction") or {}
    decoys = list(con.get("decoys") or [])
    out = []
    if decoys:
        m = copy.deepcopy(exp)                    # distractor capture
        m["answer"] = decoys[0]
        out.append(("distractor_capture", m))
    m = copy.deepcopy(exp)                        # hallucination
    m["answer"] = "POL-0000"
    out.append(("hallucinated_value", m))
    return out


def _mut_c29(exp):
    out = []
    m = copy.deepcopy(exp)
    if exp["class"] == "AMBIGUOUS":               # silent disambiguation
        m["class"] = "ANSWER"
        m["answer"] = (exp.get("readings") or ["RM-X"])[0]
        del m["readings"]
    else:                                          # over-flagging
        m["class"] = "AMBIGUOUS"
        m["readings"] = [exp.get("answer", "RM-X"), "RM-OTHER"]
        del m["answer"]
    out.append(("ambiguity_flip", m))
    return out


def _mut_c30(exp):
    canon = exp["canonical"]
    out = []
    m = copy.deepcopy(exp)                        # digit drift
    import re as _re
    m["canonical"] = _re.sub(r"\d", lambda c: str((int(c.group()) + 1)
                                                  % 10), canon)
    out.append(("digit_drift", m))
    parts = canon.split(":")
    if len(parts) >= 2:                           # canonical divergence
        m = copy.deepcopy(exp)
        m["canonical"] = ":".join(["wrong_op"] + parts[1:])
        out.append(("canonical_divergence", m))
    return out


def _mut_c31(exp):
    req = list(exp.get("required_citations") or [])
    out = []
    if req:
        m = copy.deepcopy(exp)                    # uncited claim
        m["required_citations"] = req[:-1]
        out.append(("uncited_claim", m))
        m = copy.deepcopy(exp)                    # phantom citation
        m["required_citations"] = req[:-1] + ["EV-PHANTOM"]
        out.append(("phantom_citation", m))
    return out


def _mut_c32(exp):
    out = []
    m = copy.deepcopy(exp)
    if exp["output_class"] == "ANSWER":           # over-abstention
        m["output_class"] = "ABSTAIN"
        m["answer"] = None
    else:                                          # confident-wrong guess
        m["output_class"] = "ANSWER"
        m["answer"] = "99:99"
    out.append(("sufficiency_flip", m))
    return out


def _mutations_for(case, exp):
    prim = case["primitive"]
    inner = exp["expected"]
    if prim == "C25":
        pairs = _mut_c25(inner)
    elif prim == "C26":
        pairs = _mut_c26(inner)
    elif prim == "C27":
        pairs = _mut_c27(inner)
    elif prim == "C28":
        pairs = _mut_c28(case, inner)
    elif prim == "C29":
        pairs = _mut_c29(inner)
    elif prim == "C30":
        pairs = _mut_c30(inner)
    elif prim == "C31":
        pairs = _mut_c31(inner)
    elif prim == "C32":
        pairs = _mut_c32(inner)
    else:
        pairs = []
    return [(name, {"case_id": case["case_id"], "expected": mutated,
                    "alternatives": []}) for name, mutated in pairs]


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows, exps = _load()
    dev = [r for r in rows if r["split"] == "development" and
           r["primitive"] in PRIMS]

    gt_rows, counts = [], {}
    for r in dev:
        res = oracle_d.validate_ground_truth(r, exps.get(r["case_id"], {}))
        counts[res.verdict.value] = counts.get(res.verdict.value, 0) + 1
        gt_rows.append({
            "case_id": r["case_id"], "primitive": r["primitive"],
            "language": r["language"], "verdict": res.verdict.value,
            "reasons": list(res.reasons),
            "verified_fields": list(res.verified_fields)})
    gt_report = {
        "schema": "ijeval.ea03d.ground_truth.v1",
        "scope": "N03 Batch D DEVELOPMENT (C25-C32) pinned full roster",
        "oracle": "eval_assurance.reference.oracle_d@1",
        "summary": {"total": len(gt_rows), "counts": counts,
                    "all_valid": counts.get("VALID", 0) == len(gt_rows)},
        "rows": gt_rows, "generated_utc": stamp}
    (EVID / "ground_truth_qualification_dev160_batch_d.json").write_text(
        json.dumps(gt_report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("GT:", counts)

    mut_rows, escapes, by_class = [], [], {}
    for r in dev:
        exp = exps.get(r["case_id"])
        if not exp:
            continue
        for name, mutated in _mutations_for(r, copy.deepcopy(exp)):
            res = oracle_d.validate_ground_truth(r, mutated)
            detected = res.verdict.value != "VALID"
            mut_rows.append({
                "case_id": r["case_id"], "primitive": r["primitive"],
                "mutation": name, "verdict": res.verdict.value,
                "detected": detected})
            by_class.setdefault(name, {"total": 0, "detected": 0})
            by_class[name]["total"] += 1
            by_class[name]["detected"] += int(detected)
            if not detected:
                escapes.append((r["case_id"], name))
    mut_report = {
        "schema": "ijeval.ea03d.gt_mutation_battery.v1",
        "scope": "handoff critical mutation targets applied to every "
                 "structurally applicable Batch D dev case",
        "summary": {"controls": len(mut_rows),
                    "detected": sum(1 for m in mut_rows if m["detected"]),
                    "escaped": len(escapes), "by_class": by_class},
        "rows": mut_rows, "generated_utc": stamp}
    (EVID / "gt_mutation_coverage_dev160_batch_d.json").write_text(
        json.dumps(mut_report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("mutations:", mut_report["summary"]["controls"], "controls,",
          len(escapes), "escapes")
    for e in escapes[:10]:
        print("  ESCAPE:", e)
    ok = gt_report["summary"]["all_valid"] and not escapes
    print("EA03-D:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
