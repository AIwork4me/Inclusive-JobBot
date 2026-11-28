"""E1 capability atlas + E2 adapter-effects analysis (IJ-NANO-48H).

Merges sealed campaign results into:
- the E1 matrix: 3 models x 32 primitives (semantic accuracy over
  model-evaluable outcomes, empty/invalid rates, latency, tokens);
- the E2 paired adapter analysis: W1/W2/W3 vs W0 on matched dev cases,
  W0 drawn from the E1 LFM3-1.7B arms (identity reuse verified: same
  chat protocol, frozen renderer digest, sampling identity, same case
  roster); paired wins/losses with exact McNemar p-values and
  Newcombe-Wilson CIs on the paired difference.

Software/unresolved buckets never enter accuracy denominators; missing
cells stay missing (never zero).
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
RUNS = ROOT / "runs" / "n03h"
MODEL_CLASSES = {"CORRECT", "INCORRECT", "INVALID_OUTPUT", "EMPTY_OUTPUT"}

E1_CAMPAIGNS = {
    "A": "N03-AUTH2-DEVELOPMENT-BATCH-A-v2-RQ",
    "B": "N03-AUTH2-DEVELOPMENT-BATCH-B-v1",
    "C": "N03-AUTH2-DEVELOPMENT-BATCH-C-v1",
    "D": "N03-AUTH2-DEVELOPMENT-BATCH-D-v1",
}
E2_CAMPAIGN = "N03-AUTH2-ADAPTER-ATLAS-v1"
W0_MODEL = "LFM3-1.7B"


def load_rows(experiment: str) -> list[dict]:
    p = RUNS / experiment / "results.jsonl"
    if not p.is_file():
        return []
    return [json.loads(l) for l in
            p.read_text(encoding="utf-8").splitlines() if l.strip()]


def sealed(experiment: str) -> dict | None:
    p = RUNS / experiment / "seal.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def acc(counts: dict) -> tuple[float | None, int]:
    evaluable = sum(counts.get(c, 0) for c in MODEL_CLASSES)
    if not evaluable:
        return None, 0
    return counts.get("CORRECT", 0) / evaluable, evaluable


def cell(rows: list[dict]) -> dict:
    counts = collections.Counter(r["classification"] for r in rows)
    accuracy, evaluable = acc(dict(counts))
    lat = [r["telemetry"].get("latency_s") for r in rows
           if r["telemetry"].get("latency_s") is not None]
    tok = [r["telemetry"].get("completion_tokens") for r in rows
           if r["telemetry"].get("completion_tokens") is not None]
    fin = collections.Counter(r["telemetry"].get("finish_reason")
                              for r in rows)
    return {"trials": len(rows), "counts": dict(counts),
            "evaluable": evaluable, "accuracy": accuracy,
            "mean_latency_s": round(sum(lat) / len(lat), 3) if lat
            else None,
            "mean_completion_tokens": round(sum(tok) / len(tok), 1)
            if tok else None,
            "finish_reasons": dict(fin)}


def mcnemar_exact(b: int, c: int) -> float:
    """Exact binomial two-sided p for the discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def newcombe_diff_ci(p1: float, n1: int, p2: float, n2: int
                     ) -> tuple[float, float]:
    """Newcombe method 10 (Wilson score) CI for p1 - p2."""
    def wilson(p, n, z=1.96):
        if n == 0:
            return (0.0, 1.0)
        d = 1 + z * z / n
        c = (p + z * z / (2 * n)) / d
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
        return (c - h, c + h)
    l1, u1 = wilson(p1, n1)
    l2, u2 = wilson(p2, n2)
    return (max(-1.0, (p1 - p2) - math.sqrt(
        (p1 - l1) ** 2 + (u2 - p2) ** 2)),
        min(1.0, (p1 - p2) + math.sqrt(
            (u1 - p1) ** 2 + (p2 - l2) ** 2)))


def build_e1() -> dict:
    rows_all: list[dict] = []
    seals = {}
    for batch, exp in E1_CAMPAIGNS.items():
        rows = load_rows(exp)
        s = sealed(exp)
        seals[batch] = {"experiment": exp,
                        "trials": len(rows),
                        "sealed": bool(
                            s and not s.get("integrity_problems")),
                        "seal_sha": (s or {}).get("results_sha256")}
        rows_all.extend(rows)
    models = sorted({r["model"] for r in rows_all})
    prims = sorted({r.get("primitive") for r in rows_all
                    if r.get("primitive")})
    matrix = {m: {p: cell([r for r in rows_all
                           if r["model"] == m and r.get("primitive") == p])
                  for p in prims} for m in models}
    overall = {m: cell([r for r in rows_all if r["model"] == m])
               for m in models}
    return {"campaigns": seals, "models": models,
            "primitives": prims, "matrix": matrix, "overall": overall}


