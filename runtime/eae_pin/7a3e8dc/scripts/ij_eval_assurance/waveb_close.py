"""Wave B closure: rule-level coverage matrix, versioned reconciliation
record, and the EA03-EA08 gate certificate issued through the real
QualificationAuthority (digest-bound, persisted registry).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)          # repo-root-bound: relative refs resolve


def rel(p) -> pathlib.Path:
    """Repo-relative evidence refs (no local identities in the published
    registry — the sensitive scanner enforces this)."""
    return pathlib.Path(os.path.relpath(pathlib.Path(p), ROOT))

from eval_assurance.qualification.store import (         # noqa: E402
    QualificationAuthority, CertificateStore)

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
SRC = ROOT / "src" / "eval_assurance"

# ---------------------------------------------------------------------------
# rule-level coverage matrix: every pinned rule -> concrete control ids
# ---------------------------------------------------------------------------
W = "witness:"   # prefix for dual-path witness ids (dualpath_witnesses)
F = "fault:"     # production-logic mutation controls
G = "gt:"        # reused ground-truth controls (597 battery, classes A-F)
D = "gtd:"       # preregistered GT-D probes
X = "ea08:"      # end-to-end evidence-integrity controls
B = "obligb:"    # reused obligation-B response witnesses (40)

MATRIX = [
    # -- pinned parser_semantics.md, per-primitive surfaces ---------------
    {"rule": "C01 bare label or single-field intent/label JSON",
     "source": "parser_semantics.md", "controls":
     [W + "C01-*-pos", W + "C01-*-posf", W + "C01-*-wrong",
      F + "P10_multiline_label_first", B + "C01-*"]},
    {"rule": "C02 JSON object with exactly the five schema fields",
     "source": "parser_semantics.md", "controls":
     [W + "C02-*-pos", W + "C02-*-extra", W + "C02-*-missing",
      F + "P03_drop_extra_fields", F + "P04_default_missing_fields"]},
    {"rule": "C02 unknown_flags object of booleans",
     "source": "parser_semantics.md", "controls":
     [W + "C02-*-flags", F + "P13_predicate_dropped",
      F + "E03_flags_ignored"]},
    {"rule": "C03 formatting: plain lines, no markers, blanks ignored",
     "source": "parser_semantics.md", "controls":
     [W + "C03-formatting-pos", W + "C03-formatting-mal",
      F + "P09_markers_tolerated", F + "E07_c03_order_insensitive"]},
    {"rule": "C03 formfill: single-field JSON {field: value}",
     "source": "parser_semantics.md", "controls":
     [W + "C03-formfill-pos", W + "C03-formfill-posf",
      W + "C03-formfill-wrong", "reconciliation:formfill-pair-compare"]},
    {"rule": "C03 oneedit: exactly one line",
     "source": "parser_semantics.md", "controls":
     ["interpreter-rule (no dev case; contract-complete implementation; "
      "confirmation-scope only)"]},
    {"rule": "C04 id list / JSON list; explicit empty result",
     "source": "parser_semantics.md", "controls":
     [W + "C04-*-pos", W + "C04-*-alt", W + "C04-*-wrong",
      F + "P14_empty_list_not_explicit (EQUIVALENT on current dataset, "
      "justified)"]},
    {"rule": "C04 ordering matters only when a sort is declared",
     "source": "parser_semantics.md", "controls":
     [W + "C04-*-alt", F + "E02_c04_subset_match", G + "class-D"]},
    {"rule": "C05 TRUE/FALSE or {\"decision\": bool}; hedges are model "
             "failures",
     "source": "parser_semantics.md", "controls":
     [W + "C05-*-pos", W + "C05-*-posf", W + "C05-*-mal",
      F + "P08_hedge_unparseable", F + "E06_inverted_decision"]},
    {"rule": "C06/C07/C08 bare id or single-field JSON",
     "source": "parser_semantics.md", "controls":
     [W + "C06-*-pos", W + "C07-*-pos", W + "C08-*-pos",
      W + "C0[6-8]-*-posf", F + "E01_any_catalog_member"]},
    # -- cross-cutting historical-immunity rules ---------------------------
    {"rule": "no positional unpacking of persisted stages (N02R root "
             "cause)", "source": "parser_semantics.md", "controls":
     ["structural: key-based access only in production/parser.py + "
      "interpreter.py (import- and code-audit controls)",
      D + "GT-D01..GT-D05"]},
    {"rule": "markdown fence tolerance", "source": "parser_semantics.md",
     "controls": [W + "*-posf", F + "P12_fences_not_stripped"]},
    {"rule": "duplicate JSON keys are a structural defect",
     "source": "parser_semantics.md", "controls":
     [W + "*-dup", F + "P02_duplicate_keys_accepted"]},
    {"rule": "empty model output is its own class",
     "source": "parser_semantics.md", "controls":
     [W + "*-empty", F + "P05_empty_as_incorrect",
      F + "P06_empty_as_software", X + "X07_missing_vs_empty_distinction"]},
    {"rule": "substring matching never sufficient; exact token equality",
     "source": "parser_semantics.md", "controls":
     [F + "E01_any_catalog_member", W + "*-wrong",
      "code-audit: single normalization point in production/parser.py"]},
    {"rule": "parse failures are PARSER_SOFTWARE_ERROR, never model "
             "failures", "source": "parser_semantics.md", "controls":
     [W + "*-swerr", F + "P08_hedge_unparseable",
      F + "P06_empty_as_software"]},
    # -- evaluator rules ----------------------------------------------------
    {"rule": "typed comparison per primitive against stored truth",
     "source": "dual-path contract", "controls":
     [W + "*-pos", W + "*-wrong", F + "E08_c02_action_only",
      F + "E06_inverted_decision"]},
    {"rule": "valid alternative solutions accepted (ties/order freedom)",
     "source": "order section 2", "controls":
     [W + "C04-*-alt", F + "E05_alternatives_ignored (EQUIVALENT on "
      "current dataset, justified)", G + "class-E"]},
    {"rule": "structural vs semantic model failures stay distinct",
     "source": "order section 2", "controls":
     [W + "*-mal", F + "E04_structural_conflation"]},
    {"rule": "unresolved disagreement -> NOT_EVALUABLE + quarantine",
     "source": "order section 2", "controls":
     ["class-discipline test (test_dualpath_waveb): every detected fault "
      "surfaces as NOT_EVALUABLE or a software class"]},
    # -- ground-truth rules (reused, independently justified) ---------------
    {"rule": "ground truth independently derivable from public payload",
     "source": "EA03 obligation A", "controls":
     [G + "597 controls classes A-F (0 escapes)", D + "38 probes"]},
    {"rule": "stored answers cross-checked, never authoritative",
     "source": "EA03 obligation A", "controls":
     [G + "class-C coupled corruption (70 controls)"]},
    # -- evidence integrity (EA08) ------------------------------------------
    {"rule": "trusted raw artifact capture and replay",
     "source": "order section 2", "controls":
     [X + "X06_offline_replay_agreement", X + "X03_artifact_tamper"]},
    {"rule": "verification receipts bind trial+execution identity",
     "source": "EA-R02", "controls":
     [X + "X01X02_verification_receipts"]},
    {"rule": "duplicate trial rejection; exact resume",
     "source": "order section 2", "controls":
     [X + "X04_duplicate_trial_rejection", X + "X05_resume_exactness"]},
]

# ---------------------------------------------------------------------------
# reconciliation record (order section 1: correct genuine defects through
# versioned evidence reconciliation)
# ---------------------------------------------------------------------------
RECONCILIATION = {
    "schema": "ijeval.ea03_n03.dualpath_reconciliation.v1",
    "defect_id": "IJE-WB-D01",
    "title": "reference oracle formfill comparator shape mismatch",
    "discovered_by": "EA04 dual-path formfill witnesses (new family-level "
                     "witness coverage; the prior 40 obligation-B "
                     "witnesses covered C03 formatting only)",
    "symptom": "every CORRECT formfill answer scored INCORRECT by the "
               "reference path (production CORRECT vs reference "
               "INCORRECT -> NOT_EVALUABLE) on all 20 dev formfill cases",
    "root_cause": "oracle._compare_typed compared the interpreter's raw "
                  "single-field dict {field: value} against the derived "
                  "{'field': F, 'value': V} record shape",
    "fix": "exact (field, value) pair comparison in oracle._compare_typed "
           "AND strict pair comparison in production _eval_c03 (both "
           "sides exact; no silent normalization)",
    "verification": {
        "positive_witnesses_after_fix": "158/160 CORRECT (all "
                                        "families)",
        "empty_truth_formatting_cases": "2/160 EMPTY_OUTPUT (agreed by "
                                        "both paths; disclosed "
                                        "limitiation: a formatting case "
                                        "whose truth is an empty line "
                                        "list cannot be scored CORRECT "
                                        "under the pinned output "
                                        "contract)",
        "gt_battery_rerun": "160/160 VALID, 38/38 probes, 597/597 "
                            "mutations detected, 40/40 obligation-B "
                            "witnesses (no regression)"},
    "prior_numbers_unchanged": True,
}


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    wit = json.loads((EVID / "dualpath_witnesses.json")
                     .read_text(encoding="utf-8"))
    camp = json.loads((EVID / "production_mutation_campaign.json")
                      .read_text(encoding="utf-8"))
    ea08 = json.loads((rel(EVID / "ea08_end_to_end.json"))
                      .read_text(encoding="utf-8"))

    # -- coverage matrix with realized control counts -----------------------
    realized = {
        "dualpath_witnesses": wit["summary"]["total"],
        "production_faults": camp["summary"]["faults"],
        "production_faults_detected": camp["summary"]["detected"],
        "production_faults_equivalent_justified":
            camp["summary"]["equivalent"],
        "gt_controls_reused": 597,
        "gtd_probes_reused": 38,
        "obligation_b_witnesses_reused": 40,
        "ea08_evidence_controls": ea08["summary"]["controls"],
    }
    proposal = {"original_minimum": 500,
                "delivered_total": sum(realized[k] for k in
                                       ("dualpath_witnesses",
                                        "production_faults",
                                        "gt_controls_reused",
                                        "gtd_probes_reused",
                                        "obligation_b_witnesses_reused",
                                        "ea08_evidence_controls")),
                "reconciliation_statement":
                    "The 597 GT controls are reused unchanged (they cover "
                    "truth-derivation rules). They are NOT counted as "
                    "substitutes for the new parser/evaluator/evidence "
                    "controls: those categories are covered by the 116 "
                    "dual-path witnesses, 20 production-logic faults and "
                    "6 EA08 evidence controls added here. No redundant "
                    "witness inflation: two production faults are "
                    "declared EQUIVALENT on the current dataset with "
                    "recorded justifications rather than fake detections."}
    (rel(EVID / "rule_coverage_matrix.json")).write_text(json.dumps(
        {"schema": "ijeval.ea03_n03.rule_coverage_matrix.v1",
         "generated_utc": stamp, "matrix": MATRIX,
         "realized_controls": realized,
         "original_proposal_reconciliation": proposal},
        indent=1, ensure_ascii=False), encoding="utf-8")

    (rel(EVID / "dualpath_reconciliation.json")).write_text(json.dumps(
        RECONCILIATION, indent=1, ensure_ascii=False), encoding="utf-8")

    # -- gate certificate through the REAL QualificationAuthority -----------
    reg_dir = EVID / "certificates"
    reg_dir.mkdir(parents=True, exist_ok=True)
    authority = QualificationAuthority(persist_to=rel(reg_dir /
                                                      "registry.json"))
    store = authority.issue_qualification(
        scope="semantic",   # aggregation scope category (eligibility lookup key)
        dataset_id="n03-batch-a-dev160@d23de5a",
        parser_version="eval_assurance.production.parser@1",
        evaluator_version="eval_assurance.production.evaluator@1",
        reference_evaluator_version="eval_assurance.reference.oracle@v2+formfill-pair-fix",
        dataset_file=rel(EVID / "pinned" / "n03_cases.public.jsonl"),
        task_contract_file=rel(EVID / "pinned" / "parser_semantics.md"),
        parser_file=rel(SRC / "production" / "parser.py"),
        interpreter_file=rel(SRC / "reference" / "interpreter.py"),
        evaluator_file=rel(SRC / "production" / "evaluator.py"),
        reference_oracle_file=rel(SRC / "reference" / "oracle.py"),
        witness_suite_file=rel(EVID / "dualpath_witnesses.json"),
        mutation_report_file=rel(EVID / "production_mutation_campaign.json"),
        evidence_files=[
            rel(EVID / "gt_mutation_coverage_dev160.json"),
            rel(EVID / "ground_truth_qualification_dev160_v2.json"),
            rel(EVID / "reconciliation_dev160.json"),
            rel(EVID / "response_witnesses.json"),
            rel(EVID / "ea08_end_to_end.json"),
            rel(EVID / "rule_coverage_matrix.json"),
            rel(EVID / "dualpath_reconciliation.json"),
            rel(EVID / "intake_verification.json"),
        ],
        replay_contract="content-addressed artifact replay "
                        "(dualpath.DualPathSession.replay)",
        protocol="cpu-dualpath-qualification:N03_BATCH_A_DEV_CPU_DUALPATH",
        limitations="CPU software qualification of the dual-path "
                    "evaluation stack on pinned Batch A dev inputs. NOT a "
                    "physical-runner qualification, NOT confirmation-"
                    "split coverage, and NOT all-32 cognitive "
                    "qualification (Batch A C01-C08 dev scope only). "
                    "Disclosed common-mode risks: shared pinned spec "
                    "authorship for production+reference legs; two "
                    "equivalent mutants on the current dataset "
                    "(P14/E05, justified); formatting cases with "
                    "empty-truth line lists cannot score CORRECT.")
    cert_ids = [c.certificate_id for c in store.snapshot().certificates]
    snapshot = store.snapshot()
    print("certificate issued:", cert_ids)
    print("registry generation:", snapshot.generation,
          "certificates:", len(snapshot.certificates))
    print("coverage matrix rows:", len(MATRIX),
          "realized:", realized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
