"""Launch one resumable arm of the frozen PC-P prompt experiment."""

from argparse import ArgumentParser
import json
from pathlib import Path
import subprocess
import sys

from benchmarks.agentic_planning_v1.runner import PROMPT_ARMS
from benchmarks.competitive_slm.tc_v2_batch import legacy


ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "atlas/benchmarks/pc_p_factorial.json"


def frozen_panel():
    panel = json.loads(PANEL.read_bytes())
    source = json.loads((ROOT / panel["source_roster"]).read_bytes())["planning_v1"]
    expected = [case_id for stratum in source["selection_by_stratum"].values() for case_id in stratum[:2]]
    variants = panel["arm_factors"]
    if (panel["case_ids"] != expected or len(set(expected)) != len(expected)
            or panel["planned_trials"] != len(expected) * len(variants) * len(panel["candidate_profiles"])
            or {name: frozenset(factors) for name, factors in variants.items()} != PROMPT_ARMS):
        raise ValueError("PC-P pilot differs from its roster or registered interventions")
    return panel


def main():
    panel = frozen_panel()
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--candidate", choices=panel["candidate_profiles"])
    parser.add_argument("--arm", choices=panel["arm_factors"])
    parser.add_argument("--model", type=Path)
    parser.add_argument("--engine-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    if args.check:
        print(f"PC-P registered {panel['planned_trials']} matched Plan-first trials")
        return
    if (not all((args.candidate, args.arm, args.engine_dir, args.output))
            or (args.model is None) != (args.candidate == "A") or args.batch_size < 1):
        parser.error("supply candidate, arm, engine and output; supply a model path for B, G or H")
    if legacy.git_state()["dirty"]:
        parser.error("the experiment requires a clean source commit")
    profile = panel["profile"]
    output = args.output.resolve()
    command = [sys.executable, "-m", "benchmarks.agentic_planning_v1.run",
               "--backend", profile["backend"], "--engine-dir", str(args.engine_dir.resolve()),
               "--tracks", panel["track"], "--panel", "primary", "--prompt-contract", args.arm,
               "--require-clean-source",
               "--seed", str(panel["seed"]), "--max-tokens", str(profile["max_tokens"]),
               "--temperature", str(profile["temperature"]), "--output", str(output),
               "--batch-size", str(args.batch_size)]
    if args.model is not None:
        command += ["--candidate", args.candidate, "--model", str(args.model.resolve())]
    for case in panel["case_ids"]:
        command.extend(("--case", case))
    if (output / "run.json").is_file():
        command.append("--resume")
    common = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True,
    ).strip()
    slot = Path(common).parent / ".runtime/ij072-pc-s-slot"
    slot.mkdir(parents=True, exist_ok=True)
    try:
        with legacy.output_lock(slot):
            raise SystemExit(subprocess.call(command))
    except OSError as error:
        parser.exit(2, f"BLOCKED: unable to run in the shared Radeon slot ({error.strerror})\n")


if __name__ == "__main__":
    main()
