#!/usr/bin/env python3
"""N02RR corrected quantitative analysis (mission IJ-NANO-1.2R RS04-RS08).

>>> DIAGNOSTIC-ONLY TOOL (IJ-EVAL-ASSURANCE-1.0 EA02-R EA-D05) <<<
This historical analyzer reads Boolean verdicts directly
(load_rows: r["sem"] = bool(verdict)) and has NO statistical eligibility
filter: rows classified REPLAY_ERROR or EVIDENCE_INCONSISTENT_STAGE2_TOOL
would enter its rates as ordinary model outcomes (EA00 §2.2 R3; the sealed
1.2R corpus contains zero such rows, so its published output is
unaffected). It is preserved unchanged as sealed evidence tooling. Formal
aggregation must go through the qualified assurance boundary instead:
src/eval_assurance/statistics/boundary.py (aggregate_semantic), which
consumes validated typed records only. Do NOT add formal reporting here.

Rebuilds the protocol matrix from the CORRECTED replay verdicts
(trial_reconciliation.jsonl) with:

- paired comparisons only (identical model+task instances, intersected
  applicable task IDs, paired n and discordant counts reported);
- exact McNemar tests + conservative Newcombe hybrid-score CIs for paired
  differences (marginal Wilson CIs alongside);
- corrected telemetry recovered from the artifacts with a measured sample
  count for EVERY mean (missing telemetry never coerced to zero);
- honest failure taxonomy (true semantic error / structural generation
  error / empty final content / truncation / tool-call-only / transport /
  stage-1 selection failure) instead of "absent evidence = empty output";
- T0/T1/T2/T3/T3b recalculation distinguishing point estimates from
  statistically supported differences;
- no equivalence claims (no preregistered practical margins exist; evidence
  without a significant difference is reported as inconclusive).

Writes evidence/IJNANO/N02RR/corrected_protocol_matrix.json.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks" / "ij_nano"))
from n02r import arms_v2 as arms          # noqa: E402
from n02r import tasks as tasks_mod       # noqa: E402

REC = ROOT / "evidence" / "IJNANO" / "N02RR" / "trial_reconciliation.jsonl"
OUT = ROOT / "evidence" / "IJNANO" / "N02RR" / "corrected_protocol_matrix.json"
PRIMARY = arms.PRIMARY_BUDGET


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round(max(0.0, (c - a) / d), 4), round(min(1.0, (c + a) / d), 4)]


def mcnemar_exact_p(b: int, c: int) -> float | None:
    """Two-sided exact McNemar (binomial on the discordant pairs)."""
    n = b + c
    if n == 0:
        return None
    lo = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, lo + 1)) / 2 ** n
    p = min(1.0, 2 * tail)
    return round(p, 5)


def newcombe_paired_diff(k1: int, k2: int, n: int):
    """Conservative Newcombe hybrid-score CI for a paired difference
    (correlation-ignoring; exact McNemar is the primary inference)."""
    if n == 0:
        return None
    p1, p2 = k1 / n, k2 / n
    l1u = wilson(k1, n) or [0, 0]
    l2u = wilson(k2, n) or [0, 0]
    d = p1 - p2
    lower = d - math.sqrt((p1 - l1u[0]) ** 2 + (l2u[1] - p2) ** 2)
    upper = d + math.sqrt((l1u[1] - p1) ** 2 + (p2 - l2u[0]) ** 2)
    return [round(max(-1.0, lower), 4), round(min(1.0, upper), 4)]


def mean_ns(values):
    vs = [v for v in values if isinstance(v, (int, float))
          and not isinstance(v, bool)]
    return (round(sum(vs) / len(vs), 2) if vs else None, len(vs))


def load_rows():
    rows = [json.loads(l) for l in REC.read_text(encoding="utf-8").splitlines()]
    for r in rows:
        c = r["corrected"]
        r["sem"] = bool(c["verdict"])
        r["struct"] = bool(c["structural_ok"])
        r["fc"] = c["failure_class"]
        r["tel"] = c["telemetry"]
        r["totals"] = c["telemetry_totals"]
        r["src_sem"] = (r.get("original_source") or {}).get("verdict")
    return rows


def agg(rows):
    n = len(rows)
    sem = sum(1 for r in rows if r["sem"])
    st = sum(1 for r in rows if r["struct"])
    empty = sum(1 for r in rows if r["fc"].startswith("EMPTY_FINAL_CONTENT"))
    empty_trunc = sum(1 for r in rows
                      if r["fc"] == "EMPTY_FINAL_CONTENT_TRUNCATED")
    trunc = sum(1 for r in rows if r["fc"] in ("GENERATION_TRUNCATED",
                                               "EMPTY_FINAL_CONTENT_TRUNCATED"))
    tco = sum(1 for r in rows if r["fc"] == "TOOL_CALL_ONLY_UNPARSED")
    lat_m, lat_n = mean_ns([r["tel"].get("latency_s") for r in rows])
    pt_m, pt_n = mean_ns([(r["tel"].get("usage") or {}).get("prompt_tokens")
                          if isinstance(r["tel"].get("usage"), dict) else None
                          for r in rows])
    ct_m, ct_n = mean_ns([(r["tel"].get("usage") or {}).get("completion_tokens")
                          if isinstance(r["tel"].get("usage"), dict) else None
                          for r in rows])
    usage_missing = sum(1 for r in rows
                        if not isinstance(r["tel"].get("usage"), dict))
    return {
        "n": n,
        "semantic_correct": {"k": sem, "rate": round(sem / n, 4) if n else None,
                             "ci95_wilson": wilson(sem, n)},
        "structural_valid": {"k": st, "rate": round(st / n, 4) if n else None,
                             "ci95_wilson": wilson(st, n)},
        "empty_final_content": {"k": empty,
                                "rate": round(empty / n, 4) if n else None,
                                "of_which_budget_exhausted": empty_trunc},
        "truncation": {"k": trunc, "rate": round(trunc / n, 4) if n else None},
        "tool_call_only_unparsed": {"k": tco},
        "mean_latency_s": {"value": lat_m, "sample_n": lat_n},
        "mean_prompt_tokens": {"value": pt_m, "sample_n": pt_n},
        "mean_completion_tokens": {"value": ct_m, "sample_n": ct_n},
        "usage_missing_n": usage_missing,
    }


def paired(rows, model, a1, a2, task_filter=None):
    """Paired comparison on identical (model, task) instances at the
    primary budget; intersected applicable task IDs only."""
    d1 = {r["task_id"]: r for r in rows
          if r["model"] == model and r["arm"] == a1 and r["budget"] == PRIMARY}
    d2 = {r["task_id"]: r for r in rows
          if r["model"] == model and r["arm"] == a2 and r["budget"] == PRIMARY}
    if task_filter is not None:
        d1 = {t: r for t, r in d1.items() if task_filter(t)}
        d2 = {t: r for t, r in d2.items() if task_filter(t)}
    common = sorted(set(d1) & set(d2))
    both = sum(1 for t in common if d1[t]["sem"] and d2[t]["sem"])
    neither = sum(1 for t in common if not d1[t]["sem"] and not d2[t]["sem"])
    b = sum(1 for t in common if d1[t]["sem"] and not d2[t]["sem"])
    c = sum(1 for t in common if not d1[t]["sem"] and d2[t]["sem"])
    k1 = sum(1 for t in common if d1[t]["sem"])
    k2 = sum(1 for t in common if d2[t]["sem"])
    return {
        "paired_n": len(common),
        "task_ids_only_a1": sorted(set(d1) - set(d2)),
        "task_ids_only_a2": sorted(set(d2) - set(d1)),
        "both_success": both, "both_fail": neither,
        "discordant_a1_only": b, "discordant_a2_only": c,
        "semantic_rate_a1": {"k": k1, "rate": round(k1 / len(common), 4)
                             if common else None,
                             "ci95_wilson": wilson(k1, len(common))},
        "semantic_rate_a2": {"k": k2, "rate": round(k2 / len(common), 4)
                             if common else None,
                             "ci95_wilson": wilson(k2, len(common))},
        "delta_paired": round((k1 - k2) / len(common), 4) if common else None,
        "delta_ci95_newcombe_conservative": newcombe_paired_diff(
            k1, k2, len(common)),
        "mcnemar_exact_p": mcnemar_exact_p(b, c),
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    rows = load_rows()
    suite = {t["task_id"]: t for t in tasks_mod.build_suite()}

    by_ma = collections.defaultdict(list)
    by_mab = collections.defaultdict(list)
    by_maf = collections.defaultdict(list)
    for r in rows:
        by_mab[(r["model"], r["arm"], r["budget"])].append(r)
        if r["budget"] == PRIMARY:
            by_ma[(r["model"], r["arm"])].append(r)
            by_maf[(r["model"], r["arm"], r["family"])].append(r)

    matched = {f"{m}|{a}": agg(rs) for (m, a), rs in sorted(by_ma.items())}

    # ---- T-set (order 1.2 addendum section 10), corrected --------------------
    tset = {}
    for m in sorted({m for m, _ in by_ma}):
        cells = {"T0_default_thinking": agg(by_ma.get((m, "M-P1"), [])),
                 "T1_thinking_disabled": agg(by_ma.get((m, "M-P2"), [])),
                 "T2_reasoning_budget_%d" % arms.REASONING_BUDGET_T2:
                     agg(by_ma.get((m, "T2"), [])),
                 "T3_completion_eager_schema": agg(by_ma.get((m, "M-P3"), [])),
                 "T3b_completion_eager_gbnf": agg(by_ma.get((m, "M-P4"), []))}
        tset[m] = {
            "cells": cells,
            "paired_tests": {
                "T2_vs_T0": paired(rows, m, "T2", "M-P1"),
                "T1_vs_T0": paired(rows, m, "M-P2", "M-P1"),
                "T3_vs_T0": paired(rows, m, "M-P3", "M-P1"),
                "T3b_vs_T3": paired(rows, m, "M-P4", "M-P3")},
        }

    # ---- matched contrasts, paired, applicability-restricted -----------------
    p7s_tasks = {t for t, task in suite.items()
                 if arms.P7S_APPLICABILITY.get(task["family"])}
    p5a_tasks = {t for t, task in suite.items()
                 if arms.P5A_APPLICABILITY.get(task["family"])}
    p7_tasks = {t for t, task in suite.items()
                if arms.P7_APPLICABILITY.get(task["family"])}
    contrasts = {}
    for m in sorted({m for m, _ in by_ma}):
        mc = contrasts.setdefault(m, {})

        def add(name, a1, a2, factor, restrict=None, scope=None):
            mc[name] = {"arm_pair": [a1, a2], "isolated_factor": factor,
                        "comparison_scope": scope or "shared applicable "
                        "tasks, paired on identical (model, task)",
                        **paired(rows, m, a1, a2, restrict)}

        add("chat_vs_completion_transport", "M-P1", "M-P3",
            "transport (information matched)")
        add("thinking_on_vs_off", "M-P1", "M-P2",
            "thinking mode (verified kwarg)")
        add("thinking_default_vs_budgeted", "M-P1", "T2",
            "reasoning budget (server profile)")
        add("schema_vs_gbnf", "M-P3", "M-P4",
            "constraint mechanism on /completion")
        add("freeform_vs_constrained_chat", "M-P0", "M-P1",
            "constraint on/off under matched information")
        add("dsl_vs_json_completion", "M-P6", "M-P3",
            "action representation under /completion")
        add("enumerated_vs_json_completion", "M-P7", "M-P3",
            "action representation under /completion",
            restrict=lambda t: t in p7_tasks,
            scope="M-P7-applicable families only "
                  "(tool_selection, enumerated_action, conditional_branch, "
                  "stop_continue)")
        add("two_stage_vs_single_json", "P7S", "M-P3",
            "decomposed selection+filling vs single structured output",
            restrict=lambda t: t in p7s_tasks,
            scope="structured_action tasks only (P7S applicability)")
        add("schema_vs_native_business_tools", "M-P1", "P5A",
            "structured output vs native tool calling (multi-factor)",
            restrict=lambda t: t in p5a_tasks,
            scope="P5A-applicable families only (tool_selection, "
                  "slot_extraction, structured_action)")
        add("business_tools_vs_record_answer", "P5A", "P5B",
            "tool-calling contract (A: business tools, B: record_answer)",
            restrict=lambda t: t in p5a_tasks,
            scope="P5A-applicable families only")

    # ---- budget curves (TOTAL generation budget panel) ------------------------
    curves = {}
    for (m, a, b), rs in sorted(by_mab.items()):
        if a in arms.BUDGET_PANEL_ARMS or b == PRIMARY:
            curves.setdefault(f"{m}|{a}", {})[str(b)] = agg(rs)

    # ---- failure taxonomy --------------------------------------------------------
    taxonomy = {}
    for (m, a), rs in sorted(by_ma.items()):
        cnt = collections.Counter(r["fc"] for r in rs)
        taxonomy[f"{m}|{a}"] = {"n": len(rs),
                                "classes": dict(sorted(cnt.items()))}

    # ---- telemetry recovery verification (source vs corrected) ------------------
    tel_check = {"rows_with_source_telemetry": 0, "usage_matches": 0,
                 "usage_both_dicts": 0, "usage_equal_absent_markers": 0,
                 "usage_real_mismatches": 0, "latency_matches": 0}
    for r in rows:
        s = r.get("original_source")
        if not s:
            continue
        tel_check["rows_with_source_telemetry"] += 1
        su, cu = s["telemetry"].get("usage"), r["tel"].get("usage")
        if isinstance(su, dict) and isinstance(cu, dict):
            tel_check["usage_both_dicts"] += 1
            if all(su.get(k) == cu.get(k) for k in
                   ("prompt_tokens", "completion_tokens", "total_tokens",
                    "cached_tokens")):
                tel_check["usage_matches"] += 1
            else:
                tel_check["usage_real_mismatches"] += 1
        elif su == cu:      # equal absent-evidence markers (never zeros)
            tel_check["usage_equal_absent_markers"] += 1
            tel_check["usage_matches"] += 1
        else:
            tel_check["usage_real_mismatches"] += 1
        if s["telemetry"].get("latency_s") == r["tel"].get("latency_s"):
            tel_check["latency_matches"] += 1

    # ---- denominators --------------------------------------------------------------
    semantic_pass = sum(1 for r in rows if r["sem"])
    matrix = {
        "schema": "ij_nano.n02rr.corrected_protocol_matrix",
        "analyzer": "n02rr_analyze (corrected replay verdicts)",
        "source_reconciliation": "evidence/IJNANO/N02RR/trial_reconciliation.jsonl",
        "replay_id": rows[0]["replay_id"] if rows else None,
        "experiment_id": "ec5b95357e960f99",
        "statistical_methods": {
            "paired": "identical (model, task) instances, intersected "
                      "applicable task IDs, primary budget 1024",
            "test": "exact McNemar (two-sided binomial on discordant pairs)",
            "diff_ci": "conservative Newcombe hybrid-score (correlation-"
                       "ignoring); marginal Wilson 95% alongside",
            "equivalence": "NO equivalence claims: no preregistered "
                           "practical margins exist; overlapping CIs or "
                           "p>=0.05 is reported as inconclusive",
            "budget_panel_note": "budget curves vary TOTAL generation budget "
                                 "(max_tokens / n_predict), NOT the server "
                                 "reasoning budget; T2 "
                                 f"({arms.REASONING_BUDGET_T2} tokens) is the "
                                 "only reasoning-budget condition - "
                                 "reasoning-budget optimality is untested"},
        "scopes": {"information_matched_causal": matched},
        "t_set_causal": tset,
        "matched_contrasts": contrasts,
        "budget_curves": curves,
        "per_family_primary_budget": {
            f"{m}|{a}|{f}": agg(rs) for (m, a, f), rs in sorted(by_maf.items())},
        "failure_taxonomy": taxonomy,
        "telemetry_recovery_check": tel_check,
        "denominators": {
            "total_rows": len(rows),
            "semantic_PASS": semantic_pass,
            "semantic_FAIL": len(rows) - semantic_pass,
            "by_execution_kind": dict(collections.Counter(
                r["execution_kind"] for r in rows)),
            "BLOCKED": 0,
            "EVIDENCE_INSUFFICIENT": sum(
                1 for r in rows if r["change_classification"]
                == "EVIDENCE_INSUFFICIENT"),
            "PHYSICAL_REEXECUTION_REQUIRED": sum(
                1 for r in rows if r["change_classification"]
                == "PHYSICAL_REEXECUTION_REQUIRED")},
    }
    OUT.write_text(json.dumps(matrix, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"cells": len(matched),
                      "semantic_PASS_corrected": semantic_pass,
                      "of": len(rows),
                      "telemetry_check": tel_check}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
