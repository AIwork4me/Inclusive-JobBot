"""Derive interim model capability passports from measured IJ-0.7 evidence."""

import argparse
import gzip
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
            result["dependent_tool_diagnostic"] = {
                backend: {
                    "run_id": record["run_id"], "status": record["status"],
                    "first_boundary": record["trials"][0].get("failure"),
                    "independent_streaming": record["independent_streaming"],
                }
                for backend in ("cpu", "webgpu")
                for record in [read(EVIDENCE / f"model_identity/aion_tools/{backend}-strict.json")]
            }
            control = read(EVIDENCE / "model_identity/aion_tools/cpu-serial-control.json")
            result["explicit_instruction_cpu_control"] = {
                key: control[key] for key in ("run_id", "backend", "profile", "status")
            }
            paired = EVIDENCE / "model_identity/aion_tools/serial-comparison.json"
            if paired.is_file():
                result["paired_cpu_radeon_instruction_control"] = read(paired)
        else:
            result["runtime_admission"] = {
                arm: {key: record[key] for key in ("run_id", "asset", "gates", "status", "gpu_engine", "gpu")}
                for arm in ("admission", "admission_strict")
                for record in [read(EVIDENCE / f"model_identity/{arm}/{candidate}/report.json")]
            }
        if candidate in "BDFG":
            trial = read(EVIDENCE / f"competitive_slm/dev/{candidate}/result.json")["row"]
            result["shared_development_diagnostic"] = {
                field: trial[field] for field in ("case_id", "run_id", "status", "argument_correct", "argument_total", "findings")
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
            checkpoint = read(EVIDENCE / "multitool/primary-vulkan-checkpoint/coverage.json")
            result["multitool_primary_checkpoint"] = {
                field: checkpoint[field]
                for field in ("run_id", "coverage_complete", "terminal", "planned", "terminal_outcomes", "strata")
            }
            full = EVIDENCE / "multitool/primary-vulkan-full/coverage.json"
            if full.is_file():
                coverage = read(full)
                result["multitool_primary_full"] = {
                    field: coverage[field]
                    for field in ("run_id", "coverage_complete", "terminal", "planned", "terminal_outcomes", "strata")
                }
                result["metrics"]["independent_parallel_tools"] = coverage["strata"]["category"]["MT-01"]
                result["metrics"]["long_horizon"] = coverage["strata"]["depth"]["16-20"]
                with gzip.open(full.with_name("terminal.jsonl.gz"), "rt", encoding="utf-8") as handle:
                    passed_depths = (row["required_tool_steps"] for row in (json.loads(line)["row"] for line in handle)
                                     if row["status"] == "PASS")
                    result["metrics"]["maximum_verified_task_depth"] = {
                        "required_steps": max(passed_depths, default=None), "scope": "MULTITOOL-V1 original Vulkan profile"
                    }
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
                for backend, profile in result["tc_v2"].items():
                    coverage = read(EVIDENCE / f"tc_v2/holdout/{backend}/coverage.json")
                    profile["first_pass_by_language"] = coverage["first_pass_by_language"]
                    profile["wilson95_first_pass"] = coverage["wilson95_first_pass"]
                for metric, component in (("independent_single_tool", "single_tool"),
                                          ("independent_dependent_tools", "sequential_multi_tool")):
                    result["metrics"][metric] = {
                        backend: profile["first_pass"]["case_rates"][component] for backend, profile in result["tc_v2"].items()
                    }
                result["metrics"]["chinese_independent"] = {
                    backend: profile["first_pass_by_language"]["zh"] for backend, profile in result["tc_v2"].items()
                }
                result["metrics"]["repeat_reliability"] = {
                    backend: profile["repeat"] for backend, profile in result["tc_v2"].items()
                }
            plan = EVIDENCE / "planning/primary-vulkan-full/diagnostic.json"
            repeated = EVIDENCE / "multitool/repeat-vulkan-full/reliability.json"
            if repeated.is_file():
                record = read(repeated)
                result["multitool_repeat"] = {key: record[key] for key in ("run_id", "scope", "all")}
            if plan.is_file():
                report = read(plan)
                result["full_planning"] = {key: report[key] for key in ("run_id", "overall", "levels", "evidence")}
                autonomy, replanning = {}, {}
                for track, levels in report["levels"].items():
                    passed_level = None
                    for level in (f"L{index}" for index in range(8)):
                        if levels[level]["qualification"]["status"] != "PASS":
                            break
                        passed_level = level
                    autonomy[track] = passed_level
                    replanning[track] = {
                        level: row["score_metrics_assessable"]["dynamic_replanning_success"]
                        for level, row in levels.items() if "dynamic_replanning_success" in row["score_metrics_assessable"]
                    }
                result["metrics"]["autonomous_level"] = {"qualified_level": autonomy, "scope": "original Vulkan profile"}
                result["metrics"]["dynamic_replanning"] = replanning
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
