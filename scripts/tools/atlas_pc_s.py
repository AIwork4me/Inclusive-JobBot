"""Launch one checked batch of the frozen PC-S reference panel."""

from argparse import ArgumentParser
import json
from pathlib import Path
import subprocess
import sys

from benchmarks.competitive_slm.tc_v2_batch import PC_S_ROSTER, legacy
from scripts.tools.atlas_reference_panel import create

SUITES = {
    "tc": ("benchmarks.competitive_slm.tc_v2_batch", "tc_v2"),
    "multi": ("benchmarks.multitool_v1.run", "multitool_v1"),
    "planning": ("benchmarks.agentic_planning_v1.run", "planning_v1"),
}


def runner_arguments(suite, frozen):
    module, cohort = SUITES[suite]
    if suite == "tc":
        return module, ["--panel", "pc-s"]
    arguments = ["--backend", "vulkan", "--panel", "primary"]
    if suite == "planning":
        arguments += ["--tracks", "".join(frozen[cohort]["tracks"])]
    for group in frozen[cohort]["selection_by_stratum"].values():
        for case_id in group:
            arguments.extend(("--case", case_id))
    return module, arguments


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=SUITES, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    frozen = json.loads(PC_S_ROSTER.read_bytes())
    if frozen != create():
        parser.error("PC-S roster differs from its frozen definition")
    module, selection = runner_arguments(args.suite, frozen)
    command = [sys.executable, "-m", module, *selection, "--candidate", "H",
               "--model", str(args.model.resolve()), "--engine-dir", str(args.engine_dir.resolve())]
    output = args.output.resolve()
    if args.preflight:
        command.append("--verify-runtime" if args.suite == "tc" else "--preflight-only")
        if args.suite == "planning":
            command.extend(("--output", str(output)))
        return subprocess.call(command)
    if legacy.git_state()["dirty"]:
        parser.error("reference inference requires a clean source commit for exact resume")
    slot = PC_S_ROSTER.parents[2] / ".runtime/ij072-pc-s-slot"
    slot.mkdir(parents=True, exist_ok=True)
    try:
        with legacy.output_lock(slot):
            command += ["--output", str(output), "--batch-size", str(args.batch_size)]
            if (output / "run.json").is_file():
                command.append("--resume")
            return subprocess.call(command)
    except OSError as error:
        parser.exit(2, f"BLOCKED: unable to run in the shared PC-S slot ({error.strerror})\n")


if __name__ == "__main__":
    raise SystemExit(main())
