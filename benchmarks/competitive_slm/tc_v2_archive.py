"""Verify and export privacy-filtered metrics from a frozen competitive TC-V2 roster."""

import argparse
from collections import Counter
from contextlib import nullcontext
import gzip
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from scripts.tools.scan_sensitive import CREDENTIAL_PATTERNS, identity_patterns

from . import statistics, tc_v2_batch as batch
from . import tc_v2_candidate as candidate


FORMAT = "ij07-competitive-tcv2-text-v1"
THINKING = "frozen_case_requirement"
PROTOCOL = "native-tool-calling"
RUNTIME = {
    "backend": "vulkan", "device": "gfx1151", "track": "controlled", "quantization": "Q8_0",
    "thinking": THINKING, "protocol": PROTOCOL, "engine_profile": candidate.ENGINE_PROFILE,
}
EVIDENCE_CLASSES = ("local_model", "synthetic_software_test")
digest_config = statistics.digest
PAYLOADS = ("trials.jsonl.gz", "statistics.json.gz")
FILES = frozenset(("archive.json", *PAYLOADS))
MAX_BYTES = 8 * 1024 * 1024
FAILURE_CODES = (
    "F02_MODEL_TOOL_SELECTION_ERROR", "F03_MODEL_ARGUMENT_ERROR", "F04_TRANSPORT_ERROR",
    "F05_PROTOCOL_ERROR", "F06_NATIVE_PARSER_ERROR", "F07_SCHEMA_VALIDATION_ERROR",
    "F08_AUTHORIZATION_DENIAL", "F09_SOP_DEPENDENCY_ERROR", "F10_TOOL_EXECUTION_ERROR",
    "F11_BUSINESS_STATE_ERROR", "F12_FINAL_ANSWER_ERROR", "F15_INSUFFICIENT_EVIDENCE",
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def _run_id(value):
    return isinstance(value, str) and re.fullmatch("ij07-competitive-tcv2-roster-[0-9a-f]{32}", value) is not None


def _json_text(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _privacy_check(raw):
    text = raw.decode("utf-8")
    for name, pattern in {**identity_patterns(), **CREDENTIAL_PATTERNS}.items():
        _require(pattern.search(text) is None, f"archive privacy check flagged {name}")


def _plan(plan, plan_sha256, panel):
    case_index = statistics._validate_plan(plan, plan_sha256)
    _require(plan["suite"] == "TC-V2" and panel in batch.PANELS, "expected a frozen TC-V2 plan and panel")
    _, roster = batch.make_roster(panel)
    _require(all(case_index[row["case_id"]]["pairing_sha256"] == row["pairing_sha256"] for row in roster),
             "statistics plan differs from frozen staged roster")
    return case_index, roster


def _verify_arm(plan, arm, configuration_sha256):
    _require(arm in batch.BATCH_CANDIDATES and arm in plan["arms"], "candidate is outside the staged statistics arms")
    expected = plan["arms"][arm]
    _require(expected["thinking"] == THINKING, "staged statistics thinking policy differs from the controlled TC-V2 profile")
    _require(_sha(configuration_sha256) and configuration_sha256 == expected["configuration_sha256"]
             and all(expected[key] == value for key, value in RUNTIME.items() if key != "engine_profile"),
             "candidate configuration or controlled profile differs from the staged statistics arm")
    return expected


def _verify_source_run(run, plan, roster):
    _require(run.get("scope") == batch.RUN_SCOPE and _run_id(run.get("run_id")),
             "source is outside the competitive roster scope")
    _require(run.get("evidence_class") in EVIDENCE_CLASSES, "source evidence class is unsupported")
    config, scope = run["configuration"], run["run_configuration"]
    config_hash, scope_hash = run["configuration_sha256"], run["run_configuration_sha256"]
    _require(digest_config(config) == config_hash and digest_config(scope) == scope_hash,
             "source run configuration digest differs")
    _require(scope.keys() == {"scope", "arm_configuration_sha256", "port", "roster", "environment_sha256"}
             and scope["scope"] == batch.RUN_SCOPE and scope["arm_configuration_sha256"] == config_hash
             and scope["roster"] == roster and _sha(scope["environment_sha256"])
             and type(scope["port"]) is int and 1024 <= scope["port"] < 65536,
             "source run differs from the frozen staged roster")
    expected = _verify_arm(plan, config["candidate"], config_hash)
    _require(config["dataset_sha256"] == roster[0]["dataset_sha256"]
             and config["dataset_manifest_sha256"] == roster[0]["manifest_sha256"]
             and config["controls_sha256"] == expected["controls_sha256"]
             and config["model"]["official_model_id"] == expected["model"]
             and config["backend"] == RUNTIME["backend"] and config["gpu"] == candidate.VULKAN_DEVICE
             and config["track"] == RUNTIME["track"] and config["model"]["quantization"] == RUNTIME["quantization"]
             and config["engine"]["profile"] == RUNTIME["engine_profile"]
             and config["budgets"] == candidate.BUDGETS,
             "source runtime, model, budgets or dataset differs from the staged statistics arm")


def _public_session_proofs(source, run):
    proofs = {}
    for tag, launch in sorted(run["sessions"].items()):
        proof = launch.get("proof")
        if proof is None:
            proofs[tag] = {"status": "BLOCKED", "artifacts_sha256": {}}
        else:
            status, artifacts = proof["status"], proof["artifacts_sha256"]
            if status == "PASS":
                _require(batch._complete_session(source, tag, launch, True) == {
                    "status": status, "artifacts_sha256": artifacts,
                }, "sealed session no longer proves physical Vulkan execution")
            proofs[tag] = {"status": status, "artifacts_sha256": artifacts}
    return proofs


def _project_trial(source, trial, results):
    key = trial["key"]
    saved = results.get(key)
    pair_status = None
    if trial["phase"] == "stream":
        primary = results.get(f"first--{trial['case_id']}", {"status": "NOT_RUN"})
        stream = saved or {"status": "NOT_RUN"}
        pair_status = _unresolved_pair(primary["status"], stream["status"]) or batch.runner.paired(primary, stream)["status"]
    if saved is None:
        return {"key": key, "status": "NOT_RUN", "pair_status": pair_status, "finding_codes": [], "proof": None}
    attempt = source / "attempts" / f"{key}.json"
    trajectory = source / "trajectories" / f"{key}.json"
    recorded = batch.read_checkpoint(attempt)
    proof = {"session": recorded["session"], "attempt_sha256": batch.legacy.sha256_of(attempt),
             "trajectory_sha256": batch.legacy.sha256_of(trajectory) if trajectory.is_file() else None,
             "sqlite_sha256": saved.get("database_sha256")}
    codes = {item.get("code") for item in saved.get("findings", ())}
    return {"key": key, "status": saved["status"], "pair_status": pair_status,
            "finding_codes": [code for code in FAILURE_CODES if code in codes], "proof": proof}


def _unresolved_pair(primary, stream):
    statuses = {primary, stream}
    return "BLOCKED" if "BLOCKED" in statuses else "NOT_RUN" if "NOT_RUN" in statuses else None


def _status_counts(values):
    counts = Counter(values)
    return {status: counts[status] for status in batch.STATUSES}


def _snapshot(source, roster, plan, plan_sha256, panel):
    lock = batch.legacy.output_lock(source) if (source / ".writer.lock").is_file() else nullcontext()
    with lock:
        run_path = source / "run.json"
        wire = run_path.read_bytes()
        run = json.loads(wire)
        _verify_source_run(run, plan, roster)
        results = batch.read_attempts(source, run)
        proofs = _public_session_proofs(source, run)
        records = [_project_trial(source, trial, results) for trial in roster]
        _require(run_path.read_bytes() == wire, "source run changed during verification")
    metadata = {
        "format": FORMAT, "panel": panel, "plan_sha256": plan_sha256, "source_run_sha256": batch.dataset.sha(wire),
        "run_id": run["run_id"], "candidate": run["configuration"]["candidate"], "evidence_class": run["evidence_class"],
        "configuration_sha256": run["configuration_sha256"], "run_configuration_sha256": run["run_configuration_sha256"],
        "roster_sha256": digest_config(roster), "dataset_sha256": roster[0]["dataset_sha256"], "runtime": RUNTIME,
        "status_counts": _status_counts(row["status"] for row in records), "sessions": proofs,
        "streaming_pair_counts": _status_counts(row["pair_status"] for row in records),
    }
    return metadata, records


def _validate_contents(metadata, records, plan, plan_sha256, roster):
    _require(metadata["format"] == FORMAT and metadata["plan_sha256"] == plan_sha256
             and metadata["runtime"] == RUNTIME and metadata["evidence_class"] in EVIDENCE_CLASSES
             and _run_id(metadata["run_id"]) and _sha(metadata["source_run_sha256"])
             and _sha(metadata["run_configuration_sha256"]) and metadata["roster_sha256"] == digest_config(roster)
             and metadata["dataset_sha256"] == roster[0]["dataset_sha256"], "archive identity differs from its staged scope")
    _verify_arm(plan, metadata["candidate"], metadata["configuration_sha256"])
    sessions = metadata["sessions"]
    for tag, proof in sessions.items():
        _require(re.fullmatch("[a-f0-9]{32}", tag) is not None and proof.keys() == {"status", "artifacts_sha256"}
                 and proof["status"] in ("PASS", "BLOCKED"), "invalid public session proof")
        files = proof["artifacts_sha256"]
        _require(files.keys() <= {"launch", "boot", "trace", "counters"} and all(_sha(value) for value in files.values())
                 and (proof["status"] != "PASS" or len(files) == 4), "invalid archived session digests")
    _require(len(records) == len(roster), "archive members differ from frozen staged roster")
    primary = {trial["case_id"]: row["status"] for row, trial in zip(records, roster) if trial["phase"] == "first"}
    for row, trial in zip(records, roster):
        _require(row.keys() == {"key", "status", "pair_status", "finding_codes", "proof"} and row["key"] == trial["key"]
                 and row["status"] in batch.STATUSES and isinstance(row["finding_codes"], list)
                 and row["finding_codes"] == [code for code in FAILURE_CODES if code in row["finding_codes"]],
                 "invalid, missing or out-of-order archived trial")
        if trial["phase"] == "stream":
            unresolved = _unresolved_pair(primary.get(trial["case_id"], "NOT_RUN"), row["status"])
            _require(row["pair_status"] == unresolved if unresolved else row["pair_status"] in batch.ASSESSED,
                     "archived streaming pair disagrees with trial coverage")
        else:
            _require(row["pair_status"] is None, "streaming pair verdict is attached to the wrong phase")
        proof = row["proof"]
        if row["status"] == "NOT_RUN":
            _require(proof is None and not row["finding_codes"], "unrun trial has observed evidence")
            continue
        _require(isinstance(proof, dict) and proof.keys() == {"session", "attempt_sha256", "trajectory_sha256", "sqlite_sha256"}
                 and proof["session"] in sessions and _sha(proof["attempt_sha256"])
                 and all(value is None or _sha(value) for value in (proof["trajectory_sha256"], proof["sqlite_sha256"]))
                 and (proof["trajectory_sha256"] is None) == (proof["sqlite_sha256"] is None),
                 "attempt or SQLite evidence digest differs")
        if row["status"] in batch.ASSESSED:
            _require(sessions[proof["session"]]["status"] == "PASS" and proof["trajectory_sha256"] is not None,
                     "measured verdict lacks sealed GPU or trajectory proof")
    _require(metadata["status_counts"] == _status_counts(row["status"] for row in records)
             and metadata["streaming_pair_counts"] == _status_counts(row["pair_status"] for row in records),
             "archive status counts differ from frozen trial outcomes")


def _statistics_fragment(metadata, records, roster):
    phases = [phase for phase in ("first", "repeat") if any(trial["phase"] == phase for trial in roster)]
    run_id = metadata["run_id"]
    identity = {key: metadata[key] for key in ("configuration_sha256", "run_configuration_sha256")}
    arm = metadata["candidate"]
    rows = []
    for trial, result in zip(roster, records):
        if trial["phase"] not in phases:
            continue
        status, codes = result["status"], result["finding_codes"]
        failure = (codes[0] if codes else "FAILURE_UNCLASSIFIED") if status == "FAIL" else (
            "BLOCKED_EVIDENCE" if status == "BLOCKED" else None
        )
        rows.append({
            **{key: trial[key] for key in ("case_id", "pairing_sha256", "phase", "repeat_index", "attempt", "seed")},
            **identity, "arm": arm, "run_id": run_id, "status": status, "failure_class": failure,
            "evidence_sha256": digest_config({"trial": result, "run_id": run_id, **identity}),
        })
    runs = {run_id: {**identity, "arm": arm, "phases": phases, "thinking": THINKING,
                     "dataset_sha256": metadata["dataset_sha256"]}} if phases else {}
    return {"schema_version": 1, "evidence_class": metadata["evidence_class"], "runs": runs, "rows": rows}


def _write_payload(path, raw):
    _privacy_check(raw)
    with path.open("xb") as handle, gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0) as stream:
        stream.write(raw)
    return {"gzip_sha256": batch.legacy.sha256_of(path), "utf8_sha256": batch.dataset.sha(raw), "utf8_bytes": len(raw)}


def _read_payload(path, entry):
    size = entry["utf8_bytes"]
    _require(entry.keys() == {"utf8_bytes", "utf8_sha256", "gzip_sha256"} and type(size) is int
             and 0 < size <= MAX_BYTES and _sha(entry["utf8_sha256"]) and _sha(entry["gzip_sha256"])
             and path.stat().st_size <= MAX_BYTES and batch.legacy.sha256_of(path) == entry["gzip_sha256"],
             "compressed archive member differs")
    with gzip.open(path, "rb") as handle:
        raw = handle.read(size + 1)
    _require(len(raw) == size and batch.dataset.sha(raw) == entry["utf8_sha256"], "expanded archive member differs")
    _privacy_check(raw)
    return raw


def export(source, destination, *, panel, plan, plan_sha256):
    case_index, roster = _plan(plan, plan_sha256, panel)
    metadata, records = _snapshot(source, roster, plan, plan_sha256, panel)
    _validate_contents(metadata, records, plan, plan_sha256, roster)
    fragment = _statistics_fragment(metadata, records, roster)
    statistics._index_results(fragment, plan, case_index)
    _require(not destination.exists(), "archive requires a fresh output directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as temp:
        staging = Path(temp) / "archive"
        staging.mkdir()
        metadata["files"] = {
            PAYLOADS[0]: _write_payload(staging / PAYLOADS[0], b"".join(map(_json_text, records))),
            PAYLOADS[1]: _write_payload(staging / PAYLOADS[1], _json_text(fragment)),
        }
        raw = _json_text(metadata)
        _privacy_check(raw)
        (staging / "archive.json").write_bytes(raw)
        verify(staging, plan=plan, plan_sha256=plan_sha256)
        staging.rename(destination)
    return metadata


def verify(folder, *, plan, plan_sha256, source=None):
    _require({path.name for path in folder.iterdir()} == FILES
             and all(path.is_file() and not path.is_symlink() for path in folder.iterdir()),
             "archive has unexpected, missing or linked members")
    raw = (folder / "archive.json").read_bytes()
    _require(len(raw) <= MAX_BYTES, "archive manifest is oversized")
    _privacy_check(raw)
    metadata = json.loads(raw)
    _require(metadata.keys() == {"format", "panel", "plan_sha256", "source_run_sha256", "run_id", "candidate",
                                 "evidence_class", "configuration_sha256", "run_configuration_sha256", "roster_sha256",
                                 "dataset_sha256", "runtime", "status_counts", "streaming_pair_counts", "sessions", "files"}
             and metadata["files"].keys() == set(PAYLOADS) and raw == _json_text(metadata), "invalid archive manifest")
    case_index, roster = _plan(plan, plan_sha256, metadata["panel"])
    trials_raw, stats_raw = (_read_payload(folder / name, metadata["files"][name]) for name in PAYLOADS)
    records = [json.loads(line) for line in trials_raw.splitlines()]
    _require(trials_raw == b"".join(map(_json_text, records)), "archive trial text is noncanonical")
    _validate_contents(metadata, records, plan, plan_sha256, roster)
    fragment = _statistics_fragment(metadata, records, roster)
    _require(stats_raw == _json_text(fragment), "statistics fragment differs from archived scoped trials")
    statistics._index_results(fragment, plan, case_index)
    if source is not None:
        replayed, raw_records = _snapshot(source, roster, plan, plan_sha256, metadata["panel"])
        _require(replayed == {key: value for key, value in metadata.items() if key != "files"}
                 and raw_records == records, "archive no longer matches the verified raw source snapshot")
    return metadata, fragment


def combine(folders, *, plan, plan_sha256):
    output = {"schema_version": 1, "evidence_class": None, "runs": {}, "rows": []}
    for folder in folders:
        _, fragment = verify(folder, plan=plan, plan_sha256=plan_sha256)
        if output["evidence_class"] is None:
            output["evidence_class"] = fragment["evidence_class"]
        _require(output["evidence_class"] == fragment["evidence_class"], "software and local-model evidence cannot mix")
        _require(not (output["runs"].keys() & fragment["runs"].keys()), "duplicate run in stats inputs")
        output["runs"].update(fragment["runs"])
        output["rows"].extend(fragment["rows"])
    case_index = statistics._validate_plan(plan, plan_sha256)
    _require(output["runs"], "no primary or repeat statistics trials in verified archives")
    statistics._index_results(output, plan, case_index)
    return output


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    modes = cli.add_subparsers(dest="mode", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--plan", type=Path, required=True)
    common.add_argument("--plan-sha256", required=True)
    pack = modes.add_parser("export", parents=[common])
    pack.add_argument("--source", type=Path, required=True)
    pack.add_argument("--output", type=Path, required=True)
    pack.add_argument("--panel", choices=batch.PANELS, default="full")
    check = modes.add_parser("verify", parents=[common])
    check.add_argument("--archive", type=Path, required=True)
    check.add_argument("--source", type=Path)
    merge = modes.add_parser("combine", parents=[common])
    merge.add_argument("--archive", type=Path, action="append", required=True)
    merge.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    try:
        plan = statistics._read_json(args.plan)
        options = {"plan": plan, "plan_sha256": args.plan_sha256}
        if args.mode == "combine":
            payload = _json_text(combine(args.archive, **options))
            _privacy_check(payload)
            with args.output.open("xb") as handle:
                handle.write(payload)
            print("Archive software verification PASS. Statistics input assembled.")
            return 0
        if args.mode == "export":
            metadata = export(args.source, args.output, panel=args.panel, **options)
        else:
            metadata, _ = verify(args.archive, source=args.source, **options)
    except (OSError, ValueError, KeyError, TypeError, EOFError) as failure:
        cli.exit(2, f"BLOCKED: {failure}\n")
    print(json.dumps({"archive_software_verification": "PASS",
                      "raw_source_rechecked": "PASS" if args.source is not None else "NOT_RUN",
                      "evidence_class": metadata["evidence_class"], "status_counts": metadata["status_counts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
