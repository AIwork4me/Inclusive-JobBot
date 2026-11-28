"""Wave B-B — Batch B dual-path witness campaign + production faults.

Family-specific witness corpus over every dev family of C09-C16
(positive / positive-fenced / wrong / malformed / dup-key / empty /
per-primitive contract-boundary witnesses / software-error), executed
through the Batch B dual-path (``dualpath_b.evaluate_dual``: production
parser_b+evaluator_b vs reference interpreter_b+oracle_b). Every
witness must classify exactly as its declared expected class.

Production-logic fault campaign: Batch B faults (parser surface /
evaluator comparator) are injected into the production leg; a fault is
DETECTED when it flips any witness classification (the dual-path turns
silently-wrong scoring into NOT_EVALUABLE disagreement); EQUIVALENT
requires a dataset-specific justification; anything else is an ESCAPE.

Witness rows carry the raw response + expected class — replay contract:
re-execute ``dualpath_b.evaluate_dual(case, expectation, raw)`` on the
pinned roster.
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

from eval_assurance import dualpath_b                              # noqa: E402
from eval_assurance.dualpath import (DUPLICATE_TRIAL,             # noqa: E402
                                     MISSING_EVIDENCE, NOT_EVALUABLE)
from eval_assurance.production import evaluator_b as pev_b        # noqa: E402
from eval_assurance.production import parser_b as ppr_b           # noqa: E402

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
PIN_FULL = EVID / "pinned_full"
PRIMS = list(ppr_b.BATCH_B)


def _load():
    rows = [json.loads(l) for l in
            (PIN_FULL / "n03_cases.public.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()]
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PIN_FULL / "n03_dev_expectations.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip())}
    return rows, exps


# ---------------------------------------------------------------------------
# witness raw builders
# ---------------------------------------------------------------------------
def _positive_raw(prim: str, exp: dict) -> str:
    e = exp["expected"]
    if prim in ("C09", "C12", "C14"):
        return json.dumps(e.get("record") or e.get("slots") or
                          e.get("values"))
    if prim == "C10":
        return json.dumps(e["document"])
    if prim == "C11":
        return e["program"]
    if prim == "C13":
        return str(e["resolution"])
    if prim == "C15":
        return json.dumps({"value": e["conversion"]["value"],
                           "unit": e["conversion"]["unit"]})
    return str(e["answer"])


def _wrong_raw(prim: str, case: dict, exp: dict) -> str:
    e = copy.deepcopy(exp["expected"])
    if prim in ("C09", "C12"):
        obj = e.get("record") or e["slots"]
        for k in sorted(obj):
            if isinstance(obj[k], bool):
                obj[k] = not obj[k]                 # type-conforming flip
                break
            if isinstance(obj[k], str):
                obj[k] = obj[k] + "-wrong"
                break
            obj[k] = obj[k] + 1
            break
        return json.dumps(obj)
    if prim == "C10":
        doc = e["document"]
        for k, v in doc.items():                    # mutate array CONTENT
            if isinstance(v, list) and v and isinstance(v[0], dict):
                item = dict(v[0])
                for ik, iv in item.items():
                    if isinstance(iv, str):
                        item[ik] = iv + "-wrong"
                        break
                    elif not isinstance(iv, bool):
                        item[ik] = iv + 1
                        break
                doc[k] = [item] + list(v[1:])
                break
        return json.dumps(doc)
    if prim == "C11":
        lines = e["program"].splitlines()
        last = lines[-1].split()
        if len(last) > 2:
            lines[-1] = " ".join([last[0]] + list(reversed(last[1:])))
        else:
            lines[-1] = " ".join([last[0], last[-1] + "x"])
        return "\n".join(lines)
    if prim == "C13":
        cands = case["public_payload"]["candidates"]
        other = next((c["id"] for c in cands
                      if c["id"] != e["resolution"]), cands[0]["id"])
        return str(other)
    if prim == "C14":
        vals = e["values"]
        k = sorted(vals)[0]
        vals[k] = vals[k] + 1
        return json.dumps(vals)
    if prim == "C15":
        return json.dumps({"value": e["conversion"]["value"] + 1.0,
                           "unit": e["conversion"]["unit"]})
    return f"not {e['answer']}"                    # substring trap (E08)


def _malformed_raw(prim: str) -> str:
    if prim in ("C09", "C10", "C12", "C14", "C15"):
        return "I believe the answer involves several considerations."
    if prim == "C11":
        return "RUN dock aisle3"
    if prim == "C13":
        return "CT-1\nCT-2"
    return "yes\nmaybe"


def _dupkey_raw(prim: str, exp: dict) -> str:
    if prim == "C09":
        rec = exp["expected"]["record"]
        k = sorted(rec)[0]
        body = ", ".join(
            [f"{json.dumps(k)}: {json.dumps(rec[k])}"] * 2 +
            [f"{json.dumps(j)}: {json.dumps(v)}"
             for j, v in rec.items() if j != k])
        return "{" + body + "}"
    if prim == "C10":
        doc = exp["expected"]["document"]
        k = sorted(doc)[0]
        body = ", ".join(
            [f"{json.dumps(k)}: {json.dumps(doc[k])}"] * 2 +
            [f"{json.dumps(j)}: {json.dumps(v)}"
             for j, v in doc.items() if j != k])
        return "{" + body + "}"
    if prim == "C12":
        slots = exp["expected"]["slots"]
        k = sorted(slots)[0]
        body = ", ".join(
            [f"{json.dumps(k)}: {json.dumps(slots[k])}"] * 2 +
            [f"{json.dumps(j)}: {json.dumps(v)}"
             for j, v in slots.items() if j != k])
        return "{" + body + "}"
    if prim == "C14":
        vals = exp["expected"]["values"]
        k = sorted(vals)[0]
        body = ", ".join(
            [f"{json.dumps(k)}: {json.dumps(vals[k])}"] * 2 +
            [f"{json.dumps(j)}: {json.dumps(v)}"
             for j, v in vals.items() if j != k])
        return "{" + body + "}"
    if prim == "C15":
        return '{"value": 1, "value": 2, "unit": "USD"}'
    if prim == "C13":
        return '{"resolution": "CT-1", "resolution": "CT-2"}'
    return None                    # text-surface primitives: not applicable


def _boundary_witnesses(prim: str, exp: dict):
    """Per-primitive contract-boundary witnesses: (kind, detail, raw,
    expected-class) with CANONICAL kind names (canary kind discipline)."""
    e = copy.deepcopy(exp["expected"])
    if prim in ("C09", "C12"):
        obj = e.get("record") or e.get("slots")
        extra = dict(obj)
        extra["undeclared_extra_field"] = 1
        dropped = {k: v for k, v in obj.items()
                   if k != sorted(obj)[0]}
        return [
            ("negative-extra-field", "undeclared field added",
             json.dumps(extra), "INVALID_OUTPUT"),
            ("negative-missing-field", "declared field dropped (no null)",
             json.dumps(dropped), "INVALID_OUTPUT"),
        ]
    if prim == "C10":
        doc = e["document"]
        trunc = dict(doc)
        for k, v in doc.items():
            if isinstance(v, list) and v:
                trunc[k] = v[:-1]
                break
        return [
            ("negative-malformed", "array truncated below declared "
             "cardinality", json.dumps(trunc), "INVALID_OUTPUT"),
        ]
    if prim == "C11":
        prog_lines = e["program"].splitlines()
        lower = "\n".join(ln.lower() for ln in prog_lines)
        first_parts = prog_lines[0].split()
        missing_arg = "\n".join([" ".join(first_parts[:-1])] +
                                prog_lines[1:]) \
            if len(first_parts) > 1 else prog_lines[0] + " x"
        out = [
            ("negative-malformed", "lowercased action token", lower,
             "INVALID_OUTPUT"),
            ("negative-malformed", "missing argument (arity error)",
             missing_arg, "INVALID_OUTPUT"),
        ]
        if len(prog_lines) >= 2:      # reordering is only observable on
            #                              multi-line programs
            out.append(("negative-wrong", "program lines reordered",
                        "\n".join(reversed(prog_lines)), "INCORRECT"))
        return out
    if prim == "C13":
        return [
            ("negative-multiline", "two ids on one line", "CT-1 CT-2",
             "INVALID_OUTPUT"),
        ]
    if prim == "C14":
        vals = e["values"]
        k = sorted(vals)[0]
        svals = dict(vals)
        svals[k] = str(vals[k])
        return [
            ("negative-malformed", "string-typed number", json.dumps(svals),
             "INVALID_OUTPUT"),
        ]
    if prim == "C15":
        return [
            ("negative-malformed", "unit field missing",
             json.dumps({"value": e["conversion"]["value"]}),
             "INVALID_OUTPUT"),
            ("negative-wrong", "unit mutated with correct value",
             json.dumps({"value": e["conversion"]["value"],
                         "unit": "XXX"}), "INCORRECT"),
        ]
    return [
        ("negative-multiline", "answer spread over two lines",
         f"{e['answer']}\nsecond line", "INVALID_OUTPUT"),
    ]


def build_witnesses(cases, exps):
    by_fam = {}
    for c in cases:
        by_fam.setdefault((c["primitive"], c["family"]), []).append(c)
    rows = []
    for (prim, fam), members in sorted(by_fam.items()):
        c = members[0]                      # representative dev case
        if prim == "C11":
            # prefer a multi-line program so order-sensitivity is
            # observable (still a real dev case of the family)
            c = next((m for m in members
                      if (exps.get(m["case_id"], {}).get("expected")
                          or {}).get("op_count", 0) >= 2), c)
        exp = exps[c["case_id"]]
        wid = f"{prim}-{fam}"
        common = {"primitive": prim, "family": fam,
                  "case_id": c["case_id"]}
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
                _boundary_witnesses(prim, exp)):
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
            r = dualpath_b.evaluate_dual(
                case, exp, w["raw"],
                production_parser=_RaisingParser().parse_response)
        else:
            r = dualpath_b.evaluate_dual(case, exp, w["raw"])
        results.append({"witness_id": w["witness_id"], "kind": w["kind"],
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
# Batch B production-logic faults (parser surface / evaluator comparator)
# ---------------------------------------------------------------------------
def _fp_dup_keys(prim, payload, response):
    """Duplicate JSON keys silently accepted (last wins)."""
    import json as _j

    def merge(pairs):
        d = {}
        for k, v in pairs:
            d[k] = v
        return d
    parsed = ppr_b.parse_response(prim, payload, response)
    if parsed.parse_class != ppr_b.PARSE_MALFORMED or \
            "duplicate JSON key" not in " ".join(parsed.violations):
        return parsed
    cleaned = ppr_b._strip_fence(
        response if isinstance(response, str) else str(response)).strip()
    try:
        val = _j.loads(cleaned, object_pairs_hook=merge)
    except ValueError:
        return parsed
    if not isinstance(val, dict):
        return parsed
    return ppr_b.ParsedAnswerB(prim, val, ppr_b.PARSE_OK, (), "json")


def _fp_no_fences(prim, payload, response):
    """Fenced JSON no longer tolerated (the fault rejects what the
    pinned contract accepts)."""
    raw = response if isinstance(response, str) else str(response)
    if raw.strip().startswith("```"):
        return ppr_b.ParsedAnswerB(
            prim, None, ppr_b.PARSE_MALFORMED,
            ("markdown fence not tolerated (fault)",), "")
    return ppr_b.parse_response(prim, payload, response)


def _fp_case_insensitive_dsl(prim, payload, response):
    parsed = ppr_b.parse_response(prim, payload, response)
    if prim != "C11" or parsed.parse_class != ppr_b.PARSE_MALFORMED:
        return parsed
    raw = response if isinstance(response, str) else str(response)
    fixed = []
    for ln in [x.strip() for x in raw.splitlines() if x.strip()]:
        parts = ln.split()
        fixed.append(" ".join([parts[0].upper()] + parts[1:]))
    return ppr_b.parse_response(prim, payload, "\n".join(fixed))


def _fp_string_numbers(prim, payload, response):
    parsed = ppr_b.parse_response(prim, payload, response)
    if prim not in ("C14", "C15") or \
            parsed.parse_class != ppr_b.PARSE_MALFORMED:
        return parsed
    val = parsed.value
    if isinstance(val, dict):
        coer = {}
        for k, v in val.items():
            if isinstance(v, str):
                try:
                    coer[k] = float(v) if "." in v else int(v)
                    continue
                except ValueError:
                    pass
            coer[k] = v
        violations = tuple(v for v in parsed.violations
                            if "string-typed" not in v and
                            "value must be a number" not in v)
        if not violations:
            return ppr_b.ParsedAnswerB(prim, coer, ppr_b.PARSE_OK, (),
                                       "json")
    return parsed


def _fp_extra_fields(prim, payload, response):
    parsed = ppr_b.parse_response(prim, payload, response)
    if prim not in ("C09", "C12") or \
            parsed.parse_class != ppr_b.PARSE_MALFORMED:
        return parsed
    violations = tuple(v for v in parsed.violations
                       if "undeclared" not in v)
    if not violations:
        return ppr_b.ParsedAnswerB(prim, parsed.value, ppr_b.PARSE_OK,
                                   (), parsed.surface)
    return parsed


def _fp_arity(prim, payload, response):
    parsed = ppr_b.parse_response(prim, payload, response)
    if prim != "C11" or parsed.parse_class != ppr_b.PARSE_MALFORMED:
        return parsed
    violations = tuple(v for v in parsed.violations
                       if "arity" not in v and "argument" not in v)
    if not violations:
        return ppr_b.ParsedAnswerB(prim, parsed.value, ppr_b.PARSE_OK,
                                   (), parsed.surface)
    return parsed


class _FEBase:
    def __init__(self, prim_filter):
        self.prim_filter = prim_filter
        self.inner = pev_b.ProductionEvaluatorB()

    def evaluate(self, case, expectation, parsed):
        if case.get("primitive") not in self.prim_filter:
            return self.inner.evaluate(case, expectation, parsed)
        return self._faulty(case, expectation, parsed)


class _FESubsetMatch(_FEBase):
    """Compares only intersecting keys (dropped fields tolerated)."""

    def _faulty(self, case, expectation, parsed):
        prim = case["primitive"]
        exp = (expectation or {}).get("expected") or {}
        if parsed.parse_class != ppr_b.PARSE_OK:
            return self.inner.evaluate(case, expectation, parsed)
        truth = exp.get("record") or exp.get("slots") or \
            exp.get("values")
        if not isinstance(parsed.value, dict) or \
                not isinstance(truth, dict):
            return self.inner.evaluate(case, expectation, parsed)
        why = []
        for k in sorted(set(parsed.value) & set(truth)):
            if parsed.value[k] != truth[k]:
                why.append(f"{k}: differs")
        ok = not why and set(parsed.value) <= set(truth)
        return pev_b.EvaluationRecordB(
            pev_b.ProductionVerdictB.CORRECT if ok else
            pev_b.ProductionVerdictB.INCORRECT, reasons=tuple(why))


class _FEDocScalars(_FEBase):
    """C10: compares only top-level scalar fields (arrays ignored)."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        doc = exp.get("document") or {}
        if parsed.parse_class != ppr_b.PARSE_OK or \
                not isinstance(parsed.value, dict):
            return self.inner.evaluate(case, expectation, parsed)
        scalars = {k: v for k, v in doc.items()
                   if not isinstance(v, (list, dict))}
        got = {k: v for k, v in parsed.value.items()
               if not isinstance(v, (list, dict))}
        ok = scalars == got and \
            set(parsed.value) == set(doc)
        return pev_b.EvaluationRecordB(
            pev_b.ProductionVerdictB.CORRECT if ok else
            pev_b.ProductionVerdictB.INCORRECT)


