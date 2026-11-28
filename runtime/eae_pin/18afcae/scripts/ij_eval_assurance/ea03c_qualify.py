"""EA03-C — Batch C ground-truth qualification + GT mutation battery.

Obligation A for C17-C24 over the PINNED full roster (development
split): every stored dev expectation independently validated by the
Batch C reference oracle (target 160/160 VALID).

Mutation battery: the handoff's per-primitive CRITICAL MUTATION
TARGETS applied to EVERY structurally applicable dev case; every
mutated expectation must be flagged (non-VALID). Fail-closed on any
escape.
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

from eval_assurance.reference import oracle_c  # noqa: E402

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
PIN_FULL = EVID / "pinned_full"
PRIMS = list(oracle_c.BATCH_C)


def _load():
    rows = [json.loads(l) for l in
            (PIN_FULL / "n03_cases.public.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()]
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PIN_FULL / "n03_dev_expectations.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip())}
    return rows, exps


def _mut_c17(exp):
    truth = exp["truth"]
    out = []
    if truth:
        m = copy.deepcopy(exp)                       # flipped truth
        m["truth"][0] = not truth[0]
        out.append(("initial_state_judgment_flip", m))
        m = copy.deepcopy(exp)                       # dropped verdict
        m["truth"] = truth[:-1]
        out.append(("dropped_predicate_verdict", m))
    return out


def _mut_c18(exp):
    edges = [list(e) for e in exp["edges"]]
    out = []
    m = copy.deepcopy(exp)                           # spurious edge
    m["edges"] = edges + [["__none_a__", "__none_b__"]]
    out.append(("spurious_edge", m))
    if edges:
        m = copy.deepcopy(exp)                       # missing edge
        m["edges"] = edges[:-1]
        out.append(("missing_edge", m))
    return out


def _drop_last_goal_relevant(plan, goal, actions):
    """Index of the last action whose effects touch a goal key, or
    None (dropping a trailing non-goal action would be a VACUOUS
    goal-miss mutation — the plan still reaches the goal)."""
    for i in range(len(plan) - 1, -1, -1):
        eff = (actions.get(plan[i]) or {}).get("effects") or {}
        if set(eff) & set(goal or {}):
            return i
    return None


def _mut_c19(payload, exp):
    plan = list(exp["reference_plan"])
    actions = payload.get("actions") or {}
    goal = payload.get("goal") or {}
    out = []
    if len(plan) >= 2:
        m = copy.deepcopy(exp)                       # precondition viol.
        m["reference_plan"] = [plan[1], plan[0]] + plan[2:]
        out.append(("precondition_violation", m))
    gi = _drop_last_goal_relevant(plan, goal, actions)
    if gi is not None and gi > 0:
        m = copy.deepcopy(exp)                       # goal miss (drop
            #                                    a goal-relevant step)
        m["reference_plan"] = plan[:gi] + plan[gi + 1:]
        out.append(("goal_miss", m))
    m = copy.deepcopy(exp)                           # hallucinated action
    m["reference_plan"] = plan + ["__undeclared_action__"]
    out.append(("hallucinated_action", m))
    return out


def _mut_c20(case, exp):
    payload = case["public_payload"]
    holding = list(exp["holding"])
    out = []
    failed = [b["id"] for b in payload["branches"]
              if b["id"] not in holding]
    if failed:
        m = copy.deepcopy(exp)                       # failed-condition
            #                                    branch selected
        m["holding"] = holding + [failed[0]]
        out.append(("failed_condition_branch", m))
    # both exclusive branches: pick a branch contradicting a holding
    # one on the same slot
    by_slot = {}
    for b in payload["branches"]:
        by_slot.setdefault(b["condition"]["slot"], []).append(b)
    for slot, bs in by_slot.items():
        if len(bs) >= 2:
            extra = [b["id"] for b in bs if b["id"] not in holding]
            if extra:
                m = copy.deepcopy(exp)
                m["holding"] = holding + [extra[0]]
                out.append(("both_exclusive_branches", m))
                break
    return out


def _mut_c21(case, exp):
    payload = case["public_payload"]
    cont = list(exp["continuation"])
    actions = payload.get("actions") or {}
    goal = payload.get("goal") or {}
    out = []
    m = copy.deepcopy(exp)                           # stale plan persist
    m["continuation"] = list(payload.get("original_plan") or
                             cont) + cont
    out.append(("stale_plan_persistence", m))
    m = copy.deepcopy(exp)                           # prefix amnesia
    m["continuation"] = list(payload.get("executed_prefix") or []) + cont
    out.append(("prefix_amnesia", m))
    gi = _drop_last_goal_relevant(cont, goal, actions)
    if gi is not None and gi > 0:
        m = copy.deepcopy(exp)                       # goal drop
        m["continuation"] = cont[:gi] + cont[gi + 1:]
        out.append(("goal_drop", m))
    return out


def _mut_c22(exp):
    out = []
    m = copy.deepcopy(exp)                           # masked error
    m["is_error"] = not exp["is_error"]
    out.append(("masked_or_false_error", m))
    if exp.get("code"):
        m = copy.deepcopy(exp)                       # code confusion
        m["code"] = "E_DIFFERENT" if exp["code"] != "E_DIFFERENT" \
            else "E_OTHER"
        out.append(("code_confusion", m))
    return out


def _mut_c23(exp):
    args = dict(exp["arguments"])
    keys = sorted(args)
    out = []
    m = copy.deepcopy(exp)                           # no-op retry (one
    #                                              value perturbed)
    if keys:
        k = keys[0]
        m["arguments"] = {**args, k: (args[k] + "-x"
                                      if isinstance(args[k], str)
                                      else args[k] + 1)}
        out.append(("noop_or_value_corrupted", m))
    if len(keys) >= 2:                               # over-correction
        m = copy.deepcopy(exp)
        m["arguments"] = {**args, keys[1]: "over-corrected"}
        out.append(("over_correction", m))
    return out


def _mut_c24(case, exp):
    payload = case["public_payload"]
    out = []
    others = [f["id"] for f in payload["fallbacks"]
              if f["id"] != exp["fallback_id"]]
    if others:
        m = copy.deepcopy(exp)                       # condition-ignoring
            #                                    fallback
        m["fallback_id"] = others[0]
        fb = next(f for f in payload["fallbacks"]
                  if f["id"] == others[0])
        m["action"] = fb["action"]
        m["arguments"] = dict(fb.get("args_template") or {})
        out.append(("condition_ignoring_fallback", m))
    m = copy.deepcopy(exp)                           # arg mismatch
    m["arguments"] = {**exp["arguments"], "extra_arg": 1}
    out.append(("argument_mismatch", m))
    m = copy.deepcopy(exp)                           # primary retry
    m["fallback_id"] = "PRIMARY_RETRY"
    out.append(("primary_retry", m))
    return out


def _mutations_for(case, exp):
    prim = case["primitive"]
    inner = exp["expected"]
    if prim == "C17":
        pairs = _mut_c17(inner)
    elif prim == "C18":
        pairs = _mut_c18(inner)
    elif prim == "C19":
        pairs = _mut_c19(case["public_payload"], inner)
    elif prim == "C20":
        pairs = _mut_c20(case, inner)
    elif prim == "C21":
        pairs = _mut_c21(case, inner)
    elif prim == "C22":
        pairs = _mut_c22(inner)
    elif prim == "C23":
        pairs = _mut_c23(inner)
    elif prim == "C24":
        pairs = _mut_c24(case, inner)
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
        res = oracle_c.validate_ground_truth(r, exps.get(r["case_id"], {}))
        counts[res.verdict.value] = counts.get(res.verdict.value, 0) + 1
        gt_rows.append({
            "case_id": r["case_id"], "primitive": r["primitive"],
            "language": r["language"], "verdict": res.verdict.value,
            "reasons": list(res.reasons),
            "verified_fields": list(res.verified_fields)})
    gt_report = {
        "schema": "ijeval.ea03c.ground_truth.v1",
        "scope": "N03 Batch C DEVELOPMENT (C17-C24) pinned full roster",
        "oracle": "eval_assurance.reference.oracle_c@1",
        "summary": {"total": len(gt_rows), "counts": counts,
                    "all_valid": counts.get("VALID", 0) == len(gt_rows)},
        "rows": gt_rows, "generated_utc": stamp}
    (EVID / "ground_truth_qualification_dev160_batch_c.json").write_text(
        json.dumps(gt_report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("GT:", counts)

    mut_rows, escapes, by_class = [], [], {}
    for r in dev:
        exp = exps.get(r["case_id"])
        if not exp:
            continue
        for name, mutated in _mutations_for(r, copy.deepcopy(exp)):
            res = oracle_c.validate_ground_truth(r, mutated)
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
        "schema": "ijeval.ea03c.gt_mutation_battery.v1",
        "scope": "handoff critical mutation targets applied to every "
                 "structurally applicable Batch C dev case",
        "summary": {"controls": len(mut_rows),
                    "detected": sum(1 for m in mut_rows if m["detected"]),
                    "escaped": len(escapes), "by_class": by_class},
        "rows": mut_rows, "generated_utc": stamp}
    (EVID / "gt_mutation_coverage_dev160_batch_c.json").write_text(
        json.dumps(mut_report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("mutations:", mut_report["summary"]["controls"], "controls,",
          len(escapes), "escapes")
    for e in escapes[:10]:
        print("  ESCAPE:", e)
    ok = gt_report["summary"]["all_valid"] and not escapes
    print("EA03-C:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
