"""Wave B-D — Batch D dual-path witness campaign + production faults.

Family-specific witness corpus over every dev family of C25-C32
through the Batch D dual-path (production parser_d/evaluator_d vs
reference interpreter_d/oracle_d). Critical witness classes: the C31
citation SUPERSET (declared alternative) and the C32 ABSTAIN marker
discipline. Fault campaign: injected production faults must flip at
least one witness classification; EQUIVALENT requires justification.
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

from eval_assurance import dualpath_d                              # noqa: E402
from eval_assurance.production import evaluator_d as pev_d        # noqa: E402
from eval_assurance.production import parser_d as ppr_d           # noqa: E402

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
PIN_FULL = EVID / "pinned_full"
PRIMS = list(ppr_d.BATCH_D)


def _load():
    rows = [json.loads(l) for l in
            (PIN_FULL / "n03_cases.public.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()]
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PIN_FULL / "n03_dev_expectations.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip())}
    return rows, exps


def _positive_raw(prim: str, exp: dict) -> str:
    e = exp["expected"]
    if prim == "C25":
        return e["decision"]
    if prim == "C26":
        return json.dumps({"decision": e["decision"],
                           "missing": e.get("missing") or []})
    if prim == "C27":
        return json.dumps({"decision": e["decision"],
                           "rules": e.get("rules") or []})
    if prim == "C28":
        return str(e["answer"])
    if prim == "C29":
        if e["class"] == "AMBIGUOUS":
            return "AMBIGUOUS: " + ", ".join(e["readings"])
        return str(e["answer"])
    if prim == "C30":
        return e["canonical"]
    if prim == "C31":
        req = e.get("required_citations") or []
        return "Supported facts follow. " + " ".join(f"({r})" for r in req)
    if e["output_class"] == "ABSTAIN":
        return "ABSTAIN"
    return str(e["answer"])


def _wrong_raw(prim: str, case: dict, exp: dict) -> str:
    e = copy.deepcopy(exp["expected"])
    payload = case["public_payload"]
    if prim == "C25":
        return "STOP" if e["decision"] == "CONTINUE" else "CONTINUE"
    if prim == "C26":
        if e["decision"] == "ASK":
            return json.dumps({"decision": "ACT", "missing": []})
        return json.dumps({"decision": "ASK", "missing": ["__x__"]})
    if prim == "C27":
        if e["decision"] == "ESCALATE":
            return json.dumps({"decision": "PROCEED", "rules": []})
        return json.dumps({"decision": "ESCALATE",
                           "rules": ["R-SPURIOUS"]})
    if prim == "C28":
        con = e.get("construction") or {}
        if con.get("decoys"):
            return str(con["decoys"][0])          # distractor capture
        return "POL-0000"
    if prim == "C29":
        if e["class"] == "AMBIGUOUS":
            return str(e["readings"][0])          # silent disambiguation
        return "AMBIGUOUS: RM-X, RM-Y"            # over-flagging
    if prim == "C30":
        canon = e["canonical"]
        return canon.split(":")[0] + ":" + \
            canon.split(":")[1][:-1] + "9"        # digit drift
    if prim == "C31":
        req = e.get("required_citations") or []
        return "Facts without sources. " + \
            " ".join(f"({r})" for r in req[:-1])  # one claim uncited
    if e["output_class"] == "ABSTAIN":
        return "11:11"                            # confident-wrong guess
    return "ABSTAIN" if str(e["answer"]) != "ABSTAIN" else "00:00"


def _malformed_raw(prim: str) -> str:
    if prim in ("C25", "C32"):
        return "I think we should probably stop now"
    if prim in ("C26", "C27"):
        return "maybe escalate? not sure"
    if prim in ("C28", "C30"):
        return "well the answer depends\non several things"
    if prim == "C29":
        return "book the room somehow"
    if prim == "C31":
        # free text is a VALID C31 surface; uncited text is a SEMANTIC
        # failure (INCORRECT), not a structural one
        return "no citations here"
    return "perhaps maybe"                    # C32: hedged non-marker


def _dupkey_raw(prim: str, exp: dict):
    if prim in ("C26", "C27"):
        key = "missing" if prim == "C26" else "rules"
        e = exp["expected"]
        d = e["decision"]
        lst = e.get(key) or []
        body = (f'"decision": "{d}", "decision": "{d}", '
                f'"{key}": {json.dumps(lst)}')
        return "{" + body + "}"
    return None


def _boundary_witnesses(prim: str, case: dict, exp: dict):
    e = copy.deepcopy(exp["expected"])
    payload = case["public_payload"]
    out = []
    if prim == "C25":
        out.append(("negative-malformed", "two-line decision",
                    "STOP\njust in case", "INVALID_OUTPUT"))
    if prim == "C26":
        if e["decision"] == "ASK" and e.get("missing"):
            out.append(("positive", "ASK line-surface naming slots",
                        "ASK: " + ", ".join(e["missing"]), "CORRECT"))
        out.append(("negative-wrong", "optional-confusion (ASK without "
                    "a required gap)",
                    json.dumps({"decision": "ASK",
                                "missing": ["note"]}), "INCORRECT"))
    if prim == "C27":
        if e["decision"] == "ESCALATE" and e.get("rules"):
            out.append(("positive", "ESCALATE line-surface",
                        "ESCALATE: " + ", ".join(e["rules"]),
                        "CORRECT"))
    if prim == "C28":
        out.append(("negative-malformed", "multi-line answer",
                    f"{e['answer']}\nsecond line", "INVALID_OUTPUT"))
    if prim == "C29":
        if e["class"] == "AMBIGUOUS":
            out.append(("negative-wrong", "silent disambiguation",
                        str(e["readings"][0]), "INCORRECT"))
        else:
            out.append(("negative-wrong", "over-flagging",
                        "AMBIGUOUS: RM-X, RM-Y", "INCORRECT"))
    if prim == "C30":
        out.append(("negative-malformed", "non-canonical surface",
                    "cancel order 881", "INVALID_OUTPUT"))
    if prim == "C31":
        req = e.get("required_citations") or []
        ids = [ev["id"] for ev in payload.get("evidence") or []]
        extra = [i for i in ids if i not in req][:1]
        if extra:
            out.append(("positive", "citation SUPERSET (declared "
                        "alternative)",
                        "Facts. " + " ".join(f"({r})" for r in
                                             req + extra), "CORRECT"))
        out.append(("negative-wrong", "phantom citation",
                    "Facts. (EV-PHANTOM)", "INCORRECT"))
    if prim == "C32":
        if e["output_class"] == "ANSWER":
            out.append(("negative-wrong", "over-abstention",
                        "ABSTAIN", "INCORRECT"))
        else:
            out.append(("negative-wrong", "marker misuse (guesses "
                        "anyway)", "probably 10:00", "INCORRECT"))
    return out


def build_witnesses(cases, exps):
    by_fam = {}
    for c in cases:
        by_fam.setdefault((c["primitive"], c["family"]), []).append(c)
    rows = []
    for (prim, fam), members in sorted(by_fam.items()):
        # representative: for C26 prefer a present-but-invalid case
        # (validity-check observability)
        c = members[0]
        if prim == "C26":
            c = next((m for m in members
                      if any((m["public_payload"].get(
                          "available_information") or {}).get(s) is not
                          None for s in
                          (m["public_payload"].get("field_validity")
                           or {}))), c)
        exp = exps[c["case_id"]]
        wid = f"{prim}-{fam}"
        common = {"primitive": prim, "family": fam, "case_id":
                  c["case_id"]}
        rows.append({**common, "witness_id": f"{wid}-pos", "kind":
                     "positive", "raw": _positive_raw(prim, exp),
                     "expected": "CORRECT"})
        rows.append({**common, "witness_id": f"{wid}-posf", "kind":
                     "positive-fenced", "raw": "```json\n" +
                     _positive_raw(prim, exp) + "\n```",
                     "expected": "CORRECT"})
        rows.append({**common, "witness_id": f"{wid}-wrong", "kind":
                     "negative-wrong", "raw": _wrong_raw(prim, c, exp),
                     "expected": "INCORRECT"})
        # C31/C32: free-form text is a structurally VALID surface there
        # (semantic scoring decides) — the malformed witness is a
        # semantic-wrong one for those primitives
        mal_kind, mal_exp = (("negative-wrong", "INCORRECT")
                             if prim in ("C31", "C32")
                             else ("negative-malformed", "INVALID_OUTPUT"))
        rows.append({**common, "witness_id": f"{wid}-mal", "kind":
                     mal_kind, "raw": _malformed_raw(prim),
                     "expected": mal_exp})
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
                     "software-error", "raw": _positive_raw(prim, exp),
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
            r = dualpath_d.evaluate_dual(
                case, exp, w["raw"],
                production_parser=_RaisingParser().parse_response)
        else:
            r = dualpath_d.evaluate_dual(case, exp, w["raw"])
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
# Batch D production-logic faults
# ---------------------------------------------------------------------------
def _fp_dup_keys(prim, payload, response):
    import json as _j

    def merge(pairs):
        d = {}
        for k, v in pairs:
            d[k] = v
        return d
    parsed = ppr_d.parse_response(prim, payload, response)
    if parsed.parse_class != ppr_d.PARSE_MALFORMED or \
            "duplicate JSON key" not in " ".join(parsed.violations):
        return parsed
    cleaned = ppr_d._strip_fence(
        response if isinstance(response, str) else str(response)).strip()
    try:
        val = _j.loads(cleaned, object_pairs_hook=merge)
    except ValueError:
        return parsed
    if not isinstance(val, dict):
        return parsed
    return ppr_d.ParsedAnswerD(prim, val, ppr_d.PARSE_OK, (), "json")


def _fp_no_fences(prim, payload, response):
    raw = response if isinstance(response, str) else str(response)
    if raw.strip().startswith("```"):
        return ppr_d.ParsedAnswerD(
            prim, None, ppr_d.PARSE_MALFORMED,
            ("markdown fence not tolerated (fault)",), "")
    return ppr_d.parse_response(prim, payload, response)


def _fp_hedged_narration(prim, payload, response):
    """Substring token detection: narration containing the token is
    accepted (the exact anti-pattern of 'no substring matching')."""
    parsed = ppr_d.parse_response(prim, payload, response)
    if prim not in ("C25", "C32") or \
            parsed.parse_class != ppr_d.PARSE_MALFORMED:
        return parsed
    raw = (response if isinstance(response, str) else str(response)
           ).upper()
    if prim == "C25":
        for tok in ("STOP", "CONTINUE"):
            if tok in raw:
                return ppr_d.ParsedAnswerD(prim, tok, ppr_d.PARSE_OK,
                                           (), "text")
    else:
        if "ABSTAIN" in raw:
            return ppr_d.ParsedAnswerD(
                prim, {"class": "ABSTAIN", "answer": None},
                ppr_d.PARSE_OK, (), "text")
    return parsed


def _fp_citations_ignored(prim, payload, response):
    parsed = ppr_d.parse_response(prim, payload, response)
    if prim != "C31" or parsed.parse_class != ppr_d.PARSE_OK:
        return parsed
    val = dict(parsed.value or {})
    val["citations"] = []
    return ppr_d.ParsedAnswerD(prim, val, ppr_d.PARSE_OK, (),
                               parsed.surface)


class _FEBase:
    def __init__(self, prim_filter):
        self.prim_filter = prim_filter
        self.inner = pev_d.ProductionEvaluatorD()

    def evaluate(self, case, expectation, parsed):
        if case.get("primitive") not in self.prim_filter:
            return self.inner.evaluate(case, expectation, parsed)
        return self._faulty(case, expectation, parsed)


class _FEValidityIgnored(_FEBase):
    """C26: present-but-invalid values treated as sufficient."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        want = sorted(exp.get("missing") or [])
        got = sorted((parsed.value or {}).get("missing") or [])
        got_without_validity = [m for m in got
                                if m not in want or m == "__x__"]
        # the fault recomputes nothing: it accepts ANY missing set that
        # is a subset of the stored one (validity gap invisible)
        ok = ((parsed.value or {}).get("decision") ==
              exp.get("decision") and set(got) <= set(want))
        return pev_d.EvaluationRecordD(
            pev_d.ProductionVerdictD.CORRECT if ok else
            pev_d.ProductionVerdictD.INCORRECT)


