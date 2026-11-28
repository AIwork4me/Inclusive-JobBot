"""Wave B-C — Batch C dual-path witness campaign + production faults.

Family-specific witness corpus over every dev family of C17-C24,
executed through the Batch C dual-path (production parser_c/evaluator_c
vs reference interpreter_c/oracle_c). The critical witness class for
C19/C21 is the ALTERNATIVE simulated-valid plan (the pinned
plan-scoring rule: any valid plan is CORRECT; the reference plan is a
witness, never the answer key) and for C22 the 200-status-wrapped
error envelope.

Fault campaign: Batch C production faults injected into the production
leg; DETECTED = any witness classification flip; EQUIVALENT requires a
dataset/architecture-specific justification; otherwise ESCAPE.
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

from eval_assurance import dualpath_c                              # noqa: E402
from eval_assurance.production import evaluator_c as pev_c        # noqa: E402
from eval_assurance.production import parser_c as ppr_c           # noqa: E402
from eval_assurance.reference.oracle_c import simulate_plan       # noqa: E402

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
PIN_FULL = EVID / "pinned_full"
PRIMS = list(ppr_c.BATCH_C)


def _load():
    rows = [json.loads(l) for l in
            (PIN_FULL / "n03_cases.public.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()]
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PIN_FULL / "n03_dev_expectations.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip())}
    return rows, exps


# ---------------------------------------------------------------------------
# alternative-plan construction (C19/C21) — must itself simulate valid
# ---------------------------------------------------------------------------
def _alternative_plan(plan, start_state, goal, actions):
    """A genuinely different plan that still simulates valid and
    reaches the goal (append a harmless applicable action, else swap
    adjacent order-independent steps). None if no variant exists."""
    ok0, _, final0 = simulate_plan(plan, start_state, actions)
    if not ok0:
        return None
    for name, spec in actions.items():
        if name in plan:
            continue
        pre = spec.get("preconditions") or {}
        if all(final0.get(k) == v for k, v in pre.items()):
            cand = plan + [name]
            ok, _, fin = simulate_plan(cand, start_state, actions)
            if ok and all(fin.get(k) == v for k, v in (goal or {}).items()):
                return cand
    for i in range(len(plan) - 1):
        cand = list(plan)
        cand[i], cand[i + 1] = cand[i + 1], cand[i]
        if cand == plan:
            continue
        ok, _, fin = simulate_plan(cand, start_state, actions)
        if ok and all(fin.get(k) == v for k, v in (goal or {}).items()):
            return cand
    return None


def _positive_raw(prim: str, case: dict, exp: dict) -> str:
    e = exp["expected"]
    if prim == "C17":
        return json.dumps(e["truth"])
    if prim == "C18":
        return json.dumps([list(x) for x in e["edges"]])
    if prim in ("C19", "C21"):
        key = "reference_plan" if prim == "C19" else "continuation"
        return json.dumps(e[key])
    if prim == "C20":
        return json.dumps(e["holding"])
    if prim == "C22":
        return json.dumps({"is_error": e["is_error"],
                           "code": e.get("code") or ""})
    if prim == "C23":
        return json.dumps(e["arguments"])
    return json.dumps({"fallback_id": e["fallback_id"],
                       "action": e["action"],
                       "arguments": e["arguments"]})


def _wrong_raw(prim: str, case: dict, exp: dict) -> str:
    e = copy.deepcopy(exp["expected"])
    payload = case["public_payload"]
    if prim == "C17":
        e["truth"][0] = not e["truth"][0]
        return json.dumps(e["truth"])
    if prim == "C18":
        e["edges"] = [list(x) for x in e["edges"]] + [["__a__", "__b__"]]
        return json.dumps(e["edges"])
    if prim == "C19":
        plan = list(e["reference_plan"])
        if len(plan) >= 2:
            plan[0], plan[1] = plan[1], plan[0]   # precondition break
        else:
            plan = [plan[0] + "_x"]
        return json.dumps(plan)
    if prim == "C20":
        others = [b["id"] for b in payload["branches"]
                  if b["id"] not in e["holding"]]
        e["holding"] = list(e["holding"]) + (others[:1] or [])
        return json.dumps(e["holding"])
    if prim == "C21":
        return json.dumps(list(payload.get("original_plan") or
                               e["continuation"]))
    if prim == "C22":
        e["is_error"] = not e["is_error"]
        return json.dumps({"is_error": e["is_error"],
                           "code": e.get("code") or ""})
    if prim == "C23":
        k = sorted(e["arguments"])[0]
        e["arguments"][k] = (e["arguments"][k] + "-x"
                             if isinstance(e["arguments"][k], str)
                             else e["arguments"][k] + 1)
        return json.dumps(e["arguments"])
    others = [f["id"] for f in payload["fallbacks"]
              if f["id"] != e["fallback_id"]]
    if others:
        fb = next(f for f in payload["fallbacks"]
                  if f["id"] == others[0])
        return json.dumps({"fallback_id": others[0],
                           "action": fb["action"],
                           "arguments": dict(fb.get("args_template")
                                             or {})})
    return json.dumps({"fallback_id": "PRIMARY_RETRY",
                       "action": e["action"], "arguments": {}})


def _malformed_raw(prim: str) -> str:
    if prim in ("C17", "C20"):
        return "probably true, maybe false, unsure"
    if prim == "C18":
        return "edge from A to B somehow"
    if prim in ("C19", "C21"):
        return "first we take payment, then reserve"
    return "I think there might be an error, perhaps E_TIMEOUT."


def _dupkey_raw(prim: str, exp: dict):
    if prim == "C22":
        return '{"is_error": true, "is_error": false, "code": "E_X"}'
    if prim == "C23":
        args = exp["expected"]["arguments"]
        k = sorted(args)[0]
        body = ", ".join(
            [f"{json.dumps(k)}: {json.dumps(args[k])}"] * 2 +
            [f"{json.dumps(j)}: {json.dumps(v)}"
             for j, v in args.items() if j != k])
        return "{" + body + "}"
    if prim == "C24":
        return ('{"fallback_id": "FB-A", "fallback_id": "FB-B", '
                '"action": "x", "arguments": {}}')
    return None                       # list surfaces: not applicable


def _boundary_witnesses(prim: str, case: dict, exp: dict):
    """(kind, detail, raw, expected-class) with canonical kinds."""
    e = copy.deepcopy(exp["expected"])
    payload = case["public_payload"]
    out = []
    if prim == "C17":
        short = list(e["truth"][:-1]) if len(e["truth"]) > 1 \
            else e["truth"] + [True]
        out.append(("negative-wrong", "truth-vector arity mismatch",
                    json.dumps(short), "INCORRECT"))
        toks = " ".join("true" if x else "false" for x in e["truth"])
        out.append(("positive", "token-form truths (line surface)",
                    toks, "CORRECT"))
        out.append(("negative-malformed", "yes/no token surface "
                    "(outside the declared vocabulary)",
                    " ".join("yes" if x else "no" for x in e["truth"]),
                    "INVALID_OUTPUT"))
    if prim == "C18":
        lines = "\n".join(f"{a} before {b}" for a, b in e["edges"])
        out.append(("positive", "a-before-b line surface", lines,
                    "CORRECT"))
        rev = json.dumps([list(x) for x in reversed(
            [tuple(ed) for ed in e["edges"]])])
        out.append(("positive", "edge order reversed (declared "
                    "freedom)", rev, "CORRECT"))
    if prim == "C19":
        alt = _alternative_plan(
            list(e["reference_plan"]),
            payload.get("initial_state") or {},
            payload.get("goal") or {}, payload.get("actions") or {})
        if alt and alt != e["reference_plan"]:
            out.append(("positive", "ALTERNATIVE simulated-valid plan",
                        json.dumps(alt), "CORRECT"))
        out.append(("negative-wrong", "hallucinated action",
                    json.dumps(list(e["reference_plan"]) +
                               ["__undeclared__"]), "INCORRECT"))
    if prim == "C21":
        alt = _alternative_plan(
            list(e["continuation"]),
            payload.get("current_state") or {},
            payload.get("goal") or {}, payload.get("actions") or {})
        if alt and alt != e["continuation"]:
            out.append(("positive", "ALTERNATIVE valid continuation",
                        json.dumps(alt), "CORRECT"))
    if prim == "C20":
        out.append(("negative-wrong", "failed-condition branch added",
                    json.dumps(list(e["holding"]) + ["__NOPE__"]),
                    "INCORRECT"))
    if prim == "C22":
        out.append(("negative-wrong", "code confusion",
                    json.dumps({"is_error": e["is_error"],
                                "code": "E_DIFFERENT"}),
                    "INCORRECT"))
    if prim == "C23":
        dropped = {k: v for k, v in e["arguments"].items()
                   if k != sorted(e["arguments"])[0]}
        out.append(("negative-wrong", "argument dropped",
                    json.dumps(dropped), "INCORRECT"))
    if prim == "C24":
        out.append(("negative-wrong", "args_template mismatch",
                    json.dumps({"fallback_id": e["fallback_id"],
                                "action": e["action"],
                                "arguments": {**e["arguments"],
                                              "extra": 1}}),
                    "INCORRECT"))
    return out


def build_witnesses(cases, exps):
    by_fam = {}
    for c in cases:
        by_fam.setdefault((c["primitive"], c["family"]), []).append(c)
    rows = []
    for (prim, fam), members in sorted(by_fam.items()):
        c = members[0]
        exp = exps[c["case_id"]]
        wid = f"{prim}-{fam}"
        common = {"primitive": prim, "family": fam, "case_id":
                  c["case_id"]}
        rows.append({**common, "witness_id": f"{wid}-pos", "kind":
                     "positive", "raw": _positive_raw(prim, c, exp),
                     "expected": "CORRECT"})
        rows.append({**common, "witness_id": f"{wid}-posf", "kind":
                     "positive-fenced", "raw": "```json\n" +
                     _positive_raw(prim, c, exp) + "\n```",
                     "expected": "CORRECT"})
        rows.append({**common, "witness_id": f"{wid}-wrong", "kind":
                     "negative-wrong", "raw": _wrong_raw(prim, c, exp),
                     "expected": "INCORRECT"})
        rows.append({**common, "witness_id": f"{wid}-mal", "kind":
                     "negative-malformed", "raw": _malformed_raw(prim),
                     "expected": "INVALID_OUTPUT"})
        dup = _dupkey_raw(prim, exp)
        if dup is not None:
            rows.append({**common, "witness_id": f"{wid}-dup", "kind":
                         "negative-dup-key", "raw": dup,
                         "expected": "INVALID_OUTPUT"})
        rows.append({**common, "witness_id": f"{wid}-empty", "kind":
                     "empty", "raw": "", "expected": "EMPTY_OUTPUT"})
        for i, (bkind, detail, braw, bexp) in enumerate(
                _boundary_witnesses(prim, c, exp)):
            rows.append({**common, "witness_id": f"{wid}-b{i}-{detail[:12]}",
                         "kind": bkind, "detail": detail, "raw": braw,
                         "expected": bexp})
        rows.append({**common, "witness_id": f"{wid}-swerr", "kind":
                     "software-error", "raw": _positive_raw(prim, c, exp),
                     "expected": "EVALUATOR_SOFTWARE_ERROR"})
    return rows


class _RaisingParser:
    def parse_response(self, prim, payload, response):
        raise RuntimeError("injected production software fault")


def run_clean_suite(rows, cases_by_id, exps):
    results = []
    for w in rows:
        case = cases_by_id[w["case_id"]]
        exp = exps[w["case_id"]]
        if w["kind"] == "software-error":
            r = dualpath_c.evaluate_dual(
                case, exp, w["raw"],
                production_parser=_RaisingParser().parse_response)
        else:
            r = dualpath_c.evaluate_dual(case, exp, w["raw"])
        results.append({"witness_id": w["witness_id"], "kind": w["kind"],
                        "detail": w.get("detail", ""),
                        "primitive": w["primitive"], "family": w["family"],
                        "case_id": w["case_id"], "raw": w["raw"],
                        "classification": r.classification,
                        "expected": w["expected"],
                        "passed": r.classification == w["expected"],
                        "production": r.production_verdict,
                        "reference": r.reference_verdict,
                        "quarantined": r.quarantine})
    return results


# ---------------------------------------------------------------------------
# Batch C production-logic faults
# ---------------------------------------------------------------------------
def _fp_dup_keys(prim, payload, response):
    import json as _j

    def merge(pairs):
        d = {}
        for k, v in pairs:
            d[k] = v
        return d
    parsed = ppr_c.parse_response(prim, payload, response)
    if parsed.parse_class != ppr_c.PARSE_MALFORMED or \
            "duplicate JSON key" not in " ".join(parsed.violations):
        return parsed
    cleaned = ppr_c._strip_fence(
        response if isinstance(response, str) else str(response)).strip()
    try:
        val = _j.loads(cleaned, object_pairs_hook=merge)
    except ValueError:
        return parsed
    if not isinstance(val, dict):
        return parsed
    return ppr_c.ParsedAnswerC(prim, val, ppr_c.PARSE_OK, (), "json")


def _fp_no_fences(prim, payload, response):
    raw = response if isinstance(response, str) else str(response)
    if raw.strip().startswith("```"):
        return ppr_c.ParsedAnswerC(
            prim, None, ppr_c.PARSE_MALFORMED,
            ("markdown fence not tolerated (fault)",), "")
    return ppr_c.parse_response(prim, payload, response)


def _fp_truth_tokens_loose(prim, payload, response):
    parsed = ppr_c.parse_response(prim, payload, response)
    if prim != "C17" or parsed.parse_class != ppr_c.PARSE_MALFORMED:
        return parsed
    toks = [t for t in str(response).replace(",", " ").split() if t]
    lut = {"yes": True, "no": False, "true": True, "false": False,
           "1": True, "0": False}
    if toks and all(t.lower() in lut for t in toks):
        return ppr_c.ParsedAnswerC(
            prim, [lut[t.lower()] for t in toks], ppr_c.PARSE_OK, (),
            "text")
    return parsed


def _fp_edges_lineform_rejected(prim, payload, response):
    """Fault: the 'a before b' line surface is no longer accepted."""
    raw = response if isinstance(response, str) else str(response)
    if prim == "C18" and not raw.strip().startswith("["):
        return ppr_c.ParsedAnswerC(
            prim, None, ppr_c.PARSE_MALFORMED,
            ("line-form edges rejected (fault)",), "")
    return ppr_c.parse_response(prim, payload, response)


def _fp_plan_lines_rejected(prim, payload, response):
    raw = response if isinstance(response, str) else str(response)
    if prim in ("C19", "C21") and not raw.strip().startswith("["):
        return ppr_c.ParsedAnswerC(
            prim, None, ppr_c.PARSE_MALFORMED,
            ("line-form plans rejected (fault)",), "")
    return ppr_c.parse_response(prim, payload, response)


class _FEBase:
    def __init__(self, prim_filter):
        self.prim_filter = prim_filter
        self.inner = pev_c.ProductionEvaluatorC()

    def evaluate(self, case, expectation, parsed):
        if case.get("primitive") not in self.prim_filter:
            return self.inner.evaluate(case, expectation, parsed)
        return self._faulty(case, expectation, parsed)


class _FETruthPrefix(_FEBase):
    """C17: compares only the first len(stored) entries (arity
    shortcuts)."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        want = list(exp.get("truth") or [])
        got = list(parsed.value or [])[:len(want)]
        ok = got == want
        return pev_c.EvaluationRecordC(
            pev_c.ProductionVerdictC.CORRECT if ok else
            pev_c.ProductionVerdictC.INCORRECT)


