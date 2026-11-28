"""EA03-B — Batch B ground-truth qualification + GT mutation battery.

Obligation A for C09-C16 over the PINNED full roster (development
split): every stored dev expectation independently validated by the
Batch B reference oracle (target: 160/160 VALID; any NOT_ESTABLISHED /
AMBIGUOUS / INVALID is reported — never silently removed).

Mutation battery: the handoff's per-primitive CRITICAL MUTATION
TARGETS are applied to EVERY structurally applicable dev case; every
mutated expectation must be flagged (non-VALID verdict). A mutation
that validates is an ESCAPE (fail-closed).
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

from eval_assurance.reference import oracle_b  # noqa: E402

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
PIN_FULL = EVID / "pinned_full"
PRIMS = list(oracle_b.BATCH_B)


def _load():
    rows = [json.loads(l) for l in
            (PIN_FULL / "n03_cases.public.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()]
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PIN_FULL / "n03_dev_expectations.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip())}
    return rows, exps


# ---------------------------------------------------------------------------
# per-primitive GT mutations (handoff "critical mutation targets")
# ---------------------------------------------------------------------------
def _mut_c09(exp):
    rec = exp["record"]
    out = []
    keys = sorted(rec)
    if keys:
        k = keys[0]                                   # type mutation
        m = copy.deepcopy(exp)
        m["record"][k] = (str(rec[k]) if not isinstance(rec[k], str)
                          else rec[k] + "x")
        out.append(("type_mutation", m))
        m = copy.deepcopy(exp)                        # dropped field
        del m["record"][k]
        out.append(("dropped_field", m))
        m = copy.deepcopy(exp)                        # extra field
        m["record"]["undeclared_extra"] = 1
        out.append(("extra_field", m))
    return out


def _mut_c10(exp):
    out = []
    m = copy.deepcopy(exp)                            # cardinality
    m["array_size"] = exp["array_size"] + 1
    out.append(("cardinality_violation", m))
    m = copy.deepcopy(exp)                            # truncation
    doc = m["document"]
    for k, v in doc.items():
        if isinstance(v, list) and v:
            m["document"] = {**doc, k: v[:-1]}
            break
    out.append(("array_truncation", m))
    m = copy.deepcopy(exp)                            # level flattening
    doc = m["document"]
    for k, v in doc.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            flat = [{**item} for item in v]
            for item in flat:
                item["flattened_" + k] = True
            m["document"] = {**doc, k: flat}
            break
    out.append(("level_flattening", m))
    return out


def _mut_c11(exp):
    prog = exp["program"]
    lines = prog.splitlines()
    out = []
    m = copy.deepcopy(exp)                            # lowercased token
    m["program"] = "\n".join(
        ln.lower() if i == 0 else ln for i, ln in enumerate(lines))
    out.append(("lowercased_token", m))
    if lines:
        parts = lines[0].split()
        m = copy.deepcopy(exp)                        # missing argument
        m["program"] = "\n".join(
            [" ".join(parts[:-1])] + lines[1:]) if len(parts) > 1 \
            else "\n".join(lines)
        out.append(("missing_argument", m))
        m = copy.deepcopy(exp)                        # arity error
        m["program"] = "\n".join(
            [lines[0] + " extraarg"] + lines[1:])
        out.append(("arity_error", m))
    m = copy.deepcopy(exp)                            # op_count drift
    m["op_count"] = exp["op_count"] + 1
    out.append(("op_count_drift", m))
    return out


def _mut_c12(exp):
    slots = exp["slots"]
    out = []
    keys = sorted(slots)
    if keys:
        k = keys[0]
        m = copy.deepcopy(exp)                        # value corrupted
        m["slots"][k] = (slots[k] + "-x") if isinstance(slots[k], str) \
            else (slots[k] + 1)
        out.append(("value_corrupted", m))
        m = copy.deepcopy(exp)                        # slot omitted (no null)
        del m["slots"][k]
        out.append(("slot_omitted_without_null", m))
    m = copy.deepcopy(exp)                            # distractor fill
    for k in keys:
        m["slots"][k] = "distractor"
        break
    out.append(("distractor_fill", m))
    return out


def _mut_c13(case, exp):
    payload = case["public_payload"]
    out = []
    m = copy.deepcopy(exp)                            # recency resolution
    same_name = [c["id"] for c in payload["candidates"]
                 if c["id"] != exp["resolution"]]
    if same_name:
        m["resolution"] = same_name[-1]
        out.append(("recency_only_resolution", m))
    m = copy.deepcopy(exp)                            # non-unique accepted
    others = [c["id"] for c in payload["candidates"]
              if c["id"] != exp["resolution"]]
    if others:
        m = copy.deepcopy(exp)
        m["resolution"] = others[0]
        out.append(("non_matching_resolution", m))
    return out


def _mut_c14(exp):
    vals = exp["values"]
    out = []
    keys = sorted(vals)
    m = copy.deepcopy(exp)                            # rounding drift
    for k in keys:
        m["values"][k] = round(float(vals[k]) + 0.1, 6)
        break
    out.append(("rounding_drift", m))
    m = copy.deepcopy(exp)                            # string-typed number
    for k in keys:
        m["values"][k] = str(vals[k])
        break
    out.append(("string_typed_number", m))
    if len(keys) >= 2:                                # field swap
        m = copy.deepcopy(exp)
        m["values"][keys[0]], m["values"][keys[1]] = \
            vals[keys[1]], vals[keys[0]]
        out.append(("field_swap", m))
    return out


def _mut_c15(exp):
    out = []
    con = exp["conversion"]
    m = copy.deepcopy(exp)                            # inverted factor
    surf = exp.get("surface") or {}
    amount = surf.get("amount", 1) or 1
    rate = surf.get("rate") or surf.get("factor") or 1
    m["conversion"]["value"] = round(rate / amount, 6) \
        if amount else con["value"]
    out.append(("inverted_factor", m))
    m = copy.deepcopy(exp)                            # double conversion
    m["conversion"]["value"] = round(con["value"] / max(rate, 1e-9), 6)
    out.append(("double_conversion", m))
    m = copy.deepcopy(exp)                            # unit mutation
    m["conversion"]["unit"] = "XXX" if con["unit"] != "XXX" else "YYY"
    out.append(("unit_mutation", m))
    return out


def _mut_c16(case, exp):
    payload = case["public_payload"]
    tool = payload.get("tool_output") or {}
    out = []
    stale = tool.get("stale_note") or {}
    if stale:
        m = copy.deepcopy(exp)                        # stale-note capture
        m["answer"] = "no" if str(exp["answer"]).lower() == "yes" else \
            str(next(iter(stale.values())))
        out.append(("stale_note_capture", m))
    m = copy.deepcopy(exp)                            # ungrounded inference
    m["answer"] = "hallucinated-answer-xyz"
    out.append(("ungrounded_inference", m))
    for k in ("order_ref", "ledger"):                 # field confusion
        if k in tool:
            m = copy.deepcopy(exp)
            m["answer"] = str(tool[k])
            out.append(("field_confusion", m))
            break
    return out


def _mutations_for(case, exp):
    prim = case["primitive"]
    inner = exp["expected"]
    if prim == "C09":
        pairs = _mut_c09(inner)
    elif prim == "C10":
        pairs = _mut_c10(inner)
    elif prim == "C11":
        pairs = _mut_c11(inner)
    elif prim == "C12":
        pairs = _mut_c12(inner)
    elif prim == "C13":
        pairs = _mut_c13(case, inner)
    elif prim == "C14":
        pairs = _mut_c14(inner)
    elif prim == "C15":
        pairs = _mut_c15(inner)
    elif prim == "C16":
        pairs = _mut_c16(case, inner)
    else:
        pairs = []
    return [(name, {"case_id": case["case_id"], "expected": mutated,
                    "alternatives": []}) for name, mutated in pairs]


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows, exps = _load()
    dev = [r for r in rows if r["split"] == "development" and
           r["primitive"] in PRIMS]

    # -- obligation A: GT validation ----------------------------------------
    gt_rows, counts = [], {}
    for r in dev:
        res = oracle_b.validate_ground_truth(r, exps.get(r["case_id"], {}))
        counts[res.verdict.value] = counts.get(res.verdict.value, 0) + 1
        gt_rows.append({
            "case_id": r["case_id"], "primitive": r["primitive"],
            "language": r["language"], "verdict": res.verdict.value,
            "reasons": list(res.reasons),
            "verified_fields": list(res.verified_fields)})
    gt_report = {
        "schema": "ijeval.ea03b.ground_truth.v1",
        "scope": "N03 Batch B DEVELOPMENT (C09-C16) pinned full roster",
        "oracle": "eval_assurance.reference.oracle_b@1",
        "summary": {"total": len(gt_rows), "counts": counts,
                    "all_valid": counts.get("VALID", 0) == len(gt_rows)},
        "rows": gt_rows, "generated_utc": stamp}
    (EVID / "ground_truth_qualification_dev160_batch_b.json").write_text(
        json.dumps(gt_report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("GT:", counts)

    # -- mutation battery ----------------------------------------------------
    mut_rows, escapes = [], []
    by_class = {}
    for r in dev:
        exp = exps.get(r["case_id"])
        if not exp:
            continue
        for name, mutated in _mutations_for(r, copy.deepcopy(exp)):
            res = oracle_b.validate_ground_truth(r, mutated)
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
        "schema": "ijeval.ea03b.gt_mutation_battery.v1",
        "scope": "handoff critical mutation targets applied to every "
                 "structurally applicable Batch B dev case",
        "summary": {"controls": len(mut_rows),
                    "detected": sum(1 for m in mut_rows if m["detected"]),
                    "escaped": len(escapes),
                    "by_class": by_class},
        "rows": mut_rows, "generated_utc": stamp}
    (EVID / "gt_mutation_coverage_dev160_batch_b.json").write_text(
        json.dumps(mut_report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("mutations:", mut_report["summary"]["controls"], "controls,",
          len(escapes), "escapes")
    for e in escapes[:10]:
        print("  ESCAPE:", e)
    ok = gt_report["summary"]["all_valid"] and not escapes
    print("EA03-B:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
