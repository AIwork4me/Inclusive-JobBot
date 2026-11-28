#!/usr/bin/env python3
"""N02R addendum section 11: classify every trial of the original
experiment (36bfed1d55a9987b) into the disposition classes:

- VALID_AS_IS            reusable within the original (native-usability,
                         diagnostic) scope
- OFFLINE_RESCORE_POSSIBLE parser-only defect; complete raw evidence kept
- DIAGNOSTIC_ONLY        request/info/applicability defects; not valid for
                         formal cross-arm causal claims
- PHYSICAL_REEXECUTION_REQUIRED P5 contract defect (PR-D02) etc.
- EVIDENCE_INSUFFICIENT  raw response truncated at the 4,000-char cap
                         (PR-D08/D09) and no complete artifact exists

The original results.jsonl is never modified."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib


def classify(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        tid = r["trial_id"]
        arm, fam = r["arm"], r["family"]
        raw = r.get("raw_trimmed")
        reasons: list[str] = []
        disposition = "VALID_AS_IS"

        # PR-D08/D09: truncated raw -> evidence insufficient for rescoring
        if raw is not None and len(raw) >= 4000:
            disposition = "EVIDENCE_INSUFFICIENT"
            reasons.append("raw response truncated at 4000-char cap")
        # PR-D02: P5 structured-action contract defect
        if arm == "P5" and fam == "structured_action":
            disposition = "PHYSICAL_REEXECUTION_REQUIRED"
            reasons.append("P5 supplied record_answer(args_json) but the "
                           "parser required a business tool name")
        # PR-D03: P7 inapplicable families
        if arm == "P7" and fam in ("slot_extraction", "structured_action"):
            disposition = "DIAGNOSTIC_ONLY"
            reasons.append("P7 has no meaningful candidate set for this "
                           "family (impossible protocol/task combination)")
        # PR-D01: information asymmetry across arms (cross-arm causal
        # comparison invalid; native-usability scope only)
        if arm in ("P0", "P1", "P2", "P3", "P4") and fam in (
                "tool_selection", "structured_action", "conditional_branch",
                "stop_continue"):
            if disposition == "VALID_AS_IS":
                disposition = "DIAGNOSTIC_ONLY"
            reasons.append("candidate/tool information not supplied to this "
                           "arm's prompt (PR-D01): native-usability scope only")
        # PR-D04: parser defects affecting verdicts in free-text/DSL arms
        if arm in ("P0", "P6") and disposition == "VALID_AS_IS":
            disposition = "OFFLINE_RESCORE_POSSIBLE"
            reasons.append("ambiguity/negation/duplicate-key parser defects "
                           "(PR-D04) - offline re-score possible with the "
                           "complete raw response")
        # PR-D06/D07: identity binding and socket-to-PID verification gaps
        # apply to the run as a whole (recorded in the audit header, not
        # per-trial): original experiment remains development/diagnostic
        # evidence at formal scope regardless of per-trial class.
        out.append({"trial_id": tid, "model": r["model"], "arm": arm,
                    "task_id": r["task_id"], "family": fam,
                    "budget": r["budget"],
                    "disposition": disposition, "reasons": reasons})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    run = pathlib.Path(args.run)
    rows = [json.loads(l) for l in
            (run / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    # trial-id uniqueness check (PR-D10 denominators feed)
    ids = [r["trial_id"] for r in rows]
    dup = [k for k, v in collections.Counter(ids).items() if v > 1]
    classified = classify(rows)
    summary = collections.Counter(c["disposition"] for c in classified)
    report = {
        "schema": "ij_nano.n02r.evidence_disposition",
        "experiment_id": run.name,
        "run_results_sha256": hashlib.sha256(
            (run / "results.jsonl").read_bytes()).hexdigest(),
        "trials_total": len(rows),
        "duplicate_trial_ids": dup,
        "run_level_caveats": [
            "PR-D06: experiment identity lacks chat-template SHA, engine DLL "
            "hashes, GPU physical identity, evaluator/parser module hashes",
            "PR-D07: socket ownership recorded from the launched PID without "
            "independent socket-to-PID verification",
            "PR-D08/D09: raw responses capped at 4,000 characters; cached-"
            "token and timing telemetry not extracted",
            "per the addendum, the original experiment is development/"
            "diagnostic evidence pending the corrected re-execution",
        ],
        "disposition_summary": dict(summary),
        "trials": classified,
    }
    out = run.parent / "evidence_disposition.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"experiment": run.name, "trials": len(rows),
                      "dispositions": dict(summary), "duplicates": dup},
                     indent=1))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
