"""Render the E1 capability atlas + E2 adapter-effects reports
(IJ-NANO-48H deliverables) from the atlas analysis JSON.

Honesty rules baked in: missing cells render as `—` (never 0.000);
unsealed campaigns are marked; software buckets stay separate;
W0-for-E2 reuse is labeled as reuse with its identity basis.
"""
from __future__ import annotations

import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]


def fmt(x, digits=3, pct=True):
    if x is None:
        return "—"
    return f"{x * 100:.{digits}f}%" if pct else f"{x:.{digits}f}"


def render_e1(e1: dict) -> str:
    lines = ["# IJ-NANO-48H — E1 Cognitive Capability Atlas (development)",
             "",
             "Chat protocol, temperature 0, seed 42, 1024-token "
             "generation budget, frozen renderer; 640 development cases "
             "x 3 models. Semantic accuracy counts CORRECT over "
             "model-evaluable outcomes only.", "",
             "## Campaign provenance", "",
             "| Batch | Experiment | Trials | Sealed |",
             "|---|---|---:|---|"]
    for b, v in sorted(e1["campaigns"].items()):
        lines.append(f"| {b} | `{v['experiment']}` | {v['trials']} | "
                     f"{'SEALED' if v['sealed'] else 'IN PROGRESS'} |")
    lines += ["", "## Overall", "",
              "| Model | n | Accuracy | EMPTY | INVALID | Mean latency "
              "| Mean completion tokens |", "|---|---:|---:|---:|---:|"
              "---:|---:|"]
    for m, v in e1["overall"].items():
        c = v["counts"]
        ev = v["evaluable"]
        lines.append(
            f"| {m} | {v['trials']} | {fmt(v['accuracy'])} | "
            f"{fmt(c.get('EMPTY_OUTPUT', 0) / ev if ev else None)} | "
            f"{fmt(c.get('INVALID_OUTPUT', 0) / ev if ev else None)} | "
            f"{fmt(v['mean_latency_s'], 2, False)} s | "
            f"{v['mean_completion_tokens'] or '—'} |")
    lines += ["", "## Per-primitive semantic accuracy", ""]
    prims = e1["primitives"]
    models = e1["models"]
    lines.append("| Primitive | " + " | ".join(models) + " |")
    lines.append("|---|" + "---:|" * len(models))
    for p in prims:
        row = [p]
        for m in models:
            cell = e1["matrix"][m].get(p, {})
            row.append(f"{fmt(cell.get('accuracy'))} "
                       f"({cell.get('trials', 0)})")
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "Cells show accuracy (trials). `—` = no evaluable "
              "evidence yet — never treated as zero.", ""]
    return "\n".join(lines)


def render_e2(e2: dict) -> str:
    lines = ["# IJ-NANO-48H — E2 Harness-Adapter Cognitive Effects",
             "",
             f"W0 source: {e2['w0_source']} ({e2['w0_cases']} cases). "
             "Paired comparisons on matched dev cases; exact McNemar "
             "over discordant pairs; Newcombe 95% CIs.", "",
             "Adapter campaign: "
             + ("SEALED" if e2["adapter_campaign_sealed"]
                else "IN PROGRESS / NOT RUN"), "",
             "## Paired adapter vs W0 (all primitives)", "",
             "| Adapter | Matched n | Adapter acc | W0 acc | Δ | 95% CI "
             "| wins | losses | McNemar p |", "|---|---:|---:|---:|---:|"
             "---|---:|---:|---:|"]
    for a, v in e2["paired"].items():
        ci = v["newcombe95_ci"]
        ci_s = f"[{ci[0]:+.3f}, {ci[1]:+.3f}]" if ci else "—"
        lines.append(
            f"| {a} | {v['matched_cases']} | "
            f"{fmt(v['adapter_accuracy'])} | {fmt(v['w0_accuracy'])} | "
            f"{v['paired_delta'] if v['paired_delta'] is not None else '—'}"
            f" | {ci_s} | {v['wins_b']} | {v['losses_c']} | "
            f"{v['mcnemar_exact_p']} |")
    lines += ["", "## Per-primitive accuracy (adapter vs W0)", ""]
    adapters = list(e2["per_primitive"])
    prims = sorted(next(iter(e2["per_primitive"].values()), {}))
    for a in adapters:
        lines += [f"### {a}", "",
                  "| Primitive | Adapter | W0 |", "|---|---:|---:|"]
        for p in prims:
            v = e2["per_primitive"][a].get(p, {})
            ad = v.get("adapter", {})
            w0 = v.get("w0", {})
            lines.append(f"| {p} | {fmt(ad.get('accuracy'))} "
                         f"({ad.get('trials', 0)}) | "
                         f"{fmt(w0.get('accuracy'))} "
                         f"({w0.get('trials', 0)}) |")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("analysis_json")
    ap.add_argument("--e1-out",
                    default="reports/IJNANO_03_SLM_COGNITIVE_"
                            "CAPABILITY_ATLAS.md")
    ap.add_argument("--e2-out",
                    default="reports/IJNANO_HARNESS_ADAPTER_COGNITIVE_"
                            "EFFECTS.md")
    args = ap.parse_args()
    data = json.loads(pathlib.Path(args.analysis_json)
                      .read_text(encoding="utf-8"))
    e1_path = ROOT / args.e1_out
    e1_path.parent.mkdir(parents=True, exist_ok=True)
    e1_path.write_text(render_e1(data["e1"]), encoding="utf-8")
    print(f"written {e1_path}")
    if "e2" in data:
        e2_path = ROOT / args.e2_out
        e2_path.write_text(render_e2(data["e2"]), encoding="utf-8")
        print(f"written {e2_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