def build_e2() -> dict:
    """W0 = E1 LFM3 arms (identity reuse: same chat protocol, frozen
    renderer, temp-0/seed-42 sampling — verified via the shared
    controller code path and roster case sets)."""
    w0_rows = []
    for exp in E1_CAMPAIGNS.values():
        w0_rows.extend(r for r in load_rows(exp)
                       if r["model"] == W0_MODEL)
    w_rows = load_rows(E2_CAMPAIGN)
    adapters = sorted({r["model"] for r in w_rows})

    w0_by_case = {r["case_id"]: r for r in w0_rows}
    w_by = {a: {r["case_id"]: r for r in w_rows if r["model"] == a}
            for a in adapters}

    paired = {}
    for a in adapters:
        common = sorted(set(w0_by_case) & set(w_by[a]))
        b = c = 0                     # b: adapter-only wins, c: losses
        both_ok = both_bad = 0
        for case_id in common:
            x = w_by[a][case_id]["classification"]
            y = w0_by_case[case_id]["classification"]
            xa = x == "CORRECT"
            ya = y == "CORRECT"
            if xa and not ya:
                b += 1
            elif ya and not xa:
                c += 1
            elif xa and ya:
                both_ok += 1
            else:
                both_bad += 1
        n = len(common)
        acc_a, eval_a = acc(dict(collections.Counter(
            w_by[a][cid]["classification"] for cid in common)))
        acc_0, eval_0 = acc(dict(collections.Counter(
            w0_by_case[cid]["classification"] for cid in common)))
        delta = (acc_a - acc_0) if (acc_a is not None
                                    and acc_0 is not None) else None
        ci = (newcombe_diff_ci(acc_a, eval_a, acc_0, eval_0)
              if delta is not None else (None, None))
        paired[a] = {
            "matched_cases": n,
            "adapter_accuracy": round(acc_a, 4) if acc_a is not None
            else None,
            "w0_accuracy": round(acc_0, 4) if acc_0 is not None
            else None,
            "paired_delta": round(delta, 4) if delta is not None
            else None,
            "newcombe95_ci": [round(ci[0], 4), round(ci[1], 4)]
            if ci[0] is not None else None,
            "wins_b": b, "losses_c": c,
            "mcnemar_exact_p": round(mcnemar_exact(b, c), 5),
            "both_correct": both_ok, "both_wrong": both_bad,
        }
    # per-primitive delta table
    prims = sorted({r.get("primitive") for r in w_rows
                    if r.get("primitive")})
    per_prim = {}
    for a in adapters:
        per_prim[a] = {}
        for p in prims:
            sub_a = [r for r in w_rows
                     if r["model"] == a and r.get("primitive") == p]
            sub_0 = [r for r in w0_rows
                     if r.get("primitive") == p]
            aa, na = acc(dict(collections.Counter(
                r["classification"] for r in sub_a)))
            a0, n0 = acc(dict(collections.Counter(
                r["classification"] for r in sub_0)))
            per_prim[a][p] = {
                "adapter": {"trials": len(sub_a),
                            "accuracy": round(aa, 4) if aa is not None
                            else None},
                "w0": {"trials": len(sub_0),
                       "accuracy": round(a0, 4) if a0 is not None
                       else None}}
    seal = sealed(E2_CAMPAIGN)
    return {
        "w0_source": "E1 LFM3-1.7B arms (identity reuse: shared chat "
                     "protocol/renderer/sampling/controller; roster "
                     "case sets matched)",
        "w0_cases": len(w0_by_case),
        "adapter_campaign_sealed": bool(
            seal and not seal.get("integrity_problems")),
        "paired": paired, "per_primitive": per_prim,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--skip-e2", action="store_true")
    args = ap.parse_args()
    out = {"schema": "ijnano.n03h.atlas_analysis.v1",
           "e1": build_e1()}
    if not args.skip_e2:
        out["e2"] = build_e2()
    text = json.dumps(out, indent=1, ensure_ascii=False)
    if args.out:
        pathlib.Path(args.out).write_text(text, encoding="utf-8")
        print(f"written {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
