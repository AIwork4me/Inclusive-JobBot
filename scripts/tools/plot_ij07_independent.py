"""Render independent TC-V2 and CPU tool-choice control figures."""

import argparse
import json
from pathlib import Path

from scripts.tools.plot_ij07_history import plt, save_svg, style


BACKENDS = {"vulkan": "Vulkan", "rocm": "ROCm/HIP"}
COLORS = ("#286C67", "#586898")


def load(path):
    return json.loads(path.read_bytes())


def metric_bars(axis, title, options, profiles, metric):
    style(axis, title, "Percent")
    locations = list(range(len(options)))
    for shift, label, color in zip((-0.18, 0.18), BACKENDS.values(), COLORS, strict=True):
        rates = [100 * metric(profiles[label], key) for key in options.values()]
        bars = axis.bar([position + shift for position in locations], rates, width=0.35,
                        color=color, label=label)
        axis.bar_label(bars, fmt="%.1f", label_type="center", color="white", fontsize=9)
    axis.set_xticks(locations, list(options))
    axis.set_ylim(0, 112)
    axis.set_yticks([0, 25, 50, 75, 100])


def render_tc_v2(evidence, output):
    profiles = {}
    for backend, label in BACKENDS.items():
        path = evidence / "tc_v2/holdout" / backend
        summary, coverage = load(path / "summary.json"), load(path / "coverage.json")
        if summary["first_pass"]["terminal"] != 500 or summary["repeat"]["completed"] != 150:
            raise ValueError("TC-V2 figures require both full backend profiles")
        profiles[label] = {**summary, **coverage}
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.8), layout="constrained")
    metric_bars(axes[0, 0], "First-pass trajectory", {
        "All cases": "overall", "Single tool": "single_tool", "Sequential": "sequential_multi_tool",
    }, profiles, lambda data, key: data["first_pass"]["case_rates"][key])
    for shift, label in zip((-0.18, 0.18), BACKENDS.values(), strict=True):
        profile = profiles[label]
        rate = profile["first_pass"]["case_rates"]["overall"]
        low, high = profile["wilson95_first_pass"]
        axes[0, 0].errorbar(shift, 100 * rate, yerr=[[100 * (rate - low)], [100 * (high - rate)]],
                            color="#263230", capsize=3, linewidth=0.9)
    metric_bars(axes[0, 1], "Required argument accuracy", {"All steps": "argument_accuracy"},
                profiles, lambda data, key: data["first_pass"][key])
    axes[0, 1].axhline(98, color="#B7533C", linestyle="--")
    axes[0, 1].annotate("98% gate", (0.98, 98), xycoords=("axes fraction", "data"),
                        xytext=(0, 4), textcoords="offset points", ha="right", color="#8C3625")
    metric_bars(axes[1, 0], "First-pass language", {"English": "en", "Chinese": "zh"}, profiles,
                lambda data, key: data["first_pass_by_language"][key]["PASS"]
                / sum(data["first_pass_by_language"][key].values()))
    metric_bars(axes[1, 1], "Three-seed reliability (50 cases)", {
        "At least one pass": "pass_at_3", "All three pass": "pass_all_3",
    }, profiles, lambda data, key: data["repeat"][key])
    fig.suptitle("Independent TC-V2 on Radeon 8060S", fontweight="bold")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, ncols=2, loc="outside lower center")
    save_svg(fig, output / "tc-v2-qualification.svg")


def render_tool_choice(evidence, output):
    data = load(evidence / "root_causes/explicit_tool_choice_cpu.json")
    cases = data["outcomes"]
    classes = {
        "Invalid selector": [key for key in cases if key.startswith("invalid-")],
        "Valid selector": [key for key in cases if not key.startswith("invalid-")],
    }
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 4.1), layout="constrained")
    for axis, (title, keys) in zip(axes, classes.items(), strict=True):
        style(axis, title, "Requests meeting expected HTTP status")
        expected = 400 if title == "Invalid selector" else 200
        counts = [sum(data[build]["cases"][key]["status"] == expected for key in keys)
                  for build in ("original", "patched")]
        bars = axis.bar(["Before", "After"], counts, color=COLORS, width=0.55)
        axis.bar_label(bars, labels=[f"{count}/{len(keys)}" for count in counts], padding=3)
        axis.set_ylim(0, len(keys) * 1.20)
    fig.suptitle("Explicit tool-choice validation control (CPU, JSON and SSE)", fontweight="bold")
    save_svg(fig, output / "tool-choice-control.svg")


