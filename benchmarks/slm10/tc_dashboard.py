"""Replay published TC-V3 seals and derive scoped physical progress and pairing."""

import argparse
from collections import Counter, defaultdict
import gzip
import json
from math import ceil, sqrt
from pathlib import Path
from random import Random
import shutil

from benchmarks.root_cause.generation_capture import protocol_reply
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import ROOT, canonical

from .tc_v3 import HERE

ARCHIVE = ROOT / "evidence/IJSLM/tc-v3"
DASHBOARD = HERE.parent / "physical_progress.json"
SUMMARY = HERE.parent / "physical_progress.md"
PRIORITY = ("A", "B", "D")
STATUS = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")


def objects(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def load_seal(path):
    raw = path.read_bytes()
    check_text(raw)
    manifest = json.loads(raw)
    if manifest["identity"]["run_id"] != path.parent.name:
        raise ValueError("trial session directory does not match its manifest")
    decoded = {}
    for name, expected in manifest["artifacts"].items():
        if name not in {"gpu.jsonl.gz", "trials.jsonl.gz"} or digest(path.parent / name) != expected:
            raise ValueError("trial archive artifact does not match its seal")
        text = gzip.decompress((path.parent / name).read_bytes())
        check_text(text)
        decoded[name] = [json.loads(line) for line in text.splitlines()]
    rows = decoded["trials.jsonl.gz"]
    if len(rows) != manifest["reservations"]:
        raise ValueError("session reservation count differs from sealed rows")
    launch = manifest["launch"]
    counters = [row for row in decoded.get("gpu.jsonl.gz", ())
                if row.get("instance", "").startswith(f"pid_{launch['pid']}_")]
    mem = [row["committed_bytes"] for row in counters
           if row["kind"] == "gpu_process_memory" and row["committed_bytes"] > 0]
    gpu = (launch["backend"] == "vulkan" and launch["owns_port"] is True and 0 < launch["layers_offloaded"]
           == launch["layers_total"] and bool(mem)
           and any(row["kind"] == "gpu_engine" and row.get("engtype") in ("3D", "Compute")
                   and 0 < row.get("utilization", 0) <= 100 for row in counters))
    if any(row["physical_execution"] == "PASS" for row in rows) and not gpu:
        raise ValueError("physical rows lack independently replayable GPU evidence")
    return manifest, rows, max(mem, default=None)


def proportion(verdicts):
    counts = Counter(verdicts)
    n = counts["PASS"] + counts["FAIL"]
    if not n:
        return {status: counts[status] for status in STATUS} | {"rate": None, "wilson_95": None}
    p = counts["PASS"] / n
    z = 1.959963984540054
    center = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    error = z * sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return {status: counts[status] for status in STATUS} | {
        "rate": p, "wilson_95": [max(0, center - error), min(1, center + error)],
    }


def paired(observations, first, second, component):
    matches = []
    for case in observations.values():
        a, b = case.get(first, {}).get(component), case.get(second, {}).get(component)
        if a in STATUS[:2] and b in STATUS[:2]:
            matches.append((a == "PASS", b == "PASS"))
    n = len(matches)
    discordant = Counter(b - a for a, b in matches)
    vals = [b - a for a, b in matches]
    interval = None
    if n > 1 and len(discordant) > 1:
        rng = Random(7107)
        draws = sorted(sum(rng.choices(vals, k=n)) / n for _ in range(2000))
        interval = [draws[49], draws[1949]]
    return {"n": n, "first_only": discordant[-1], "second_only": discordant[1],
            "second_minus_first": sum(vals) / n if n else None, "bootstrap_95": interval}


def percentile(values):
    if not values:
        return {"n": 0, "p50": None, "p95": None}
    values = sorted(values)
    return {"n": len(values), "p50": values[ceil(len(values) * .5) - 1], "p95": values[ceil(len(values) * .95) - 1]}


def timings(trace):
    durations, tokens = [], []
    for event in trace.get("wire", ()):
        try:
            reply = protocol_reply(event["response"].encode(), json.loads(event["provider_request"])["stream"])
            timing = reply.get("timings") or {}
            durations.append(timing["prompt_ms"] + timing["predicted_ms"])
            tokens.append(reply["usage"]["total_tokens"])
        except (KeyError, TypeError, ValueError):
            continue
    count = len(trace.get("wire", ()))
    return count, sum(durations) if count and len(durations) == count else None, (
        sum(tokens) if count and len(tokens) == count else None)


def combined(values):
    return "FAIL" if "FAIL" in values else "PASS" if all(value == "PASS" for value in values) else "BLOCKED"


def dashboard(directory):
    roster = {row["trial_id"]: row for row in objects(HERE / "roster.jsonl")}
    cases = {row["case_id"]: row for row in objects(HERE / "holdout-public.jsonl")}
    planned = Counter(row["candidate"] for row in roster.values())
    baseline = {candidate: Counter(planned=count) for candidate, count in planned.items()}
    catalog = {}
    groups = defaultdict(Counter)
    pairs = defaultdict(lambda: defaultdict(dict))
    repeats = defaultdict(lambda: defaultdict(dict))
    sums = defaultdict(lambda: defaultdict(list))
    seen = set()
    for path in sorted(directory.glob("*/manifest.json")):
        manifest, rows, memory = load_seal(path)
        candidate = manifest["identity"]["candidate"]
        catalog[path.parent.name] = digest(path)
        for row in rows:
            key = row["trial_id"]
            task = roster[key]
            if key in seen or candidate != task["candidate"] or row["status"] not in STATUS:
                raise ValueError("duplicate or misrouted TC-V3 physical seal")
            seen.add(key)
            baseline[candidate]["sealed"] += 1
            baseline[candidate][row["status"]] += 1
            if row["physical_execution"] != "PASS":
                continue
            baseline[candidate]["executed"] += 1
            trace = row["trace"]
            case = cases[task["case_id"]]
            if any(trace[label] != task[label] for label in ("case_id", "track", "seed", "trial_id")):
                raise ValueError("sealed trace no longer matches frozen trial identity")
            metrics = row["component_assessment"].copy()
            metrics["complete_arguments"] = combined(
                [metrics[key] for key in ("required_arguments", "entity_binding", "json_schema")])
            if case["family"] != "clarification":
                metrics["first_pass_mechanical"] = combined([metrics["tool_selection"], metrics["tool_result"]])
            track = task["track"]
            if track == "sdk_repeat":
                repeats[candidate][case["case_id"]][task["seed"]] = metrics
            else:
                pairs[candidate][case["case_id"]][track] = metrics
            for name, status in metrics.items():
                for stratum in ("all", "language/" + case["language"], "family/" + case["family"]):
                    groups[candidate, track, stratum, name][status] += 1
            count, latency, tokens = timings(trace)
            sums[candidate, track]["model_requests"].append(count)
            if latency is not None:
                sums[candidate, track]["provider_ms"].append(latency)
            if tokens is not None:
                sums[candidate, track]["total_tokens"].append(tokens)
        if memory is not None:
            sums[candidate, "all"]["session_peak_gpu_committed_bytes"].append(memory)
    models = {}
    for model, count in baseline.items():
        if model not in PRIORITY and not count["sealed"]:
            continue
        count["NOT_RUN"] = count["planned"] - count["sealed"]
        models[model] = {key: count[key] for key in ("planned", "executed", "sealed", *STATUS)}
    by_scope = {
        "/".join(key): proportion(status for status, n in counts.items() for _ in range(n))
        for key, counts in groups.items()
    }
    comparisons = {
        model: {f"{first}_vs_{second}/{component}": paired(pairs[model], first, second, component)
                for first, second in (("direct_first", "sdk_first"), ("sdk_first", "sdk_streaming"))
                for component in ("first_pass_mechanical", "tool_selection", "required_arguments", "tool_result")}
        for model in PRIORITY
    }
    repeat_checks = {}
    for model in PRIORITY:
        cells = [row for row in repeats[model].values() if len(row) == 3]
        evaluable = [list(row.values()) for row in cells
                     if all(cell.get("first_pass_mechanical") in STATUS[:2] for cell in row.values())]
        repeat_checks[model] = {"three_seed_cases": len(cells), "evaluated": len(evaluable),
                                "all_pass": sum(all(m["first_pass_mechanical"] == "PASS" for m in row)
                                                for row in evaluable)}
    return {
        "models": models, "sealed_manifests": catalog, "core_required": 36550,
        "core_remaining": 36550 - sum(count["executed"] for count in models.values()),
        "component_matrix": by_scope, "paired_matrix": comparisons, "repeat_matrix": repeat_checks,
        "performance": {"/".join(key): {metric: percentile(values) for metric, values in fields.items()}
                        for key, fields in sums.items()},
        "notes": {
            "strict_end_to_end": "BLOCKED pending qualified semantic and remaining mechanical evidence",
            "confidence_intervals": "Wilson intervals use observed PASS/FAIL only. Paired bootstrap uses complete evaluable pairs.",
            "provider_ms": "Sum of native prompt and prediction timings. Excludes SDK and tool overhead.",
            "sdk_first": "Real SDK with provider JSON validated and adapted to SSE at the SDK boundary.",
            "sdk_streaming": "Real SDK with provider SSE. The security boundary buffers each complete response.",
            "gpu_memory": "Peak committed bytes per instrumented llama-server GPU session.",
        },
    }


def markdown(report):
    lines = [
        "# TC-V3 physical progress", "",
        f"Core trials remaining: **{report['core_remaining']:,} of 36,550**.", "",
        "| Candidate | Planned | Executed | Sealed | Strict PASS | Strict FAIL | Strict BLOCKED | NOT_RUN |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model, count in report["models"].items():
        numbers = (count[key] for key in ("planned", "executed", "sealed", *STATUS))
        lines.append("| " + model + " | " + " | ".join(f"{number:,}" for number in numbers) + " |")
    lines += ["", "## Tool selection by track", "",
              "| Candidate and track | PASS | FAIL | BLOCKED | Wilson 95% CI |",
              "|---|---:|---:|---:|---:|"]
    for key, metrics in sorted(report["component_matrix"].items()):
        model, track, scope, component = key.split("/", 3)
        if (scope, component) != ("all", "tool_selection"):
            continue
        limits = metrics["wilson_95"]
        interval = "—" if limits is None else f"{limits[0]:.1%}–{limits[1]:.1%}"
        lines.append(f"| {model} / {track} | {metrics['PASS']} | {metrics['FAIL']} | {metrics['BLOCKED']} | {interval} |")
    lines += ["", "The current rows represent the completed portion of the frozen roster. "
              "Use the full matrix for paired effects, case strata, repeats and provider telemetry. "
              "[Machine-readable dashboard](physical_progress.json)", ""]
    return "\n".join(lines).encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish-from", type=Path, action="append")
    args = parser.parse_args()
    if args.publish_from is not None:
        paths = sorted(path for source in args.publish_from for path in source.glob("*/manifest.json"))
        for path in paths:
            manifest, _, _ = load_seal(path)
            destination = ARCHIVE / path.parent.name
            destination.mkdir(parents=True, exist_ok=True)
            for name in (*manifest["artifacts"], "manifest.json"):
                source, target = path.parent / name, destination / name
                if target.exists():
                    if digest(target) != digest(source):
                        raise ValueError("published physical seal differs from the runtime copy")
                else:
                    shutil.copyfile(source, target)
        report = dashboard(ARCHIVE)
        DASHBOARD.write_bytes(canonical(report) + b"\n")
        SUMMARY.write_bytes(markdown(report))
    replay = dashboard(ARCHIVE)
    if DASHBOARD.read_bytes() != canonical(replay) + b"\n" or SUMMARY.read_bytes() != markdown(replay):
        raise ValueError("published dashboard differs from replayed physical seals")
    report = json.loads(DASHBOARD.read_bytes())
    print(json.dumps({"models": report["models"], "core_remaining": report["core_remaining"]}, indent=2))


if __name__ == "__main__":
    main()