class _FETypeLoose(_FEBase):
    """str()-coerced comparison everywhere (1 == "1" == True)."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        if parsed.parse_class != ppr_b.PARSE_OK:
            return self.inner.evaluate(case, expectation, parsed)
        truth = exp.get("record") or exp.get("slots") or \
            exp.get("values") or {}
        val = parsed.value if isinstance(parsed.value, dict) else {}
        if not truth:
            return self.inner.evaluate(case, expectation, parsed)
        why = []
        if set(val) != set(truth):
            why.append("fields differ")
        for k in sorted(set(val) & set(truth)):
            if str(val[k]) != str(truth[k]):
                why.append(f"{k}: differs")
        return pev_b.EvaluationRecordB(
            pev_b.ProductionVerdictB.CORRECT if not why else
            pev_b.ProductionVerdictB.INCORRECT, reasons=tuple(why))


class _FEAnyCandidate(_FEBase):
    """C13: any candidate id counts as CORRECT."""

    def _faulty(self, case, expectation, parsed):
        if parsed.parse_class != ppr_b.PARSE_OK:
            return self.inner.evaluate(case, expectation, parsed)
        ids = {str(c.get("id")) for c in
               (case.get("public_payload") or {}).get("candidates")
               or []}
        ok = str(parsed.value) in ids
        return pev_b.EvaluationRecordB(
            pev_b.ProductionVerdictB.CORRECT if ok else
            pev_b.ProductionVerdictB.INCORRECT)


class _FEValueTolerance(_FEBase):
    """C14/C15: +/- 1.0 tolerance instead of exact."""

    def _faulty(self, case, expectation, parsed):
        prim = case["primitive"]
        exp = (expectation or {}).get("expected") or {}
        if parsed.parse_class != ppr_b.PARSE_OK:
            return self.inner.evaluate(case, expectation, parsed)
        if prim == "C15":
            con = exp.get("conversion") or {}
            v = (parsed.value or {}).get("value")
            if isinstance(v, (int, float)) and \
                    abs(float(v) - float(con.get("value", 0))) <= 1.0 and \
                    (parsed.value or {}).get("unit") == con.get("unit"):
                return pev_b.EvaluationRecordB(
                    pev_b.ProductionVerdictB.CORRECT)
        vals = exp.get("values")
        if isinstance(vals, dict) and \
                isinstance(parsed.value, dict) and \
                set(parsed.value) == set(vals):
            if all(abs(float(parsed.value[k]) - float(vals[k])) <= 1.0
                   for k in vals):
                return pev_b.EvaluationRecordB(
                    pev_b.ProductionVerdictB.CORRECT)
        return self.inner.evaluate(case, expectation, parsed)


class _FEUnitIgnored(_FEBase):
    """C15: unit mismatch tolerated."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        con = exp.get("conversion") or {}
        v = (parsed.value or {}).get("value")
        if parsed.parse_class == ppr_b.PARSE_OK and \
                isinstance(v, (int, float)) and \
                abs(float(v) - float(con.get("value", 0))) <= 0.005 + 1e-9:
            return pev_b.EvaluationRecordB(
                pev_b.ProductionVerdictB.CORRECT)
        return self.inner.evaluate(case, expectation, parsed)