class _FERulesIgnored(_FEBase):
    """C27: policy rules ignored — always PROCEED."""

    def _faulty(self, case, expectation, parsed):
        ok = (parsed.value or {}).get("decision") == "PROCEED" and \
            not (parsed.value or {}).get("rules")
        return pev_d.EvaluationRecordD(
            pev_d.ProductionVerdictD.CORRECT if ok else
            pev_d.ProductionVerdictD.INCORRECT)


class _FESubstringAnswer(_FEBase):
    """C28: truth appearing anywhere in the answer counts CORRECT."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        ok = str(exp.get("answer", "")) in str(parsed.value or "")
        return pev_d.EvaluationRecordD(
            pev_d.ProductionVerdictD.CORRECT if ok else
            pev_d.ProductionVerdictD.INCORRECT)


class _FEFirstId(_FEBase):
    """C29: always resolves to the first listed candidate."""

    def _faulty(self, case, expectation, parsed):
        rooms = (case.get("public_payload") or {}).get("rooms") or []
        first = (rooms[0].get("id") if rooms else None)
        if (parsed.value or {}).get("class") == "ANSWER":
            ok = parsed.value.get("answer") == first
            return pev_d.EvaluationRecordD(
                pev_d.ProductionVerdictD.CORRECT if ok else
                pev_d.ProductionVerdictD.INCORRECT)
        return pev_d.EvaluationRecordD(
            pev_d.ProductionVerdictD.INCORRECT,
            reasons=("ambiguous requests must be silently resolved "
                     "to the first candidate (fault)",))


class _FEPrefixCanonical(_FEBase):
    """C30: canonical prefix acceptance (truncated ids score)."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        want = str(exp.get("canonical") or "")
        got = str(parsed.value or "")
        ok = want.startswith(got) and got
        return pev_d.EvaluationRecordD(
            pev_d.ProductionVerdictD.CORRECT if ok else
            pev_d.ProductionVerdictD.INCORRECT)


