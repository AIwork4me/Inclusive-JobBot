"""Export complete TC-V2 trial records after validating checkpoints and databases."""

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import shutil

from benchmarks.job_productivity_v1.statistics import wilson_interval
from benchmarks.tool_calling_v2.holdout import dataset
from benchmarks.tool_calling_v2.holdout.qualify import pid_counter_proof, read_checkpoint
from scripts.tools.scan_sensitive import scan


def archive(root, out):
    run = json.loads((root / "run.json").read_bytes())
    summary = json.loads((root / "summary.json").read_bytes())
    cases, manifest = dataset.load("holdout")
    case_ids = {case["id"] for case in cases}
    terminal = sorted((root / "terminal").glob("*.json"))
    interruptions = sorted((root / "interruptions").glob("*.json"))
    counter_paths = [item["counter_file"] for item in run["sessions"].values()]
    names = ["run.json", "summary.json", *counter_paths, *(
        file.relative_to(root).as_posix() for file in terminal + interruptions
    )]
    findings = scan(root, names)
    if findings:
        raise ValueError("TC-V2 raw evidence failed privacy checks " + str(findings))
    results = defaultdict(dict)
    session_phases = defaultdict(set)
    out.mkdir(exist_ok=False)
    raw_digest = hashlib.sha256()
    with (out / "terminal.jsonl.gz").open("wb") as handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0, compresslevel=6) as compressed:
            for file in terminal:
                key = file.stem
                phase, identifier = key.split("--", 1)
                result = read_checkpoint(file, run, key, root / "sqlite")
                results[phase][identifier] = result
                session_phases[result["session"]].add(phase)
                wire = file.read_bytes().strip() + b"\n"
                compressed.write(wire)
                raw_digest.update(wire)
    if any(set(results[key]) != case_ids for key in ("first", "stream")):
        raise ValueError("full first-pass or streaming roster absent")
    if any(set(results[f"repeat-{seed}"]) != set(manifest["repeat"]["cases"])
           for seed in manifest["repeat"]["seeds"]):
        raise ValueError("repeat roster differs from the frozen plan")
    for name in ("run.json", "summary.json"):
        shutil.copyfile(root / name, out / name)
    for file in interruptions:
        dest = out / "interruptions"
        dest.mkdir(exist_ok=True)
        shutil.copyfile(file, dest / file.name)
    for name in counter_paths:
        (out / (name + ".gz")).write_bytes(gzip.compress((root / name).read_bytes(), compresslevel=6, mtime=0))
    by_language = defaultdict(Counter)
    for case in cases:
        by_language[case["language"]][results["first"][case["id"]]["status"]] += 1
    (out / "coverage.json").write_bytes((json.dumps({
        "run_id": run["run_id"], "qualification": summary["status"],
        "terminal_uncompressed_sha256": raw_digest.hexdigest(),
        "coverage_by_phase": {key: len(rows) for key, rows in results.items()},
        "first_pass_by_language": by_language,
        "wilson95_first_pass": wilson_interval(sum(result["status"] == "PASS" for result in results["first"].values()), len(cases)),
        "interrupted_attempts": len(interruptions),
        "supplemental_physical_gpu_proof": {
            tag: pid_counter_proof(root, {
                **session,
                "phase": "fixed_fixture" if session_phases[tag] == {"fixture"} else "trajectory",
            })
            for tag, session in run["sessions"].items()
        },
        "scope": "physical GPU and synthetic transactional world; original SQLite files stay local",
    }, indent=2, sort_keys=True) + "\n").encode())
    print(f"PASS: {len(terminal)} exact TC-V2 trial records, SQLite digests and run coverage")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    archive(args.source, args.output)


if __name__ == "__main__":
    main()
