"""Verify and archive the deterministic JOB-V1 receipt-correction control."""

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks.job_productivity_v1.holdout.dataset import canonical, digest, load
from benchmarks.job_productivity_v1.holdout.run_f import create_plan, load_rows, state_bytes, summarize
from scripts.tools.scan_sensitive import scan


INTAKE_SOURCE = "benchmarks/job_productivity_v1/holdout/arm_f.py"
SAFETY_FIELDS = ("unauthorized_effects", "unconfirmed_commits", "duplicate_commits", "false_approvals")
OUTCOME_FIELDS = ("status", "business_state_status", "completed", "intake", "answer", "reads", "before_sqlite", "after_sqlite")
AUDIT_VOLATILE = {"transaction_id", "call_id", "elapsed_ms"}


def load_verified(source, freeze, panel):
    run = json.loads((source / "run.json").read_bytes())
    config = run["configuration"]
    roster = create_plan(freeze, panel, [])
    if (config["arm"] != "F" or config["panel"] != panel or config["scope"] != "panel"
            or config["git"]["dirty"] or config["freeze_sha256"] != freeze.manifest["freeze_sha256"]
            or config["planned"] != roster or run["fingerprint"] != digest(config)):
        raise ValueError("receipt-correction run identity differs from the full frozen roster")
    names = ["run.json", "summary.json", *(f"cases/{key}.json" for key in sorted(roster))]
    rows = load_rows(source / "cases", source / "sqlite", roster, run["run_id"])
    summary = json.loads((source / "summary.json").read_bytes())
    if rows.keys() != roster.keys() or summary != summarize(run, rows):
        raise ValueError("receipt-correction summary differs from the verified SQLite checkpoints")
    if scan(source, names):
        raise ValueError("receipt-correction source failed privacy checks")
    return config, summary, rows, names


def outcome(row):
    result = {key: row[key] for key in OUTCOME_FIELDS}
    ending = row["after_sqlite"]
    result["after_sqlite"] = {**ending, "audit_events": sorted(
        state_bytes({key: value for key, value in event.items() if key not in AUDIT_VOLATILE})
        for event in ending["audit_events"].values()
    )}
    result["reads"] = sorted(map(state_bytes, row["reads"]))
    return result


def compare(before, after):
    baseline, _, original, _ = before
    corrected, _, replay, _ = after
    controlled = baseline.keys() - {"git", "sources"}
    changed_sources = {name for name in baseline["sources"].keys() | corrected["sources"].keys()
                       if baseline["sources"].get(name) != corrected["sources"].get(name)}
    if (baseline.keys() != corrected.keys() or any(baseline[key] != corrected[key] for key in controlled)
            or changed_sources != {INTAKE_SOURCE} or baseline["git"]["commit"] == corrected["git"]["commit"]):
        raise ValueError("paired receipt-correction runs must differ in exactly the intake source")
    changes = []
    for key in sorted(original):
        left, right = original[key], replay[key]
        if (any(left[item] != right[item] for item in ("pairing_sha256", "initial_input", "followups", "before_sqlite"))
                or left["model_calls"] or right["model_calls"]
                or any(left[item] or right[item] for item in SAFETY_FIELDS)):
            raise ValueError(f"paired input, safety or initial state differs for {key}")
        left_outcome, right_outcome = outcome(left), outcome(right)
        different = [field for field in OUTCOME_FIELDS if left_outcome[field] != right_outcome[field]]
        if different:
            changes.append({"trial": key, "pairing_sha256": left["pairing_sha256"], "fields": different,
                            "baseline_status": left["status"], "corrected_status": right["status"],
                            "baseline_intake_reason": left["intake"]["reason"],
                            "baseline_checkpoint_sha256": left["artifact_sha256"],
                            "corrected_checkpoint_sha256": right["artifact_sha256"]})
    return {"unchanged_trials": len(original) - len(changes), "changed_trials": changes,
            "changed_source": INTAKE_SOURCE, "source_sha256": {"baseline": baseline["sources"][INTAKE_SOURCE],
                                                               "corrected": corrected["sources"][INTAKE_SOURCE]}}


def pack(source, output, verified):
    _, summary, rows, names = verified
    output.mkdir(parents=True)
    for name in names[:2]:
        (output / name).write_bytes((source / name).read_bytes())
    raw = b"".join(canonical({"name": name, "raw_json": (source / name).read_bytes().decode("utf-8")})
                   for name in names[2:])
    compressed = gzip.compress(raw, mtime=0)
    (output / "records.jsonl.gz").write_bytes(compressed)
    (output / "archive.json").write_bytes(canonical({"records": len(rows), "run_id": summary["run_id"],
                                                     "uncompressed_sha256": sha256(raw).hexdigest(),
                                                     "gzip_sha256": sha256(compressed).hexdigest()}))


def archive(baseline_root, corrected_root, output):
    if output.exists():
        raise ValueError("choose a fresh control archive directory")
    freeze = load()
    report = {"scope": "post-hoc deterministic counterfactual on the existing frozen JOB-V1 roster",
              "comparison": "Reads and audit events compared as multisets. Run-specific audit IDs and elapsed time excluded.",
              "panels": {}}
    with TemporaryDirectory(dir=output.parent) as temporary:
        staging = Path(temporary) / "control"
        for panel in ("primary", "repeat"):
            baseline, corrected = Path(f"{baseline_root}-{panel}"), Path(f"{corrected_root}-{panel}")
            before, after = load_verified(baseline, freeze, panel), load_verified(corrected, freeze, panel)
            report["panels"][panel] = {**compare(before, after), "baseline": before[1], "corrected": after[1]}
            pack(baseline, staging / "baseline" / panel, before)
            pack(corrected, staging / "corrected" / panel, after)
        (staging / "comparison.json").write_bytes(canonical(report))
        staging.rename(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-prefix", required=True, type=Path)
    parser.add_argument("--corrected-prefix", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = archive(args.baseline_prefix, args.corrected_prefix, args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"BLOCKED: {error}\n")
    print({panel: len(detail["changed_trials"]) for panel, detail in report["panels"].items()})


if __name__ == "__main__":
    main()