class _FEEdgesOrderStrict(_FEBase):
    """C18: requires the declared edge ORDER (order is free)."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        want = [tuple(e) for e in (exp.get("edges") or [])]
        got = [tuple(e) for e in (parsed.value or [])]
        ok = got == want
        return pev_c.EvaluationRecordC(
            pev_c.ProductionVerdictC.CORRECT if ok else
            pev_c.ProductionVerdictC.INCORRECT)


class _FEPlanStringMatch(_FEBase):
    """C19/C21: scores by string equality with the reference plan
    instead of simulating (the exact defect the plan-scoring rule
    exists to prevent)."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        want = list(exp.get("reference_plan") or
                    exp.get("continuation") or [])
        got = [str(x) for x in (parsed.value or [])]
        ok = got == want
        return pev_c.EvaluationRecordC(
            pev_c.ProductionVerdictC.CORRECT if ok else
            pev_c.ProductionVerdictC.INCORRECT)


class _FEHoldingSuperset(_FEBase):
    """C20: accepts supersets of the holding set."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        want = set(exp.get("holding") or [])
        got = {str(x) for x in (parsed.value or [])}
        ok = want and want <= got
        return pev_c.EvaluationRecordC(
            pev_c.ProductionVerdictC.CORRECT if ok else
            pev_c.ProductionVerdictC.INCORRECT)


class _FEStatusClearsError(_FEBase):
    """C22: an HTTP 200 wrapper clears the body error (the exact
    anti-rule of the primitive)."""

    def _faulty(self, case, expectation, parsed):
        resp = (case.get("public_payload") or {}).get("response") or {}
        if resp.get("http_status") == 200:
            return pev_c.EvaluationRecordC(
                pev_c.ProductionVerdictC.CORRECT
                if parsed.value.get("is_error") is False and
                (parsed.value.get("code") or "") == "" else
                pev_c.ProductionVerdictC.INCORRECT)
        return self.inner.evaluate(case, expectation, parsed)


class _FEArgsSubset(_FEBase):
    """C23: compares only intersecting keys."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        want = exp.get("arguments") or {}
        got = parsed.value if isinstance(parsed.value, dict) else {}
        why = [k for k in set(got) & set(want) if got[k] != want[k]]
        ok = not why and set(got) <= set(want)
        return pev_c.EvaluationRecordC(
            pev_c.ProductionVerdictC.CORRECT if ok else
            pev_c.ProductionVerdictC.INCORRECT)


