"""Re-evaluate all 1,000 frozen IJ-0 traces without invoking a model."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from .evaluator import Call, evaluate
from .legacy_oracle import WRITES, make_workflow


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "benchmarks/tool_calling/datasets"
BASELINE = ROOT / "evidence/IJ0/protocol"
DEFAULT_OUTPUT = ROOT / "evidence/IJ06/rescoring"
BACKENDS = ("vulkan", "rocm")


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def json_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def calls_from_trace(row: dict) -> tuple[list[Call], tuple[tuple[str, str], ...]]:
    calls, problems = [], []
    for turn, step in enumerate(row["steps"]):
        if step.get("error") is not None:
            problems.append(("F05_PROTOCOL_ERROR", "original model API request failed"))
        if step.get("stream_matches_non_stream") is False:
            problems.append(("F05_PROTOCOL_ERROR", "historical streaming comparison failed"))
        for item in step.get("tool_calls", []):
            if item.get("id") != item.get("replay_id"):
                problems.append(("F05_PROTOCOL_ERROR", "original call identity differs from replay identity"))
            calls.append(Call(turn, item.get("id"), item["name"], item["arguments_raw"],
                              item.get("tool_result"), item["type"]))
    if row.get("unauthorized_executed"):
        problems.append(("F08_AUTHORIZATION_DENIAL", "original trace records forbidden tool execution"))
    if row["category"] == "thinking_separation":
        if not any(step.get("reasoning", "").strip() for step in row["steps"]):
            problems.append(("F05_PROTOCOL_ERROR", "missing reasoning content"))
        if any(any(marker in step.get("content", "") for marker in ("<think>", "</think>")) for step in row["steps"]):
            problems.append(("F05_PROTOCOL_ERROR", "reasoning tags leaked into visible content"))
    if row["steps"] and row["steps"][-1].get("tool_calls"):
        problems.append(("F05_PROTOCOL_ERROR", "trace ended with a tool call, without a terminal answer"))
    return calls, tuple(problems)


def rescore(case: dict, row: dict) -> dict:
    calls, problems = calls_from_trace(row)
    workflow = make_workflow(case, observed_write=any(name in WRITES for name in row["executed"]))
    verdict = evaluate(workflow, calls, row["final_text"], historical=True, trace_problems=problems)
    v1 = row["status"]
    observation = f"V1_{v1}_V2_TRACE_{verdict['trace_status']}"
    reasons = []
    if observation == "V1_FAIL_V2_TRACE_PASS":
        failures = row["failures"]
        if any(item.startswith(("first step ", "first call ", "argument order_id:")) for item in failures):
            reasons.append("V1_STRICT_ORDER_OR_GROUPING")
        if any(item.startswith("answer lacks required fact ") for item in failures):
            reasons.append("V1_ANSWER_MATCHING")
    return {
        "id": case["id"], "category": case["category"], "original_run_id": row["run_id"],
        "v1_status": v1, "comparison": observation, "v1_false_failure_reasons": reasons, **verdict,
    }


def summarize(rows: list[dict]) -> dict:
    return {
        "cases": len(rows),
        "v1_status": dict(Counter(row["v1_status"] for row in rows)),
        "trace_status": dict(Counter(row["trace_status"] for row in rows)),
        "strict_sop_status": dict(Counter(row["strict_sop_status"] for row in rows)),
        "business_state_status": dict(Counter(row["business_state_status"] for row in rows)),
        "status": dict(Counter(row["status"] for row in rows)),
        "argument_correct": sum(row["argument_correct"] for row in rows),
        "argument_total": sum(row["argument_total"] for row in rows),
        "comparison": dict(Counter(row["comparison"] for row in rows)),
        "v1_false_failure_reasons": dict(Counter(
            reason for row in rows for reason in row["v1_false_failure_reasons"]
        )),
        "cases_by_finding": dict(Counter(
            code for row in rows for code in {finding["code"] for finding in row["findings"]}
        )),
    }


def evidence() -> dict[str, str]:
    dataset = DATA / "tool_calling_500.jsonl"
    dataset_sha = sha256(dataset)
    manifest = read_json(DATA / "dataset.manifest.json")
    cases = json_lines(dataset)
    ids = [case["id"] for case in cases]
    if len(ids) != 500 or len(set(ids)) != len(ids) or not any(
        item["path"] == dataset.name and item["sha256"] == dataset_sha for item in manifest["files"]
    ):
        raise ValueError("dataset identity differs from the frozen manifest")
    code = Path(__file__).parent
    metadata = {
        "evidence_type": "RESCORED_DIAGNOSTIC_V2",
        "historical_baseline": "DIAGNOSTIC_BASELINE_V1",
        "new_inference": False, "independent_holdout": False,
        "dataset_sha256": dataset_sha,
        "code_sha256": {name: sha256(code / name) for name in (
            "rescore.py", "evaluator.py", "oracle.py", "legacy_oracle.py"
        )},
        "historical_sources": {}, "by_backend": {},
    }
    documents = {}
    for backend in BACKENDS:
        source = BASELINE / f"tool_calling_test_{backend}"
        run = read_json(source / "run.json")
        metrics = read_json(source / "metrics.json")
        samples = json_lines(source / "results.jsonl")
        if (run["dataset_sha256"] != dataset_sha or run["selected_case_ids"] != ids
                or run["server"]["backend"] != backend or [row["id"] for row in samples] != ids
                or any(row["run_id"] != run["run_id"] for row in samples)
                or metrics["run_id"] != run["run_id"] or metrics["cases"] != len(ids)
                or metrics["pass"] != sum(row["status"] == "PASS" for row in samples)):
            raise ValueError(f"{backend} run identities, coverage or V1 counts disagree")
        for case, row in zip(cases, samples, strict=True):
            if case["category"] != row["category"] or row["status"] not in ("PASS", "FAIL"):
                raise ValueError(f"historical row metadata disagrees for {row['id']}")
        rows = [rescore(case, row) for case, row in zip(cases, samples, strict=True)]
        by_category = defaultdict(list)
        for row in rows:
            by_category[row["category"]].append(row)
        documents[f"{backend}.jsonl"] = "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        )
        metadata["historical_sources"][backend] = {
            "run_id": run["run_id"], "git": run["git"], "engine": run["engine"],
            "server": run["server"], "sdk": run["sdk"],
            "files_sha256": {name: sha256(source / name) for name in ("run.json", "metrics.json", "results.jsonl")},
        }
        metadata["by_backend"][backend] = {
            **summarize(rows), "by_category": {name: summarize(group) for name, group in by_category.items()},
        }
    metadata["results_sha256"] = {name: hashlib.sha256(body.encode("utf-8")).hexdigest()
                                  for name, body in documents.items()}
    documents["summary.json"] = json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return documents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="verify existing artifacts byte-for-byte")
    args = parser.parse_args()
    documents = evidence()
    if args.check:
        missing = [name for name, body in documents.items()
                   if not (args.output / name).is_file() or (args.output / name).read_bytes() != body.encode("utf-8")]
        if missing:
            parser.exit(1, f"FAIL: regenerated evidence differs: {', '.join(missing)}\n")
    else:
        args.output.mkdir(parents=True, exist_ok=True)
        changes = [(args.output / name, body.encode("utf-8")) for name, body in documents.items()]
        if any(path.exists() and path.read_bytes() != data for path, data in changes):
            parser.exit(1, "FAIL: output contains different evidence. Select a new output directory.\n")
        for path, data in changes:
            if not path.exists():
                temporary = path.with_suffix(".tmp")
                temporary.write_bytes(data)
                temporary.replace(path)
    print("PASS: evidence covers 500 original cases per backend, 1,000 traces total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