class _FESubstringAnswer(_FEBase):
    """C16: truth appearing anywhere in the answer counts CORRECT."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        if parsed.parse_class == ppr_b.PARSE_OK and \
                str(exp.get("answer", "")).lower() in \
                str(parsed.value).lower():
            return pev_b.EvaluationRecordB(
                pev_b.ProductionVerdictB.CORRECT)
        return self.inner.evaluate(case, expectation, parsed)


class _FEProgramOrder(_FEBase):
    """C11: program lines compared as a set (order ignored)."""

    def _faulty(self, case, expectation, parsed):
        exp = (expectation or {}).get("expected") or {}
        want = sorted(ln for ln in
                      str(exp.get("program") or "").splitlines() if ln)
        got = sorted(str(x) for x in (parsed.value or []))
        if parsed.parse_class == ppr_b.PARSE_OK:
            return pev_b.EvaluationRecordB(
                pev_b.ProductionVerdictB.CORRECT if got == want else
                pev_b.ProductionVerdictB.INCORRECT)
        return self.inner.evaluate(case, expectation, parsed)


PARSER_FAULTS_B = {
    "B-P01_duplicate_keys_accepted": _fp_dup_keys,
    "B-P02_fences_not_stripped": _fp_no_fences,
    "B-P03_case_insensitive_dsl": _fp_case_insensitive_dsl,
    "B-P04_string_numbers_coerced": _fp_string_numbers,
    "B-P05_extra_fields_tolerated": _fp_extra_fields,
    "B-P06_arity_not_checked": _fp_arity,
}
EVALUATOR_FAULTS_B = {
    "B-E01_subset_field_match": lambda: _FESubsetMatch(
        ("C09", "C12")),
    "B-E02_document_scalars_only": lambda: _FEDocScalars(("C10",)),
    "B-E04_type_loose_compare": lambda: _FETypeLoose(
        ("C09", "C12", "C14")),
    "B-E05_any_candidate_ok": lambda: _FEAnyCandidate(("C13",)),
    "B-E06_value_tolerance_1": lambda: _FEValueTolerance(
        ("C14", "C15")),
    "B-E07_unit_ignored": lambda: _FEUnitIgnored(("C15",)),
    "B-E08_substring_answer": lambda: _FESubstringAnswer(("C16",)),
    "B-E09_program_order_ignored": lambda: _FEProgramOrder(("C11",)),
}

#: mutants provably equivalent on the CURRENT Batch B stack, with the
#: architecture-specific justification (reported honestly; controls stay
#: active for stacks where the justification fails)
EQUIVALENT_FAULTS_B = {
    "B-E01_subset_field_match":
        "parser_b enforces exact schema key sets on C09/C12 before a "
        "PARSE_OK reaches the evaluator (missing/undeclared fields are "
        "INVALID_OUTPUT), so an evaluator-side subset comparator can "
        "never observe a key-set difference on a parse that reaches it. "
        "Control stays active for parsers without schema enforcement.",
    "B-E04_type_loose_compare":
        "parser_b enforces declared leaf types on C09/C12 and rejects "
        "string-typed numbers on C14/C15 at the parse boundary, so "
        "str()-coerced comparator equality never sees a type-mismatched "
        "OK parse. Control stays active for parsers without type "
        "enforcement.",
}


def run_fault_campaign(rows, cases_by_id, exps, clean):
    out = []
    for name, pfn in PARSER_FAULTS_B.items():
        detections = []
        for w in rows:
            if w["kind"] == "software-error":
                continue
            r = dualpath_b.evaluate_dual(
                cases_by_id[w["case_id"]], exps[w["case_id"]], w["raw"],
                production_parser=pfn)
            if r.classification != clean[w["witness_id"]]:
                detections.append({
                    "witness_id": w["witness_id"], "kind": w["kind"],
                    "clean": clean[w["witness_id"]],
                    "faulty": r.classification})
        out.append({"fault": name,
                    "verdict": "DETECTED" if detections else
                    ("EQUIVALENT" if name in EQUIVALENT_FAULTS_B
                     else "ESCAPE"),
                    "detected": bool(detections),
                    "equivalent_justification":
                        EQUIVALENT_FAULTS_B.get(name, ""),
                    "detections": detections[:10],
                    "detection_count": len(detections)})
    for name, efn in EVALUATOR_FAULTS_B.items():
        detections = []
        for w in rows:
            if w["kind"] == "software-error":
                continue
            r = dualpath_b.evaluate_dual(
                cases_by_id[w["case_id"]], exps[w["case_id"]], w["raw"],
                production_evaluator=efn())
            if r.classification != clean[w["witness_id"]]:
                detections.append({
                    "witness_id": w["witness_id"], "kind": w["kind"],
                    "clean": clean[w["witness_id"]],
                    "faulty": r.classification})
        out.append({"fault": name,
                    "verdict": "DETECTED" if detections else
                    ("EQUIVALENT" if name in EQUIVALENT_FAULTS_B
                     else "ESCAPE"),
                    "detected": bool(detections),
                    "equivalent_justification":
                        EQUIVALENT_FAULTS_B.get(name, ""),
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
        "schema": "ijeval.wavebb.dualpath_witnesses.v1",
        "scope": "N03 Batch B dev families (C09-C16) through the Batch B "
                 "dual-path (production parser_b/evaluator_b vs reference "
                 "interpreter_b/oracle_b)",
        "replay_contract": "re-execute dualpath_b.evaluate_dual(case, "
                           "expectation, raw) on the pinned full roster",
        "summary": {"total": len(clean_results),
                    "passed": sum(1 for r in clean_results if r["passed"]),
                    "failed": len(failed)},
        "rows": clean_results, "generated_utc": stamp}
    (EVID / "dualpath_witnesses_batch_b.json").write_text(
        json.dumps(wit_report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("witnesses:", wit_report["summary"])
    for f in failed[:12]:
        print("  FAIL:", f["witness_id"], "got", f["classification"],
              "want", f["expected"], "| prod", f["production"],
              "ref", f["reference"])

    clean = {r["witness_id"]: r["classification"]
             for r in clean_results}
    faults = run_fault_campaign(witnesses, cases_by_id, exps, clean)
    escapes = [f for f in faults if f["verdict"] == "ESCAPE"]
    mut_report = {
        "schema": "ijeval.wavebb.production_mutation_campaign.v1",
        "scope": "Batch B production-logic faults (parser surface + "
                 "evaluator comparator), detected via dual-path "
                 "classification flip vs the clean suite",
        "summary": {"faults": len(faults),
                    "detected": sum(1 for f in faults if f["detected"]),
                    "escapes": len(escapes)},
        "faults": faults, "generated_utc": stamp}
    (EVID / "production_mutation_campaign_batch_b.json").write_text(
        json.dumps(mut_report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("faults:", mut_report["summary"])
    for f in faults:
        print(f"  {f['fault']}: {f['verdict']} ({f['detection_count']})")
    ok = not failed and not escapes
    print("Wave B-B campaign:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
