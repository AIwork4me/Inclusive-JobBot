#!/usr/bin/env python3
"""EA00 §2.1 — historical evaluation-defect inventory generator
(mission IJ-EVAL-ASSURANCE-1.0).

Emits evidence/IJEVAL/EA00/historical_defect_inventory.json from the audited
defect ledgers of the parent missions (IJ-NANO EV01-EV07 / NA-D01-NA-D08 /
PR-D01-PR-D10 / RS01-RS08) plus defects first discovered by THIS audit
(IJE-D00x). Cross-mission entries (Atlas / IJ-SLM / IJ-SDK) are merged from
the sweep recorded in the same evidence directory.

Sources of record (per family):
  EV01-EV07   docs/IJNANO_MISSION_ORDER_V1_2.md §2;
              evidence/IJNANO/N05AR/defect_ledger.json (repair 210935c,
              audited baseline f62ddc2)
  NA-D01-08   docs/IJNANO_MISSION_ORDER_V1_1.md §4;
              evidence/IJNANO/N06A-R/defect_ledger.json (repair 031706f,
              audited f3d5817f)
  PR-D01-10   docs/IJNANO_MISSION_ORDER_V1_2_N02R_ADDENDUM.md §2-§9;
              reports/IJNANO_02R_EXPERIMENT_INTEGRITY_AUDIT.md (audited
              9b137f6; repairs 1c26c17/6c97354/c9b5e40/b0c7f44/26445d6)
  RS01-RS08   docs/IJNANO_MISSION_ORDER_V1_2R.md; root-cause and
              reconciliation reports (repair bc4555e; introduced 8e87604,
              masked b0d57e9)
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "IJEVAL" / "EA00" / "historical_defect_inventory.json"

SCHEMA = 1


def D(defect_id, mission, revision, location, behavior, root_cause, repair,
      regression, residual, eae_control, status):
    return {
        "defect_id": defect_id,
        "affected_mission": mission,
        "source_revision": revision,
        "affected_location": location,
        "original_incorrect_behavior": behavior,
        "root_cause": root_cause,
        "existing_repair": repair,
        "existing_regression_coverage": regression,
        "residual_risk": residual,
        "applicable_eae_control": eae_control,
        "verification_status": status,
    }


NANO = "IJ-NANO"
EV = f"{NANO}-1.2/N05A-R"
NAD = f"{NANO}-1.1/N06A-R"
PRD = f"{NANO}-1.2/N02R"
RS = f"{NANO}-1.2R/N02RR"

DEFECTS = [
    # ---- EV01-EV07: cognitive evaluator (comparators.py / contracts.py) ----
    D("EV01", EV, "audited f62ddc2 (repair 210935c)",
      "src/nanoagent/eval/comparators.py :: eval_state_interpretation",
      "state_interpretation matched predicates via zip(got, want) positional "
      "pairing; excess predicates were caught but missing/duplicate/"
      "contradictory predicates were not",
      "positional instead of identity-keyed predicate matching",
      "identity-keyed matching; new reason codes MISSING_PREDICATE, "
      "DUPLICATE_PREDICATE",
      "tests/ij_nano/test_n05ar_ev_concerns.py (6 red tests); evidence/"
      "IJNANO/N05AR/{red_run,green_run}.txt",
      "none noted", "EA04 parser predicates; EA05 differential evaluation",
      "REPAIRED_GREEN"),
    D("EV02", EV, "audited f62ddc2 (repair 210935c)",
      "src/nanoagent/eval/comparators.py :: eval_action_representation / "
      "eval_slot_value / _raw_reasons; contracts.py SlotSpec.optional",
      "action_representation ignored unexpected keys in response.args (no "
      "optional-arg contract) and duplicate raw JSON keys went undetected",
      "no strict argument-declaration contract; lenient raw JSON parsing",
      "ARGUMENT_UNDECLARED reason code; strict duplicate-key gate -> "
      "PARSE_INVALID; SlotSpec.optional",
      "5 red tests in test_n05ar_ev_concerns.py",
      "none noted", "EA04 structured responses (extra arguments, duplicate "
      "keys); EA07 mutants 'extra argument discarded', 'duplicate JSON key "
      "accepted'",
      "REPAIRED_GREEN"),
    D("EV03", EV, "audited f62ddc2 (repair 210935c)",
      "src/nanoagent/eval/comparators.py :: predicate_holds",
      "single predicate_holds() conflated expression EQUIVALENCE with TRUTH "
      "against observed world state; TypeError on invalid types",
      "one function serving two distinct semantics",
      "split predicates_equivalent() vs predicate_truth(pred, world); 12 "
      "TRUTH_CONTROLS in controls.py",
      "7 red tests; coverage in evidence/IJNANO/N05AR/coverage_matrix.json",
      "equivalence is only the explicitly documented contract - no general "
      "logical-equivalence reasoning claimed",
      "EA05 independent reference evaluator (independent predicate logic)",
      "REPAIRED_GREEN"),
    D("EV04", EV, "audited f62ddc2 (repair 210935c)",
      "src/nanoagent/eval/comparators.py :: canonical_label",
      "blanket canonical_label() folding merged distinct tool/entity/action "
      "identifiers (identifier collisions)",
      "case/spacing folding applied across identifier kinds",
      "kind-scoped identifier_matches(kind, aliases): labels fold; tool/"
      "entity/action exact unless declared alias",
      "red tests; recorded behavior change (v1 folded positives became "
      "collision negatives)",
      "N03 dataset authors must not emit folded identifiers",
      "EA04 closed-vocabulary responses (exact identifiers, substring "
      "collisions); EA03 dataset qualification",
      "REPAIRED_GREEN"),
    D("EV05", EV, "audited f62ddc2 (repair 210935c)",
      "src/nanoagent/eval/contracts.py SlotSpec; comparators.py check_slot",
      "a scalar answer with no unit silently inherited the hidden expected "
      "unit (missing-unit pass-through)",
      "unit comparison defaulted to the expectation's unit",
      "SlotSpec.unit_publicly_declared; new reason code UNIT_MISSING; "
      "non-finite/numeric-string remain TYPE_MISMATCH",
      "2 red tests", "none noted",
      "EA04 unit handling; EA07 mutant 'wrong unit accepted'",
      "REPAIRED_GREEN"),
    D("EV06", EV, "audited f62ddc2 (repair 210935c)",
      "src/nanoagent/eval/comparators.py MUTANTS/apply_mutant; "
      "qualification.py mutation_gate",
      "mutation testing only removed post-hoc reason codes; no "
      "comparator-level logic mutants existed",
      "test-of-the-tests gap (meta-verification weakness)",
      "9 comparator-level mutant classes, all detected with named witnesses; "
      "mutation_gate in qualification.py",
      "evidence/IJNANO/N05AR/coverage_matrix.json",
      "none noted",
      "EA07 mutation framework (historical mutants as permanent controls)",
      "REPAIRED_GREEN"),
    D("EV07", EV, "audited f62ddc2 (repair 210935c)",
      "src/nanoagent/eval/{contracts,qualification}.py",
      "16 declared reason codes vs 14 tested (PARSE_INVALID, "
      "ARGUMENT_MISMATCH untested); malformed evaluator inputs silently "
      "accepted",
      "coverage reconciliation absent; no input validation on evaluator "
      "entry",
      "contract v2: 19 declared = 19 tested; ARGUMENT_MISMATCH declared "
      "obsolete with disposition; validate_control_battery + "
      "qualify_family_scope",
      "green run ij_nano 173/173, ij_sdk 93 OK",
      "qualify_family_scope validates declarations structurally; new "
      "families verified only when their battery actually runs",
      "EA02 typed contract central validator; EA06 golden witnesses",
      "REPAIRED_GREEN"),

    # ---- NA-D01-NA-D08: runtime/execution integrity (evaluation-adjacent) --
    D("NA-D01", NAD, "audited f3d5817f (repair 031706f)",
      "src/nanoagent/gateway/gateway.py :: Transaction begin/commit",
      "nested-state aliasing: self._draft = dict(self._store) shallow copy "
      "leaked references across transaction isolation boundary",
      "shallow copy of nested state",
      "deep-copy on begin/commit",
      "tests/ij_nano/test_na_d01_transaction.py; red/green evidence/"
      "IJNANO/N06A-R/",
      "in-memory synthetic store; durable transactional storage deferred",
      "EA08 evidence/state integrity; EA16 verified environment controls",
      "REPAIRED_GREEN"),
    D("NA-D02", NAD, "audited f3d5817f (repair 031706f)",
      "src/nanoagent/core/events.py :: EventLog",
      "event hash omitted parent_id/ts_utc; restore accepted cross-trial/"
      "dangling/duplicate rows",
      "incomplete hash envelope; unvalidated restore",
      "EventLog envelope, verify_against_seal, sha256 seal digest",
      "tests/ij_nano/test_na_d02_events.py",
      "hash-format change: pre-repair logs do not verify (none persisted)",
      "EA08 evidence identity/causal parents; EA10 circuit breaker",
      "REPAIRED_GREEN"),
    D("NA-D03", NAD, "audited f3d5817f (repair 031706f)",
      "src/nanoagent/core/checkpoint.py :: restore",
      "checkpoints carried no experiment id/spec/seal/idempotency binding; "
      "restore() validated nothing; restart granted fresh budget",
      "unbound checkpoint schema; trusting restore input",
      "schema v2, CheckpointInvalid, atomic os.replace publish, "
      "BudgetController.restore() re-derives deadline",
      "tests/ij_nano/test_na_d03_checkpoint.py",
      "none noted", "EA08 recovery tests (crash/corrupt checkpoint/resume)",
      "REPAIRED_GREEN"),
    D("NA-D04", NAD, "audited f3d5817f (repair 031706f)",
      "src/nanoagent/core/budget.py :: Reservation",
      "zero-unit bypass, negative specs, no settle/unknown semantics, no "
      "max_tokens binding, reserve race",
      "unvalidated reservation arithmetic without atomicity",
      "Reservation.settle/settle_unknown, max_completion_tokens(), RLock "
      "atomicity",
      "tests/ij_nano/test_na_d04_budget.py",
      "none noted", "EA08 resource accounting (finite resource values)",
      "REPAIRED_GREEN"),
    D("NA-D05", NAD, "audited f3d5817f (repair 031706f)",
      "src/nanoagent/core/state.py :: apply_verified",
      "any nonempty source_event_id accepted for trusted facts; values "
      "stored by reference",
      "provenance not bound to a verified event log",
      "apply_verified requires bound-log event, authorized stage, typed "
      "validation, deep copies",
      "tests/ij_nano/test_na_d05_provenance.py",
      "none noted", "EA08 provenance binding; EA05 oracle independence",
      "REPAIRED_GREEN"),
    D("NA-D06", NAD, "audited f3d5817f (repair 031706f)",
      "src/nanoagent/gateway/gateway.py :: dispatch boundaries",
      "state_epoch_getter accepted but never consulted (stale-state "
      "writes after epoch bump/cancel)",
      "missing boundary checks",
      "double boundary check pre-dispatch + pre-commit; non-reversible "
      "tools require approval",
      "tests/ij_nano/test_na_d06_epoch_cancel.py",
      "none noted", "EA10 hard-stop triggers (unauthorized state effect)",
      "REPAIRED_GREEN"),
    D("NA-D07", NAD, "audited f3d5817f (repair 031706f)",
      "src/nanoagent/gateway/gateway.py :: approvals/idempotency",
      "bare reusable call_key; effect_key unbound to tool/args (forged "
      "idempotency)",
      "unbound approval/idempotency keys",
      "approval binds tool+canonical-args sha256+operation+scope+expiry; "
      "write-ahead pending mark; checkpoint export/load",
      "tests/ij_nano/test_na_d07_approval_idem.py",
      "single-process dict idempotency only",
      "EA16 reward hacking tests (forged results, skipped approvals)",
      "REPAIRED_GREEN"),
    D("NA-D08", NAD, "audited f3d5817f (repair 031706f)",
      "src/nanoagent/gateway/schema.py",
      "bounds/length/pattern silently ignored; arrays rejected; unsupported "
      "keywords accepted at registration",
      "lenient schema interpretation",
      "explicit supported-keyword set; validate_tool_schema() fails closed "
      "at registration",
      "tests/ij_nano/test_na_d08_schema.py",
      "trusted jsonschema 4.26.0 pinned but NOT installed - limited-"
      "validator fail-closed branch applies (IJE-B-002)",
      "EA04 structured responses (wrong types, overflow); EA02 contract "
      "validator",
      "REPAIRED_GREEN"),

    # ---- PR-D01-PR-D10: protocol/parser + experiment integrity ------------
    D("PR-D01", PRD, "audited 9b137f6 (repair 1c26c17)",
      "benchmarks/ij_nano/n02r/{tasks.py,arms.py} prompt rendering",
      "arms P0-P4 received no tool inventory/candidate lists while P5-P7 "
      "did; cross-arm comparisons confounded candidate exposure with "
      "constrained decoding",
      "unequal information across experimental arms",
      "information-matched arms M-P0..M-P7 in arms_v2.py; evidence/"
      "IJNANO/N02R/pr_d01_information_manifest.json; audit script "
      "scripts/ij_nano/n02r_pr_audit.py",
      "tests/ij_nano/test_n02r_pr_concerns.py (24/24)",
      "experiment 36bfed1d55a9987b remains diagnostic evidence",
      "EA03 task contracts (public input equality); EA11 matched "
      "comparisons", "REPAIRED_GREEN"),
    D("PR-D02", PRD, "audited 9b137f6 (repair 1c26c17)",
      "benchmarks/ij_nano/n02r/arms.py P5 arm + parser",
      "P5 supplied record_answer(args_json) but the parser required a real "
      "business tool name - contract-valid responses rejected (false "
      "negatives)",
      "request/response contract mismatch within one arm",
      "split P5A (native business tools) / P5B (declared record_answer), "
      "arms_v2.py",
      "tests/ij_nano/test_n02r_pr_concerns.py",
      "none noted", "EA04 tool-call contracts; EA05 differential paths",
      "REPAIRED_GREEN"),
    D("PR-D03", PRD, "audited 9b137f6 (repair 1c26c17)",
      "benchmarks/ij_nano/n02r/arms.py P7 arm",
      "P7 had degenerate/empty candidate sets for slot_extraction and "
      "structured_action families",
      "missing applicability registry",
      "preregistered applicability registry + new P7S two-stage protocol, "
      "arms_v2.py",
      "tests/ij_nano/test_n02r_pr_concerns.py",
      "none noted", "EA03 task applicability qualification",
      "REPAIRED_GREEN"),
    D("PR-D04/D05", PRD, "audited 9b137f6 (repair 1c26c17)",
      "benchmarks/ij_nano/n02r/arms.py :: _closed_set_find, "
      "_coerce_slot_value, _kv_scan, _payload_from_json, parse_response; "
      "scorer.score",
      "contradictory answers accepted (candidate-ordering resolution); "
      "multiple tool calls collapsed; unexpected args discarded; no "
      "warnings/raw/normalization audit fields; +2 adjacent defects "
      "(sentence punctuation blocking, ordering-luck ambiguity)",
      "parser resolved ambiguity by candidate ordering instead of rejecting",
      "parser v2 in arms_v2.py; gate N02R_PARSER_EVALUATOR_INTEGRITY_GO "
      "(evidence/IJNANO/N02R/parser_evaluator_qualification.json)",
      "tests/ij_nano/test_n02r_pr_concerns.py; full ij_nano suite 206/206",
      "none noted",
      "EA04 parser qualification (ambiguity, multiple candidates, "
      "contradictions); EA07 mutants 'contradictory answer accepted', "
      "'identifier substring matching'", "REPAIRED_GREEN"),
    D("PR-D06", PRD, "audited 9b137f6 (repair 1c26c17)",
      "benchmarks/ij_nano/n02r/controller.py :: _identity",
      "experiment identity omitted chat template, DLL SHAs, GPU identity, "
      "evaluator/parser module hashes, quantization; resume could mix "
      "environments",
      "incomplete identity binding",
      "controller_v2.py full binding; resume guard refuses identity "
      "mismatch",
      "tests/ij_nano/test_n02r_pr_concerns.py",
      "36bfed1d55a9987b run-level caveats apply to all its trials",
      "EA08 mandatory evidence identity; EA10 evidence-identity-change "
      "trigger", "REPAIRED_GREEN"),
    D("PR-D07", PRD, "audited 9b137f6 (repair 1c26c17)",
      "benchmarks/ij_nano/n02r controller session code :: wait_ready",
      "launched PID assigned as socket owner without verification (GPU "
      "engine identity unproven)",
      "assumed rather than verified socket ownership",
      "controller_v2.py netstat LISTEN socket-owner PID must equal "
      "launched PID, fail-closed",
      "tests/ij_nano/test_n02r_pr_concerns.py",
      "36bfed1d55a9987b run-level caveats", "EA08 engine identity binding",
      "REPAIRED_GREEN"),
    D("PR-D08/D09", PRD, "audited 9b137f6 (repair 1c26c17)",
      "benchmarks/ij_nano/n02r/controller.py trial records",
      "raw responses truncated to 4,000 chars; no cached tokens/timings/"
      "stop types; SSE reconciliation blind to reasoning channel",
      "lossy evidence capture",
      "controller_v2.py endpoint-specific telemetry, NOT_CAPTURED/"
      "UNAVAILABLE markers, content-addressed runs/<id>/responses/"
      "<trial_id>.json artifacts",
      "tests/ij_nano/test_n02r_pr_concerns.py",
      "36bfed1d55a9987b run-level caveats",
      "EA08 complete sanitized raw response; EA11 resource metrics "
      "(missing telemetry never zero)", "REPAIRED_GREEN"),
    D("PR-D10", PRD, "audited 9b137f6 (repair 26445d6)",
      "benchmarks/ij_nano/n02r plan arithmetic / analyzer",
      "plan claimed 2,160 unique trials; actual unique trials 2,016 "
      "(later corrected plan 2,184 / 2,256-slot accounting)",
      "denominator arithmetic error (duplicate counting)",
      "reconciled via scripts/ij_nano/n02r_analyze_v2.py denominators "
      "block",
      "n02r_analyze_v2 output", "none noted",
      "EA11 denominator reconciliation (planned vs applicable vs unique)",
      "RECONCILED"),

    # ---- RS01-RS08: offline rescore catastrophe + reconciliation ----------
    D("RS01", RS, "introduced 8e87604, masked b0d57e9, repaired bc4555e "
      "(defective line at 26445d6)",
      "scripts/ij_nano/n02r_rescore.py:71 :: artifact stage loading",
      "stage, path, http_json, http_error, latency = art['stages'][-1] "
      "unpacked the persisted DICT as a tuple (dict iteration yields keys); "
      "http_json became the string 'http', the isinstance guard substituted "
      "None, and ALL 1,397 offline-rescored rows of ec5b95357e960f99 were "
      "sealed PARSE_INVALID with corrupted telemetry (588 false negatives, "
      "0 false positives)",
      "positional unpacking of a persisted dictionary (schema change "
      "between writer and reader)",
      "scripts/ij_nano/n02rr_replay_lib.py key-based schema-validated "
      "loader; ArtifactIntegrityError -> EVIDENCE_INSUFFICIENT (never a "
      "model failure); defective semantics preserved as "
      "mutant_unpack_last_stage(); rewritten fail-closed n02r_rescore.py",
      "evidence/IJNANO/N02RR/rs01_red_reproduction.json; replay "
      "qualification gate (19 controls, mutant rejected); tests/ij_nano/"
      "test_n02rr_replay_qualification.py",
      "original defective evidence preserved sealed by design",
      "EA07 historical mutant (mandatory); EA08 artifact loader controls; "
      "EA09 canaries (artifact failure controls)",
      "REPAIRED_GREEN_SEALED"),
    D("RS02", RS, "repaired bc4555e",
      "scripts/ij_nano/n02rr_replay_lib.py :: replay P7S reconstruction",
      "replay scored only the final stage; stage-2 request derivation from "
      "the EXPECTED rather than ACTUAL stage-1 tool let wrong selections "
      "hide behind correct-looking final answers",
      "single-stage scoring of a two-stage protocol",
      "causal reconstruction: stage-1 selection recomputed from preserved "
      "response; stage-2 payload verified against ACTUAL selection; "
      "EVIDENCE_INCONSISTENT_STAGE2_TOOL class",
      "qualification controls 5/6/6b; p7s_reconstruction fields in "
      "trial_reconciliation.jsonl (30/30 consistent, 23 wrong selections "
      "propagate visibly)",
      "P7S conclusions only n=10 - statistically inconclusive",
      "EA04 multi-stage responses; EA05 differential; EA07 mutant 'wrong "
      "stage-one selection hidden by stage two'", "REPAIRED_GREEN"),
    D("RS03", RS, "repaired bc4555e",
      "evidence chain (2,184 slots)",
      "no end-to-end verification existed that identity, roster, hashes, "
      "schema, provenance and replay semantics agreed across the corpus",
      "missing whole-chain verification",
      "scripts/ij_nano/n02rr_evidence_verify.py -> evidence/IJNANO/N02RR/"
      "evidence_verification.json (2,184/2,184 at six levels, 0 findings)",
      "gate N02R_QUANTITATIVE_EVIDENCE_RECONCILED",
      "none noted", "EA08 end-to-end evidence integrity; EA09 preflight "
      "canaries", "VERIFIED"),
    D("RS04-RS08", RS, "repaired bc4555e",
      "scripts/ij_nano/n02rr_analyze.py (statistics/telemetry)",
      "unpaired/unmatched task sets compared directly; missing telemetry "
      "treated as empty/zero; 'absent evidence = empty output' failure "
      "conflation; equivalence implied from overlapping CIs; budget-panel "
      "mislabeled as reasoning-budget sweep",
      "statistical method defects (matching, missingness, claims discipline)",
      "paired McNemar + Newcombe CIs on intersected applicable tasks; "
      "sample counts for every mean (missing never zero); corrected "
      "failure taxonomy; no equivalence claims; corrected budget-panel "
      "labeling",
      "evidence/IJNANO/N02RR/corrected_protocol_matrix.json; withdrawn-"
      "claims list in reconciliation report §8",
      "N02R v1 matrix superseded - must not drive N03 protocol freezes",
      "EA11 qualified statistics (denominators, matched comparisons, "
      "resource metrics); EA12 historical revalidation",
      "REPAIRED_GREEN"),

    # ---- defects first discovered by THIS audit (EA00) --------------------
    D("IJE-D001", "IJ-EVAL-ASSURANCE-1.0/EA00", "bc4555e (audited HEAD)",
      "scripts/ij_nano/n02rr_replay_lib.py:326-330 (coercion) + "
      "scripts/ij_nano/n02rr_analyze.py:86,97,143-148,291 (consumption) + "
      "scripts/ij_nano/n02r_rescore.py:118 (sealing)",
      "a replay/evaluator EXCEPTION is coerced to semantic_correct=False; "
      "classification layers label it REPLAY_ERROR/EVIDENCE_INSUFFICIENT "
      "but the production analyzer computes r['sem']=bool(verdict) with NO "
      "eligibility filter, so such rows enter semantic rates, paired tests "
      "and the headline PASS count as ordinary model failures",
      "INV01 violation surface: boolean verdict field doubles as evaluation-"
      "status field; consumers free to ignore the labels",
      "PENDING - to be closed by EA02 eligible_for_semantic_statistics + "
      "typed verdict/status separation (SemanticVerdict.NOT_EVALUABLE)",
      "evidence/IJEVAL/EA00/n02rr_residual_risk_reproduction.json (R1+R3: "
      "injected headline 870/2184 -> 871/2186; sealed corpus has ZERO such "
      "rows so published 1.2R headline unaffected)",
      "structural/latent: any future corpus with replay errors or evidence-"
      "insufficient rows would be silently contaminated",
      "EA02 contract validator; EA11 analyzer eligibility; EA09 in-flight "
      "NOT_EVALUABLE controls; EA10 circuit breaker",
      "REPRODUCED_REPAIR_PENDING"),
    D("IJE-D002", "IJ-EVAL-ASSURANCE-1.0/EA00", "bc4555e (audited HEAD)",
      "scripts/ij_nano/n02rr_replay_lib.py classify_failure + verdict "
      "fields (P7S path)",
      "a causally impossible two-stage response (stage-2 payload "
      "contradicts the ACTUAL stage-1 selection) retains "
      "semantic_correct=True; only failure_class="
      "EVIDENCE_INCONSISTENT_STAGE2_TOOL signals invalid evidence, and the "
      "analyzer ignores that label too (counted as semantic PASS)",
      "verdict decided from final payload alone; evidence-consistency "
      "carried only in a side label",
      "PENDING - same EA02/EA05 closure as IJE-D001 (evidence-invalid "
      "rows must become NOT_EVALUABLE, not PASS)",
      "evidence/IJEVAL/EA00/n02rr_residual_risk_reproduction.json (R2)",
      "structural/latent (zero occurrences in sealed corpus)",
      "EA02 invalid-combination validator (REPLAY/inconsistent + CORRECT "
      "illegal); EA04 multi-stage; EA05 differential",
      "REPRODUCED_REPAIR_PENDING"),
]


def main() -> int:
    cross = ROOT / "evidence" / "IJEVAL" / "EA00" / "cross_mission_sweep.json"
    cross_entries = []
    if cross.exists():
        cross_entries = json.loads(
            cross.read_text(encoding="utf-8")).get("defects", [])
    payload = {
        "schema": "ijeval.ea00.historical_defect_inventory",
        "schema_version": SCHEMA,
        "generated_by": "scripts/ij_eval_assurance/ea00_defect_inventory.py",
        "families": {
            "ij_nano_EV": 7, "ij_nano_NA-D": 8, "ij_nano_PR-D": 10,
            "ij_nano_RS": 8, "ijeval_new": 2,
            "cross_mission": len(cross_entries),
        },
        "defects": DEFECTS + cross_entries,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"total": len(payload["defects"]),
                      "families": payload["families"],
                      "out": str(OUT.relative_to(ROOT))}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
