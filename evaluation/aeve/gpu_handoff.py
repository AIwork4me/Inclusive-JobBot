"""Verify the complete Q2 archives and record the idle Radeon handoff."""

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree

from benchmarks.root_cause.gpu_lease import identities, physical_gpu
from .archive import digest
from .controller import DEFAULT, gpu_lock
from .q2_closure import FROZEN, build
from .runtime import ROOT, write_json

EVIDENCE = Path("evidence/IJ073/aeve")
Q2_REPORT = EVIDENCE / "q2_closure.json"
HANDOFF = EVIDENCE / "gpu_handoff.json"
CONTROLS = {
    "test_live_mutex_contends_across_worktrees_and_recovers_abandoned_owner",
    "test_inference_subprocess_ends_when_its_controller_is_killed",
    "test_frozen_job_dedup_survives_two_controller_processes",
}


def verified_controls(path):
    tree = ElementTree.parse(path)
    rows = [row for row in tree.iter("testcase") if row.get("name") in CONTROLS]
    if ({row.get("name") for row in rows} != CONTROLS or len(rows) != len(CONTROLS)
            or any(row.find(tag) is not None for row in rows for tag in ("failure", "error", "skipped"))):
        raise ValueError("required Windows process/lease controls did not pass")
    return dict.fromkeys(sorted(CONTROLS), "PASS")


def seal_handoff(root, state, controls, output):
    report_path = root / Q2_REPORT
    original = json.loads(report_path.read_bytes())
    if original["recorded"] != 6850 or build(root / "evaluation/aeve/results", original["session_manifests"]) != original:
        raise ValueError("handoff requires the complete verifiable frozen Q2 roster")
    passed = verified_controls(controls)
    with (gpu_lock(state, "controller.lock"), gpu_lock(state),
          physical_gpu(mission_id="IJ-0.7.3", lease_owner="handoff-gate",
                       runtime_session="q2-to-ij-slm-1.0") as lease):
        report = {
            "version": "IJ073-GPU-HANDOFF-1", "status": "PASS",
            "successor": "IJ-SLM-1.0", "sealed_radeon_trials": original["recorded"],
            "q2_qualification": original["judge_qualification"],
            "q2_report_sha256": digest(report_path), "q2_frozen_protocol_sha256": digest(FROZEN),
            "lease": lease, "process_controls": passed,
            "process_controls_sha256": digest(root / "tests/regression/test_host_gpu_lease.py"),
            "deferred_queue": "PAUSED", "resume_instructions": "HANDOFF.md",
        }
        write_json(output, report)
    return report


def require_handoff(root):
    gate = json.loads((root / HANDOFF).read_bytes())
    host, gpu = identities()
    if (gate.get("version") != "IJ073-GPU-HANDOFF-1" or gate.get("status") != "PASS"
            or gate.get("successor") != "IJ-SLM-1.0" or gate.get("sealed_radeon_trials") != 6850
            or gate.get("process_controls") != dict.fromkeys(CONTROLS, "PASS")
            or gate.get("deferred_queue") != "PAUSED"
            or gate["lease"]["host_sha256"] != host or gate["lease"]["gpu_physical_sha256"] != gpu
            or digest(root / Q2_REPORT) != gate["q2_report_sha256"]
            or digest(FROZEN) != gate["q2_frozen_protocol_sha256"]):
        raise ValueError("GPU handoff is incomplete or belongs to a different host or device")
    return gate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows-controls", type=Path, required=True)
    parser.add_argument("--state", type=Path, default=DEFAULT)
    parser.add_argument("--output", type=Path, default=ROOT / HANDOFF)
    args = parser.parse_args()
    result = seal_handoff(ROOT, args.state, args.windows_controls, args.output)
    print(result["status"], result["sealed_radeon_trials"])


if __name__ == "__main__":
    main()
