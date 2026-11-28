#!/usr/bin/env python3
"""EA02-R EA-D03 — systematic state-combination validation.

Exhaustive enumeration of the core cognitive dimensions, dedicated
exhaustive blocks for business/safety and evaluator/disagreement, and
malformed-type injections — compared against an INDEPENDENTLY AUTHORED
rule model (below) that is derived from the written specification
(docs/IJEVAL_RESULT_CONTRACT.md v1.1) and deliberately does NOT call the
production validator. Escapes (model-illegal, validator-legal) and false
rejections (model-legal, validator-illegal) must both be ZERO.

stdlib only (unittest-era environment; Hypothesis confirmed unavailable —
reproducible exhaustive/seeded enumeration instead).
"""
from __future__ import annotations

import itertools
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance.contracts import (BusinessVerdict, ContractTypeError,   # noqa: E402
                                      EvaluationResult, EvaluationStatus,
                                      EvaluatorStatus, EvidenceIntegrity,
                                      ExecutionStatus, ParserStatus,
                                      PublicationEligibility,
                                      QualificationStatus, SafetyVerdict,
                                      SemanticVerdict, verify_evidence,
                                      violations)

PROV = {"experiment_id": "e1", "trial_id": "t1", "task_id": "k1",
        "model": "S1", "dataset_id": "d1", "parser_version": "p1",
        "evaluator_version": "v1"}
SHA = "a" * 64


def envelope():
    return verify_evidence(PROV, artifact_sha256_computed=SHA,
                           artifact_sha256_expected=SHA,
                           schema_validated=True, trial_identity_match=True)


# ---------------------------------------------------------------------------
# Independent rule model — authored from the SPECIFICATION text only.
# Each rule returns True when the combination is ILLEGAL.
# ---------------------------------------------------------------------------
DECISIVE = {SemanticVerdict.CORRECT, SemanticVerdict.INCORRECT}


def model_illegal(s: dict) -> list[str]:
    fired = []

    def rule(rid, cond):
        if cond:
            fired.append(rid)

    decisive = s["verdict"] in DECISIVE
    rule("R01_pipeline_vs_decisive",
         s["pipeline"] != EvaluationStatus.VALID and decisive)
    rule("R02_model_invalid_vs_correct",
         s["parser"] == ParserStatus.MODEL_OUTPUT_INVALID
         and s["verdict"] == SemanticVerdict.CORRECT)
    rule("R03_unsupported_vs_decisive",
         s["parser"] == ParserStatus.UNSUPPORTED_REPRESENTATION and decisive)
    rule("R04_parser_error_vs_decisive",
         s["parser"] == ParserStatus.PARSER_SOFTWARE_ERROR and decisive)
    rule("R05_parser_error_needs_error_pipeline",
         s["parser"] == ParserStatus.PARSER_SOFTWARE_ERROR
         and s["pipeline"] == EvaluationStatus.VALID)
    rule("R06_evaluator_error_vs_decisive",
         s["evaluator"] == EvaluatorStatus.ERROR and decisive)
    rule("R07_evaluator_error_pipeline",
         s["evaluator"] == EvaluatorStatus.ERROR
         and s["pipeline"] != EvaluationStatus.EVALUATOR_ERROR)
    disagree = s["disagreement"] or s["evaluator"] == EvaluatorStatus.DISAGREEMENT
    rule("R08_disagreement_pipeline",
         disagree and s["pipeline"] != EvaluationStatus.ORACLE_DISAGREEMENT)
    rule("R09_disagreement_vs_qualified",
         disagree and (decisive or s["publication"]
                       == PublicationEligibility.ELIGIBLE))
    env = s.get("envelope_ok")
    rule("R10_verified_needs_envelope",
         s["evidence"] == EvidenceIntegrity.VERIFIED and not env)
    rule("R11_verified_envelope_identity",
         s["evidence"] == EvidenceIntegrity.VERIFIED
         and env is False)    # envelope present but contradicting
    rule("R12_decisive_needs_verified_evidence",
         decisive and s["evidence"] != EvidenceIntegrity.VERIFIED)
    rule("R13_marker_vs_decisive", bool(s["marker"]) and decisive)
    rule("R14_rejected_vs_decisive",
         s["evidence"] == EvidenceIntegrity.REJECTED and decisive)
    rule("R15_decisive_needs_provenance",
         decisive and not s["provenance_ok"])
    rule("R16_execution_vs_decisive",
         s["execution"] in (ExecutionStatus.NOT_RUN, ExecutionStatus.BLOCKED,
                            ExecutionStatus.PARTIAL) and decisive)
    rule("R17_canary_vs_eligible",
         s["execution"] == ExecutionStatus.CANARY_CONTROL
         and s["publication"] == PublicationEligibility.ELIGIBLE)
    rule("R18_undecidable_vs_eligible",
         s["verdict"] in (SemanticVerdict.NOT_EVALUABLE,
                          SemanticVerdict.NOT_APPLICABLE)
         and s["publication"] == PublicationEligibility.ELIGIBLE)
    business_active = s.get("business") is not None and \
        s.get("business") != BusinessVerdict.NOT_APPLICABLE
    if business_active and s.get("business") == BusinessVerdict.PASS:
        rule("R19_business_pass_world",
             s.get("world") is not True)
        rule("R20_business_pass_safety_violation",
             s.get("safety") == SafetyVerdict.VIOLATION)
        rule("R21_business_pass_safety_unverified",
             s.get("safety") == SafetyVerdict.NOT_VERIFIED)
        rule("R22_business_pass_pipeline",
             s["pipeline"] != EvaluationStatus.VALID)
    rule("R23_qualification_vs_eligible",
         s["qualification"] in (QualificationStatus.UNQUALIFIED,
                                QualificationStatus.REVOKED,
                                QualificationStatus.PENDING)
         and s["publication"] == PublicationEligibility.ELIGIBLE)
    rule("R24_safety_violation_vs_eligible",
         s.get("safety") == SafetyVerdict.VIOLATION
         and s["publication"] == PublicationEligibility.ELIGIBLE)
    return fired


