#!/usr/bin/env python3
"""EA01 — evaluation threat model / FMEA matrix generator
(mission IJ-EVAL-ASSURANCE-1.0).

Emits evidence/IJEVAL/EA01/failure_mode_matrix.json: the 27-layer
evidence-to-verdict pipeline (mission order section 3) with per-layer failure
modes, FMEA prioritization (severity, potential affected trial count,
detectability, recoverability, downstream contamination risk) and the
mandatory control mapping (preventive control, detection mechanism,
containment action, regression test, qualification requirement) for every
critical mode.

Failure classes (order section 3): ACC accidental implementation defect,
CMODE common-mode evaluator defect, FP false positive, FN false negative,
LOSS silent data loss, CORRUPT corrupted evidence, VER version
incompatibility, LEAK hidden-answer leakage, REWARD reward hacking,
STATE unauthorized state effect, RECOVERY incorrect recovery, MAL malicious
or malformed input.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "IJEVAL" / "EA01" / "failure_mode_matrix.json"

LAYERS = [
    "L01_task_specification", "L02_dataset_generation",
    "L03_reference_answer_generation", "L04_business_world_init",
    "L05_task_applicability", "L06_prompt_rendering",
    "L07_model_request_generation", "L08_inference_transport",
    "L09_response_decoding", "L10_raw_artifact_capture",
    "L11_artifact_serialization", "L12_artifact_loading",
    "L13_parser_behavior", "L14_semantic_normalization",
    "L15_typed_response_construction", "L16_reference_oracle",
    "L17_production_evaluator", "L18_business_state_verification",
    "L19_multi_stage_causal_reconstruction", "L20_resource_accounting",
    "L21_trial_identity", "L22_resume_and_deduplication",
    "L23_statistical_aggregation", "L24_report_generation",
    "L25_qualification_issuance", "L26_reward_generation",
    "L27_publication",
]

# (layer, mode, class, sev 1-5, trial_impact, detectability, recoverability,
#  contamination, prevention, detection, containment, regression,
#  qualification)  -- historical evidence tags in mode ids where applicable.
M = [
 # L01 task specification
 ("L01", "task contract incomplete (fields missing: applicability, scope, licensing)", "ACC", 4,
  "all trials of family", "M (only when verdicts look odd)", "M (regenerate+rerun)",
  "invalid conclusions for family",
  "EA03 required task contract schema", "EA03 dataset qualification battery",
  "EA10 quarantine family scope", "tests/ij_eval_assurance/test_contracts.py",
  "EA03_DATASET_QUALIFICATION_GO"),
 ("L01", "ambiguous task admits multiple defensible answers scored against one", "ACC", 4,
  "subset of family", "L (looks like model error)", "M",
  "false negatives published", "EA03 ambiguity/negative-case qualification",
  "EA05 differential disagreement", "EA10 stop + NOT_EVALUABLE",
  "EA03 mutation: ambiguous task injected", "EA03 gate incl. ambiguous/impossible tasks"),
 # L02 dataset generation
 ("L02", "duplicate or paraphrase-inflated cases", "ACC", 3, "denominators",
  "M", "H (dedup)", "inflated coverage claims", "EA03 dedup + identity",
  "EA11 denominator reconciliation", "EA10 revoke affected certificate",
  "EA11 duplicate-trial test", "EA03 gate"),
 ("L02", "train/confirmation/holdout overlap", "LEAK", 5, "all formal claims",
  "L", "L (holdout burned)", "contaminated generalization claims",
  "EA03 overlap checks", "EA03 overlap tests", "EA10 block publication",
  "EA03 overlap mutation", "EA03 gate + EA13 holdout protection"),
 # L03 reference answers
 ("L03", "expected answer wrong (generation bug or typo)", "ACC", 5,
  "affected tasks, both directions", "L", "M (fix + full rescore)",
  "false positives AND negatives", "EA03 independent verification of expectations",
  "EA05 reference evaluator disagreement", "EA10 quarantine task set",
  "EA03 flipped-answer mutation", "EA03 gate"),
 ("L03", "same generator produces test answer and verification logic (shared root)", "CMODE", 5,
  "family-wide", "L (self-consistent)", "M",
  "systematically wrong family verdicts", "EA03 independence requirement",
  "EA05 differential independence analysis", "EA10 revoke scope",
  "EA05 shared-implementation detector test", "EA05 gate"),
 ("L03", "expectations leak into public prompt or tool schema", "LEAK", 5,
  "all trials of tasks", "L", "M", "invalid capability measurement",
  "EA03 leakage scan", "EA06 leakage witnesses + EA13 access boundary",
  "EA10 hard stop", "EA06 leak witness", "EA03/EA13 gates"),
 # L04 business world init
 ("L04", "invalid initial state (unreachable/inconsistent world)", "ACC", 4,
  "world's tasks", "M", "H", "false negatives",
  "EA03 invalid-initial-state qualification", "EA05 state invariant checks",
  "EA10 quarantine world", "EA03 invalid-ICS mutation", "EA03 gate"),
 # L05 applicability
 ("L05", "task applied where not applicable (empty candidate set, missing tool)", "ACC", 4,
  "affected arm x family cells", "M (PR-D03 class)", "H",
  "arm-fairness distortion", "EA03 applicability registry",
  "EA11 applicability-filtered denominators", "EA10 mark inapplicable",
  "PR-D03 regression class", "EA03/EA11 gates"),
 # L06 prompt rendering
 ("L06", "arms receive unequal information (tool inventory present/absent)", "ACC", 4,
  "cross-arm comparisons", "M (PR-D01 class)", "H (re-render)",
  "confounded contrasts", "EA03 information-matched rendering",
  "EA11 arm-pair information manifest check", "EA10 block comparison",
  "PR-D01 manifest test", "EA11 gate"),
 ("L06", "template regression alters bytes mid-experiment", "VER", 4,
  "trials after change", "M (identity hash)", "H",
  "mixed-configuration corpus", "EA08 request-renderer identity binding",
  "EA08 identity check on resume", "EA10 stop + fork identity",
  "EA08 renderer hash test", "EA08 gate"),
 # L07 request generation
 ("L07", "wrong chat template / missing think tags / kwarg silently dropped", "ACC", 4,
  "arm-wide", "M (PR-D/b0c7f44 class)", "H", "invalid arm results",
  "EA08 chat-template binding", "EA08 byte-identical render verification",
  "EA10 quarantine arm", "renderer parity test", "EA08 gate"),
 # L08 transport
 ("L08", "HTTP 200 with error payload (coerced params, truncated schema reply)", "CORRUPT", 4,
  "subset (RC-11/J-3 class)", "M", "H (artifact preserved)",
  "false negatives (model blamed)", "EA08 endpoint contract validation",
  "EA08 response-shape checks", "EA10 transport-error class",
  "RC-11-style red test", "EA08 gate"),
 ("L08", "stale/wrong server on port (false ready)", "STATE", 3, "whole run",
  "M (D-010 class)", "M", "wrong-engine evidence",
  "EA08 socket-PID + engine identity proof", "EA08 launch verification",
  "EA10 stop run", "D-010 regression", "EA08 gate"),
 # L09 decoding
 ("L09", "partial UTF-8 / SSE reasoning-channel blindness", "CORRUPT", 3,
  "subset", "M", "H", "corrupted content into parser",
  "EA08 strict decode validation", "EA08 decode checks",
  "EA10 artifact reject", "decode fuzz test", "EA08 gate"),
 # L10 raw capture
 ("L10", "raw response truncated at capture (4000-char class)", "LOSS", 4,
  "long responses", "L (PR-D08 class)", "L (bytes gone)",
  "unrecoverable verdict disputes", "EA08 complete sanitized raw capture",
  "EA08 length/sha verification", "EA10 reject evidence",
  "PR-D08 regression", "EA08 gate"),
 # L11 serialization
 ("L11", "non-deterministic serialization / float round-trip loss", "CORRUPT", 2,
  "scattered", "M", "H", "replay divergence",
  "EA08 canonical serialization", "EA08 replay byte agreement",
  "EA10 mark replay-invalid", "serialization round-trip test", "EA08 gate"),
 # L12 artifact loading
 ("L12", "positional unpacking of persisted dict (RS01)", "ACC", 5,
  "all replayed rows", "L (looks like model failure)", "H (artifacts intact)",
  "mass false negatives (588-class)", "EA08 key-based validated loader only",
  "EA07 mutant control + EA09 canary", "EA10 circuit break + quarantine",
  "RS01 mutant gate", "EA08 gate"),
 ("L12", "missing/corrupt artifact silently scored", "CORRUPT", 5,
  "affected rows", "M", "H", "fabricated verdicts",
  "EA08 mandatory sha+schema before scoring", "EA08 loader rejects",
  "EA10 EVIDENCE_INSUFFICIENT class", "loader reject battery", "EA08 gate"),
 # L13 parser
 ("L13", "substring/negation tolerance in matching (IJSDK-D02 class)", "FP", 5,
  "family-wide", "L", "M", "false positives published",
  "EA04 closed matching rules", "EA05 independent assertions",
  "EA10 revoke parser scope", "EA04 battery + EA07 substring mutant",
  "EA04 gate"),
 ("L13", "candidate-order ambiguity resolution (PR-D04 class)", "FP", 4,
  "ambiguous outputs", "M", "H", "arbitrary verdicts",
  "EA04 reject-on-ambiguity", "EA04 ambiguity controls",
  "EA10 NOT_EVALUABLE", "PR-D04 regression", "EA04 gate"),
 ("L13", "duplicate JSON keys accepted", "FP", 3, "subset", "M", "H",
  "silent field override", "EA04 strict duplicate-key rejection",
  "EA04 dup-key controls", "EA10 parse-invalid", "EV02/IJ06 regression",
  "EA04 gate"),
 ("L13", "parser exception converted to model failure (IJE-D001 class)", "FN", 5,
  "all crashing rows", "L (looks like PARSE_INVALID)", "H",
  "mass false negatives", "EA02 typed status separation",
  "EA09 NOT_EVALUABLE canary", "EA10 hard stop on evaluator exception",
  "EA00 R1 reproduction as permanent test", "EA02 gate"),
 # L14 normalization
 ("L14", "normalization folds distinct identifiers (EV04 class)", "FP", 4,
  "collision-prone ids", "L", "M", "false positives",
  "EA04 kind-scoped matching + recorded normalizations",
  "EA04 collision witnesses", "EA10 rescore", "EV04 regression", "EA04 gate"),
 ("L14", "unit inheritance / thousands-separator mismatch (EV05/TC-V1-d class)",
  "FP", 3, "quantity tasks", "M", "H", "both-direction errors",
  "EA04 explicit unit contract", "EA04 equivalence rules",
  "EA10 rescore", "EA04 unit battery", "EA04 gate"),
 # L15 typed construction
 ("L15", "wrong field bound into typed response (name-only checks, ORC-V2-b class)",
  "ACC", 4, "affected args", "M", "H", "wrong verdicts",
  "EA02 strict typed construction", "EA02 contract validator",
  "EA10 reject record", "typed-construction tests", "EA02 gate"),
 # L16 reference oracle
 ("L16", "reference oracle shares defect with production (CMODE)", "CMODE", 5,
  "whole scope", "L (they agree)", "M",
  "false confidence in wrong verdicts", "EA05 independence analysis",
  "EA06 golden witness library + EA07 mutants", "EA10 revoke scope",
  "EA05 independence detector", "EA05 gate"),
 ("L16", "oracle uses private graph/hidden state for public decisions (ORC-1 class)",
  "ACC", 4, "affected tasks", "M", "M", "unfair verdicts",
  "EA05 public-contract-only reference", "EA05 differential",
  "EA10 rescore", "ORC regression class", "EA05 gate"),
 # L17 production evaluator
 ("L17", "evaluator upgrade changes semantics without identity fork", "VER", 4,
  "post-upgrade rows", "M", "H", "mixed-era corpus",
  "EA08 evaluator version binding", "EA08 replay agreement check",
  "EA10 stop + requalify", "version-fork test", "EA08/EA12 gates"),
 ("L17", "evaluator crashes swallowed by broad except (masking)", "RECOVERY", 5,
  "all rows post-defect", "L", "H (if preserved)",
  "contaminated statistics (IJE-D001)", "EA02 INV10 fail-closed",
  "EA09 canary + EA10 anomaly detector", "EA10 circuit break",
  "exception-mask mutant", "EA02/EA10 gates"),
 # L18 business state verification
 ("L18", "final state never validated (IJSDK-D03 class)", "STATE", 5,
  "business trials", "L", "M", "unsafe actions score PASS (INV09)",
  "EA05 independent postcondition verification", "EA05 state differential",
  "EA10 hard stop", "D03 reproduction battery", "EA05/EA16 gates"),
 # L19 multi-stage reconstruction
 ("L19", "final-stage answer hides wrong stage-1 selection (RS02/IJE-D002 class)",
  "FP", 4, "two-stage trials", "M", "H", "false positives",
  "EA04 causal reconstruction mandatory", "EA05 stage-consistency checks",
  "EA10 EVIDENCE_INCONSISTENT class", "RS02/6b control",
  "EA04/EA05 gates"),
 ("L19", "stage-2 scored against EXPECTED not ACTUAL selection", "ACC", 4,
  "two-stage trials", "M", "H", "false positives",
  "EA04 actual-selection verification", "RS02 replay checks",
  "EA10 rescore", "RS02 regression", "EA04 gate"),
 # L20 resource accounting
 ("L20", "missing telemetry coerced to zero (RS07/PR-D08 class)", "LOSS", 3,
  "resource metrics", "M", "H", "understated costs, wrong rankings",
  "EA11 never-zero missingness", "EA11 sample counts + missing counts",
  "EA11 UNAVAILABLE reporting", "RS07 regression", "EA11 gate"),
 # L21 trial identity
 ("L21", "trial id collision or cross-experiment merge (HA-4 class)", "CORRUPT", 4,
  "merged rows", "M", "M", "conflicting scores merged",
  "EA08 trial identity binding", "EA08 identity validation",
  "EA10 reject duplicates", "HA-4 regression", "EA08 gate"),
 # L22 resume/dedup
 ("L22", "resume from stale/contaminated checkpoint", "RECOVERY", 4,
  "post-resume rows", "M", "M", "mixed-identity corpus",
  "EA08 resume guard (identity+seal)", "EA08 resume validation",
  "EA10 stop + requalify", "NA-D03/PR-D06 regression", "EA08 gate"),
 ("L22", "duplicate dispatch counted as independent trials (HA-5 class)", "FP", 3,
  "denominators", "M", "H", "inflated n", "EA11 unique-trial identity",
  "EA11 denominator reconciliation", "EA11 dedup",
  "HA-5 regression", "EA11 gate"),
 # L23 aggregation
 ("L23", "unevaluable rows enter semantic rates (IJE-D001/R3 class)", "FN", 5,
  "all rows", "L (verdict field looks normal)", "H",
  "headline contamination", "EA02 eligible_for_semantic_statistics",
  "EA11 analyzer consumes contract only", "EA10 anomaly detector",
  "EA00 R3 reproduction as permanent test", "EA02/EA11 gates"),
 ("L23", "unmatched task populations compared (RS04 class)", "ACC", 4,
  "contrast level", "M", "H", "spurious significance",
  "EA11 matched-comparison requirement", "EA11 pairing checks",
  "EA11 block report", "RS04 regression", "EA11 gate"),
 ("L23", "canary trials counted as model evidence", "ACC", 3, "denominators",
  "M", "H", "rate distortion", "EA09 canary accounting exclusion",
  "EA09 control ledger", "EA09 exclude + report",
  "EA09 accounting test", "EA09 gate"),
 # L24 reports
 ("L24", "report consumes unqualified rows or revoked scopes", "ACC", 5,
  "whole report", "M", "M", "invalid publication",
  "EA11 publication gate binding", "EA11 certificate verification",
  "EA11 PUBLICATION_BLOCKED", "EA18 bypass challenge 3-5", "EA11/EA18 gates"),
 ("L24", "superseded numbers reused for decisions (N02R-matrix class)", "VER", 3,
  "downstream decisions", "M", "H", "stale claims propagate",
  "EA11 supersession notices + matrix identity", "EA11 freshness check",
  "EA11 block", "supersession test", "EA11/EA12 gates"),
 # L25 qualification issuance
 ("L25", "qualification gate false-passes (IJSDK-D01 class)", "ACC", 5,
  "whole mission scope", "L", "M", "unqualified evaluator certified",
  "EA02 central validator; EA17 certificate binds evidence",
  "EA17 certificate integrity checks", "EA10 revoked-cert detection",
  "D01-style weakened-oracle battery", "EA17/EA18 gates"),
 ("L25", "scope creep: one family's certificate covers another (INV08)", "ACC", 4,
  "unqualified families", "M", "M", "unearned trust",
  "EA17 scoped certificates", "EA17 scope verification",
  "EA10 revoke", "EA18 scope-bypass test", "EA17 gate"),
 # L26 reward generation
 ("L26", "invalid evaluation yields reward 0 / negative (punishes model for evaluator bug)",
  "REWARD", 4, "affected rollouts", "M", "H",
  "biased policy training", "EA16 invalid-reward status contract",
  "EA16 reward controls", "EA16 trainer rejects rollout",
  "EA16 synthetic tests", "EA16 gate"),
 ("L26", "reward hacking (read answers, forge tool results, skip approvals)", "REWARD", 5,
  "trained policy", "M", "M", "capability illusion (INV09)",
  "EA16 reward-hacking test suite", "EA16 anti-hack detectors",
  "EA16 zero reward + quarantine", "EA16 hacking battery", "EA16 gate"),
 # L27 publication
 ("L27", "credentials/personal paths/weights committed", "MAL", 4, "repo",
  "H (publish_check)", "M", "security/privacy incident",
  "AGENTS.md + publish gate on every commit", "publish_check.py findings count",
  "block commit", "publish_check synthetic control", "standing repo rule"),
 ("L27", "final evidence diverges from claimed numbers", "ACC", 4, "report",
  "M", "H", "unreproducible claims", "EA11 evidence-bound claims",
  "EA18 acceptance re-derivation", "EA11 block",
  "EA18 clean-checkout campaign", "EA18/EA19 gates"),
]


def main() -> int:
    modes = []
    for (layer, mode, cls, sev, impact, det, rec, cont,
         prev, detec, conta, reg, qual) in M:
        modes.append({
            "mode_id": f"FM-{len(modes)+1:03d}",
            "layer": layer,
            "failure_mode": mode,
            "failure_class": cls,
            "severity": sev,
            "potential_affected_trials": impact,
            "detectability": det,
            "recoverability": rec,
            "downstream_contamination": cont,
            "controls": {
                "prevention": prev, "detection": detec,
                "containment": conta, "regression_test": reg,
                "qualification_requirement": qual,
            },
        })
    critical = [m for m in modes if m["severity"] >= 4]
    by_class = {}
    for m in modes:
        by_class[m["failure_class"]] = by_class.get(m["failure_class"], 0) + 1
    by_layer = {}
    for m in modes:
        by_layer[m["layer"]] = by_layer.get(m["layer"], 0) + 1
    payload = {
        "schema": "ijeval.ea01.failure_mode_matrix",
        "schema_version": 1,
        "generated_by": "scripts/ij_eval_assurance/ea01_failure_model.py",
        "pipeline_layers": LAYERS,
        "layers_without_dedicated_modes": [
            l for l in LAYERS if l not in by_layer],
        "failure_classes_legend": {
            "ACC": "accidental implementation defect",
            "CMODE": "common-mode evaluator defect",
            "FP": "false positive", "FN": "false negative",
            "LOSS": "silent data loss", "CORRUPT": "corrupted evidence",
            "VER": "version incompatibility", "LEAK": "hidden-answer leakage",
            "REWARD": "reward hacking", "STATE": "unauthorized state effect",
            "RECOVERY": "incorrect recovery", "MAL": "malicious/malformed input"},
        "counts": {"modes": len(modes), "critical_severity_ge4": len(critical),
                   "by_class": by_class, "by_layer": by_layer},
        "modes": modes,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps(payload["counts"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
