"""Wave B closure campaign (EA04–EA08, order section 2).

Builds the family-specific Golden Witness suite from the PINNED Batch A
dev dataset, executes it through the ACTUAL integrated dual-path
(artifact capture -> trusted loader -> ProductionParser ->
ProductionEvaluator | Independent Interpreter -> Reference Oracle ->
verdict comparison), runs the EA07 production-logic mutation campaign
(P/E fault families from ``eval_assurance.faults``), the EA08
end-to-end evidence controls (duplicate rejection, exact resume,
offline replay, artifact tamper, missing-evidence distinction,
verification receipts) and emits the rule-level coverage matrix.

All outputs are deterministic given the pinned inputs (no clocks inside
result rows; generated_utc only in headers).
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance import faults                              # noqa: E402
from eval_assurance.dualpath import (DUPLICATE_TRIAL,          # noqa: E402
                                     EMPTY_OUTPUT, INVALID_OUTPUT,
                                     MISSING, MISSING_EVIDENCE,
                                     NOT_EVALUABLE,
                                     PARSER_SOFTWARE_ERROR,
                                     DualPathSession, evaluate_dual)
from eval_assurance.evidence import (issue_verification_receipt,  # noqa: E402
                                     validate_receipt_for)
from eval_assurance.production.evaluator import (              # noqa: E402
    ProductionEvaluator, ProductionVerdict)
from eval_assurance.production.parser import parse_response    # noqa: E402

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
PINNED = EVID / "pinned"

_LABEL_PRIMS = ("C01", "C06", "C07", "C08")
_LABEL_JSON_KEY = {"C01": "intent", "C06": "choice", "C07": "action",
                   "C08": "tool_id"}


def load_pinned():
    cases = [json.loads(l) for l in
             (PINNED / "n03_cases.public.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip()]
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PINNED /
                                     "n03_dev_expectations.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip())}
    dev = [c for c in cases if c.get("split") == "development"]
    return cases, exps, dev


def positive_raw(prim: str, exp: dict, style: str = "bare") -> str:
    e = exp["expected"]
    if prim == "C01":
        return e["label"] if style == "bare" else json.dumps(
            {"intent": e["label"]}, ensure_ascii=False)
    if prim == "C02":
        return json.dumps({k: e[k] for k in
                           ("action", "object", "deadline",
                            "completion_criterion", "unknown_flags")},
                          ensure_ascii=False)
    if prim == "C03":
        if "lines" in e:
            return "\n".join(e["lines"])
        if "field" in e:
            return json.dumps({e["field"]: e["value"]},
                              ensure_ascii=False)
    if prim == "C04":
        return json.dumps(e["ids"]) if style == "json" else \
            ", ".join(e["ids"])
    if prim == "C05":
        return ("TRUE" if e["decision"] else "FALSE") if style == "bare" \
            else json.dumps({"decision": e["decision"]})
    if prim == "C06":
        return e["choice"] if style == "bare" else json.dumps(
            {"choice": e["choice"]}, ensure_ascii=False)
    if prim == "C07":
        return e["action"] if style == "bare" else json.dumps(
            {"action": e["action"]}, ensure_ascii=False)
    if prim == "C08":
        return e["tool_id"] if style == "bare" else json.dumps(
            {"tool_id": e["tool_id"]}, ensure_ascii=False)
    raise ValueError(prim)


def wrong_raw(prim: str, case: dict, exp: dict) -> str:
    """A well-formed but semantically WRONG answer (derived from the
    public surface, never equal to the truth)."""
    e = exp["expected"]
    p = case.get("public_payload") or {}
    if prim == "C01":
        cat = list(p.get("intent_catalog") or {})
        other = next((k for k in cat if k != e["label"]), cat[0])
        return other
    if prim == "C02":
        return json.dumps({"action": e["action"], "object": "wrong-thing",
                           "deadline": e.get("deadline"),
                           "completion_criterion":
                               e.get("completion_criterion"),
                           "unknown_flags": e.get("unknown_flags")},
                          ensure_ascii=False)
    if prim == "C03":
        if "lines" in e:
            lines = list(e["lines"])
            if not lines:
                return "a line that matches nothing"
            if len(lines) > 1:
                return "\n".join(lines[::-1])
            return lines[0] + " extra"
        if "field" in e:
            return json.dumps({e["field"]: "wrong-value"},
                              ensure_ascii=False)
    if prim == "C04":
        return json.dumps([]) if e.get("ids") else '["SKU-NOPE"]'
    if prim == "C05":
        return "FALSE" if e["decision"] else "TRUE"
    if prim == "C06":
        cat = [o.get("id") for o in (p.get("options") or [])
               if o.get("id") and o.get("id") != e["choice"]]
        return cat[0] if cat else "PLN-NONE"
    if prim == "C07":
        cat = list(p.get("action_catalog") or {})
        other = next((k for k in cat if k != e["action"]), cat[0])
        return other
    if prim == "C08":
        tools = [t.get("id") for t in (p.get("tools") or [])
                 if t.get("id") != e["tool_id"]]
        return tools[0] if tools else "no_such_tool"
    raise ValueError(prim)


def malformed_raw(prim: str) -> str:
    if prim in _LABEL_PRIMS:
        return "I believe the answer is probably this one, thanks"
    if prim == "C02":
        return "the goal is to migrate the report by friday"
    if prim == "C03":
        return "- first bullet\n- second bullet"
    if prim == "C04":
        return "SKU-001 and SKU-002"
    if prim == "C05":
        return "probably true, I think so"
    raise ValueError(prim)


def dupkey_raw(prim: str, exp: dict) -> str:
    key = _LABEL_JSON_KEY.get(prim)
    if prim in _LABEL_PRIMS:
        val = exp["expected"].get({"C01": "label", "C06": "choice",
                                   "C07": "action",
                                   "C08": "tool_id"}[prim])
        return json.dumps({key: val, key: val})[: 0] + \
            '{"%s": "%s", "%s": "%s"}' % (key, val, key, val)
    if prim == "C02":
        e = exp["expected"]
        return ('{"action": "%s", "action": "%s", "object": "%s", '
                '"deadline": %s, "completion_criterion": %s, '
                '"unknown_flags": %s}' % (
                    e["action"], e["action"], e["object"],
                    json.dumps(e.get("deadline")),
                    json.dumps(e.get("completion_criterion")),
                    json.dumps(e.get("unknown_flags"))))
    return malformed_raw(prim)


def build_witnesses(cases, exps):
    """Family-specific witness corpus: every dev family of every
    primitive contributes positive / fenced / wrong / malformed /
    dup-key / empty rows (plus C04 order-freedom alternatives)."""
    rows = []
    by_fam = {}
    for c in cases:
        if c.get("split") != "development":
            continue
        by_fam.setdefault((c["primitive"], c["family"]), []).append(c)
    for (prim, fam), cs in sorted(by_fam.items()):
        c = cs[0]
        exp = exps.get(c["case_id"])
        if exp is None:
            continue
        empty_truth = (prim == "C03" and not exp["expected"].get("lines")
                       and "lines" in exp["expected"])
        rows.append({"witness_id": f"{prim}-{fam}-pos",
                     "case_id": c["case_id"], "primitive": prim,
                     "family": fam, "kind": "positive",
                     "raw": positive_raw(prim, exp),
                     "expected": "EMPTY_OUTPUT" if empty_truth
                     else "CORRECT"})
        if prim in ("C01", "C02", "C05", "C06", "C07", "C08") or \
                (prim == "C03" and "field" in exp["expected"]):
            fenced = "```json\n" + positive_raw(
                prim, exp, "json") + "\n```"
            rows.append({"witness_id": f"{prim}-{fam}-posf",
                         "case_id": c["case_id"], "primitive": prim,
                         "family": fam, "kind": "positive-fenced",
                         "raw": fenced,
                         "expected": "EMPTY_OUTPUT" if empty_truth
                         else "CORRECT"})
        rows.append({"witness_id": f"{prim}-{fam}-wrong",
                     "case_id": c["case_id"], "primitive": prim,
                     "family": fam, "kind": "negative-wrong",
                     "raw": wrong_raw(prim, c, exp),
                     "expected": "INCORRECT"})
        rows.append({"witness_id": f"{prim}-{fam}-mal",
                     "case_id": c["case_id"], "primitive": prim,
                     "family": fam, "kind": "negative-malformed",
                     "raw": malformed_raw(prim),
                     "expected": "INVALID_OUTPUT"})
        rows.append({"witness_id": f"{prim}-{fam}-dup",
                     "case_id": c["case_id"], "primitive": prim,
                     "family": fam, "kind": "negative-dup-key",
                     "raw": dupkey_raw(prim, exp),
                     "expected": "INVALID_OUTPUT"})
        rows.append({"witness_id": f"{prim}-{fam}-empty",
                     "case_id": c["case_id"], "primitive": prim,
                     "family": fam, "kind": "empty", "raw": "",
                     "expected": "EMPTY_OUTPUT"})
        if prim == "C04" and not exp["expected"].get("order") and \
                len(exp["expected"].get("ids") or []) > 1:
            rows.append({"witness_id": f"{prim}-{fam}-alt",
                         "case_id": c["case_id"], "primitive": prim,
                         "family": fam, "kind": "alt-positive",
                         "raw": json.dumps(
                             list(exp["expected"]["ids"])[::-1]),
                         "expected": "CORRECT"})
        # -- targeted contract-boundary witnesses -------------------------
        if prim == "C02":
            base = json.loads(positive_raw(prim, exp))
            rows.append({"witness_id": f"{prim}-{fam}-extra",
                         "case_id": c["case_id"], "primitive": prim,
                         "family": fam,
                         "kind": "negative-extra-field",
                         "raw": json.dumps({**base, "priority": "high"},
                                           ensure_ascii=False),
                         "expected": "INVALID_OUTPUT"})
            flip = dict(base["unknown_flags"])
            if flip:
                k0 = next(iter(flip))
                flip[k0] = not flip[k0]
            rows.append({"witness_id": f"{prim}-{fam}-flags",
                         "case_id": c["case_id"], "primitive": prim,
                         "family": fam, "kind": "negative-flags-flip",
                         "raw": json.dumps({**base, "unknown_flags": flip},
                                           ensure_ascii=False),
                         "expected": "INCORRECT"})
            # a missing-field witness is only meaningful on a case whose
            # truth for the omitted field is null (the P04 fault would
            # fabricate exactly that default)
            mcase = mexp = null_f = None
            for cc in cs:
                e_exp = exps.get(cc["case_id"])
                if not e_exp:
                    continue
                for f in ("completion_criterion", "deadline"):
                    if e_exp["expected"].get(f) is None:
                        mcase, mexp, null_f = cc, e_exp, f
                        break
                if mcase is not None:
                    break
            if mcase is not None:
                partial = json.loads(positive_raw(prim, mexp))
                partial.pop(null_f)
                rows.append({"witness_id": f"{prim}-{fam}-missing",
                             "case_id": mcase["case_id"],
                             "primitive": prim, "family": fam,
                             "kind": "negative-missing-field",
                             "raw": json.dumps(partial,
                                               ensure_ascii=False),
                             "expected": "INVALID_OUTPUT"})
        if prim in _LABEL_PRIMS:
            val = exp["expected"].get(
                {"C01": "label", "C06": "choice", "C07": "action",
                 "C08": "tool_id"}[prim])
            rows.append({"witness_id": f"{prim}-{fam}-multiline",
                         "case_id": c["case_id"], "primitive": prim,
                         "family": fam, "kind": "negative-multiline",
                         "raw": f"{val}\nbecause that one fits best",
                         "expected": "INVALID_OUTPUT"})
    # software-error witnesses: one per primitive (injected exception)
    for prim in sorted({r["primitive"] for r in rows}):
        base = next(r for r in rows if r["primitive"] == prim)
        rows.append({"witness_id": f"{prim}-swerr",
                     "case_id": base["case_id"], "primitive": prim,
                     "family": base["family"], "kind": "software-error",
                     "raw": base["raw"],
                     "expected": "PARSER_SOFTWARE_ERROR"})
    return rows


def run_clean_suite(rows, cases_by_id, exps, workdir):
    session = DualPathSession(workdir)
    results = []
    for w in rows:
        case = cases_by_id[w["case_id"]]
        exp = exps[w["case_id"]]
        if w["kind"] == "software-error":
            r = evaluate_dual(case, exp, w["raw"],
                              production_parser=faults.RaisingParser()
                              .parse_response)
        else:
            # every witness gets its own trial identity (same case,
            # different protocol slot): witnesses are never benchmark
            # trials and never collide with each other
            r = session.run_trial(case, exp, w["raw"],
                                  model="witness",
                                  protocol=f"suite-{w['witness_id']}")
        results.append({"witness_id": w["witness_id"], "kind": w["kind"],
                        "primitive": w["primitive"], "family": w["family"],
                        "case_id": w["case_id"], "raw": w["raw"],
                        "classification": r.classification,
                        "expected": w["expected"],
                        "passed": r.classification == w["expected"],
                        "production": r.production_verdict,
                        "reference": r.reference_verdict,
                        "quarantined": r.quarantine})
    return session, results


#: mutants that are provably equivalent on the CURRENT pinned dataset,
#: with the dataset-specific justification (order: report surviving
#: mutants and unresolved risk honestly; do not inflate coverage)
EQUIVALENT_MUTANTS = {
    "P14_empty_list_not_explicit":
        "No dev C04 case has an empty truth id-set and no case's first "
        "payload item equals a single-id truth, so the fallback guess "
        "never flips any witness verdict (checked exhaustively over the "
        "160 dev expectations). Control stays active for datasets with "
        "empty-result C04 truths.",
    "E05_alternatives_ignored":
        "Stored dev expectations carry descriptive alternatives only "
        "('ties in unspecified keys may differ' / 'no alternatives') and "
        "no winners arrays, so production CORRECT never depends on the "
        "alternatives field on this dataset. Control stays active for "
        "datasets with answer-bearing alternatives.",
}


def run_fault_campaign(rows, cases_by_id, exps, clean_results):
    clean = {r["witness_id"]: r["classification"]
             for r in clean_results}
    out = []
    for name in faults.PARSER_FAULTS + faults.EVALUATOR_FAULTS:
        p = faults.make_parser_fault(name) if name.startswith("P") \
            else parse_response
        e = faults.make_evaluator_fault(name) if name.startswith("E") \
            else ProductionEvaluator()
        detections = []
        for w in rows:
            if w["kind"] == "software-error":
                continue
            case = cases_by_id[w["case_id"]]
            r = evaluate_dual(case, exps[w["case_id"]], w["raw"],
                              production_parser=p,
                              production_evaluator=e)
            if r.classification != clean[w["witness_id"]]:
                detections.append({
                    "witness_id": w["witness_id"], "kind": w["kind"],
                    "clean": clean[w["witness_id"]],
                    "faulty": r.classification})
        verdict = ("DETECTED" if detections else
                   "EQUIVALENT" if name in EQUIVALENT_MUTANTS
                   else "ESCAPE")
        out.append({"fault": name, "verdict": verdict,
                    "detected": bool(detections),
                    "equivalent_justification":
                        EQUIVALENT_MUTANTS.get(name, ""),
                    "detections": detections[:12],
                    "detection_count": len(detections)})
    return out


def run_ea08_controls(rows, cases_by_id, exps, tmp):
    """Duplicate rejection, exact resume, replay agreement, artifact
    tamper, missing-evidence distinction, verification receipts."""
    controls = []
    subset = [w for w in rows if w["kind"] in
              ("positive", "negative-wrong", "empty")][:24]

    # -- duplicate rejection ------------------------------------------------
    s = DualPathSession(tmp / "dup")
    w = subset[0]
    case, exp = cases_by_id[w["case_id"]], exps[w["case_id"]]
    first = s.run_trial(case, exp, w["raw"], model="dup", protocol="t")
    again = s.run_trial(case, exp, w["raw"], model="dup", protocol="t")
    counts = s.analyze()["counts"]
    controls.append({
        "control": "X04_duplicate_trial_rejection",
        "result": "PASS" if again.classification == DUPLICATE_TRIAL
        and first.classification not in (DUPLICATE_TRIAL,)
        and counts.get(DUPLICATE_TRIAL, 0) == 0
        and len(s.quarantine) == 1
        and len(s.trials) == 1 else "FAIL",
        "detail": {"counts": counts,
                   "quarantined_attempts": len(s.quarantine),
                   "note": "duplicate attempts are quarantined and "
                           "never enter the trial denominator; the "
                           "original record is preserved"}})

    # -- exact resume --------------------------------------------------------
    s = DualPathSession(tmp / "resume")
    half = len(subset) // 2

    def _proto(w):
        return f"rs-{w['witness_id']}"
    for w in subset[:half]:
        s.run_trial(cases_by_id[w["case_id"]], exps[w["case_id"]],
                    w["raw"], model="resume", protocol=_proto(w))
    s.save()
    s2 = DualPathSession(tmp / "resume")
    loaded = s2.load()
    for w in subset[half:]:
        s2.run_trial(cases_by_id[w["case_id"]], exps[w["case_id"]],
                     w["raw"], model="resume", protocol=_proto(w))
    # replay the first half on the resumed session: duplicates rejected
    for w in subset[:half]:
        s2.run_trial(cases_by_id[w["case_id"]], exps[w["case_id"]],
                     w["raw"], model="resume", protocol=_proto(w))
    exact = all(s2.trials.get(
        s.trial_id(w["case_id"], "resume", _proto(w))) is not None
        for w in subset) and len(s2.trials) == len(subset)
    controls.append({
        "control": "X05_resume_exactness",
        "result": "PASS" if loaded and exact and
        len(s2.quarantine) == half else "FAIL",
        "detail": {"trials": len(s2.trials),
                   "duplicates_rejected": len(s2.quarantine)}})

    # -- replay agreement + artifact tamper + missing evidence ----------------
    s = DualPathSession(tmp / "replay")

    def _rproto(w):
        return f"rp-{w['witness_id']}"
    for w in subset:
        s.run_trial(cases_by_id[w["case_id"]], exps[w["case_id"]],
                    w["raw"], model="rp", protocol=_rproto(w))
    replays = [s.replay(cases_by_id[w["case_id"]], exps[w["case_id"]],
                        "rp", _rproto(w)) for w in subset]
    controls.append({
        "control": "X06_offline_replay_agreement",
        "result": "PASS" if all(r["matches_recorded"] for r in replays)
        else "FAIL",
        "detail": {"replayed": len(replays)}})

    tid = s.trial_id(subset[0]["case_id"], "rp", _rproto(subset[0]))
    art = pathlib.Path(s.workdir / "artifacts" /
                       f"{s.trials[tid]['artifact_sha256'][:24]}.json")
    art.write_text(art.read_text(encoding="utf-8").replace(
        '"content": "', '"content": "TAMPERED ', 1), encoding="utf-8")
    problems = s.verify()
    controls.append({
        "control": "X03_artifact_tamper_detection",
        "result": "PASS" if any("hash mismatch" in p for p in problems)
        and s.trials[tid]["classification"] == MISSING_EVIDENCE
        else "FAIL",
        "detail": problems[:2]})

    m = DualPathSession(tmp / "missing")
    r = m.run_trial(cases_by_id[subset[0]["case_id"]],
                    exps[subset[0]["case_id"]], MISSING,
                    model="m", protocol="t")
    controls.append({
        "control": "X07_missing_vs_empty_distinction",
        "result": "PASS" if r.classification == MISSING_EVIDENCE else
        "FAIL",
        "detail": {"missing": r.classification}})

    # -- verification receipts (trusted loader) --------------------------------
    s = DualPathSession(tmp / "receipt")
    w = subset[0]
    s.run_trial(cases_by_id[w["case_id"]], exps[w["case_id"]], w["raw"],
                model="rc", protocol="t")
    tid = s.trial_id(w["case_id"], "rc", "t")
    art = s.workdir / "artifacts" / \
        f"{s.trials[tid]['artifact_sha256'][:24]}.json"
    receipt = issue_verification_receipt(
        art, expected_sha256=s.trials[tid]["artifact_sha256"],
        trial_id=tid, experiment_id="waveb-ea08")
    ok_same = validate_receipt_for(receipt, trial_id=tid,
                                   experiment_id="waveb-ea08")
    try:
        validate_receipt_for(receipt, trial_id="other-trial",
                             experiment_id="waveb-ea08")
        cross = "ACCEPTED (BAD)"
    except ValueError:
        cross = "REJECTED"
    try:
        issue_verification_receipt(
            art, expected_sha256="0" * 64, trial_id=tid,
            experiment_id="waveb-ea08")
        forged = "ACCEPTED (BAD)"
    except ValueError:
        forged = "REJECTED"
    controls.append({
        "control": "X01X02_verification_receipts",
        "result": "PASS" if cross == "REJECTED" and forged == "REJECTED"
        and ok_same is receipt else "FAIL",
        "detail": {"cross_trial_reuse": cross,
                   "forged_digest": forged}})
    return controls


def main() -> int:
    cases, exps, dev = load_pinned()
    cases_by_id = {c["case_id"]: c for c in cases}
    rows = build_witnesses(cases, exps)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with tempfile.TemporaryDirectory(dir=str(ROOT / ".runtime")) as td:
        tmp = pathlib.Path(td)
        session, clean = run_clean_suite(rows, cases_by_id, exps,
                                         tmp / "clean")
        failures = [r for r in clean if not r["passed"]]
        wit = {
            "schema": "ijeval.ea03_n03.dualpath_witnesses.v1",
            "generated_utc": stamp,
            "suite": "family-specific golden witnesses through the actual "
                     "integrated dual-path (artifact->loader->production|"
                     "reference->comparison)",
            "rows": clean,
            "summary": {"total": len(clean),
                        "passed": len(clean) - len(failures),
                        "failed": len(failures)}}
        (EVID / "dualpath_witnesses.json").write_text(
            json.dumps(wit, indent=1, ensure_ascii=False),
            encoding="utf-8")

        campaign = run_fault_campaign(rows, cases_by_id, exps, clean)
        escapes = [c["fault"] for c in campaign
                   if c["verdict"] == "ESCAPE"]
        (EVID / "production_mutation_campaign.json").write_text(
            json.dumps({"schema":
                        "ijeval.ea03_n03.production_mutation_campaign.v1",
                        "generated_utc": stamp,
                        "detection_rule": "a fault is DETECTED when any "
                        "witness classification changes from its clean "
                        "expected value under the fault-injected "
                        "production leg (dual-path disagreement, class "
                        "collapse or software-error surfacing)",
                        "faults": campaign,
                        "summary": {
                            "faults": len(campaign),
                            "detected": sum(1 for c in campaign
                                            if c["verdict"] == "DETECTED"),
                            "equivalent": sum(1 for c in campaign
                                              if c["verdict"] ==
                                              "EQUIVALENT"),
                            "escapes": escapes}}, indent=1,
                       ensure_ascii=False), encoding="utf-8")

        ea08 = run_ea08_controls(rows, cases_by_id, exps, tmp)
        (EVID / "ea08_end_to_end.json").write_text(
            json.dumps({"schema": "ijeval.ea03_n03.ea08_end_to_end.v1",
                        "generated_utc": stamp, "controls": ea08,
                        "summary": {
                            "controls": len(ea08),
                            "passed": sum(1 for c in ea08
                                          if c["result"] == "PASS")}},
                       indent=1, ensure_ascii=False), encoding="utf-8")

    print("witnesses:", wit["summary"])
    det = sum(1 for c in campaign if c["verdict"] == "DETECTED")
    eqv = sum(1 for c in campaign if c["verdict"] == "EQUIVALENT")
    print(f"fault campaign: {det} detected + {eqv} equivalent (justified) "
          f"of {len(campaign)}; escapes: {escapes}")
    print("ea08:", sum(1 for c in ea08 if c["result"] == "PASS"), "/",
          len(ea08))
    return 0 if not failures and not escapes and all(
        c["result"] == "PASS" for c in ea08) else 1


if __name__ == "__main__":
    raise SystemExit(main())
