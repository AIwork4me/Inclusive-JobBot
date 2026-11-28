#!/usr/bin/env python3
"""N02R_PARSER_EVALUATOR_INTEGRITY_GO qualification generator.

Runs the end-to-end control suite (raw API-shaped response -> parser ->
evaluator verdict) against the frozen parser (arms_v2) and evaluator
(contract v2) implementations and records the implementation hashes the
qualification binds to. The N05AR comparator qualification is retained
untouched; this gate covers the integration layer only."""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks" / "ij_nano"))
sys.path.insert(0, str(ROOT / "tests"))

from n02r import arms_v2 as arms  # noqa: E402
from n02r import scorer  # noqa: E402


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_suite() -> dict:
    """Execute tests/ij_nano/test_n02r_pr_concerns.py in a fresh process."""
    proc = subprocess.run(
        [sys.executable, "-I", "-m", "unittest", "discover",
         "-s", "tests/ij_nano", "-t", ".", "-p", "test_n02r_pr_concerns.py"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=600)
    ok = proc.returncode == 0
    tail = (proc.stdout or proc.stderr or "").strip().splitlines()[-3:]
    return {"ok": ok, "returncode": proc.returncode, "summary_tail": tail}


def coverage_probe() -> dict:
    """Confirm the mandatory-negative list maps to executed controls."""
    src = (ROOT / "tests" / "ij_nano" / "test_n02r_pr_concerns.py") \
        .read_text(encoding="utf-8")
    mandatory = [
        "Multiple competing candidate answers", "Negated candidate answer",
        "Contradictory final answer", "Unexpected tool argument",
        "Duplicate JSON key", "Duplicate DSL key",
        "Incorrect DSL slot name", "Invalid DSL header",
        "Trailing contradictory DSL content", "Malformed quantity",
        "Wrong entity", "Multiple unexpected tool calls",
        "Wrong record_answer function name", "Truncated output",
        "Missing required answer"]
    probes = {
        "Multiple competing candidate answers": "test_multiple_competing_candidates_rejected",
        "Negated candidate answer": "test_negated_candidate_rejected",
        "Contradictory final answer": "test_contradictory_final_answer_rejected",
        "Unexpected tool argument": "test_unexpected_tool_argument_visible_to_evaluator",
        "Duplicate JSON key": "test_duplicate_json_key_in_content_rejected",
        "Duplicate DSL key": "test_duplicate_dsl_key_rejected",
        "Incorrect DSL slot name": "test_incorrect_dsl_slot_name_rejected",
        "Invalid DSL header": "test_invalid_dsl_header_rejected",
        "Trailing contradictory DSL content": "test_trailing_contradictory_dsl_rejected",
        "Malformed quantity": "test_malformed_quantity_rejected",
        "Wrong entity": "test_wrong_entity_stays_rejected",
        "Multiple unexpected tool calls": "test_multiple_tool_calls_flagged",
        "Wrong record_answer function name": "test_wrong_record_answer_name_rejected_for_closed_families",
        "Truncated output": "test_truncated_output_stays_rejected",
        "Missing required answer": "test_missing_required_answer_stays_rejected",
    }
    missing = [m for m, probe in probes.items() if probe not in src]
    return {"mandatory_negatives": len(mandatory),
            "controls_present": len(mandatory) - len(missing),
            "missing": missing}


def main() -> int:
    suite_result = run_suite()
    coverage = coverage_probe()
    impl = {
        "parser": sha(ROOT / "benchmarks/ij_nano/n02r/arms_v2.py"),
        "scorer": sha(ROOT / "benchmarks/ij_nano/n02r/scorer.py"),
        "evaluator_contracts": sha(ROOT / "src/nanoagent/eval/contracts.py"),
        "evaluator_comparators": sha(ROOT / "src/nanoagent/eval/comparators.py"),
        "evaluator_units": sha(ROOT / "src/nanoagent/eval/units.py"),
        "control_suite": sha(ROOT / "tests/ij_nano/test_n02r_pr_concerns.py"),
    }
    record = {
        "schema": "ij_nano.n02r.parser_evaluator_qualification",
        "gate": "N02R_PARSER_EVALUATOR_INTEGRATION_GO",
        "generated_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "control_suite_result": suite_result,
        "mandatory_negative_coverage": coverage,
        "implementation_hashes": impl,
        "scope_note": "integration layer only; the N05AR comparator "
                      "qualification (evidence/IJNANO/N05A + N05AR) is "
                      "retained separately; no business-Oracle grant",
    }
    granted = (suite_result["ok"] and not coverage["missing"])
    record["gate_status"] = "PASS" if granted else "FAIL"
    out = ROOT / "evidence" / "IJNANO" / "N02R" / "parser_evaluator_qualification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"gate": record["gate"],
                      "status": record["gate_status"],
                      "suite_ok": suite_result["ok"],
                      "coverage": coverage["controls_present"]}, indent=1))
    return 0 if granted else 1


if __name__ == "__main__":
    sys.exit(main())