def build_record(s: dict) -> EvaluationResult:
    env = None
    if s.get("envelope_ok") is True:
        env = envelope()
    elif s.get("envelope_ok") is False:
        # envelope whose identity contradicts the record provenance
        other = dict(PROV, trial_id="different-trial")
        env = verify_evidence(other, artifact_sha256_computed=SHA,
                              artifact_sha256_expected=SHA,
                              schema_validated=True, trial_identity_match=True)
    return EvaluationResult(
        execution_status=s["execution"],
        evaluation_status=s["pipeline"],
        parser_status=s["parser"],
        semantic_verdict=s["verdict"],
        evaluator_status=s["evaluator"],
        business_verdict=s.get("business", BusinessVerdict.NOT_APPLICABLE),
        safety_verdict=s.get("safety", SafetyVerdict.NOT_APPLICABLE),
        qualification=s["qualification"],
        publication=s["publication"],
        evidence=s["evidence"],
        evidence_invalid_reason="x" if s.get("marker") else None,
        oracle_disagreement=s["disagreement"],
        business_world_valid=s.get("world"),
        provenance=dict(PROV) if s["provenance_ok"] else {},
        verified_evidence=env)


def run_battery() -> dict:
    stats = {"generated": 0, "model_legal": 0, "model_illegal": 0,
             "rule_firing_counts": {}, "escapes": [], "false_rejections": []}

    def check(spec):
        stats["generated"] += 1
        fired = model_illegal(spec)
        if fired:
            stats["model_illegal"] += 1
        else:
            stats["model_legal"] += 1
        for rid in fired:
            stats["rule_firing_counts"][rid] = \
                stats["rule_firing_counts"].get(rid, 0) + 1
        produced = violations(build_record(spec))
        if not fired and produced:
            stats["false_rejections"].append({"spec": key_of(spec),
                                              "validator": produced[:3]})
        if fired and not produced:
            stats["escapes"].append({"spec": key_of(spec), "model": fired})

    def key_of(spec):
        return {k: (v.value if hasattr(v, "value") else v)
                for k, v in spec.items()}

    base = dict(evaluator=EvaluatorStatus.OK, disagreement=False,
                evidence=EvidenceIntegrity.VERIFIED, envelope_ok=True,
                marker=False, provenance_ok=True)

    # Block 1 — exhaustive cognitive core (8,640 combos)
    for ex, pl, pa, ve, qu, pu in itertools.product(
            list(ExecutionStatus), list(EvaluationStatus),
            list(ParserStatus), list(SemanticVerdict),
            list(QualificationStatus), list(PublicationEligibility)):
        check({**base, "execution": ex, "pipeline": pl, "parser": pa,
               "verdict": ve, "qualification": qu, "publication": pu})

    # Block 2 — exhaustive business/safety/world × pipeline (192 combos)
    for bu, sa, wo, pl in itertools.product(
            list(BusinessVerdict), list(SafetyVerdict),
            [True, False, None],
            [EvaluationStatus.VALID, EvaluationStatus.EVALUATOR_ERROR]):
        check({**base, "execution": ExecutionStatus.EXECUTED,
               "pipeline": pl, "parser": ParserStatus.PARSE_OK,
               "verdict": SemanticVerdict.NOT_EVALUABLE,
               "qualification": QualificationStatus.QUALIFIED,
               "publication": PublicationEligibility.DIAGNOSTIC_ONLY,
               "business": bu, "safety": sa, "world": wo})

    # Block 3 — exhaustive evaluator/disagreement × pipeline × verdict (216)
    for ev, di, pl, ve in itertools.product(
            list(EvaluatorStatus), [False, True],
            list(EvaluationStatus), list(SemanticVerdict)):
        check({**base, "execution": ExecutionStatus.EXECUTED,
               "pipeline": pl, "parser": ParserStatus.PARSE_OK,
               "verdict": ve, "qualification": QualificationStatus.QUALIFIED,
               "publication": PublicationEligibility.DIAGNOSTIC_ONLY,
               "evaluator": ev, "disagreement": di})

    # Block 4 — exhaustive evidence/envelope/provenance/marker/publication/
    # safety (360 combos; exercises R10-R15 and R24)
    for ev, env_ok, prov_ok, marker, pu, sa in itertools.product(
            list(EvidenceIntegrity), [None, True, False], [True, False],
            [False, True], list(PublicationEligibility),
            [SafetyVerdict.SAFE, SafetyVerdict.VIOLATION]):
        check({**base, "execution": ExecutionStatus.EXECUTED,
               "pipeline": EvaluationStatus.VALID,
               "parser": ParserStatus.PARSE_OK,
               "verdict": SemanticVerdict.CORRECT,
               "qualification": QualificationStatus.QUALIFIED,
               "evidence": ev, "envelope_ok": env_ok,
               "provenance_ok": prov_ok, "marker": marker,
               "publication": pu, "safety": sa})

    # Malformed-type injections: constructor must reject (ContractTypeError)
    rejected = 0
    injections = 0
    good = dict(execution_status=ExecutionStatus.EXECUTED,
                evaluation_status=EvaluationStatus.VALID,
                parser_status=ParserStatus.PARSE_OK,
                semantic_verdict=SemanticVerdict.CORRECT)
    for field_name, bad in itertools.product(
            ["execution_status", "evaluation_status", "parser_status",
             "semantic_verdict", "evaluator_status", "business_verdict",
             "safety_verdict", "qualification", "publication", "evidence"],
            ["EXECUTED", 1, None]):
        injections += 1
        try:
            EvaluationResult(**{**good, field_name: bad})
        except ContractTypeError:
            rejected += 1
    for bad in ["true", 1, None, []]:
        injections += 1
        try:
            EvaluationResult(**{**good, "oracle_disagreement": bad})
        except ContractTypeError:
            rejected += 1
    for bad in ["true", 1, []]:
        injections += 1
        try:
            EvaluationResult(**{**good, "business_world_valid": bad})
        except ContractTypeError:
            rejected += 1
    for bad in ["True", "False", 1, 0, None, [], "PASS"]:
        injections += 1
        try:
            EvaluationResult.evaluated(semantic=bad)
        except ContractTypeError:
            rejected += 1
    stats["malformed_injections"] = injections
    stats["malformed_rejected"] = rejected
    return stats


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    stats = run_battery()
    payload = {
        "schema": "ijeval.ea02r.state_space",
        "independent_rule_model": "model_illegal() in this script "
                                  "(authored from the specification, never "
                                  "calls the validator under test)",
        "blocks": {
            "cognitive_core": "exhaustive execution x pipeline x parser x "
                              "verdict x qualification x publication (8,640)",
            "business_block": "exhaustive business x safety x world x "
                              "pipeline (192)",
            "evaluator_block": "exhaustive evaluator x disagreement x "
                               "pipeline x verdict (216)",
            "malformed_types": "field-substitution injections (constructor "
                               "must raise ContractTypeError)"},
        "results": stats,
        "declared_invariants": 24,
        "invariants_exercised": len(stats["rule_firing_counts"]),
        "escapes": len(stats["escapes"]),
        "false_rejections": len(stats["false_rejections"]),
    }
    out = ROOT / "evidence" / "IJEVAL" / "EA02R" / "state_space_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # full escape lists can be large; keep first 20 examples each in evidence
    stats["escapes"] = stats["escapes"][:20]
    stats["false_rejections"] = stats["false_rejections"][:20]
    out.write_text(json.dumps(payload, indent=1, default=str,
                              ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in
                      ("results", "invariants_exercised", "escapes",
                       "false_rejections")}, default=str, indent=1)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