PARSER_FAULTS_C = {
    "C-P01_duplicate_keys_accepted": _fp_dup_keys,
    "C-P02_fences_not_stripped": _fp_no_fences,
    "C-P03_truth_tokens_loose": _fp_truth_tokens_loose,
    "C-P04_edges_lineform_rejected": _fp_edges_lineform_rejected,
    "C-P05_plan_lines_rejected": _fp_plan_lines_rejected,
}
EVALUATOR_FAULTS_C = {
    "C-E01_truth_prefix_match": lambda: _FETruthPrefix(("C17",)),
    "C-E02_edges_order_strict": lambda: _FEEdgesOrderStrict(("C18",)),
    "C-E03_plan_string_match": lambda: _FEPlanStringMatch(("C19", "C21")),
    "C-E04_holding_superset": lambda: _FEHoldingSuperset(("C20",)),
    "C-E05_status_clears_error": lambda: _FEStatusClearsError(("C22",)),
    "C-E06_args_subset_match": lambda: _FEArgsSubset(("C23",)),
}

EQUIVALENT_FAULTS_C = {}


def run_fault_campaign(rows, cases_by_id, exps, clean):
    out = []
    for name, pfn in PARSER_FAULTS_C.items():
        detections = []
        for w in rows:
            if w["kind"] == "software-error":
                continue
            r = dualpath_c.evaluate_dual(
                cases_by_id[w["case_id"]], exps[w["case_id"]], w["raw"],
                production_parser=pfn)
            if r.classification != clean[w["witness_id"]]:
                detections.append({
                    "witness_id": w["witness_id"], "kind": w["kind"],
                    "clean": clean[w["witness_id"]],
                    "faulty": r.classification})
        out.append({"fault": name,
                    "verdict": "DETECTED" if detections else
                    ("EQUIVALENT" if name in EQUIVALENT_FAULTS_C
                     else "ESCAPE"),
                    "detected": bool(detections),
                    "equivalent_justification":
                        EQUIVALENT_FAULTS_C.get(name, ""),
                    "detections": detections[:10],
                    "detection_count": len(detections)})
    for name, efn in EVALUATOR_FAULTS_C.items():
        detections = []
        for w in rows:
            if w["kind"] == "software-error":
                continue
            r = dualpath_c.evaluate_dual(
                cases_by_id[w["case_id"]], exps[w["case_id"]], w["raw"],
                production_evaluator=efn())
            if r.classification != clean[w["witness_id"]]:
                detections.append({
                    "witness_id": w["witness_id"], "kind": w["kind"],
                    "clean": clean[w["witness_id"]],
                    "faulty": r.classification})
        out.append({"fault": name,
                    "verdict": "DETECTED" if detections else
                    ("EQUIVALENT" if name in EQUIVALENT_FAULTS_C
                     else "ESCAPE"),
                    "detected": bool(detections),
                    "equivalent_justification":
                        EQUIVALENT_FAULTS_C.get(name, ""),
                    "detections": detections[:10],
                    "detection_count": len(detections)})
    return out


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows, exps = _load()
    dev = [r for r in rows if r["split"] == "development" and
           r["primitive"] in PRIMS]
    cases_by_id = {r["case_id"]: r for r in rows}

    witnesses = build_witnesses(dev, exps)
    clean_results = run_clean_suite(witnesses, cases_by_id, exps)
    failed = [r for r in clean_results if not r["passed"]]
    wit_report = {
        "schema": "ijeval.wavebc.dualpath_witnesses.v1",
        "scope": "N03 Batch C dev families (C17-C24) through the Batch C "
                 "dual-path; alternative simulated-valid plans are "
                 "positive witnesses (plan-scoring rule)",
        "replay_contract": "re-execute dualpath_c.evaluate_dual(case, "
                           "expectation, raw) on the pinned full roster",
        "summary": {"total": len(clean_results),
                    "passed": sum(1 for r in clean_results if r["passed"]),
                    "failed": len(failed)},
        "rows": clean_results, "generated_utc": stamp}
    (EVID / "dualpath_witnesses_batch_c.json").write_text(
        json.dumps(wit_report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("witnesses:", wit_report["summary"])
    for f in failed[:12]:
        print("  FAIL:", f["witness_id"], f.get("detail", ""),
              "got", f["classification"], "want", f["expected"],
              "| prod", f["production"], "ref", f["reference"])

    clean = {r["witness_id"]: r["classification"] for r in clean_results}
    faults = run_fault_campaign(witnesses, cases_by_id, exps, clean)
    escapes = [f for f in faults if f["verdict"] == "ESCAPE"]
    mut_report = {
        "schema": "ijeval.wavebc.production_mutation_campaign.v1",
        "scope": "Batch C production-logic faults, detected via "
                 "dual-path classification flip vs the clean suite",
        "summary": {"faults": len(faults),
                    "detected": sum(1 for f in faults if f["detected"]),
                    "escapes": len(escapes)},
        "faults": faults, "generated_utc": stamp}
    (EVID / "production_mutation_campaign_batch_c.json").write_text(
        json.dumps(mut_report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("faults:", mut_report["summary"])
    for f in faults:
        print(f"  {f['fault']}: {f['verdict']} ({f['detection_count']})")
    ok = not failed and not escapes
    print("Wave B-C campaign:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
