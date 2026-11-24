"""Generate or verify exact-byte IJ-0.7 artifact and archived run coverage."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "reports/IJ07_ARTIFACT_MANIFEST.json"
GLOBS = (
    "evidence/IJ07/**/*", "reports/IJ07_*.md", "benchmarks/agentic_planning_v1/**/*",
    "benchmarks/competitive_slm/**/*", "benchmarks/job_productivity_v1/holdout/**/*",
    "benchmarks/multitool_v1/**/*", "benchmarks/root_cause/**/*", "benchmarks/tool_calling_v2/holdout/**/*",
    "configs/ij07/**/*", "patches/ij07/**/*", "scripts/tools/*ij07*.py",
    "tests/regression/ij07/*.py", "docs/IJ07_EXECUTION_PLAN.md",
    "portability/deepx-dxm2/IJ07_DEPLOYMENT_REQUIREMENTS.md",
)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def manifest_bytes():
    indexed = set(subprocess.check_output(
        ["git", "ls-files", "--cached", "-z"], cwd=ROOT,
    ).decode("utf-8").split("\0"))
    artifacts = {}
    for pattern in GLOBS:
        for file in ROOT.glob(pattern):
            relative = file.relative_to(ROOT)
            if relative.as_posix() in indexed and file.is_file():
                artifacts[relative.as_posix()] = {"sha256": sha256(file), "size": file.stat().st_size}
    if not artifacts:
        raise ValueError("no IJ-0.7 files found")
    return (json.dumps({"schema_version": 1, "files": artifacts}, indent=2, sort_keys=True) + "\n").encode()


def check_replay_archive():
    root = ROOT / "evidence/IJ07/historical_replay/full"
    summary_path = root / "summary.json"
    if not summary_path.is_file():
        return
    summary = json.loads(summary_path.read_bytes())
    if set(summary["arms"]) != {"R0-V", "R0-R", "R1-V", "R1-R"} or summary["cases_executed"] != 2000:
        raise ValueError("historical arm coverage differs")
    for arm, entry in summary["arms"].items():
        folder = root / arm
        for name, expected in entry["archive_sha256"].items():
            if Path(name).name != name or sha256(folder / name) != expected:
                raise ValueError(f"{arm} archive digest differs for {name}")
        run = json.loads((folder / "run.json").read_bytes())
        metadata = json.loads((folder / "summary.json").read_bytes())
        ids, digest = [], hashlib.sha256()
        with gzip.open(folder / "results.jsonl.gz", "rb") as stream:
            for line in stream:
                digest.update(line)
                row = json.loads(line)
                if row["run_id"] != run["run_id"]:
                    raise ValueError(f"{arm} mismatched run identity")
                ids.append(row["id"])
        if len(ids) != 500 or len(set(ids)) != 500 or ids != run["configuration"]["case_ids"]:
            raise ValueError(f"{arm} missing, duplicate or out-of-order cases")
        if digest.hexdigest() != metadata["result_sha256"]:
            raise ValueError(f"{arm} inflated evidence digest mismatch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    expected = manifest_bytes()
    check_replay_archive()
    if args.write:
        MANIFEST.write_bytes(expected)
    elif not MANIFEST.is_file() or MANIFEST.read_bytes() != expected:
        parser.exit(1, "FAIL: IJ-0.7 artifact manifest differs\n")
    print("PASS:", len(json.loads(expected)["files"]), "IJ-0.7 artifact digests")


if __name__ == "__main__":
    main()
