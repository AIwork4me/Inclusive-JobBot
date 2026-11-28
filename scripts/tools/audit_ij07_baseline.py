"""Rebuild IJ-0.7's archival audit from the frozen IJ-0.6 artifacts."""

import argparse
from collections import Counter
import json
from pathlib import Path

from benchmarks.tool_calling_v2 import rescore
from scripts.tools.verify_ij06_evidence import validate_baseline, validate_ij06_artifacts


ROOT = Path(__file__).resolve().parents[2]
STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}


def audit_backend(historical, rescored):
    for original, audited in zip(historical, rescored, strict=True):
        if (original["id"], original["category"], original["status"]) != (
            audited["id"], audited["category"], audited["v1_status"]
        ):
            raise ValueError("historical and rescored row identity mismatch")
        if any(audited[key] not in STATUSES for key in ("trace_status", "status", "business_state_status")):
            raise ValueError("invalid archived status")
    return {
        "cases": len(historical),
        "v1": dict(Counter(row["status"] for row in historical)),
        "semantic": dict(Counter(row["trace_status"] for row in rescored)),
        "diagnostic_verdict": dict(Counter(row["status"] for row in rescored)),
        "business_state": dict(Counter(row["business_state_status"] for row in rescored)),
        "arguments": {
            "correct": sum(row["argument_correct"] for row in rescored),
            "total": sum(row["argument_total"] for row in rescored),
        },
        "findings_by_case": dict(Counter(
            code for row in rescored for code in {item["code"] for item in row["findings"]}
        )),
    }


def archived_rows(root, backend, documents):
    historical_path = root / f"evidence/IJ0/protocol/tool_calling_test_{backend}/results.jsonl"
    historical = rescore.json_lines(historical_path)
    rescored = [json.loads(line) for line in documents[f"{backend}.jsonl"].splitlines()]
    sequential = "sequential_multi_tool"
    seq_original = [row for row in historical if row["category"] == sequential]
    seq_rescored = [row for row in rescored if row["category"] == sequential]
    empty_tags = [
        row["id"] for row in seq_original if row["status"] == "PASS" and any(
            call["name"] == "create_ticket" and (call.get("arguments") or {}).get("tags") == []
            for step in row["steps"] for call in step.get("tool_calls", [])
        )
    ]
    return {
        "all": audit_backend(historical, rescored),
        "sequential": audit_backend(seq_original, seq_rescored),
        "v1_pass_with_empty_ticket_tags": empty_tags,
        "v1_and_semantic_fail_sequential": [
            row["id"] for row in seq_rescored
            if row["v1_status"] == row["trace_status"] == "FAIL"
        ],
    }


def rows_for_parser(root, backend):
    path = root / f"evidence/IJ06/parser/p4b-clean-windows-{backend}"
    rows = rescore.json_lines(path / "results.jsonl")
    summary = rescore.read_json(path / "summary.json")
    if len({row["id"] for row in rows}) != len(rows) or any(row["run_id"] != summary["run_id"] for row in rows):
        raise ValueError("parser row identities disagree")
    for key in ("status", "native", "wire", "strict_arguments", "parser_stream_parity", "execution_safety"):
        if dict(Counter(row[key] for row in rows)) != summary[key]:
            raise ValueError(f"parser {key} counts disagree")
    return {
        **summary,
        "fixture_count": len(rows),
        "wire_failure_ids": [row["id"] for row in rows if row["wire"] == "FAIL"],
    }


def audit():
    prior = ROOT / "evidence/IJ06"
    upstream_manifest = ROOT / "reports/IJ06_ARTIFACT_MANIFEST.json"
    baseline_count = validate_baseline(ROOT)
    artifact_count = validate_ij06_artifacts(ROOT)
    documents = rescore.evidence()
    for name, body in documents.items():
        if (prior / "rescoring" / name).read_bytes() != body.encode("utf-8"):
            raise ValueError(f"archived evaluator output differs: {name}")
    native = rescore.read_json(prior / "parser/p4b-windows-direct.json")
    regression = rescore.read_json(prior / "security/software_regression_windows.json")
    return {
        "status": "PASS",
        "scope": "archival audit",
        "new_model_inference": False,
        "source_manifests": {
            "evidence/IJ06/baseline_manifest.json": rescore.sha256(prior / "baseline_manifest.json"),
            "reports/IJ06_ARTIFACT_MANIFEST.json": rescore.sha256(upstream_manifest),
        },
        "baseline_blob_count": baseline_count,
        "ij06_artifact_count": artifact_count,
        "recalculated": {backend: archived_rows(ROOT, backend, documents) for backend in rescore.BACKENDS},
        "p4b_fixed_wire_cases": {backend: rows_for_parser(ROOT, backend) for backend in rescore.BACKENDS},
        "p4b_native": {"run_id": native["run_id"], "counts": native["counts"]},
        "gateway_software_only": {
            "run_id": regression["run_id"],
            "counts": dict(Counter(case["status"] for case in regression["cases"])),
        },
        "sdk": {
            variant: {
                backend: {
                    gate: result["status"] for gate, result in rescore.read_json(
                        prior / "antigravity" / f"{prefix}{backend}.json"
                    )["results"].items()
                }
                for backend in rescore.BACKENDS
            }
            for variant, prefix in (("b12359", ""), ("p4b", "p4b-"))
        },
        "job_v1_development": {
            backend: dict(Counter(
                row["status"] for row in rescore.read_json(
                    prior / f"performance/{backend}/development.json"
                )["results"]
            ))
            for backend in rescore.BACKENDS
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = ROOT / "evidence/IJ07/baseline_manifest.json"
    data = (json.dumps(audit(), sort_keys=True, indent=2) + "\n").encode("utf-8")
    if output.exists() or args.check:
        if not output.is_file() or output.read_bytes() != data:
            parser.exit(1, "FAIL: archival audit differs from evidence/IJ07/baseline_manifest.json\n")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as handle:
            handle.write(data)
    print("PASS: IJ-0.7 archival audit")


if __name__ == "__main__":
    main()
