"""Per-campaign analysis: model x primitive capability matrix with
honest coverage accounting (IJ-NANO-48H order section 16).

Semantic accuracy counts CORRECT over MODEL-EVALUABLE outcomes only
(CORRECT + INCORRECT + INVALID_OUTPUT + EMPTY_OUTPUT); software /
unresolved buckets are reported separately and never enter the
denominator. Missing telemetry is reported as missing, never zero.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
RUNS = ROOT / "runs" / "n03h"

MODEL_CLASSES = {"CORRECT", "INCORRECT", "INVALID_OUTPUT", "EMPTY_OUTPUT"}


def analyze(workdir: pathlib.Path) -> dict:
    rows = []
    p = workdir / "results.jsonl"
    if p.is_file():
        rows = [json.loads(l) for l in
                p.read_text(encoding="utf-8").splitlines() if l.strip()]
    seal = None
    if (workdir / "seal.json").is_file():
        seal = json.loads((workdir / "seal.json").read_text(
            encoding="utf-8"))
    state = None
    if (workdir / "campaign_state.json").is_file():
        state = json.loads((workdir / "campaign_state.json").read_text(
            encoding="utf-8"))

    models = sorted({r["model"] for r in rows})
    prims = sorted({r.get("primitive") or "?" for r in rows})
    matrix: dict = {}
    for model in models:
        matrix[model] = {}
        for prim in prims:
            sub = [r for r in rows
                   if r["model"] == model and r.get("primitive") == prim]
            counts = collections.Counter(r["classification"] for r in sub)
            evaluable = sum(counts.get(c, 0) for c in MODEL_CLASSES)
            lat = [r["telemetry"].get("latency_s") for r in sub
                   if r["telemetry"].get("latency_s") is not None]
            tok = [r["telemetry"].get("completion_tokens") for r in sub
                   if r["telemetry"].get("completion_tokens") is not None]
            fin = collections.Counter(
                r["telemetry"].get("finish_reason") for r in sub)
            matrix[model][prim] = {
                "trials": len(sub),
                "counts": dict(counts),
                "evaluable": evaluable,
                "semantic_accuracy": round(
                    counts.get("CORRECT", 0) / evaluable, 4)
                if evaluable else None,
                "mean_latency_s": round(sum(lat) / len(lat), 3)
                if lat else None,
                "mean_completion_tokens": round(sum(tok) / len(tok), 1)
                if tok else None,
                "finish_reasons": dict(fin),
            }
    overall = {}
    for model in models:
        sub = [r for r in rows if r["model"] == model]
        counts = collections.Counter(r["classification"] for r in sub)
        evaluable = sum(counts.get(c, 0) for c in MODEL_CLASSES)
        overall[model] = {
            "trials": len(sub),
            "counts": dict(counts),
            "semantic_accuracy": round(
                counts.get("CORRECT", 0) / evaluable, 4) if evaluable
            else None,
            "empty_output_rate": round(
                counts.get("EMPTY_OUTPUT", 0) / evaluable, 4)
            if evaluable else None,
            "invalid_output_rate": round(
                counts.get("INVALID_OUTPUT", 0) / evaluable, 4)
            if evaluable else None,
        }
    langs = collections.Counter(
        (r["model"], r.get("language")) for r in rows)
    return {
        "workdir": str(workdir),
        "experiment": state.get("experiment_id") if state else
        workdir.name,
        "sealed": bool(seal and not seal.get("integrity_problems")),
        "seal": seal,
        "physical_attempts": state.get("physical_attempts")
        if state else None,
        "trials_recorded": len(rows),
        "overall": overall,
        "matrix": matrix,
        "language_split": {f"{m}|{l}": n for (m, l), n in
                           sorted(langs.items())},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("experiment_dir")
    args = ap.parse_args()
    wd = pathlib.Path(args.experiment_dir)
    if not wd.is_absolute():
        wd = RUNS / wd
    out = analyze(wd)
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