def render_multitool_checkpoint(evidence, output):
    data = load(evidence / "multitool/primary-vulkan-checkpoint/coverage.json")
    depths = ("2-3", "4-5", "6-10", "11-15", "16-20")
    rates, limits, labels = [], [], []
    for depth in depths:
        result = data["strata"]["depth"][depth]
        count = sum(result["counts"].values())
        rates.append(100 * result["counts"].get("PASS", 0) / count)
        limits.append([100 * value for value in result["wilson95_among_terminal"]])
        labels.append(f"{depth}\nn={count}")
    fig, axis = plt.subplots(figsize=(8.4, 4.7), layout="constrained")
    style(axis, f"MULTITOOL-V1 Vulkan checkpoint · {data['terminal']}/{data['planned']} cases", "Pass rate (%)")
    axis.errorbar(list(range(len(depths))), rates,
                  yerr=[[rate - bounds[0] for rate, bounds in zip(rates, limits, strict=True)],
                        [bounds[1] - rate for rate, bounds in zip(rates, limits, strict=True)]],
                  fmt="o-", linewidth=1.6, capsize=5, color=COLORS[0])
    axis.set_xticks(list(range(len(depths))), labels)
    axis.set_ylim(0, 100)
    axis.set_xlabel("Required tool calls · Wilson 95% intervals within the completed prefix")
    save_svg(fig, output / "multitool-checkpoint-depth.svg")


def render_multitool_full(data, output):
    if data["terminals"] != 600 or not data["coverage_complete"]:
        raise ValueError("full MULTITOOL figures require 600 terminal cases")
    depths = ("2-3", "4-5", "6-10", "11-15", "16-20")
    values = [data["by_depth"][depth] for depth in depths]
    metrics = (
        ("Task and argument success", "Percent"),
        ("Error-recovery task success", "Percent"),
        ("Case wall time", "P95 seconds"),
        ("Inference per case", "Mean model calls"),
    )
    fig, axes = plt.subplots(2, 2, figsize=(9.7, 6.4), layout="constrained")
    for axis, (title, units) in zip(axes.flat, metrics, strict=True):
        style(axis, title, units)
        axis.set_xlabel("Required tool steps")
    x_values = list(range(len(depths)))
    rates = [100 * value["task_success"]["rate"] for value in values]
    interval = [[100 * rate for rate in value["wilson95_terminal"]] for value in values]
    axes[0, 0].errorbar(x_values, rates,
                       yerr=[[rate - limits[0] for rate, limits in zip(rates, interval, strict=True)],
                             [limits[1] - rate for rate, limits in zip(rates, interval, strict=True)]],
                       fmt="o-", capsize=4, color=COLORS[0], label="Task success (95% Wilson)")
    axes[0, 0].plot(x_values, [100 * value["argument_accuracy"]["rate"] for value in values],
                   "s--", color=COLORS[1], label="Argument fields")
    axes[0, 0].legend(frameon=False, loc="upper right")
    axes[0, 1].plot(x_values, [100 * value["recovery_task_success"]["rate"] for value in values],
                   "o-", color=COLORS[0])
    axes[1, 0].plot(x_values, [value["latency_ms_p95_nearest_rank"] / 1000 for value in values],
                   "o-", color=COLORS[0])
    axes[1, 1].plot(x_values, [value["model_calls_mean"] for value in values], "o-", color=COLORS[0])
    for axis in axes.flat:
        axis.set_xticks(x_values, depths)
        axis.set_ylim(bottom=0)
    axes[0, 0].set_ylim(top=106)
    axes[0, 1].set_ylim(top=106)
    fig.suptitle("MULTITOOL-V1 · 600 physical Vulkan trials", fontweight="bold")
    save_svg(fig, output / "multitool-full-depth.svg")

    fig, axes = plt.subplots(3, 1, figsize=(9, 8), layout="constrained")
    style(axes[0], "First unverified required node", "Cases")
    steps = list(range(1, 21))
    counts = data["first_unverified_tool_step"]
    axes[0].bar(steps, [counts.get(str(step), 0) for step in steps], color=COLORS[0], width=0.73)
    style(axes[1], "Conditional node verification", "Percent")
    conditional = data["conditional_step_success"]
    observed = [step for step in steps if str(step) in conditional]
    axes[1].plot(observed, [100 * conditional[str(step)]["rate"] for step in observed],
                 "o-", color=COLORS[1])
    axes[1].set_ylim(0, 106)
    for axis in axes[:2]:
        axis.set_xticks(steps)
    axes[1].set_xlabel("Position in the frozen topological oracle order")
    style(axes[2], "Recorded tokens per case", "Mean prompt + output")
    axes[2].plot(x_values, [value["token_mean"] for value in values], "o-", color=COLORS[0])
    axes[2].set_xticks(x_values, depths)
    axes[2].set_xlabel("Required tool steps")
    axes[2].set_ylim(bottom=0)
    save_svg(fig, output / "multitool-full-step-evidence.svg")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path("evidence/IJ07"))
    parser.add_argument("--output", type=Path, default=Path("evidence/IJ07/figures"))
    args = parser.parse_args()
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "svg.hashsalt": "IJ07-independent"})
    args.output.mkdir(parents=True, exist_ok=True)
    render_tc_v2(args.evidence, args.output)
    render_tool_choice(args.evidence, args.output)
    render_multitool_checkpoint(args.evidence, args.output)
    full = args.evidence / "multitool/primary-vulkan-full/metrics.json"
    if full.is_file():
        render_multitool_full(load(full), args.output)


if __name__ == "__main__":
    main()
