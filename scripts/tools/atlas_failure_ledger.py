"""Index the documented RC-01 and RC-02 diagnostic evidence by failed trial."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
from pathlib import Path

from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.atlas_validity.evaluation import parsed, planning_scores_v2
from scripts.tools.atlas_progress import document, jsonl

ROOT = Path(__file__).resolve().parents[2]


def planning():
    frozen = ROOT / "benchmarks/agentic_planning_v1"
    cases = {row["case_id"]: row for row in load_jsonl(frozen / "datasets/holdout.jsonl")}
    graphs = {row["case_id"]: row for row in load_jsonl(frozen / "task_graphs/holdout.jsonl")}
    for panel, count in (("primary", 1600), ("repeat", 960)):
        folder = ROOT / "evidence/IJ07/planning" / f"{panel}-vulkan-full"
        diagnostic = document(folder / "diagnostic.json")
        seen = set()
        for shard in sorted(folder.glob("planning-part-*.jsonl.gz")):
            for member in jsonl(shard):
                if not member["name"].startswith("cases/"):
                    continue
                row = json.loads(member["raw_text"])
                if row["run_id"] != diagnostic["run_id"] or row["status"] != "FAIL" or member["name"] in seen:
                    raise ValueError("unexpected frozen planning trial")
                seen.add(member["name"])
                case_id = row["case_id"]
                findings = row["findings"]
                first = findings[0] if findings else None
                plan = parsed(row["plan_raw"])
                plan_shape = ("missing" if not row["plan_raw"] else "unparsed" if plan is None
                              else "object:" + ",".join(sorted(plan)))
                scores = planning_scores_v2(cases[case_id], graphs[case_id], row)
                source_file, source_function = (("benchmarks/agentic_planning_v1/runner.py", "run_trajectory")
                                                if findings else ("benchmarks/agentic_planning_v1/oracle.py", "score"))
                yield {
                    "cluster": "RC-01",
                    "case_id": case_id,
                    "run_id": row["run_id"],
                    "model_id": "MiniCPM5-2B",
                    "panel": panel,
                    "trial": row["trial"]["trial_id"],
                    "track": row["track"],
                    "language": cases[case_id]["language"],
                    "failure_signature": first["code"] if first else "ORACLE_REJECTED",
                    "raw_generation_reference": {
                        "archive": shard.relative_to(ROOT).as_posix(), "trial_member": member["name"],
                        "journal_member": row["journal"], "journal_sha256": row["journal_sha256"],
                    },
                    "first_observable_divergence": (first.get("detail", first["code"]) if first else
                                                   row["errors"][0] if row["errors"] else "frozen oracle rejected the terminal result"),
                    "source_file": source_file,
                    "source_function": source_function,
                    "source_commit": diagnostic["identity"]["git"]["commit"],
                    "root_cause_hypothesis": ("overlapping initial and final output contracts" if row["track"] == "P" else
                                              "boundary or oracle rejects the captured behavior"),
                    "minimal_reproducer": None,
                    "counterfactual": "paired P1 and frozen P0 still required",
                    "root_cause_status": "SUPPORTED_BUT_INCOMPLETE",
                    "fix_commit": None,
                    "red_green_test": ("tests/regression/ij07/test_agentic_planning_v1.py"
                                       if row["track"] == "P" else None),
                    "regression_evidence": "evidence/IJ07/root_causes/planning_reference_boundary_control.json",
                    "remaining_limitation": "The first observed rejection does not establish its model-level cause.",
                    "initial_plan_shape": plan_shape if row["track"] == "P" else None,
                    "diagnostic_scores": scores,
                }
        if len(seen) != count:
            raise ValueError(f"wrong number of planning trials in {panel}")


def quote():
    reference = "evidence/IJ072/root_causes/rc02-quote-diagnostic.json"
    data = document(ROOT / reference)
    for candidate, result in data["candidates"].items():
        for trial in result["trials"]:
            yield {
                "cluster": "RC-02",
                "case_id": trial["case_id"],
                "run_id": result["run_id"],
                "model_id": {"B": "LFM3-1.7B", "D": "Qwen3.5-2B",
                             "F": "Ministral-3-3B-Instruct", "G": "Gemma-4-E2B-it"}[candidate],
                "trial": trial["key"],
                "language": trial["language"],
                "failure_signature": trial["finding_codes"],
                "raw_generation_reference": {
                    "archive_index": f"evidence/IJ071/legacy_competitive/{candidate}/trials.jsonl.gz",
                    "source_sha256": trial["trajectory_sha256"],
                    "completion_id": trial["terminal_completion_id"],
                },
                "first_observable_divergence": trial["finding_codes"][0],
                "source_file": "benchmarks/tool_calling_v2/holdout/runner.py",
                "source_function": "run_trajectory",
                "source_commit": result["source_commit"],
                "root_cause_hypothesis": "strict final rendering or tool-trajectory mismatch",
                "minimal_reproducer": "scripts/tools/atlas_quote_controls.py",
                "counterfactual": ("remove JSON fence in a secondary diagnostic"
                                   if trial["fence_only_counterfactual"] else None),
                "root_cause_status": "SUPPORTED_BUT_INCOMPLETE",
                "fix_commit": None,
                "red_green_test": None,
                "regression_evidence": reference,
                "remaining_limitation": "Paired live prompt or template controls and independent qualification remain open.",
            }


def output_data():
    rows = [*planning(), *quote()]
    counts = defaultdict(Counter)
    dimensions = defaultdict(Counter)
    for row in rows:
        if row["cluster"] == "RC-01":
            group = f"{row['panel']}/{row['track']}"
            counts[group][row["failure_signature"]] += 1
            for dimension, status in row["diagnostic_scores"].items():
                dimensions[group][f"{dimension}/{status}"] += 1
    summary = {"scope": "RC-01 planning and RC-02 quote diagnostics", "ledger_rows": len(rows),
               "planning_failure_signatures": counts, "planning_layered_scores": dimensions}
    return {
        "atlas/root_causes/failure_ledger.jsonl": "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        "evidence/IJ072/root_causes/rc01-diagnostic.json": json.dumps(summary, indent=2, sort_keys=True) + "\n",
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name, data in output_data().items():
        target = ROOT / name
        if args.check:
            if target.read_bytes() != data.encode():
                parser.error(f"stale root-cause evidence: {name}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(data.encode())
    print("Historical RC-01 and RC-02 source references verified")


if __name__ == "__main__":
    main()
