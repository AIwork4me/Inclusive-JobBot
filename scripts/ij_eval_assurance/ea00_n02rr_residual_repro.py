#!/usr/bin/env python3
"""EA00 §2.2 — N02RR residual-risk reproduction (mission IJ-EVAL-ASSURANCE-1.0).

Investigated risk (mission order section 2.2): in
``scripts/ij_nano/n02rr_replay_lib.py`` the replay parse/score step catches
every exception and records ``replay_error``, but then emits

    "semantic_correct": (scored["semantic_correct"] if scored else False)

so a replay EXCEPTION is coerced to an ordinary-looking semantic FAIL record.
``classify_failure``/``change_classification`` label such rows REPLAY_ERROR /
EVIDENCE_INSUFFICIENT, but the production analyzer
(``scripts/ij_nano/n02rr_analyze.py``) computes ``r["sem"] = bool(verdict)``
with NO eligibility filter, so those rows would enter semantic rates, paired
tests and the headline PASS count directly.

Second risk: a P7S trial whose stage-2 payload contradicts its stage-1
selection is classified EVIDENCE_INCONSISTENT_STAGE2_TOOL, yet its scored
verdict can be True — the analyzer would count it as a semantic PASS.

This script REPRODUCES both behaviors with the production components
(ReplayEngine + n02rr_analyze.load_rows/agg) on CPU, using the sealed N02RR
corpus plus two clearly-marked synthetic rows. It does not modify any sealed
evidence file and never calls n02rr_analyze.main() (which would rewrite the
corrected protocol matrix); it patches the module-level REC path to a
temporary copy instead.

Outputs: evidence/IJEVAL/EA00/n02rr_residual_risk_reproduction.json
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ij_nano"))
sys.path.insert(0, str(ROOT / "scripts" / "ij_eval_assurance"))

import n02rr_replay_lib as rl          # noqa: E402
import n02rr_qualification_lib as qlib  # noqa: E402
import n02rr_analyze                    # noqa: E402

rl.bootstrap_paths()

SEALED = ROOT / "evidence" / "IJNANO" / "N02RR" / "trial_reconciliation.jsonl"
OUT = (ROOT / "evidence" / "IJEVAL" / "EA00"
       / "n02rr_residual_risk_reproduction.json")
TMP_CONTROLS = ROOT / "evidence" / "IJEVAL" / "EA00" / "_controls_tmp"


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def replay_record_to_corrected(rec: dict) -> dict:
    """Map a ReplayEngine output into the reconciliation ``corrected`` block,
    mirroring n02rr_rescore.py lines 213-226 (the production writer)."""
    def tel_summary(tel):
        if not isinstance(tel, dict):
            return {"invalid": repr(tel)[:80]}
        usage = tel.get("usage")
        return {"latency_s": tel.get("latency_s"),
                "usage": usage if isinstance(usage, dict) else repr(usage)[:80],
                "finish_reason": tel.get("finish_reason"),
                "truncated": tel.get("truncated"),
                "content_chars": len(tel["content"])
                if isinstance(tel.get("content"), str) else None}
    return {
        "verdict": rec["semantic_correct"],
        "parser_output": rec["parser"]["payload"],
        "structural_ok": rec["parser"]["structural_ok"],
        "failure_reasons": rec["reasons"],
        "telemetry": tel_summary(rec["telemetry"]),
        "telemetry_totals": {k: v for k, v
                             in rec["telemetry_totals"].items()
                             if k != "per_stage"},
        "failure_class": rl.classify_failure(rec),
        "p7s": rec.get("p7s_reconstruction"),
        "stage1_selection_wrong_tool": rec.get("stage1_selection_wrong_tool"),
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    results: dict = {
        "mission": "IJ-EVAL-ASSURANCE-1.0",
        "task": "EA00 section 2.2 N02RR residual-risk reproduction",
        "inputs": {
            "sealed_reconciliation":
                "evidence/IJNANO/N02RR/trial_reconciliation.jsonl",
            "sealed_reconciliation_sha256": _sha(SEALED),
        },
        "reproductions": {},
    }

    # ----------------------------------------------------------------------
    # R1 — replay exception coerced to semantic FAIL (production engine)
    # ----------------------------------------------------------------------
    tmp = TMP_CONTROLS
    if tmp.exists():
        shutil.rmtree(tmp)
    battery = qlib.ControlBattery(qlib.make_controller(), tmp)
    controls = {c["name"]: c for c in battery.controls()}

    good = controls["correct_chat_json"]
    # baseline: known-correct witness scores True through the green engine
    base_rec = battery.engine.replay(good["row"])
    base_fc = rl.classify_failure(base_rec)

    # force the EVALUATOR to raise (software failure, not model failure)
    real_score = battery.engine.scorer.score
    def _raise(task, payload):
        raise RuntimeError("synthetic evaluator crash (EA00 R1)")
    battery.engine.scorer.score = _raise
    try:
        crash_rec = battery.engine.replay(good["row"])
    finally:
        battery.engine.scorer.score = real_score
    crash_fc = rl.classify_failure(crash_rec)
    crash_cc = rl.change_classification(True, crash_rec["semantic_correct"],
                                        {"parser": {"structural_ok": True},
                                         "telemetry": {}}, crash_rec)

    results["reproductions"]["R1_replay_exception_coercion"] = {
        "witness": "correct_chat_json (known-correct control)",
        "baseline": {"semantic_correct": base_rec["semantic_correct"],
                     "failure_class": base_fc},
        "with_evaluator_crash": {
            "semantic_correct": crash_rec["semantic_correct"],
            "reasons": crash_rec["reasons"],
            "replay_error": crash_rec["replay_error"],
            "failure_class": crash_fc,
            "change_classification": crash_cc,
        },
        "finding": (
            "A software exception in the evaluator is coerced to "
            "semantic_correct=False (n02rr_replay_lib.py:326-330). The "
            "classification layers label it REPLAY_ERROR/EVIDENCE_"
            "INSUFFICIENT, but the boolean verdict field carries it into any "
            "verdict-reading consumer."),
    }

    # ----------------------------------------------------------------------
    # R2 — verdict True + EVIDENCE_INCONSISTENT_STAGE2_TOOL (production)
    # ----------------------------------------------------------------------
    hidden = controls["wrong_selection_hidden_by_final_response"]
    hid_rec = battery.engine.replay(hidden["row"])
    hid_fc = rl.classify_failure(hid_rec)
    results["reproductions"]["R2_inconsistent_stage2_retains_true_verdict"] = {
        "witness": "wrong_selection_hidden_by_final_response",
        "semantic_correct": hid_rec["semantic_correct"],
        "failure_class": hid_fc,
        "stage1_selection_wrong_tool": hid_rec["stage1_selection_wrong_tool"],
        "finding": (
            "A causally impossible two-stage response retains "
            "semantic_correct=True; only failure_class signals the evidence "
            "inconsistency. classify_failure orders the check before the "
            "SUCCESS shortcut (RS02), but the verdict field is unchanged."),
    }

    # ----------------------------------------------------------------------
    # R3 — production analyzer ingests both rows without eligibility filter
    # ----------------------------------------------------------------------
    sealed_rows = [json.loads(l) for l in
                   SEALED.read_text(encoding="utf-8").splitlines()]
    template = copy.deepcopy(sealed_rows[0])
    cell = (template["model"], template["arm"], template["budget"])

    def synth(trial_id, corrected, change_class):
        r = copy.deepcopy(template)
        r["trial_id"] = trial_id
        r["synthetic"] = True
        r["injected_by"] = "ea00_n02rr_residual_repro"
        r["corrected"] = corrected
        r["change_classification"] = change_class
        return r

    r1_row = synth("SYNTH-EA00-REPLAY-ERROR",
                   replay_record_to_corrected(crash_rec),
                   crash_cc)
    r2_row = synth("SYNTH-EA00-EVIDENCE-INCONSISTENT",
                   replay_record_to_corrected(hid_rec),
                   "UNCHANGED_VALID")

    tmp_rec = TMP_CONTROLS / "contaminated_reconciliation.jsonl"
    tmp_rec.parent.mkdir(parents=True, exist_ok=True)
    with tmp_rec.open("w", encoding="utf-8") as f:
        for r in sealed_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.write(json.dumps(r1_row, ensure_ascii=False) + "\n")
        f.write(json.dumps(r2_row, ensure_ascii=False) + "\n")

    real_rec_path = n02rr_analyze.REC

    def prod_load(path):
        n02rr_analyze.REC = path
        try:
            return n02rr_analyze.load_rows()      # production loader
        finally:
            n02rr_analyze.REC = real_rec_path

    baseline_rows = prod_load(SEALED)
    rows = prod_load(tmp_rec)

    # headline exactly as n02rr_analyze.main() line 291 computes it
    baseline_pass = sum(1 for r in baseline_rows if r["sem"])
    contaminated_pass = sum(1 for r in rows if r["sem"])
    # the cell aggregate exactly as agg() computes it
    cell_rows = [r for r in rows
                 if (r["model"], r["arm"], r["budget"]) == cell]
    cell_agg = n02rr_analyze.agg(cell_rows)
    baseline_cell = n02rr_analyze.agg(
        [r for r in baseline_rows
         if (r["model"], r["arm"], r["budget"]) == cell])
    evidence_insufficient = sum(
        1 for r in rows if r["change_classification"]
        == "EVIDENCE_INSUFFICIENT")

    results["reproductions"]["R3_production_analyzer_no_eligibility_filter"] = {
        "method": ("sealed 2,184 rows + 2 clearly-marked synthetic rows; "
                   "production load_rows()+agg(); main() NOT executed (it "
                   "would rewrite the corrected protocol matrix)"),
        "baseline_sealed": {
            "rows": len(baseline_rows),
            "semantic_PASS": baseline_pass,
        },
        "contaminated": {
            "rows": len(rows),
            "semantic_PASS_main_style": contaminated_pass,
            "EVIDENCE_INSUFFICIENT_label_count": evidence_insufficient,
        },
        "cell_delta": {
            "cell": f"{cell[0]}|{cell[1]}|budget={cell[2]}",
            "baseline_n": baseline_cell["n"],
            "baseline_semantic_k": baseline_cell["semantic_correct"]["k"],
            "contaminated_n": cell_agg["n"],
            "contaminated_semantic_k": cell_agg["semantic_correct"]["k"],
            "contaminated_rate": cell_agg["semantic_correct"]["rate"],
        },
        "finding": (
            "n02rr_analyze.load_rows sets r['sem']=bool(verdict) with no "
            "filter on failure_class/change_classification: the REPLAY_ERROR "
            "row is counted as a model semantic FAIL and the EVIDENCE_"
            "INCONSISTENT_STAGE2_TOOL row as a semantic PASS in the same "
            "rates, paired tests (paired() lines 143-148 use the same "
            "r['sem']) and the headline semantic_PASS (main line 291). The "
            "EVIDENCE_INSUFFICIENT label is reported as a denominator "
            "annotation only and excludes nothing."),
    }

    results["corpus_status"] = {
        "finding": ("The sealed N02RR corpus contains ZERO REPLAY_ERROR / "
                    "EVIDENCE_INSUFFICIENT / EVIDENCE_INCONSISTENT_STAGE2_TOOL"
                    " rows, so the published corrected headline (870/2,184) "
                    "is NOT contaminated; both risks are structural/latent."),
        "sealed_counts": {
            "REPLAY_ERROR": sum(1 for r in sealed_rows
                                if r["corrected"]["failure_class"]
                                == "REPLAY_ERROR"),
            "EVIDENCE_INCONSISTENT_STAGE2_TOOL": sum(
                1 for r in sealed_rows
                if r["corrected"]["failure_class"]
                == "EVIDENCE_INCONSISTENT_STAGE2_TOOL"),
            "EVIDENCE_INSUFFICIENT": sum(
                1 for r in sealed_rows if r["change_classification"]
                == "EVIDENCE_INSUFFICIENT"),
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    shutil.rmtree(TMP_CONTROLS)
    print(json.dumps({
        "R1_coerced_verdict": crash_rec["semantic_correct"],
        "R1_failure_class": crash_fc,
        "R2_verdict": hid_rec["semantic_correct"],
        "R2_failure_class": hid_fc,
        "R3_baseline_PASS": results["reproductions"]
            ["R3_production_analyzer_no_eligibility_filter"]
            ["baseline_sealed"]["semantic_PASS"],
        "R3_contaminated_PASS": contaminated_pass,
        "sealed_zero_risk_rows": results["corpus_status"]["sealed_counts"],
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
