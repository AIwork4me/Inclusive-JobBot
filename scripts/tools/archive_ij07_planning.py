"""Verify, summarize and optionally archive a frozen AGENTIC-PLAN-V1 run.

python -m scripts.tools.archive_ij07_planning --source .runtime/ij07-planning-diagnostic
Add --output NEW_DIRECTORY to archive the exact evidence and a diagnostic JSON report.
"""

import argparse
from collections import Counter, defaultdict
from hashlib import file_digest, sha256
import json
from pathlib import Path, PurePosixPath
import re
from shutil import copyfile
from statistics import pvariance
from tempfile import TemporaryDirectory

from benchmarks.agentic_planning_v1.contract import THRESHOLDS_PCT
from benchmarks.agentic_planning_v1.freeze import FROZEN, encode, verify
from benchmarks.job_productivity_v1.statistics import wilson_interval
from scripts.tools.scan_sensitive import scan


STATUSES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
TRACKS = ("A", "P")
JOURNAL_NAME = re.compile(r"attempts/(AP1-L[0-7]-\d{3}-[AP]-0[1-3])\.[0-9a-f]{32}\.jsonl")
SESSION_NAME = re.compile(r"[0-9a-f]{32}-(?:gpu|generation)\.jsonl")


def digest(value):
    return sha256(encode(value)).hexdigest()


def sha(path):
    with path.open("rb") as handle:
        return file_digest(handle, "sha256").hexdigest()


def document(path):
    return json.loads(path.read_bytes())


def jsonl(path):
    with path.open("rb") as handle:
        for line in handle:
            yield json.loads(line)


