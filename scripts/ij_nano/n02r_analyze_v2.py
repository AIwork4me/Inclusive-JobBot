#!/usr/bin/env python3
"""N02R analyzer v2: builds evidence/IJNANO/N02R/protocol_matrix.json from
the corrected (v2) experiment records, with scope separation, matched
contrasts (incl. the T0-T3 causal set), budget curves and the PR-D10
denominator reconciliation. Reads v2 record schema (telemetry/parser
nested; handles v1 records for the diagnostic scope when present)."""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks" / "ij_nano"))
from n02r import arms_v2 as arms  # noqa: E402
from n02r import tasks as tasks_mod  # noqa: E402


def wilson(p, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - a) / d), min(1.0, (c + a) / d))


def get(r, dotted):
    cur = r
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _num(v):
    return v if isinstance(v, (int, float)) else None


def agg(rows):
    n = len(rows)
    sem_k = sum(1 for r in rows if r.get("semantic_correct"))
    st_k = sum(1 for r in rows if get(r, "parser.structural_ok"))
    empty_k = sum(1 for r in rows if get(r, "telemetry.content") in (None, "")
                  or get(r, "content_empty") is True)
    trunc_k = sum(1 for r in rows if get(r, "telemetry.truncated") is True
                  or r.get("truncated") is True)
    rsn_k = sum(1 for r in rows if get(r, "telemetry.reasoning_content_present")
                is True or r.get("reasoning_content_present") is True)
    lats = [v for v in (_num(get(r, "telemetry.latency_s")) or r.get("latency_s")
                        for r in rows) if v is not None]
    pts = [v for v in (_num(get(r, "telemetry.usage.prompt_tokens"))
                       for r in rows) if v is not None]
    cts = [v for v in (_num(get(r, "telemetry.usage.completion_tokens"))
                       for r in rows) if v is not None]
    mean = lambda v: round(sum(v) / len(v), 2) if v else None
    return {
        "n": n,
        "semantic_correct": {"rate": round(sem_k / n, 4) if n else None,
                             "ci95": [round(x, 4) for x in
                                      wilson(sem_k / n if n else 0, n)]},
        "structural_valid": {"rate": round(st_k / n, 4) if n else None,
                             "ci95": [round(x, 4) for x in
                                      wilson(st_k / n if n else 0, n)]},
        "empty_final_content_rate": round(empty_k / n, 4) if n else None,
        "truncation_rate": round(trunc_k / n, 4) if n else None,
        "reasoning_present_rate": round(rsn_k / n, 4) if n else None,
        "mean_latency_s": mean(lats), "mean_prompt_tokens": mean(pts),
        "mean_completion_tokens": mean(cts),
    }


