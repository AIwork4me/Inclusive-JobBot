#!/usr/bin/env python3
"""IJ-SDK: machine-readable mission dashboard.

Phase gates and final acceptance gates are reported in separate sections. A
phase gate is never counted as an acceptance gate: if the acceptance gate list
is not defined in the repository, the acceptance section says so and reports
zero mapped, rather than borrowing phase results.

Output: evidence/IJSDK/dashboard.json

Usage (PowerShell, repository root):
  python -I scripts/tools/ij_sdk_dashboard.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STATE = "MISSION_STATE_IJSDK.json"
OUT = "evidence/IJSDK/dashboard.json"
ACCEPTANCE_GATE_COUNT = 20


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def acceptance_gates(mapping: dict) -> list[dict]:
    defined = mapping.get("gate_list_present_in_repository") is True
    return [{"id": f"G{n:02d}", "status": "NOT_RUN" if defined else "UNMAPPED",
             "definition": "see mission state" if defined else "NOT_DEFINED_IN_REPOSITORY",
             "source_phase_gate": None}
            for n in range(1, ACCEPTANCE_GATE_COUNT + 1)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=OUT)
    args = parser.parse_args(argv)
    state = json.loads((REPO / STATE).read_text(encoding="utf-8"))

    phase_rows = []
    for phase, entry in state["phases"].items():
        phase_rows.append({
            "phase": phase,
            "gate": entry.get("gate"),
            "status": entry.get("status"),
            "gate_status": entry.get("gate_status", entry.get("status")),
            "progress": entry.get("progress"),
            "reopened_by": entry.get("reopened_by"),
            "previous_status": entry.get("previous_status"),
            "superseded_by": entry.get("superseded_by"),
            "evidence": entry.get("evidence", []),
        })
    tally = {s: sum(1 for r in phase_rows if r["gate_status"] == s) for s in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")}
    verdicts = {**state.get("final_verdicts", {}), **state.get("ij_sdk_1_1_verdicts", {})}
    gates = acceptance_gates(state.get("acceptance_gate_mapping", {}))

    dashboard = {
        "schema_version": 1,
        "generated_utc": utc(),
        "mission": state.get("mission"),
        "sub_mission": state.get("sub_mission"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "head": git("rev-parse", "HEAD"),
        "frozen_source_commit": state.get("frozen_source_commit"),
        "current_phase": state.get("current_phase"),
        "phase_gates": {
            "note": "Phase completion only. These are NOT final acceptance gates.",
            "tally": tally,
            "rows": phase_rows,
        },
        "final_acceptance_gates": {
            "system": "G01-G20 of the original mission order",
            "defined_in_repository": state.get("acceptance_gate_mapping", {}).get("gate_list_present_in_repository") is True,
            "mapped": state.get("acceptance_gate_mapping", {}).get("mapped", 0),
            "satisfied": state.get("acceptance_gate_mapping", {}).get("satisfied", 0),
            "total": ACCEPTANCE_GATE_COUNT,
            "rows": gates,
        },
        "verdicts": verdicts,
        "verdict_tally": {s: sum(1 for v in verdicts.values() if v == s)
                          for s in ("GO", "QUALIFIED", "FROZEN", "PASS", "BLOCKED", "FAIL", "NOT_RUN")},
        "formal_benchmark": {
            "gpu_matrix_authorized": state.get("formal_gpu_matrix_authorized") is True,
            "authorization_basis": state.get("formal_gpu_matrix_authorization"),
            "trials": {
                "note": "Formal-matrix accounting. Development qualification cases are listed separately and are never "
                        "counted as formal trials.",
                "planned_applicable_slots": 0,
                "executed": 0,
                "evidence_valid": 0,
                "business_pass": 0, "business_fail": 0, "blocked": 0, "not_run": 0, "inapplicable_cells": 0,
            },
            "development_qualification_trials": {
                "p3_conformance_pre_hardening": {"arms": 10, "cases_per_arm": 1, "counts_as_formal_evidence": False,
                                                 "status": "superseded; gate reopened by P0R"},
            },
        },
        "recovery": state.get("recovery"),
    }
    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dashboard, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {args.out}: phase gates {tally} | acceptance gates mapped "
          f"{dashboard['final_acceptance_gates']['mapped']}/{ACCEPTANCE_GATE_COUNT}, satisfied 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
