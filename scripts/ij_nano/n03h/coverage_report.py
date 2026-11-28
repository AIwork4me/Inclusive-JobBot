"""Final acceptance coverage accounting (IJ-NANO-48H order section 23).

Consolidates planned vs executed slots across every campaign scope
with seal status, physical attempts, EAE authorization checksums and
remaining work — the exact numbers the final report must report
independently, never summing overlapping planned or reused slots into
a misleading physical count.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[3]
RUNS = ROOT / "runs" / "n03h"
STATE = ROOT / "MISSION_STATE_IJNANO_48H.json"

SCOPES = {
    "E1 Batch A dev (AUTH-2A-RQ)": {
        "experiment": "N03-AUTH2-DEVELOPMENT-BATCH-A-v2-RQ",
        "planned": 480},
    "E1 Batch B dev (AUTH-2B)": {
        "experiment": "N03-AUTH2-DEVELOPMENT-BATCH-B-v1",
        "planned": 480},
    "E1 Batch C dev (AUTH-2C)": {
        "experiment": "N03-AUTH2-DEVELOPMENT-BATCH-C-v1",
        "planned": 480},
    "E1 Batch D dev (AUTH-2D)": {
        "experiment": "N03-AUTH2-DEVELOPMENT-BATCH-D-v1",
        "planned": 480},
    "E1 confirmation (AUTH-3)": {
        "experiment": None, "planned": 960,
        "status_override": "BLOCKED (AUTH-3 not registered; by design)"},
    "E2 adapter atlas (AUTH-2W)": {
        "experiment": "N03-AUTH2-ADAPTER-ATLAS-v1",
        "planned": 1920},
    "E3 native reproduction": {
        "experiment": None, "planned": 1140,
        "status_override": "BLOCKED (task acquisition + sandbox; "
                           "sources study frozen)"},
    "E4 cross-harness": {"experiment": None, "planned": 720,
                         "status_override": "BLOCKED (E3 + scope)"},
    "E5 runtime x adapter factorial": {
        "experiment": None, "planned": 480,
        "status_override": "BLOCKED (scope not released)"},
    "E6 reasoning budget": {"experiment": None, "planned": 1080,
                            "status_override": "BLOCKED (scope not "
                                               "released)"},
    "E6 larger-model reference": {"experiment": None, "planned": 320,
                                  "status_override": "BLOCKED (scope "
                                              "not released)"},
    "E7 learnability": {"experiment": None, "planned": 1440,
                        "status_override": "BLOCKED (scope not "
                                           "released)"},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    state = json.loads(STATE.read_text(encoding="utf-8"))
    started = state["clock"]["started_utc"]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    rows = []
    total_planned = total_executed = 0
    for name, sc in SCOPES.items():
        planned = sc["planned"]
        total_planned += planned
        entry = {"scope": name, "planned": planned}
        if sc.get("status_override"):
            entry.update({"executed": 0, "status": sc["status_override"]})
        else:
            wd = RUNS / sc["experiment"]
            results = wd / "results.jsonl"
            executed = sum(1 for _ in open(results, encoding="utf-8")) \
                if results.is_file() else 0
            seal_p = wd / "seal.json"
            seal = json.loads(seal_p.read_text(
                encoding="utf-8")) if seal_p.is_file() else None
            state_p = wd / "campaign_state.json"
            attempts = None
            if state_p.is_file():
                attempts = json.loads(state_p.read_text(
                    encoding="utf-8")).get("physical_attempts")
            total_executed += executed
            entry.update({
                "executed": executed,
                "physical_attempts": attempts,
                "sealed": bool(seal and not seal.get(
                    "integrity_problems")),
                "results_sha256": (seal or {}).get("results_sha256"),
                "status": "COMPLETE" if executed >= planned
                and seal else ("EXECUTING" if executed else
                               "NOT_RUN")})
        rows.append(entry)

    out = {
        "schema": "ijnano.n03h.coverage.v1",
        "campaign": {"started_utc": started, "reported_utc": now,
                     "deadline_utc": state["clock"]["deadline_utc"]},
        "scopes": rows,
        "totals": {
            "planned_slots_all_scopes": total_planned,
            # physical attempts across executed scopes only (no
            # double counting: each scope's roster is disjoint)
            "executed_trials_sealed_or_running": total_executed,
            "note": "planned totals include BLOCKED scopes for "
                    "accountability; executed counts are per-scope "
                    "physical records"},
    }
    text = json.dumps(out, indent=1, ensure_ascii=False)
    if args.out:
        pathlib.Path(args.out).write_text(text, encoding="utf-8")
        print(f"written {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
