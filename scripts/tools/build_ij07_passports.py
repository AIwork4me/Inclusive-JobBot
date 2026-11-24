"""Derive interim model capability passports from measured IJ-0.7 evidence."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJ07"


def read(path):
    return json.loads(path.read_bytes())


def passports():
    history = read(EVIDENCE / "historical_replay/full/summary.json")
    performance = read(EVIDENCE / "performance/historical_summary.json")
    for candidate in "ABCDEFGH":
        identity = read(EVIDENCE / f"model_identity/{candidate}.json")
        result = {
            "candidate": candidate, "model_id": identity["official_model_id"], "identity": identity,
            "qualification": "NOT_RUN", "scope": "interim diagnostic",
            "metrics": dict.fromkeys(("independent_single_tool", "independent_parallel_tools",
                                     "independent_dependent_tools", "maximum_verified_task_depth",
                                     "autonomous_level", "dynamic_replanning", "long_horizon",
                                     "chinese_independent", "repeat_reliability", "quantization_qualification"), "NOT_RUN"),
            "production_admission": "BLOCKED",
        }
        if candidate == "C":
            result["native_runtime_reference"] = {
                backend: {
                    key: record[key] for key in ("run_id", "backend", "versions", "status", "reported_device_type")
                }
                for backend in ("cpu", "webgpu")
                for record in [read(EVIDENCE / f"model_identity/aion_reference/{backend}.json")]
            }
        else:
            result["runtime_admission"] = {
                arm: {key: record[key] for key in ("run_id", "asset", "gates", "status", "gpu_engine", "gpu")}
                for arm in ("admission", "admission_strict")
                for record in [read(EVIDENCE / f"model_identity/{arm}/{candidate}/report.json")]
            }
        if candidate == "A":
            result["historical_diagnostic"] = {
                arm: {
                    "run_id": data["run_id"], "wire_single_tool": data["by_category"]["single_tool"]["trace_status"],
                    "dependent_multi_tool_semantic": data["by_category"]["sequential_multi_tool"]["trace_status"],
                    "dependent_multi_tool_verdict": data["by_category"]["sequential_multi_tool"]["status"],
                    "argument_fields": {"correct": data["v2"]["argument_correct"], "total": data["v2"]["argument_total"]},
                    "verified_empty_tag_generation_cases": len(data["historical_empty_tags_cases_with_empty_pre_parser_array"]),
                }
                for arm, data in history["arms"].items()
            }
            result["resource_evidence"] = {
                row["identity"]["arm"]: {"request_ms": row["latency"]["trajectory_request_wall_ms"],
                                         "gpu_peak_bytes": row["resources"]["process_gpu_memory_peak_bytes"]}
                for row in performance
            }
            result["planning_diagnostic"] = read(EVIDENCE / "planning/diagnostic/summary.json")["counts"]
            result["multitool_diagnostic"] = read(EVIDENCE / "multitool/diagnostic/summary.json")["tasks"]
            result["tc_v2"] = {}
            for backend in ("vulkan", "rocm"):
                path = EVIDENCE / f"tc_v2/holdout/{backend}/summary.json"
                if path.is_file():
                    qualification = read(path)
                    result["tc_v2"][backend] = {
                        field: qualification[field] for field in ("run_id", "status", "first_pass", "repeat", "gates")
                    }
            if result["tc_v2"]:
                result["qualification"] = "FAIL" if any(
                    row["status"] == "FAIL" for row in result["tc_v2"].values()
                ) else "BLOCKED"
        yield candidate, result
    job_primary = read(EVIDENCE / "job_ablation/F/primary/summary.json")
    job_repeat = read(EVIDENCE / "job_ablation/F/repeat/summary.json")
    yield "I", {
        "candidate": "I", "model_id": None, "scope": "deterministic software baseline",
        "historical_structured_development": {"PASS": 3, "FAIL": 0},
        "job_v1_arm_f": {"primary": job_primary, "repeat": job_repeat},
        "model_native_planning": "NOT_RUN", "production_admission": "BLOCKED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    directory = EVIDENCE / "model_passports"
    if not args.check:
        directory.mkdir(exist_ok=True)
    for candidate, row in passports():
        path = directory / f"{candidate}.json"
        data = (json.dumps(row, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
        if args.check:
            if path.read_bytes() != data:
                parser.exit(1, f"FAIL: passport {candidate} differs\n")
        else:
            path.write_bytes(data)
    print("PASS: nine interim capability passports")


if __name__ == "__main__":
    main()