class _FEOneCitationEnough(_FEBase):
    """C31: a single required citation suffices."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        required = set(exp.get("required_citations") or [])
        cited = set((parsed.value or {}).get("citations") or [])
        ok = len(required & cited) >= 1
        return pev_d.EvaluationRecordD(
            pev_d.ProductionVerdictD.CORRECT if ok else
            pev_d.ProductionVerdictD.INCORRECT)


class _FEGuessTolerated(_FEBase):
    """C32: any ANSWER scores CORRECT (ABSTAIN discipline dropped)."""

    def _faulty(self, case, expectation, parsed):
        ok = (parsed.value or {}).get("class") == "ANSWER"
        return pev_d.EvaluationRecordD(
            pev_d.ProductionVerdictD.CORRECT if ok else
            pev_d.ProductionVerdictD.INCORRECT)


PARSER_FAULTS_D = {
    "D-P01_duplicate_keys_accepted": _fp_dup_keys,
    "D-P02_fences_not_stripped": _fp_no_fences,
    "D-P03_hedged_narration_accepted": _fp_hedged_narration,
    "D-P04_citations_ignored": _fp_citations_ignored,
}
EVALUATOR_FAULTS_D = {
    "D-E01_validity_gap_tolerated": lambda: _FEValidityIgnored(("C26",)),
    "D-E02_rules_ignored": lambda: _FERulesIgnored(("C27",)),
    "D-E03_substring_answer": lambda: _FESubstringAnswer(("C28",)),
    "D-E04_first_id_resolution": lambda: _FEFirstId(("C29",)),
    "D-E05_prefix_canonical": lambda: _FEPrefixCanonical(("C30",)),
    "D-E06_one_citation_enough": lambda: _FEOneCitationEnough(("C31",)),
    "D-E07_guess_tolerated": lambda: _FEGuessTolerated(("C32",)),
}

EQUIVALENT_FAULTS_D = {}


def run_fault_campaign(rows, cases_by_id, exps, clean):
    out = []
    for name, pfn in PARSER_FAULTS_D.items():
        detections = []
        for w in rows:
            if w["kind"] == "software-error":
                continue
            r = dualpath_d.evaluate_dual(
                cases_by_id[w["case_id"]], exps[w["case_id"]], w["raw"],
                production_parser=pfn)
            if r.classification != clean[w["witness_id"]]:
                detections.append({
                    "witness_id": w["witness_id"], "kind": w["kind"],
                    "clean": clean[w["witness_id"]],
                    "faulty": r.classification})
        out.append({"fault": name,
                    "verdict": "DETECTED" if detections else
                    ("EQUIVALENT" if name in EQUIVALENT_FAULTS_D
                     else "ESCAPE"),
                    "detected": bool(detections),
                    "equivalent_justification":
                        EQUIVALENT_FAULTS_D.get(name, ""),
                    "detections": detections[:10],
                    "detection_count": len(detections)})
    for name, efn in EVALUATOR_FAULTS_D.items():
        detections = []
        for w in rows:
            if w["kind"] == "software-error":
                continue
            r = dualpath_d.evaluate_dual(
                cases_by_id[w["case_id"]], exps[w["case_id"]], w["raw"],
                production_evaluator=efn())
            if r.classification != clean[w["witness_id"]]:
                detections.append({
                    "witness_id": w["witness_id"], "kind": w["kind"],
                    "clean": clean[w["witness_id"]],
                    "faulty": r.classification})
        out.append({"fault": name,
                    "verdict": "DETECTED" if detections else
                    ("EQUIVALENT" if name in EQUIVALENT_FAULTS_D
                     else "ESCAPE"),
                    "detected": bool(detections),
                    "equivalent_justification":
                        EQUIVALENT_FAULTS_D.get(name, ""),
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
        "schema": "ijeval.wavebd.dualpath_witnesses.v1",
        "scope": "N03 Batch D dev families (C25-C32) through the Batch D "
                 "dual-path; citation supersets and ABSTAIN discipline "
                 "are explicit witness classes",
        "replay_contract": "re-execute dualpath_d.evaluate_dual(case, "
                           "expectation, raw) on the pinned full roster",
        "summary": {"total": len(clean_results),
                    "passed": sum(1 for r in clean_results if r["passed"]),
                    "failed": len(failed)},
        "rows": clean_results, "generated_utc": stamp}
    (EVID / "dualpath_witnesses_batch_d.json").write_text(
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
        "schema": "ijeval.wavebd.production_mutation_campaign.v1",
        "scope": "Batch D production-logic faults, detected via "
                 "dual-path classification flip vs the clean suite",
        "summary": {"faults": len(faults),
                    "detected": sum(1 for f in faults if f["detected"]),
                    "escapes": len(escapes)},
        "faults": faults, "generated_utc": stamp}
    (EVID / "production_mutation_campaign_batch_d.json").write_text(
        json.dumps(mut_report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("faults:", mut_report["summary"])
    for f in faults:
        print(f"  {f['fault']}: {f['verdict']} ({f['detection_count']})")
    ok = not failed and not escapes
    print("Wave B-D campaign:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
