#!/usr/bin/env python3
"""N02R results analyzer: aggregates trial records into the protocol
matrix deliverable with uncertainty, matched-comparison contrasts and
coverage accounting (planned vs executed vs blocked)."""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks" / "ij_nano"))
from n02r import arms as arms_mod  # noqa: E402
from n02r import tasks as tasks_mod  # noqa: E402


def wilson(p_hat: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    denom = 1 + z * z / n
    centre = p_hat + z * z / (2 * n)
    adj = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - adj) / denom), min(1.0, (centre + adj) / denom))


def rate(rows: list[dict], key: str) -> tuple[float, int, tuple[float, float]]:
    n = len(rows)
    k = sum(1 for r in rows if r.get(key))
    return (k / n if n else 0.0), n, wilson(k / n if n else 0.0, n)


def agg(rows: list[dict]) -> dict:
    sem, n, ci_sem = rate(rows, "semantic_correct")
    struct, _, ci_struct = rate(rows, "structural_valid")
    empty, _, _ = rate(rows, "content_empty")
    trunc, _, _ = rate(rows, "truncated")
    toolc, _, _ = rate(rows, "tool_correct")
    argsc, _, _ = rate(rows, "args_correct")
    lats = [r["latency_s"] for r in rows if r.get("latency_s") is not None]
    pts = [r["prompt_tokens"] for r in rows if r.get("prompt_tokens")]
    cts = [r["completion_tokens"] for r in rows if r.get("completion_tokens")]
    mean = lambda v: round(sum(v) / len(v), 2) if v else None
    return {
        "n": n,
        "semantic_correct": {"rate": round(sem, 4), "ci95": [round(x, 4) for x in ci_sem]},
        "structural_valid": {"rate": round(struct, 4),
                             "ci95": [round(x, 4) for x in ci_struct]},
        "tool_correct_rate": round(toolc, 4),
        "args_correct_rate": round(argsc, 4),
        "empty_content_rate": round(empty, 4),
        "truncation_rate": round(trunc, 4),
        "mean_latency_s": mean(lats),
        "mean_prompt_tokens": mean(pts),
        "mean_completion_tokens": mean(cts),
        "reasoning_present_rate": round(
            sum(1 for r in rows if r.get("reasoning_content_present")) / n, 4) if n else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run dir under evidence/IJNANO/N02R/runs")
    ap.add_argument("--phase", default="all", choices=["main", "panel", "all"])
    args = ap.parse_args()
    run = pathlib.Path(args.run)
    rows = [json.loads(l) for l in
            (run / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    experiment_id = manifest["experiment_id"]

    by_ma = collections.defaultdict(list)      # (model, arm) @ primary budget
    by_mab = collections.defaultdict(list)     # (model, arm, budget)
    per_family = collections.defaultdict(list)  # (model, arm, family)
    for r in rows:
        by_mab[(r["model"], r["arm"], r["budget"])].append(r)
        if r["budget"] == arms_mod.PRIMARY_BUDGET:
            by_ma[(r["model"], r["arm"])].append(r)
            per_family[(r["model"], r["arm"], r["family"])].append(r)

    matrix = {
        "schema": "ij_nano.n02r.protocol_matrix",
        "experiment_id": experiment_id,
        "manifest": manifest,
        "suite_hash": tasks_mod.suite_hash(),
        "arms": arms_mod.ARM_LABELS,
        "primary_budget": arms_mod.PRIMARY_BUDGET,
        "primary_budget_matrix": {
            f"{m}|{a}": agg(rs) for (m, a), rs in sorted(by_ma.items())},
        "budget_panel": {
            f"{m}|{a}|{b}": agg(rs)
            for (m, a, b), rs in sorted(by_mab.items())
            if a in arms_mod.BUDGET_PANEL_ARMS},
        "per_family_primary_budget": {
            f"{m}|{a}|{f}": agg(rs)
            for (m, a, f), rs in sorted(per_family.items())},
    }

    # matched contrasts at the primary budget (order 3.4): each contrast
    # isolates one factor; multi-factor arms are annotated as such
    def contrast(name: str, m: str, a1: str, a2: str, factor: str):
        r1, r2 = by_ma.get((m, a1), []), by_ma.get((m, a2), [])
        s1, n1, ci1 = rate(r1, "semantic_correct")
        s2, n2, ci2 = rate(r2, "semantic_correct")
        t1, _, _ = rate(r1, "structural_valid")
        t2, _, _ = rate(r2, "structural_valid")
        delta = s1 - s2
        se = math.sqrt((s1 * (1 - s1) / n1 if n1 else 0)
                       + (s2 * (1 - s2) / n2 if n2 else 0))
        matrix.setdefault("matched_contrasts", {}).setdefault(m, {})[name] = {
            "arm_pair": [a1, a2], "isolated_factor": factor,
            "semantic": {"a1": round(s1, 4), "a2": round(s2, 4),
                         "delta": round(delta, 4),
                         "se_diff": round(se, 4), "n1": n1, "n2": n2},
            "structural": {"a1": round(t1, 4), "a2": round(t2, 4)},
        }

    for m in sorted({m for m, _ in by_ma}):
        contrast("chat_vs_completion_transport", m, "P1", "P3",
                 "transport (rendered semantics matched via schema)")
        contrast("thinking_enabled_vs_disabled", m, "P1", "P2",
                 "thinking mode (verified kwarg)")
        contrast("json_schema_vs_gbnf", m, "P3", "P4",
                 "constraint mechanism on /completion")
        contrast("schema_vs_native_tools", m, "P1", "P5",
                 "structured-output representation (multi-factor: prompt shape differs)")
        contrast("freeform_vs_constrained_chat", m, "P0", "P1",
                 "constraint on/off under chat transport (multi-factor)")
        contrast("dsl_vs_json_completion", m, "P6", "P3",
                 "action representation under /completion (multi-factor)")
        contrast("enumerated_vs_json_completion", m, "P7", "P3",
                 "action representation under /completion (multi-factor)")

    # coverage accounting (order 3.5): planned vs executed vs remaining
    planned_main = 3 * len(arms_mod.ARMS) * 60
    planned_panel = 3 * len(arms_mod.BUDGET_PANEL_ARMS) * 12 * len(arms_mod.BUDGETS)
    main_trials = sum(len(rs) for (m, a, b), rs in by_mab.items()
                      if b == arms_mod.PRIMARY_BUDGET)
    panel_trials = sum(len(rs) for (m, a, b), rs in by_mab.items()
                       if a in arms_mod.BUDGET_PANEL_ARMS and b != arms_mod.PRIMARY_BUDGET)
    matrix["coverage"] = {
        "planned_main": planned_main, "executed_main": main_trials,
        "remaining_main": planned_main - main_trials,
        "planned_panel_extra": planned_panel, "executed_panel_extra": panel_trials,
        "remaining_panel_extra": planned_panel - panel_trials,
        "status": "COMPLETE" if (main_trials >= planned_main
                                 and panel_trials >= planned_panel) else "IN_PROGRESS",
    }

    out = run / "protocol_matrix.json"
    out.write_text(json.dumps(matrix, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"coverage": matrix["coverage"],
                      "cells": len(matrix["primary_budget_matrix"]),
                      "contrast_models": len(matrix.get("matched_contrasts", {}))},
                     indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
