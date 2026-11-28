"""Run and record the deterministic IJ-0.6 gateway/security software suite."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4
from xml.etree import ElementTree

from redact_text import redact

ROOT = Path(__file__).resolve().parents[2]
SCOPES = ("src/model_gateway", "src/business_tools", "tests/gateway", "tests/security")
INPUTS = (
    "pyproject.toml",
    "requirements.lock",
    "scripts/tools/run_ij06_security_tests.py",
    "scripts/windows/run_ij06_security_tests.ps1",
    "benchmarks/tool_calling/fixtures/minicpm5_parser_fixtures.json",
    "evidence/IJ0/protocol/parser_fixtures_strict_vulkan/fixtures.json",
    "evidence/IJ0/protocol/parser_fixtures_strict_rocm/fixtures.json",
)


def digest_files() -> dict[str, str]:
    paths = [ROOT / name for name in INPUTS]
    for scope in SCOPES:
        paths.extend((ROOT / scope).glob("*.py"))
    return {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    report_path, log_path = output / "summary.json", output / "tests.log"
    if report_path.exists():
        parser.error("An evidence summary already exists. Choose another output directory.")
    sources = digest_files()
    git = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT))
    start = datetime.now(UTC).isoformat()
    with TemporaryDirectory() as private:
        xml = Path(private) / "gateway-test-results.xml"
        outcome = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests/gateway", "tests/security", f"--junitxml={xml}"],
            cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        rows = []
        if xml.exists():
            for item in ElementTree.parse(xml).iter("testcase"):
                status = "PASS"
                if item.find("skipped") is not None:
                    status = "NOT_RUN"
                if item.find("failure") is not None or item.find("error") is not None:
                    status = "FAIL"
                rows.append({"id": f"{item.get('classname')}::{item.get('name')}", "status": status})
        # Pytest failure reports can reference temporary and user-specific paths.
        # The captured log remains local, and paths in it receive normal redaction.
        log_path.write_text(redact(outcome.stdout + outcome.stderr), encoding="utf-8", newline="\n")

    if digest_files() != sources:
        raise RuntimeError("Test inputs changed during the gateway run")
    counts = dict(Counter(row["status"] for row in rows))
    status = "PASS" if outcome.returncode == 0 and len(rows) >= 150 and counts == {"PASS": len(rows)} else "FAIL"
    summary = {
        "schema_version": 1, "run_id": f"ij06-security-{uuid4().hex}", "status": status,
        "evidence_type": "SOFTWARE_TESTS_WITH_HISTORICAL_WIRE_REPLAY_AND_MOCK_LOOPBACK_HTTP",
        "qualification": False, "git_commit_sha": git, "git_dirty_state": dirty,
        "platform": platform.system(), "python": platform.python_version(),
        "dependency_versions": {name: importlib.metadata.version(name) for name in ("pytest", "jsonschema")},
        "start_time_utc": start, "end_time_utc": datetime.now(UTC).isoformat(),
        "source_manifest": sources,
        "source_manifest_sha256": sha256(json.dumps(sources, sort_keys=True).encode("utf-8")).hexdigest(),
        "pytest_exit_code": outcome.returncode, "counts": counts, "cases": rows,
    }
    with report_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(f"{status} gateway and security software suite {counts}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
