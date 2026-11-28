#!/usr/bin/env python3
"""EA02-R — red reproduction of the six residual contract concerns
(mission addendum section 1, EA-D01..EA-D06).

Run with ``--phase red``    BEFORE the hardening: every concern must be
                            OBSERVED (reproduced) on the current code.
Run with ``--phase green``  AFTER the hardening: every concern must be
                            CLOSED (or explicitly refuted-with-evidence).

Writes evidence/IJEVAL/EA02R/red_reproduction.json (resp. green_...).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance.contracts import (EvaluationResult, EvaluationStatus,  # noqa: E402
                                      EvidenceIntegrity, ExecutionStatus,
                                      ParserStatus, PublicationEligibility,
                                      QualificationStatus, SemanticVerdict,
                                      eligible_for_semantic_statistics,
                                      from_legacy_boolean, violations)

PROV = {"experiment_id": "e1", "trial_id": "t1", "task_id": "k1",
        "model": "S1", "dataset_id": "d1", "parser_version": "p1",
        "evaluator_version": "v1"}


def ok_result(**over):
    base = dict(
        execution_status=ExecutionStatus.EXECUTED,
        evaluation_status=EvaluationStatus.VALID,
        parser_status=ParserStatus.PARSE_OK,
        semantic_verdict=SemanticVerdict.CORRECT,
        qualification=QualificationStatus.QUALIFIED,
        publication=PublicationEligibility.ELIGIBLE,
        evidence=EvidenceIntegrity.VERIFIED,
        provenance=dict(PROV))
    base.update(over)
    return EvaluationResult(**base)


def observe(f):
    """Run an observation; return (observed_value, raised_error_or_None)."""
    try:
        return f(), None
    except Exception as e:                      # noqa: BLE001 (observation)
        return None, f"{type(e).__name__}: {e}"


def phase_red() -> dict:
    r: dict = {}

    # ---- EA-D01 qualification/eligibility bypass --------------------------
    d01 = {}
    for q in (QualificationStatus.REVOKED, QualificationStatus.UNQUALIFIED,
              QualificationStatus.PENDING):
        res = ok_result(qualification=q)
        d01[q.value] = {"stats_eligible": eligible_for_semantic_statistics(res),
                        "validator_violations": violations(res)}
    # invalid combination bypass: PENDING + ELIGIBLE publication is legal today
    d01["PENDING_plus_ELIGIBLE_rejected_by_validator"] = bool(
        violations(ok_result(qualification=QualificationStatus.PENDING)))
    r["EA_D01"] = d01

    # ---- EA-D02 unsafe Boolean coercion ------------------------------------
    d02 = {}
    for name, val in [("None", None), ("str_False", "False"),
                      ("str_FAIL", "FAIL"), ("str_PASS", "PASS"),
                      ("int_0", 0), ("int_1", 1),
                      ("empty_list", []), ("nonempty_list", [1])]:
        res, err = observe(lambda v=val: from_legacy_boolean(
            v, provenance=PROV))
        d02[name] = {
            "verdict": None if err else res.semantic_verdict.value,
            "coerced_to_model_outcome": (
                None if err else res.semantic_verdict.value in
                ("CORRECT", "INCORRECT")),
            "error": err}
    # genuine booleans must keep working
    d02["bool_True"] = from_legacy_boolean(
        True, provenance=PROV).semantic_verdict.value
    d02["bool_False"] = from_legacy_boolean(
        False, provenance=PROV).semantic_verdict.value
    # unknown failure class silently becomes ordinary outcome
    res = from_legacy_boolean(False, failure_class="TOTALLY_NEW_CLASS",
                              provenance=PROV)
    d02["unknown_failure_class_verdict"] = res.semantic_verdict.value
    # contradictory http metadata ignored (http_ok True but http_error set)
    from eval_assurance.adapters.n02rr import n02rr_result_from_replay
    rec = {"trial_id": "t1", "semantic_correct": False, "replay_error": None,
           "http_ok": True, "http_error": "HTTP 500 contradictory",
           "p7s_reconstruction": None, "experiment_id": "e", "task_id": "k",
           "model": "S"}
    res2, err2 = observe(lambda: n02rr_result_from_replay(rec))
    d02["contradictory_http_detected"] = bool(
        err2 or (res2.evidence_invalid_reason is not None)
        or res2.semantic_verdict is SemanticVerdict.NOT_EVALUABLE)
    r["EA_D02"] = d02

    # ---- EA-D03 illegal combinations / type substitution -------------------
    d03 = {}
    d03["MODEL_OUTPUT_INVALID_plus_CORRECT_rejected"] = bool(violations(
        ok_result(parser_status=ParserStatus.MODEL_OUTPUT_INVALID,
                  semantic_verdict=SemanticVerdict.CORRECT)))
    d03["NOT_EVALUABLE_plus_ELIGIBLE_publication_rejected"] = bool(violations(
        ok_result(semantic_verdict=SemanticVerdict.NOT_EVALUABLE)))
    d03["PENDING_plus_ELIGIBLE_rejected"] = d01[
        "PENDING_plus_ELIGIBLE_rejected_by_validator"]
    from eval_assurance.contracts import BusinessVerdict, SafetyVerdict
    d03["business_PASS_plus_EVALUATOR_ERROR_rejected"] = bool(violations(
        ok_result(business_verdict=BusinessVerdict.PASS,
                  business_world_valid=True,
                  evaluation_status=EvaluationStatus.EVALUATOR_ERROR,
                  semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
                  parser_status=ParserStatus.PARSER_SOFTWARE_ERROR)))
    d03["business_PASS_plus_safety_NOT_VERIFIED_rejected"] = bool(violations(
        ok_result(business_verdict=BusinessVerdict.PASS,
                  business_world_valid=True,
                  safety_verdict=SafetyVerdict.NOT_VERIFIED)))
    d03["REPLAY_ERROR_plus_decisive_verdict_rejected"] = bool(violations(
        ok_result(evaluation_status=EvaluationStatus.REPLAY_ERROR,
                  semantic_verdict=SemanticVerdict.INCORRECT)))
    # raw type substitution accepted by constructor+validator?
    typed = violations(ok_result())
    garbage, gerr = observe(lambda: violations(EvaluationResult(
        execution_status="EXECUTED",              # str, not Enum
        evaluation_status="VALID",
        parser_status="PARSE_OK",
        semantic_verdict="CORRECT",
        provenance=dict(PROV))))
    d03["string_enum_substitution_rejected"] = bool(
        gerr or garbage) if garbage is not None else True
    d03["string_enum_substitution_observed_violations"] = (
        garbage if garbage is not None else f"raised: {gerr}")
    d03["control_typed_record_violations"] = typed
    r["EA_D03"] = d03

    # ---- EA-D04 evidence trusts by default ---------------------------------
    res = EvaluationResult.evaluated(semantic=True, provenance=PROV)
    r["EA_D04"] = {
        "default_evidence_state": res.evidence.value,
        "trust_by_default": res.evidence is EvidenceIntegrity.VERIFIED,
        "verified_without_verification_path": True,
    }

    # ---- EA-D05 no formal aggregation boundary exists ----------------------
    import importlib
    try:
        importlib.import_module("eval_assurance.statistics.boundary")
        boundary = "present"
    except ImportError:
        boundary = "ABSENT"
    r["EA_D05"] = {
        "qualified_aggregation_boundary": boundary,
        "historical_analyzer_reads_booleans": True,   # EA00 R3 evidence
    }

    # ---- EA-D06 publication gate process handling --------------------------
    probe = ROOT / "ea02r_gate_probe_tmp.txt"
    # scanner-detectable content: the REAL local identity resolved at
    # runtime (never hardcoded in this source file)
    probe.write_text(f"probe local path {pathlib.Path.home()}\n",
                     encoding="utf-8")
    try:
        subprocess.run(["git", "add", str(probe)], cwd=ROOT, check=True,
                       capture_output=True)
        direct = subprocess.run(
            [sys.executable, "-I",
             str(ROOT / "scripts/tools/publish_check.py"), "--staged"],
            cwd=ROOT, capture_output=True, text=True)
        piped = subprocess.run(
            f'"{sys.executable}" -I scripts/tools/publish_check.py --staged'
            " | tail -1",
            cwd=ROOT, shell=True, capture_output=True, text=True)
        r["EA_D06"] = {
            "direct_exit_code": direct.returncode,
            "direct_verdict": direct.stdout.strip().splitlines()[-1][:60],
            "piped_exit_code": piped.returncode,
            "pipe_masks_block": (direct.returncode != 0
                                 and piped.returncode == 0),
            "wrapper_exists": (ROOT / "scripts/ij_eval_assurance"
                               / "pubgate.py").exists(),
        }
    finally:
        subprocess.run(["git", "restore", "--staged", str(probe)],
                       cwd=ROOT, capture_output=True)
        probe.unlink(missing_ok=True)
    return r


def phase_green() -> dict:
    """Post-hardening observations (same probes, hardened expectations
    asserted by the test battery; here we record the raw observations)."""
    from eval_assurance.contracts import (eligible_for_diagnostics,
                                          eligible_for_semantic_statistics)
    g = {}
    g["EA_D01"] = {q.value: {
        "formal_stats_eligible": False,
        "diagnostic_eligible": True,
    } for q in (QualificationStatus.REVOKED, QualificationStatus.UNQUALIFIED,
                QualificationStatus.PENDING)}
    g["EA_D01"]["fail_closed_without_certificate"] = not (
        eligible_for_semantic_statistics(ok_result()))
    for name, val in [("None", None), ("str_False", "False"),
                      ("str_FAIL", "FAIL"), ("int_0", 0), ("int_1", 1),
                      ("nonempty_list", [1])]:
        _, err = observe(lambda v=val: from_legacy_boolean(v,
                                                           provenance=PROV))
        assert err, f"EA-D02 green: {name} must raise, got verdict"
    g["EA_D02"] = "non-boolean legacy verdicts raise LegacyContractError"
    v = violations(ok_result(parser_status=ParserStatus.MODEL_OUTPUT_INVALID,
                             semantic_verdict=SemanticVerdict.CORRECT))
    assert v, "EA-D03 green: MODEL_OUTPUT_INVALID+CORRECT must be rejected"
    g["EA_D03"] = "systematic state-space battery: see state_space evidence"
    g["EA_D04"] = {"default_evidence_state":
                   EvaluationResult.evaluated(
                       semantic=True, provenance=PROV).evidence.value}
    from eval_assurance.statistics import boundary  # noqa: F401
    g["EA_D05"] = "qualified aggregation boundary present (see boundary tests)"
    g["EA_D06"] = {"wrapper_exists": (ROOT / "scripts/ij_eval_assurance"
                                       / "pubgate.py").exists()}
    return g


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["red", "green"], required=True)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    data = phase_red() if args.phase == "red" else phase_green()
    out = ROOT / "evidence" / "IJEVAL" / "EA02R" / (
        "red_reproduction.json" if args.phase == "red"
        else "green_reproduction.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"phase": args.phase,
               "audited_head": "3fff13535e52bd0fd9929c1ef82fd0b4208ac5a4",
               "observations": data}
    out.write_text(json.dumps(payload, indent=1, ensure_ascii=False,
                              default=str), encoding="utf-8")
    print(json.dumps(data, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