def rate_ci(rows, key="semantic_correct"):
    n = len(rows)
    if key == "structural":
        k = sum(1 for r in rows if get(r, "parser.structural_ok") is True
                or r.get("structural_valid") is True)
    else:
        k = sum(1 for r in rows if r.get(key))
    return (k / n if n else 0.0), n, wilson(k / n if n else 0.0, n)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="v2 run dir")
    ap.add_argument("--diagnostic-run", default=None,
                    help="optional v1 run dir (36bfed1d...) for the "
                         "native-usability diagnostic scope")
    args = ap.parse_args()
    run = pathlib.Path(args.run)
    rows = [json.loads(l) for l in
            (run / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    identity = manifest["identity"]

    by_ma, by_mab, by_maf = collections.defaultdict(list), \
        collections.defaultdict(list), collections.defaultdict(list)
    for r in rows:
        by_mab[(r["model"], r["arm"], r["budget"])].append(r)
        if r["budget"] == arms.PRIMARY_BUDGET:
            by_ma[(r["model"], r["arm"])].append(r)
            by_maf[(r["model"], r["arm"], r["family"])].append(r)

    # ---- scopes ---------------------------------------------------------
    matched = {f"{m}|{a}": agg(rs) for (m, a), rs in sorted(by_ma.items())}

    diagnostic = {}
    if args.diagnostic_run:
        drun = pathlib.Path(args.diagnostic_run)
        drows = [json.loads(l) for l in
                 (drun / "results.jsonl").read_text(encoding="utf-8").splitlines()]
        dma = collections.defaultdict(list)
        for r in drows:
            if r["budget"] == arms.PRIMARY_BUDGET:
                dma[(r["model"], r["arm"])].append(r)
        diagnostic = {f"{m}|{a}": agg(rs) for (m, a), rs in sorted(dma.items())}

    # ---- T0-T3 causal set (order 1.2 addendum section 10) ----------------
    tset = {}
    for m in sorted({m for m, _ in by_ma}):
        t0 = by_ma.get((m, "M-P1"), [])
        t1 = by_ma.get((m, "M-P2"), [])
        t2 = by_ma.get((m, "T2"), [])
        t3 = by_ma.get((m, "M-P3"), [])
        t3b = by_ma.get((m, "M-P4"), [])
        cells = {"T0_default_thinking": agg(t0),
                 "T1_thinking_disabled": agg(t1),
                 "T2_reasoning_budget_%d" % arms.REASONING_BUDGET_T2: agg(t2),
                 "T3_completion_eager_schema": agg(t3),
                 "T3b_completion_eager_gbnf": agg(t3b)}
        # trade-off: structural success vs semantic correctness
        tset[m] = {
            "cells": cells,
            "tradeoff": {
                "structural_success": {k: v["structural_valid"]["rate"]
                                       for k, v in cells.items()},
                "empty_final_content": {k: v["empty_final_content_rate"]
                                        for k, v in cells.items()},
                "semantic_correctness": {k: v["semantic_correct"]["rate"]
                                         for k, v in cells.items()},
            },
        }

    # ---- matched contrasts -------------------------------------------------
    contrasts = {}
    for m in sorted({m for m, _ in by_ma}):
        def contrast(name, a1, a2, factor):
            r1, r2 = by_ma.get((m, a1), []), by_ma.get((m, a2), [])
            s1, n1, _ = rate_ci(r1)
            s2, n2, _ = rate_ci(r2)
            t1_, _, _ = rate_ci(r1, key="structural")
            t2_, _, _ = rate_ci(r2, key="structural")
            st1 = [r for r in r1 if get(r, "parser.structural_ok")]
            st2 = [r for r in r2 if get(r, "parser.structural_ok")]
            sem_cond_1 = (sum(1 for r in st1 if r["semantic_correct"]) / len(st1)) \
                if st1 else None
            sem_cond_2 = (sum(1 for r in st2 if r["semantic_correct"]) / len(st2)) \
                if st2 else None
            delta = (s1 - s2) if (n1 and n2) else None
            se = math.sqrt(s1 * (1 - s1) / n1 + s2 * (1 - s2) / n2) \
                if (n1 and n2) else None
            contrasts.setdefault(m, {})[name] = {
                "arm_pair": [a1, a2], "isolated_factor": factor,
                "semantic_rate": [round(s1, 4) if n1 else None,
                                  round(s2, 4) if n2 else None],
                "structural_rate": [round(t1_, 4) if n1 else None,
                                    round(t2_, 4) if n2 else None],
                "semantic_given_structural": [
                    round(sem_cond_1, 4) if sem_cond_1 is not None else None,
                    round(sem_cond_2, 4) if sem_cond_2 is not None else None],
                "delta_semantic": round(delta, 4) if delta is not None else None,
                "se_diff": round(se, 4) if se is not None else None,
                "n": [n1, n2]}
        contrast("chat_vs_completion_transport", "M-P1", "M-P3",
                 "transport (information matched)")
        contrast("thinking_on_vs_off", "M-P1", "M-P2",
                 "thinking mode (verified kwarg)")
        contrast("thinking_default_vs_budgeted", "M-P1", "T2",
                 "reasoning budget (server profile)")
        contrast("schema_vs_gbnf", "M-P3", "M-P4",
                 "constraint mechanism on /completion")
        contrast("schema_vs_native_business_tools", "M-P1", "P5A",
                 "structured output vs native tool calling (multi-factor)")
        contrast("business_tools_vs_record_answer", "P5A", "P5B",
                 "tool-calling contract (A: business tools, B: record_answer)")
        contrast("freeform_vs_constrained_chat", "M-P0", "M-P1",
                 "constraint on/off under matched information")
        contrast("dsl_vs_json_completion", "M-P6", "M-P3",
                 "action representation under /completion")
        contrast("enumerated_vs_json_completion", "M-P7", "M-P3",
                 "action representation under /completion")
        contrast("two_stage_vs_single_json", "P7S", "M-P3",
                 "decomposed selection+filling vs single structured output")

    # ---- budget curves -------------------------------------------------------
    curves = {}
    for (m, a, b), rs in sorted(by_mab.items()):
        if a in arms.BUDGET_PANEL_ARMS or b == arms.PRIMARY_BUDGET:
            curves.setdefault(f"{m}|{a}", {})[str(b)] = agg(rs)

    # ---- denominators (PR-D10) -------------------------------------------------
    unique_ids = {r["trial_id"] for r in rows}
    planned_main = 3 * 560
    planned_panel_extra = 3 * 4 * 12 * 4
    planned_unique = planned_main + planned_panel_extra
    p7s_trials = sum(1 for r in rows if r["arm"] == "P7S")
    physical_attempts = len(rows) + p7s_trials       # P7S = two requests
    artifact_missing = [r["trial_id"] for r in rows
                        if not get(r, "response_artifact_sha256")]
    evidence_valid = len(rows) - len(artifact_missing)
    semantic_pass = sum(1 for r in rows if r["semantic_correct"])
    inapplicable_slots = 3 * (2 * 10 * 1 + 1 * 10 * 0)  # P7 SX+SA per model
    matrix_scope_counts = {
        "planned_logical_slots": planned_unique,
        "planned_main": planned_main, "planned_panel_extra": planned_panel_extra,
        "unique_trial_ids_executed": len(unique_ids),
        "physical_attempts": physical_attempts,
        "p7s_two_request_trials": p7s_trials,
        "evidence_valid_trials": evidence_valid,
        "artifact_missing_trials": len(artifact_missing),
        "semantic_PASS": semantic_pass,
        "semantic_FAIL": len(rows) - semantic_pass,
        "BLOCKED": 0, "NOT_RUN": planned_unique - len(unique_ids),
        "INAPPLICABLE_planned_excluded": inapplicable_slots,
        "reused_trials_counted_as_independent": 0,
    }

    matrix = {
        "schema": "ij_nano.n02r.protocol_matrix",
        "analyzer": "v2",
        "experiment_id": identity["experiment_id"],
        "identity": identity,
        "suite_hash": tasks_mod.suite_hash(),
        "scopes": {
            "information_matched_causal": matched,
            "native_usability_diagnostic": diagnostic,
        },
        "t_set_causal": tset,
        "matched_contrasts": contrasts,
        "budget_curves": curves,
        "per_family_primary_budget": {
            f"{m}|{a}|{f}": agg(rs) for (m, a, f), rs in sorted(by_maf.items())},
        "denominators": matrix_scope_counts,
    }
    out = ROOT / "evidence" / "IJNANO" / "N02R" / "protocol_matrix.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(matrix, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"experiment": identity["experiment_id"],
                      "cells_matched": len(matched),
                      "contrasts_models": len(contrasts),
                      "denominators": matrix_scope_counts}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
