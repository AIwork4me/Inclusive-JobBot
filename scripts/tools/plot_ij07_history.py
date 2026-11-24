"""Render publication figures only from full, verified historical runs."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt


ARMS = ("R0-V", "R0-R", "R1-V", "R1-R")
COLORS = ("#286C67", "#B7533C", "#A58E53")
LABELS = ("b12359\nVulkan", "b12359\nROCm/HIP", "P4b\nVulkan", "P4b\nROCm/HIP")


def style(axis, title, ylabel):
    axis.set_title(title, loc="left", fontweight="bold")
    axis.set_ylabel(ylabel)
    axis.spines[["top", "right"]].set_visible(False)
    axis.set_axisbelow(True)
    axis.grid(axis="y", color="#D7E0DC", linewidth=0.65)


def save_svg(fig, path):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        fig.savefig(handle, format="svg", metadata={"Date": None})
    plt.close(fig)


def render(replay, performance, output):
    if replay["cases_executed"] != 2000 or set(replay["arms"]) != set(ARMS):
        raise ValueError("figures require four complete 500-case runs")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "svg.hashsalt": "IJ07"})
    output.mkdir(parents=True, exist_ok=True)
    counts = [replay["arms"][arm]["v2"]["status"] for arm in ARMS]
    fig, axis = plt.subplots(figsize=(8.5, 4.8), layout="constrained")
    style(axis, "Historical replay outcomes by parser and backend", "Cases")
    baseline = [0] * len(ARMS)
    for status, color in zip(("PASS", "FAIL", "BLOCKED"), COLORS, strict=True):
        heights = [row.get(status, 0) for row in counts]
        bars = axis.bar(LABELS, heights, bottom=baseline, label=status, color=color, width=0.61)
        axis.bar_label(bars, label_type="center", color="white", fontweight="bold")
        baseline = [old + new for old, new in zip(baseline, heights, strict=True)]
    axis.set_ylim(0, 550)
    axis.legend(loc="upper center", ncols=3, frameon=False)
    save_svg(fig, output / "historical-outcomes.svg")

    reports = {entry["identity"]["arm"]: entry for entry in performance}
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6), layout="constrained")
    for axis, phase in zip(axes, ("prefill", "decode"), strict=True):
        rates = [reports[arm]["trajectory_phases"][phase]["duration_weighted_tokens_per_second"] for arm in ARMS]
        style(axis, f"Native {phase}", "Tokens/s")
        bars = axis.bar(LABELS, rates, color=["#286C67", "#586898", "#286C67", "#586898"], width=0.64)
        axis.bar_label(bars, fmt="%.1f", padding=3)
        axis.set_ylim(0, max(rates) * 1.16)
        axis.tick_params(axis="x", labelsize=9)
    fig.suptitle("Radeon diagnostic throughput per measured trajectory", fontweight="bold")
    save_svg(fig, output / "historical-throughput.svg")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--performance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(json.loads(args.replay.read_bytes()), json.loads(args.performance.read_bytes()), args.output)


if __name__ == "__main__":
    main()