def safe_file(directory, name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name or str(path) != name:
        raise ValueError("invalid archive path")
    target = directory / path
    if not target.resolve().is_relative_to(directory.resolve()):
        raise ValueError("archive path escapes source directory")
    return target


def verify_roster(config):
    if config["manifest"] != verify(FROZEN) or config["selection"] not in {"diagnostic", "complete_panel"}:
        raise ValueError("run does not match the frozen planning benchmark")
    cases = {case["case_id"]: case for case in jsonl(FROZEN / "datasets/holdout.jsonl")}
    trial_rows = config["trials"]
    if not trial_rows or config["panel"] not in {"primary", "repeat"}:
        raise ValueError("missing planning roster or panel identity")
    repeat = document(FROZEN / "datasets/repeat_panel.json")
    eligible = [case["case_id"] for case in repeat["cases"]] if config["panel"] == "repeat" else list(cases)
    seeds = repeat["seeds"] if config["panel"] == "repeat" else [trial_rows[0]["seed"]]
    tracks = sorted({trial["track"] for trial in trial_rows})
    selected = {trial["case_id"] for trial in trial_rows}
    if (not selected.issubset(eligible) or not set(tracks).issubset(TRACKS)
            or any(type(seed) is not int or not 0 <= seed < 2**32 - 1 for seed in seeds)
            or (config["selection"] == "complete_panel" and selected != set(eligible))):
        raise ValueError("run selects cases, tracks or seeds outside the frozen panel")
    expected = [
        {"trial_id": f"{case_id}-{track}-{index:02}", "case_id": case_id, "track": track,
         "repeat_index": index, "seed": seed}
        for case_id in eligible if case_id in selected for track in tracks for index, seed in enumerate(seeds, 1)
    ]
    if trial_rows != expected:
        raise ValueError("roster trial order, seed or identity differs from the freeze")
    return cases, {row["trial_id"]: row for row in expected}


def session_evidence(source, run, hashes):
    """Bind source observer rows and GPU telemetry to recorded sessions."""
    indexes, proofs = {}, {}
    names = set()
    for index, session in enumerate(run["sessions"], 1):
        if session.get("backend") != run["configuration"]["backend"]:
            raise ValueError("session backend differs from the run identity")
        traces = {}
        positive = 0
        memory = False
        for key, suffix in (("trace_file", "-generation.jsonl"), ("counter_file", "-gpu.jsonl")):
            name = session.get(key)
            if name is None:
                continue
            if type(name) is not str or not SESSION_NAME.fullmatch(name) or not name.endswith(suffix) or name in names:
                raise ValueError("invalid or reused session evidence filename")
            names.add(name)
            path = safe_file(source, name)
            if not path.is_file():
                continue
            hashes[name] = sha(path)
            if key == "trace_file":
                for row in jsonl(path):
                    completion = row["completion_id"]
                    if completion in traces:
                        raise ValueError("duplicate source completion ID in session")
                    traces[completion] = digest(row)
            else:
                prefix = f"pid_{session['pid']}_"
                for row in jsonl(path):
                    if not row.get("instance", "").startswith(prefix):
                        continue
                    util = row.get("utilization", 0)
                    if (row["kind"] == "gpu_engine" and row.get("engtype") in {"3D", "Compute"}
                            and type(util) in (float, int) and 0 < util <= 100):
                        positive += 1
                    if row["kind"] == "gpu_process_memory" and row.get("committed_bytes", 0) > 0:
                        memory = True
        indexes[index] = traces
        launch = (session.get("owns_port") is True and session.get("layers_offloaded", 0) > 0
                  and (session.get("gpu") or {}).get("architecture") == "gfx1151" and session.get("build")
                  and session.get("template_sha256"))
        proofs[index] = {"status": "PASS" if launch and positive and memory else "BLOCKED",
                         "gpu": session.get("gpu"), "build": session.get("build"),
                         "layers_offloaded": session.get("layers_offloaded"), "positive_engine_samples": positive,
                         "process_gpu_memory_observed": memory, "indexed_source_completions": len(traces)}
    return indexes, proofs


def verify_journal(path, name, run, trial, result, indexes, used_completions):
    raw = path.read_bytes()
    journal_sha = sha256(raw).hexdigest()
    if result is not None and journal_sha != result["journal_sha256"]:
        raise ValueError(f"attempt journal digest differs for {trial['trial_id']}")
    lines = raw.splitlines()
    if not lines:
        raise ValueError("empty recorded attempt journal")
    head = json.loads(lines[0])
    session = head.get("server_session")
    if (head.get("kind") != "attempt" or head.get("trial") != trial or head.get("run_id") != run["run_id"]
            or head.get("configuration_sha256") != run["fingerprint"] or type(session) is not int
            or not 1 <= session <= len(run["sessions"])):
        raise ValueError(f"attempt header differs from the run: {name}")
    if result is None:
        return journal_sha, None

    events = [json.loads(line) for line in lines[1:]]
    expected_terminal = {"kind": "terminal", "status": result["status"], "findings": result["findings"]}
    if not events or not raw.endswith(b"\n") or events[-1] != expected_terminal or session != result["server_session"]:
        raise ValueError("journal terminal event differs from the checkpoint")
    requests = {}
    observed, captures = [], set()
    bound = 0
    for event in events[:-1]:
        kind, turn = event["kind"], event.get("turn")
        if kind == "request":
            if type(turn) is not int or turn != len(requests) or event["body"].get("seed") != trial["seed"]:
                raise ValueError("journal request turn or seed differs from the checkpoint")
            requests[turn] = event["body"]
        elif kind == "capture":
            if turn not in requests or turn in captures:
                raise ValueError("journal capture lacks a unique earlier request")
            capture = event["wire"]
            body = capture["request"]
            if any(body.get(key) != value for key, value in requests[turn].items()):
                raise ValueError("captured wire request differs from the journal request")
            captures.add(turn)
            generation = capture.get("source_generation") or {}
            completion = generation.get("completion_id")
            if completion in indexes[session]:
                if digest(generation) != indexes[session][completion] or (session, completion) in used_completions:
                    raise ValueError("source observer hash differs or a completion was reused")
                ids = response_ids(capture.get("raw_response"), body.get("stream") is True)
                if ids and ids != {completion}:
                    raise ValueError("source observer completion identity differs from the wire")
                used_completions.add((session, completion))
                bound += 1
        elif kind == "proposals":
            if turn not in captures:
                raise ValueError("journal proposal lacks captured model evidence")
        elif kind == "observation":
            if event["record"]["turn"] not in captures:
                raise ValueError("journal observation precedes captured model evidence")
            observed.append(event["record"])
        else:
            raise ValueError("unexpected event in completed attempt journal")
    if observed != result["records"]:
        raise ValueError("journal observations differ from the terminal checkpoint")
    coverage = {"requests": len(requests), "captured": len(captures), "observer_bound": bound,
                "status": "PASS" if len(requests) == len(captures) == bound > 0 else "BLOCKED"}
    return journal_sha, coverage


def response_ids(raw, stream):
    """Observe comparable response IDs and leave a malformed wire to its recorded finding."""
    if type(raw) is not str:
        return set()
    try:
        rows = [json.loads(line[5:].strip()) for line in raw.splitlines()
                if line.startswith("data:") and line[5:].strip() != "[DONE]"] if stream else [json.loads(raw)]
    except ValueError:
        return set()
    return {row["id"] for row in rows if type(row) is dict and type(row.get("id")) is str}


def count_status(values):
    counts = Counter(dict.fromkeys(STATUSES, 0))
    counts.update(values)
    return counts


def rates(counts):
    total = sum(counts.values())
    assessed = counts["PASS"] + counts["FAIL"]
    return {"planned_n": total, "assessable_n": assessed, "counts": counts,
            "verified_success_per_planned": counts["PASS"] / total if total else None,
            "assessable_success_rate": counts["PASS"] / assessed if assessed else None,
            "wilson95_assessable": wilson_interval(counts["PASS"], assessed),
            "success_bounds_including_unknown": [counts["PASS"] / total, 1 - counts["FAIL"] / total] if total else None}


def repeat_summary(trials):
    grouped = defaultdict(list)
    per_seed = defaultdict(list)
    for row, status in trials:
        grouped[row["case_id"]].append(status)
        per_seed[row["seed"]].append(status)
    first, any_three, all_three = [], [], []
    transitions = Counter()
    for statuses in grouped.values():
        first.append(statuses[0])
        transitions.update(f"{left}->{right}" for left, right in zip(statuses, statuses[1:]))
        unknown = "BLOCKED" if "BLOCKED" in statuses else "NOT_RUN"
        any_three.append("PASS" if "PASS" in statuses else "FAIL" if set(statuses) == {"FAIL"} else unknown)
        all_three.append("FAIL" if "FAIL" in statuses else "PASS" if set(statuses) == {"PASS"} else unknown)
    seed_rates = {str(seed): rates(count_status(statuses)) for seed, statuses in per_seed.items()}
    complete = len(seed_rates) == 3 and all(rate["planned_n"] == rate["assessable_n"] for rate in seed_rates.values())
    return {"first_pass": rates(count_status(first)), "pass_at_three": rates(count_status(any_three)),
            "pass_all_three": rates(count_status(all_three)), "transitions": transitions, "by_seed": seed_rates,
            "population_variance_of_seed_pass_rates": pvariance(rate["assessable_success_rate"] for rate in seed_rates.values())
            if complete else None}


def observations(rows):
    metrics = defaultdict(list)
    for row in rows:
        for key, value in row.get("metrics", {}).items():
            if value is not None:
                metrics[key].append(value)
        plan = row.get("plan")
        if row["track"] == "P" and plan is not None:
            metrics["initial_plan_observed"].append(plan["observed"])
            metrics["initial_subgoal_coverage"].append(plan["initial_subgoal_coverage"])
            metrics["initial_plan_preceded_tools"].append(row["plan_before_tools"])
    return {key: {"observations": len(values), "sum": sum(values), "mean": sum(values) / len(values)}
            for key, values in sorted(metrics.items())}


def failure_indicators(rows):
    codes = Counter()
    for row in rows:
        if row["status"] == "PASS":
            continue
        seen = {finding["code"] for finding in row["findings"]}
        if row["status"] == "FAIL":
            if row.get("final_raw") is not None and row.get("final_matches") is False:
                seen.add("FINAL_ANSWER_MISMATCH")
            if row.get("errors"):
                seen.add("ORACLE_TRACE_ERROR")
            if row.get("metrics", {}).get("required_subgoal_coverage", 1) < 1:
                seen.add("REQUIRED_SUBGOALS_MISSING")
        codes.update(seen or {"NO_RECORDED_FAILURE_INDICATOR"})
    return codes


def groups(run, roster, cases, results, trace_proof, session_proof):
    config = run["configuration"]
    repeat = config["panel"] == "repeat"
    stats = {track: {} for track in TRACKS}
    for track in TRACKS:
        for level in THRESHOLDS_PCT:
            trials = [trial for trial in roster.values() if trial["track"] == track and cases[trial["case_id"]]["level"] == level]
            rows = [results[trial["trial_id"]] for trial in trials if trial["trial_id"] in results]
            pairs = [(trial, results.get(trial["trial_id"], {}).get("status", "NOT_RUN")) for trial in trials]
            first = rates(count_status(status for trial, status in pairs if trial["repeat_index"] == 1))
            attribution, safety = Counter(), Counter()
            for row in rows:
                attribution.update(row["attribution"])
                safety.update(row["safety"])
            coverage = [trace_proof[row["trial"]["trial_id"]]["status"] == "PASS"
                        and session_proof[row["server_session"]]["status"] == "PASS" for row in rows]
            evidence = "NOT_RUN"
            if rows and (not all(coverage) or any(r["status"] == "BLOCKED" for r in rows)):
                evidence = "BLOCKED"
            elif rows and len(rows) == len(trials):
                evidence = "PASS"
            nominal = 20 if repeat else 100
            threshold = THRESHOLDS_PCT[level] / 100
            qualification = {"status": "NOT_RUN", "threshold": threshold, "statistically_supported": None}
            if not repeat and config["selection"] == "complete_panel" and first["planned_n"] == nominal:
                if evidence == "BLOCKED" or any(safety.values()) or attribution["host"] or attribution["sop"]:
                    qualification["status"] = "BLOCKED"
                elif evidence == "PASS":
                    qualification["status"] = "PASS" if first["assessable_success_rate"] >= threshold else "FAIL"
                    qualification["statistically_supported"] = first["wilson95_assessable"][0] >= threshold
            stats[track][level] = {"nominal_suite_cases": nominal, "selected_cases": first["planned_n"],
                                   "trials": len(trials), "counts": count_status(status for _, status in pairs),
                                   "first_pass": first, "evidence_status": evidence, "qualification": qualification,
                                   "failure_indicators": failure_indicators(rows),
                                   "score_metrics_assessable": observations([r for r in rows if r["status"] in STATUSES[:2]]),
                                   "attribution": attribution, "safety": safety,
                                   "reliability": repeat_summary(pairs) if repeat and pairs else None}
    return stats


def inspect(source):
    run = document(source / "run.json")
    if run["fingerprint"] != digest(run["configuration"]):
        raise ValueError("run configuration fingerprint differs")
    existing = source / "archive_manifest.json"
    if existing.is_file():
        manifest = document(existing)
        if manifest["run_id"] != run["run_id"] or manifest["configuration_sha256"] != run["fingerprint"]:
            raise ValueError("archive manifest belongs to another run")
        for name, expected in manifest["sha256"].items():
            if sha(safe_file(source, name)) != expected:
                raise ValueError(f"archive digest differs: {name}")
    cases, roster = verify_roster(run["configuration"])
    hashes = {"run.json": sha(source / "run.json")}
    indexes, sessions = session_evidence(source, run, hashes)
    results, pending_journals, proof, by_journal = {}, [], {}, {}
    for path in sorted((source / "cases").glob("*.json")):
        row = document(path)
        trial = roster.get(path.stem)
        payload = {key: value for key, value in row.items() if key != "artifact_sha256"}
        if (trial is None or row["trial"] != trial or row["status"] not in STATUSES[:3]
                or row["run_id"] != run["run_id"] or row["run_fingerprint"] != run["fingerprint"]
                or row["case_id"] != trial["case_id"] or row["track"] != trial["track"] or row["seed"] != trial["seed"]
                or row["artifact_sha256"] != digest(payload)):
            raise ValueError(f"checkpoint identity or artifact digest differs: {path.stem}")
        if row["journal"] in by_journal:
            raise ValueError("attempt journal reused between checkpoints")
        by_journal[row["journal"]] = row
        results[trial["trial_id"]] = row
        hashes[path.relative_to(source).as_posix()] = sha(path)
    used = set()
    for path in sorted((source / "attempts").glob("*.jsonl")):
        name = path.relative_to(source).as_posix()
        match = JOURNAL_NAME.fullmatch(name)
        if not match or match[1] not in roster:
            raise ValueError("journal belongs to an unknown trial")
        row = by_journal.pop(name, None)
        if row is not None and row["trial"]["trial_id"] != match[1]:
            raise ValueError("attempt journal filename differs from the checkpoint trial")
        hashes[name], coverage = verify_journal(path, name, run, roster[match[1]], row, indexes, used)
        if coverage is None:
            pending_journals.append(name)
        else:
            proof[match[1]] = coverage
    if by_journal:
        raise ValueError("terminal checkpoint is missing its attempt journal")

    overall = rates(count_status(results.get(trial, {}).get("status", "NOT_RUN") for trial in roster))
    summary_status = "NOT_RUN"
    summary_path = source / "summary.json"
    if summary_path.is_file():
        summary = document(summary_path)
        if (summary["run_id"] != run["run_id"] or summary["fingerprint"] != run["fingerprint"]
                or summary["planned_trials"] != len(roster)
                or any(summary["counts"][key] > overall["counts"][key] for key in STATUSES[:3])):
            raise ValueError("runtime summary differs from the verified checkpoints")
        if summary["counts"] == overall["counts"]:
            summary_status = "PASS"
        hashes["summary.json"] = sha(summary_path)
    telemetry = {key: sum(row[key] for row in proof.values()) for key in ("requests", "captured", "observer_bound")}
    physical = "NOT_RUN"
    if results:
        missing = any(sessions[row["server_session"]]["status"] != "PASS" or proof[trial_id]["status"] != "PASS"
                      or row["status"] == "BLOCKED" for trial_id, row in results.items())
        physical = "BLOCKED" if missing else "PASS"
    config = run["configuration"]
    nominal = (160 * 3 if config["panel"] == "repeat" else 800) * len(TRACKS)
    report = {"schema_version": 1, "suite": "AGENTIC-PLAN-V1", "run_id": run["run_id"],
              "configuration_sha256": run["fingerprint"], "selection": config["selection"], "panel": config["panel"],
              "identity": {key: config.get(key) for key in ("git", "backend", "engine", "model", "sdk_installed", "sdk_used", "settings")},
              "coverage": {"nominal_suite_trials": nominal, "scheduled_trials": len(roster),
                           "suite_trials_outside_run": nominal - len(roster)},
              "overall": overall, "levels": groups(run, roster, cases, results, proof, sessions),
              "evidence": {"checkpoint_integrity": "PASS" if results else "NOT_RUN", "runtime_summary_consistency": summary_status,
                           "physical_execution_status": physical, "sessions": sessions, "telemetry": telemetry,
                           "recorded_trials": len(results), "pending_trials": len(roster) - len(results),
                           "retained_uncheckpointed_attempts": pending_journals},
              "method": {"uncertainty": "Wilson 95% over assessable outcomes only. Bounds over the planned roster leave BLOCKED and NOT_RUN unresolved.",
                         "failure_indicators": "Observed runner codes and derived oracle flags can coexist. Counts do not assign root cause.",
                         "diagnostic": "A diagnostic selection cannot meet the full-panel capability threshold. Physical status describes observed evidence independently of task results."}}
    if existing.is_file() and set(manifest["sha256"]) != {*hashes, "diagnostic.json"}:
        raise ValueError("archive inventory differs from the exact run evidence")
    return report, hashes


def analyze(source):
    return inspect(source)[0]


def archive(source, output):
    if output.exists() or output.resolve().is_relative_to(source.resolve()):
        raise ValueError("archive output must be a new directory outside the run")
    report, hashes = inspect(source)
    if scan(source, sorted(hashes)):
        raise ValueError("planning evidence failed privacy checks")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as temp:
        staging = Path(temp) / "archive"
        staging.mkdir()
        for name, expected in sorted(hashes.items()):
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            copyfile(safe_file(source, name), target)
            if sha(target) != expected:
                raise ValueError(f"source changed while archiving: {name}")
        (staging / "diagnostic.json").write_bytes(encode(report))
        manifest = {"schema_version": 1, "run_id": report["run_id"], "configuration_sha256": report["configuration_sha256"],
                    "sha256": {**hashes, "diagnostic.json": sha(staging / "diagnostic.json")}}
        (staging / "archive_manifest.json").write_bytes(encode(manifest))
        staging.rename(output)
    return report


def archive_closed_prefix(source, output, count):
    """Archive the original journals from completed sessions of a live roster."""
    live_bytes = (source / "run.json").read_bytes()
    run = json.loads(live_bytes)
    if not 1 <= count <= len(run["sessions"]):
        raise ValueError("closed session count is outside the live run")
    sessions = run["sessions"][:count]
    with TemporaryDirectory() as temporary:
        prefix = Path(temporary)
        for session in sessions:
            counter = session["counter_file"]
            stop = counter.removesuffix("-gpu.jsonl") + "-gpu-stop"
            if not safe_file(source, stop).is_file():
                raise ValueError("requested GPU session still runs")
            for field in ("trace_file", "counter_file"):
                name = session[field]
                copyfile(safe_file(source, name), prefix / name)
        for folder in ("cases", "attempts"):
            (prefix / folder).mkdir()
        for file in sorted((source / "cases").glob("*.json")):
            case = document(file)
            if case["server_session"] <= count:
                copyfile(file, prefix / "cases" / file.name)
        for file in sorted((source / "attempts").glob("*.jsonl")):
            with file.open(encoding="utf-8") as handle:
                header = handle.readline()
            if header.endswith("\n") and json.loads(header)["server_session"] <= count:
                copyfile(file, prefix / "attempts" / file.name)
        (prefix / "run.json").write_bytes(encode({
            **run, "sessions": sessions, "closed_prefix": {
                "count": count, "live_run_json_sha256": sha256(live_bytes).hexdigest(),
            },
        }))
        return archive(prefix, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Write a new byte-preserving evidence archive")
    parser.add_argument("--closed-session-count", type=int, help="Archive a prefix of fully closed sessions")
    args = parser.parse_args()
    try:
        if args.closed_session_count is not None:
            if args.output is None:
                parser.error("--closed-session-count requires --output")
            report = archive_closed_prefix(args.source, args.output, args.closed_session_count)
        else:
            report = archive(args.source, args.output) if args.output else analyze(args.source)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"FAIL: {error}\n")
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
