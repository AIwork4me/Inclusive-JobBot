"""Verify and archive a full MULTITOOL-V1 panel or a timestamped checkpoint prefix."""

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path

from benchmarks.job_productivity_v1.statistics import wilson_interval
from benchmarks.multitool_v1 import dataset
from benchmarks.multitool_v1.run import digest
from benchmarks.tool_calling_v2.holdout.qualify import pid_counter_proof, read_checkpoint
from scripts.tools.scan_sensitive import scan


def rate_intervals(strata):
    return {
        key: {"counts": dict(counts),
              "wilson95_among_terminal": wilson_interval(counts["PASS"], sum(counts.values()))}
        for key, counts in sorted(strata.items())
    }


def archive(source, output, *, pc_s=False, pc_s_checkpoint=False, pc_s_stream_pairs=False, draft_guard_control=None):
    run_path = source / "run.json"
    summary_path = source / "summary.json"
    run = json.loads(run_path.read_bytes())
    config = run["configuration"]
    freeze = dataset.load_freeze()
    reference = pc_s or pc_s_checkpoint or pc_s_stream_pairs or draft_guard_control is not None
    scope = "diagnostic" if reference else "full_panel"
    if (run["fingerprint"] != digest(config) or config["freeze_sha256"] != freeze.manifest["freeze_sha256"]
            or config["scope"] != scope):
        raise ValueError("MULTITOOL run identity differs from the requested freeze")
    if draft_guard_control is not None:
        from scripts.tools.atlas_pc_s import draft_guard_roster

        selected = set(draft_guard_roster())
        if (config["candidate"] != "J" or config["panel"] != "primary" or config.get("stream")
                or bool(config.get("require_observed_draft")) != (draft_guard_control == "observed")
                or len(config["roster"]) != len(selected)
                or {row["case_id"] for row in config["roster"]} != selected):
            raise ValueError("MULTITOOL draft authorization diagnostic differs from its frozen treatment")
    elif reference:
        from scripts.tools.atlas_reference_panel import create

        frozen = create()["multitool_v1"]
        selected = {case_id for group in frozen["selection_by_stratum"].values()
                    for case_id in (group[:1] if pc_s_stream_pairs else group)}
        if (config["candidate"] not in {"H", "J"} or config["panel"] != "primary"
                or bool(config.get("stream")) != pc_s_stream_pairs or len(config["roster"]) != len(selected)
                or {row["case_id"] for row in config["roster"]} != selected):
            raise ValueError("MULTITOOL PC-S run differs from the frozen Qwen reference roster")
    roster = {item["key"]: (item["case_id"], item["seed"]) for item in config["roster"]}
    final_summary = json.loads(summary_path.read_bytes()) if summary_path.is_file() else None
    paths = sorted((source / "cases").glob("*.json"))
    interruptions = sorted((source / "interruptions").glob("*.json"))
    names = {"run.json", *(p.relative_to(source).as_posix() for p in paths + interruptions)}
    if final_summary is not None:
        names.add("summary.json")
    for session in run["sessions"].values():
        names.add(session["counter_file"])
    if scan(source, sorted(names)):
        raise ValueError("MULTITOOL evidence failed privacy checks")
    rows, wire_digest = [], hashlib.sha256()
    for path in paths:
        row = read_checkpoint(path, run, path.stem, source / "sqlite")
        if roster.get(path.stem) != (row["case_id"], row["seed"]):
            raise ValueError(f"unexpected case or seed {path.stem}")
        rows.append((row, path.read_bytes().strip() + b"\n"))
    if not rows:
        raise ValueError("MULTITOOL has no terminal records")
    if final_summary is not None and len(rows) != final_summary["terminal"]:
        raise ValueError("terminal count differs from recorded summary")
    counters = defaultdict(Counter)
    findings = Counter()
    for row, wire in rows:
        wire_digest.update(wire)
        language = freeze.active[row["case_id"]].oracle["language"]
        for dimension, key in (("depth", row["depth_bin"]), ("category", row["category"]),
                               ("language", language), ("disposition", row["expected_outcome"])):
            counters[dimension][key, row["status"]] += 1
        findings.update(item["code"] for item in row["findings"])
    strata = {}
    for dimension, entries in counters.items():
        groups = defaultdict(Counter)
        for (key, status), count in entries.items():
            groups[key][status] = count
        strata[dimension] = rate_intervals(groups)
    resolved = final_summary is not None and len(rows) == len(roster)
    counts = Counter(row["status"] for row, _ in rows)
    sessions = {row["session"] for row, _ in rows}
    proof = {tag: pid_counter_proof(source, run["sessions"][tag]) for tag in sorted(sessions)}
    result = {
        "run_id": run["run_id"], "configuration_sha256": run["fingerprint"], "coverage_complete": resolved,
        "planned": len(roster), "terminal": len(rows), "pending": len(roster) - len(rows),
        "terminal_outcomes": dict(counts), "run_end_summary": final_summary, "strata": strata,
        "finding_counts": dict(findings), "interrupted_attempts": len(interruptions),
        "argument_correct": sum(row["argument_correct"] for row, _ in rows),
        "argument_total": sum(row["argument_total"] for row, _ in rows),
        "terminal_uncompressed_sha256": wire_digest.hexdigest(),
        "physical_sessions": proof,
        "source_capture_scope": "per-request generation traces; live sampler snapshots may continue growing",
    }
    if reference and (final_summary is None or final_summary["physical_evidence_status"] != "PASS"
                      or any(run["sessions"][tag].get("proof") != info or info["status"] != "PASS"
                             for tag, info in proof.items())):
        raise ValueError("MULTITOOL PC-S requires a closed physical checkpoint")
    if (pc_s or pc_s_stream_pairs or draft_guard_control is not None) and not resolved:
        raise ValueError("MULTITOOL PC-S full coverage requires all frozen trials")
    output.mkdir(parents=True, exist_ok=False)
    (output / "run.json").write_bytes(dataset.canonical(run))
    with (output / "terminal.jsonl.gz").open("wb") as handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0, compresslevel=6) as compressed:
            for _, wire in rows:
                compressed.write(wire)
    for tag, session_proof in proof.items():
        name = run["sessions"][tag]["counter_file"]
        snapshot = (source / name).read_bytes()
        snapshot_sha256 = hashlib.sha256(snapshot).hexdigest()
        recorded = session_proof.get("sha256", {}).get("counter")
        if (resolved or reference) and snapshot_sha256 != recorded:
            raise ValueError(f"final session counter snapshot differs from proof: {tag}")
        session_proof["published_counter_sha256"] = snapshot_sha256
        (output / (name + ".gz")).write_bytes(gzip.compress(snapshot, mtime=0))
    (output / "coverage.json").write_bytes(dataset.canonical(result))
    print(f"PASS: archived {len(rows)}/{len(roster)} exact MULTITOOL checkpoints")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--pc-s", action="store_true", help="verify the complete frozen Qwen reference diagnostic")
    mode.add_argument("--pc-s-checkpoint", action="store_true", help="verify a closed batch of the frozen reference panel")
    mode.add_argument("--pc-s-stream-pairs", action="store_true", help="verify the fixed depth/language streaming panel")
    mode.add_argument("--draft-guard-control", choices=("legacy", "observed"))
    args = parser.parse_args()
    archive(args.source, args.output, pc_s=args.pc_s, pc_s_checkpoint=args.pc_s_checkpoint,
            pc_s_stream_pairs=args.pc_s_stream_pairs, draft_guard_control=args.draft_guard_control)


if __name__ == "__main__":
    main()
