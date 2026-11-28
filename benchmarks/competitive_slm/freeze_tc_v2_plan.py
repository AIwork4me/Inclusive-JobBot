"""Freeze the four strict-aligned TC-V2 contrasts from the exact execution checkout."""

import argparse
from itertools import combinations
import json
from pathlib import Path

from benchmarks.competitive_slm import statistics, tc_v2_batch, tc_v2_candidate


ASSETS = {
    "B": "LiquidAI__LFM3-1.7B-GGUF",
    "D": "unsloth__Qwen3.5-2B-GGUF",
    "F": "mistralai__Ministral-3-3B-Instruct-2512-GGUF",
    "G": "ggml-org__gemma-4-E2B-it-GGUF",
}


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-head", required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    git = tc_v2_candidate.legacy.git_state()
    if git["commit"] != args.execution_head or git["dirty"]:
        raise ValueError("use the clean, exact recorded competitive execution checkout")
    plan = statistics.frozen_suite("TC-V2")
    _, roster = tc_v2_batch.make_roster("full")
    plan_pairing = {case["case_id"]: case["pairing_sha256"] for case in plan["cases"]}
    if any(plan_pairing[trial["case_id"]] != trial["pairing_sha256"] for trial in roster):
        raise ValueError("statistics case pairing differs from the execution roster")
    arms = {}
    for key, directory in ASSETS.items():
        assets = sorted((args.candidate_root / directory).glob("*Q8_0.gguf"))
        if len(assets) != 1:
            raise ValueError(f"expected one exact candidate file for {key}")
        runtime = tc_v2_candidate.verify_runtime(key, assets[0].resolve(strict=True), args.engine_dir.resolve(strict=True))
        config = tc_v2_candidate.build_configuration(
            runtime, roster[0]["dataset_sha256"], roster[0]["manifest_sha256"],
            extra_files=(Path(tc_v2_batch.__file__),),
        )
        arms[key] = {
            "model": config["model"]["official_model_id"], "backend": config["backend"],
            "device": config["gpu"]["architecture"], "track": config["track"],
            "quantization": config["model"]["quantization"], "thinking": config["budgets"]["thinking"],
            "protocol": "native-tool-calling", "controls_sha256": config["controls_sha256"],
            "configuration_sha256": statistics.digest(config),
        }
    if len({arm["controls_sha256"] for arm in arms.values()}) != 1:
        raise ValueError("strict candidate controls differ")
    plan.update(
        schema_version=1, arms=arms, bootstrap={"seed": 20261124, "samples": 10000},
        comparisons=[{"id": f"{left}-to-{right}", "left": left, "right": right, "vary": "model"}
                     for left, right in combinations(arms, 2)],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    lock = args.output.with_name(args.output.stem + ".lock.json")
    if args.output.exists() or lock.exists():
        raise ValueError("choose a fresh statistics plan and lock destination")
    write(args.output, plan)
    write(lock, {
        "plan_sha256": statistics.digest(plan), "execution_head": git["commit"],
        "roster_sha256": statistics.digest(roster), "trials_per_arm": len(roster),
        "frozen_utc": tc_v2_candidate.legacy.utc_now(),
    })
    print(f"PASS: frozen {len(arms)} exact TC-V2 arm configurations and {len(plan['comparisons'])} matched contrasts")


if __name__ == "__main__":
    main()
