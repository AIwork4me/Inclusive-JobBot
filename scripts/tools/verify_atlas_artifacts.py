"""Generate or check SHA256 digests for the versioned IJ-0.7.1 artifacts."""

from argparse import ArgumentParser
from hashlib import file_digest
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "atlas/artifact_manifest.json"
PREFIXES = ("atlas/", "evidence/IJ071/", "benchmarks/atlas_validity/", "reports/ATLAS_",
            "scripts/tools/atlas_", "tests/regression/test_atlas_")
FILES = {"docs/IJ071_EXECUTION_PLAN.md", "scripts/tools/verify_atlas_artifacts.py"}


def manifest_bytes():
    index = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    digests = {}
    for name in sorted(set(index)):
        target = ROOT / name
        if target == MANIFEST or not (name in FILES or name.startswith(PREFIXES)):
            continue
        with target.open("rb") as stream:
            digests[name] = {"sha256": file_digest(stream, "sha256").hexdigest(),
                             "size": target.stat().st_size}
    if not digests:
        raise ValueError("no staged or tracked Atlas artifacts")
    return (json.dumps({"schema_version": 1, "files": digests}, indent=2) + "\n").encode()


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    expected = manifest_bytes()
    if args.write:
        MANIFEST.write_bytes(expected)
    elif MANIFEST.read_bytes() != expected:
        parser.exit(1, "Atlas artifact digest mismatch\n")
    print(f"{len(json.loads(expected)['files'])} Atlas artifact digests verified")


if __name__ == "__main__":
    main()
