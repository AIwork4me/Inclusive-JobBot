"""Verify the preserved baseline and an optional IJ-0.6 qualification manifest."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
STATUSES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
HASHES = (
    "source_manifest_sha256", "engine_binary_sha256", "model_sha256", "chat_template_sha256",
    "dataset_sha256", "evaluator_sha256", "oracle_sha256", "tool_schema_sha256", "policy_sha256",
)
COMMIT_IDS = ("git_commit_sha", "engine_commit", "modelscope_revision")
IJ06_ARCHIVE = "d2e5b31aa1f0894638f7b648a4cf3591fbb71e6e"
IJ06_LIVING_FILES = {
    "BLOCKERS.md", "DECISIONS.md", "HANDOFF.md", "MISSION_STATE.json", "TASK_LEDGER.md",
    ".gitattributes", ".github/workflows/evidence-validation.yml", "scripts/tools/verify_ij06_evidence.py",
    "tests/security/test_gateway_execution.py",
    "benchmarks/ij06_sdk/qualify.py", "benchmarks/ij06_sdk/wire_boundary.py",
    "src/model_gateway/streaming.py", "tests/antigravity/test_wire_boundary.py",
}


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path):
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def manifest_file(root, entry):
    relative = entry["path"]
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError(f"invalid evidence path {relative}")
    if not path.is_file():
        raise ValueError(f"missing evidence file {relative}")
    if digest(path) != entry["sha256"]:
        raise ValueError(f"evidence digest mismatch {relative}")
    return path


def validate_baseline(root):
    path = root / "evidence/IJ06/baseline_manifest.json"
    manifest = read_json(path)
    for name, expected in manifest["files"].items():
        manifest_file(root, {"path": name, "sha256": expected})
    return len(manifest["files"])


def validate_artifacts(root, path):
    manifest = read_json(path)
    files = manifest["files"]
    if not files or path.relative_to(root).as_posix() in files:
        raise ValueError("invalid or self-referencing artifact manifest")
    for name, expected in files.items():
        manifest_file(root, {"path": name, "sha256": expected})
    return len(files)


def validate_ij06_artifacts(root):
    path = root / "reports/IJ06_ARTIFACT_MANIFEST.json"
    files = read_json(path)["files"]
    if not files or path.relative_to(root).as_posix() in files:
        raise ValueError("invalid or self-referencing IJ-0.6 artifact manifest")
    for name, expected in files.items():
        if name not in IJ06_LIVING_FILES:
            manifest_file(root, {"path": name, "sha256": expected})
            continue
        blob = subprocess.run(
            ["git", "show", f"{IJ06_ARCHIVE}:{name}"], cwd=root, check=True, capture_output=True,
        ).stdout
        if hashlib.sha256(blob).hexdigest() != expected:
            raise ValueError(f"archived IJ-0.6 digest mismatch {name}")
    return len(files)


def utc_time(value):
    stamp = datetime.fromisoformat(value)
    if stamp.utcoffset() != timedelta():
        raise ValueError("timestamp must be UTC")
    return stamp


def verify_gpu(paths, backend):
    launch = read_json(paths["gpu_launch"])
    pid = launch.get("pid")
    if (
        type(pid) is not int or pid <= 0 or launch.get("backend") != backend
        or launch.get("status") != "PASS" or launch.get("owns_port") is not True
        or not launch.get("layers_offloaded")
    ):
        return False
    prefix = f"pid_{pid}_"
    samples = [row for row in read_rows(paths["gpu_counters"]) if row.get("instance", "").startswith(prefix)]
    compute = any(
        row.get("kind") == "gpu_engine" and row.get("engtype") in ("3D", "Compute")
        and 0 < row.get("utilization", 0) <= 100
        for row in samples
    )
    memory = any(row.get("kind") == "gpu_process_memory" and row.get("committed_bytes", 0) > 0 for row in samples)
    return compute and memory


def validate_run(document, root, required_gates):
    errors = []
    identity = document.get("identity", {})
    files = document.get("files", {})
    gates = document.get("gates", {})
    for key in (*HASHES, *COMMIT_IDS):
        length = 64 if key in HASHES else 40
        if not re.fullmatch(f"[0-9a-f]{{{length}}}", str(identity.get(key, ""))):
            errors.append(f"missing or invalid identity {key}")
    for key in ("run_id", "parser_version", "sdk_version", "backend"):
        if not isinstance(identity.get(key), str) or not identity[key]:
            errors.append(f"missing identity {key}")
    if type(identity.get("seed")) is not int:
        errors.append("missing integer seed")
    config_id = identity.get("configuration", {}).get("id")
    if not config_id:
        errors.append("missing configuration ID")
    dlls = identity.get("runtime_dll_sha256", {})
    if not dlls or any(not re.fullmatch("[0-9a-f]{64}", str(value)) for value in dlls.values()):
        errors.append("missing or invalid runtime DLL identity")
    if identity.get("git_dirty_state") is not False:
        errors.append("qualification source is dirty or missing clean identity")
    try:
        if utc_time(identity["end_time_utc"]) < utc_time(identity["start_time_utc"]):
            errors.append("end time precedes start")
    except (KeyError, ValueError, TypeError):
        errors.append("missing or invalid UTC interval")

    paths = {}
    for label, entry in files.items():
        try:
            paths[label] = manifest_file(root, entry)
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append(str(error))
    for label in ("source_manifest", "dataset", "traces"):
        if label not in paths:
            errors.append(f"missing validated {label}")
    for label in ("source_manifest", "dataset"):
        if label in paths and files[label]["sha256"] != identity.get(f"{label}_sha256"):
            errors.append(f"{label} manifest and run digests differ")
    if document.get("qualification") is not True:
        errors.append("run is missing the qualification classification")
    if identity.get("backend") in ("vulkan", "rocm"):
        if document.get("evidence_type") != "REAL_GPU" or not identity.get("gpu_identity"):
            errors.append("GPU qualification requires real GPU evidence and identity")
        if not {"gpu_launch", "gpu_counters", "cpu_reference"} <= paths.keys():
            errors.append("GPU qualification requires launch, process counters and CPU reference")
        elif not verify_gpu(paths, identity["backend"]):
            errors.append("GPU process activity, memory or managed launch identity missing")
    if any(status not in STATUSES for status in gates.values()):
        errors.append("invalid gate status")
    if document.get("go") is True and (
        not required_gates or any(gates.get(name) != "PASS" for name in required_gates)
    ):
        errors.append("GO requires every configured prerequisite gate to pass")

    if "dataset" in paths and "traces" in paths:
        cases = read_rows(paths["dataset"])
        traces = read_rows(paths["traces"])
        case_ids = [row["id"] for row in cases]
        trace_ids = [row["id"] for row in traces]
        if len(set(case_ids)) != len(case_ids) or len(set(trace_ids)) != len(trace_ids):
            errors.append("duplicate case ID")
        if set(case_ids) != set(trace_ids):
            errors.append("dataset and trace coverage differ")
        if any(row.get("run_id") != identity.get("run_id") or row.get("config_id") != config_id for row in traces):
            errors.append("trace configuration or run ID mismatch")
        counts = Counter(row.get("status") for row in traces)
        if set(counts) - set(STATUSES):
            errors.append("invalid trace status")
        summary = {"cases": len(traces), **{key: counts[key] for key in STATUSES}}
        if document.get("summary") != summary:
            errors.append("summary does not match per-case trace")

        holdout = document.get("holdout", {})
        try:
            independent = (
                holdout["tuned_using_holdout"] is False
                and holdout["independence_review"] == "PASS"
                and holdout["candidate_git_sha"] == identity["git_commit_sha"]
                and utc_time(holdout["candidate_frozen_utc"]) <= utc_time(identity["start_time_utc"])
                and "development" in paths
            )
        except (KeyError, ValueError, TypeError):
            independent = False
        if not independent:
            errors.append("holdout freeze or independence review missing or invalid")
        else:
            dev = read_rows(paths["development"])
            dev_ids = {row["id"] for row in dev}
            if not dev or not cases or any(not row.get("template_id") for row in (*dev, *cases)):
                errors.append("holdout and development require template identities")
            dev_templates = {row.get("template_id") for row in dev}
            if dev_ids.intersection(case_ids) or dev_templates.intersection(row.get("template_id") for row in cases):
                errors.append("holdout and development overlap")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, help="qualification manifest rooted at its parent directory")
    parser.add_argument("--required-gate", action="append", default=[])
    args = parser.parse_args()
    try:
        print(f"PASS: {validate_baseline(ROOT)} preserved baseline files")
        artifacts = ROOT / "reports/IJ06_ARTIFACT_MANIFEST.json"
        if artifacts.is_file():
            print(f"PASS: {validate_ij06_artifacts(ROOT)} IJ-0.6 artifacts")
        if args.run:
            for_error = validate_run(read_json(args.run), args.run.parent, set(args.required_gate))
            if for_error:
                for problem in for_error:
                    print(f"FAIL: {problem}", file=sys.stderr)
                return 1
            print("PASS: qualification manifest structure and integrity")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.CalledProcessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
