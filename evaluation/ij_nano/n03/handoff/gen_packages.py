#!/usr/bin/env python3
"""Generate Batch B/C/D qualification handoff packages (IJ-NANO-1.3S
order section 4: publish each batch's package as soon as ready)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BASE = ROOT / "evaluation" / "ij_nano" / "n03"

COMPONENTS = {
  "task_contracts_taxonomy": "evaluation/ij_nano/n03/taxonomy.json",
  "public_case_roster": "evaluation/ij_nano/n03/dataset/public/n03_cases.public.jsonl",
  "dev_expectations": "evaluation/ij_nano/n03/dataset/expectations/n03_dev_expectations.jsonl",
  "confirmation_protected_manifest_hashonly": "evidence/IJNANO/N03/dataset/confirmation_protected_manifest.json",
  "model_registry": "evaluation/ij_nano/n03/model_registry.json",
  "slot_manifest": "evidence/IJNANO/N03/dataset/slot_manifest.json",
  "dataset_verification_report": "evidence/IJNANO/N03/dataset/verification_report.json",
  "dataset_build_manifest": "evidence/IJNANO/N03/dataset/build_manifest.json",
  "schema_conformance_report": "evidence/IJNANO/N03/dataset/schema_conformance.json",
  "batch_a_preservation_proof": "evidence/IJNANO/N03/dataset/batch_a_preservation.json",
}

SPEC = {
 "B": {
  "range": "C09-C16", "title": "generation and extraction",
  "per_primitive": {
   "C09": ("flat JSON object per declared schema",
           "record equals the public details after canonicalization",
           "type mutation; dropped/extra field; duplicate key"),
   "C10": ("nested JSON with exact array cardinality",
           "document equals public details; array length equals declared",
           "cardinality violation; level flattening; truncation"),
   "C11": ("one DSL statement per line, declared tokens only",
           "grammar-valid and step-count-consistent program",
           "lowercased action token; missing argument; arity error"),
   "C12": ("slot record with declared normalizations",
           "slot values surface in the message; keys within schema",
           "value corrupted; slot omitted without null; distractor fill"),
   "C13": ("one candidate id (mention resolution)",
           "unique attribute-agreement match per construction",
           "recency-only resolution; non-unique match accepted"),
   "C14": ("numeric JSON values, exact magnitude and sign",
           "values appear in text (comma forms normalized)",
           "rounding drift; string-typed number; field swap"),
   "C15": ("value + canonical unit code",
           "arithmetic recomputation from supplied factors",
           "inverted factor; double conversion; unit mutation"),
   "C16": ("grounded short answer",
           "answer recomputable by query over the tool output",
           "stale-note capture; ungrounded inference; field confusion")}},
 "C": {
  "range": "C17-C24", "title": "state, planning and recovery",
  "per_primitive": {
   "C17": ("true/false per queried predicate id",
           "predicate evaluation over the typed state",
           "initial-state judgment after transitions; invented predicate"),
   "C18": ("list of 'a before b' dependency edges",
           "pre/eff intersection algebra (set equality)",
           "spurious edge; missing edge; serialization bias"),
   "C19": ("ordered action list",
           "SIMULATION: preconditions hold per step and the goal "
           "predicate holds at the end - any valid plan is CORRECT, the "
           "reference plan is a witness, never the answer key",
           "precondition violation; goal miss; hallucinated action"),
   "C20": ("ids of holding branches only",
           "condition evaluation over state; mutual exclusion",
           "failed-condition branch; both exclusive branches"),
   "C21": ("continuation plan from CURRENT state",
           "simulation from current state reaches goal; no prefix "
           "re-execution",
           "stale-plan persistence; prefix amnesia; goal drop"),
   "C22": ("is_error boolean + catalog code",
           "error-envelope rule (200 status never clears a body error)",
           "masked error; false error; code confusion"),
   "C23": ("corrected argument record",
           "diff equals exactly the diagnosed field with the "
           "diagnosis-driven fix",
           "no-op retry; over-correction; unrelated mutation"),
   "C24": ("fallback id + action + arguments",
           "first condition-holding declared fallback; template args",
           "primary retry; condition-ignoring fallback; arg mismatch")}},
 "D": {
  "range": "C25-C32", "title": "decision and robustness",
  "per_primitive": {
   "C25": ("STOP or CONTINUE token",
           "goal predicate over state",
           "premature termination; unnecessary continuation"),
   "C26": ("ACT or ASK + missing slot names",
           "sufficiency vs required schema; invalid counts as missing",
           "unnecessary clarification; missing clarification; optional "
           "confusion"),
   "C27": ("ESCALATE + rule id, or PROCEED",
           "threshold predicate evaluation over policy",
           "threshold error; rule omission; spurious escalation"),
   "C28": ("typed answer from the relevant span",
           "target present in document; decoys differ",
           "distractor capture; stale value; hallucination"),
   "C29": ("id, or AMBIGUOUS + conflicting ids",
           "candidate duplication rule (declared ambiguity)",
           "silent disambiguation; over-flagging"),
   "C30": ("canonical op string op:entity[:extra]",
           "entity token verbatim; pair-consistent across languages",
           "digit drift; language echo; canonical divergence"),
   "C31": ("answer with per-claim citations",
           "citations exist and cover required claims",
           "uncited claim; phantom citation; contradiction"),
   "C32": ("answer or ABSTAIN marker",
           "declared sufficiency: fact present iff answerable",
           "confident-wrong guess; over-abstention; marker misuse")}},
}


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    roster = [json.loads(l) for l in
              (BASE / "dataset" / "public" /
               "n03_cases.public.jsonl").read_text(encoding="utf-8").splitlines()]
    for batch, spec in SPEC.items():
        prims = [p for p in sorted(spec["per_primitive"])
                 if any(r["primitive"] == p for r in roster)]
        cases = [r for r in roster if r["primitive"] in prims]
        pkg_dir = BASE / "handoff" / f"batch_{batch.lower()}"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        # per-batch requirement digest components include the batch docs
        rows = ["| Primitive | Parser surface | Oracle rule | Critical "
                "mutation targets |", "|---|---|---|---|"]
        for p in sorted(spec["per_primitive"]):
            rows.append(f"| {p} | " + " | ".join(spec["per_primitive"][p])
                        + " |")
        doc = (f"# Batch {batch} ({spec['range']}) — {spec['title']}\n\n"
               "Consumer: IJ-EVAL-ASSURANCE (PR #13). Parser semantics, "
               "independent-oracle rules and mutation targets per "
               "primitive. Cross-cutting rules from the Batch A package "
               "(`../batch_a/parser_semantics.md`) apply unchanged "
               "(key-based access, no substring membership, EMPTY_OUTPUT "
               "separation, exception-masking immunity).\n\n"
               + "\n".join(rows) + "\n\n"
               "Plan-scoring rule (C19/C21): validity is established by "
               "simulating the emitted plan against the published "
               "preconditions/effects and evaluating the goal predicate — "
               "alternative valid plans are CORRECT; the reference plan "
               "is a witness, not an answer key.\n\n"
               "No EA gate is granted by this package.\n")
        (pkg_dir / "requirements.md").write_text(doc, encoding="utf-8")
        pkg = {
          "package_id": f"n03-batch-{batch.lower()}-qualification-package",
          "version": "v1",
          "scope": f"{spec['range']}: {len(cases)} cases in the complete "
                   "960-case roster (see build_manifest for split counts)",
          "producer": "IJ-NANO lane (PR #11), IJ-NANO-1.3S",
          "consumer": "IJ-EVAL-ASSURANCE (PR #13); grants NO EA gate",
          "requirements_doc": f"evaluation/ij_nano/n03/handoff/batch_"
                              f"{batch.lower()}/requirements.md",
          "components_sha256": {k: sha(ROOT / v)
                                for k, v in COMPONENTS.items()} |
                               {"requirements_doc": sha(
                                   pkg_dir / "requirements.md")},
          "note": "components are the complete-roster artifacts; the "
                  "pinned git revision of this package freezes them",
        }
        (pkg_dir / "package.json").write_text(
            json.dumps(pkg, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print(f"batch {batch}: package written ({len(cases)} cases, "
              f"{len(pkg['components_sha256'])} digests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
