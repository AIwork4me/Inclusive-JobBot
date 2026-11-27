"""Replay published TC-V3 seals under a versioned supplemental capability assessment."""

import argparse
from collections import Counter, defaultdict
import gzip
from hashlib import sha256
import json
from pathlib import Path

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import canonical

from .mechanical_registry import REGISTRY, require_registry
from .tc_capability_replay import REQUEST_BINDINGS, TELEMETRY, VERDICTS, assess
from .tc_dashboard import ARCHIVE, STATUS, load_seal, objects
from .tc_v3 import HERE, verify_freeze

VERSION = "IJ-SLM-TC-V3-CAPABILITY-METRICS/1.0"
RATE_COUNTS = {
    "DUPLICATE_PROPOSAL_RATE": ("duplicate_proposals", "proposals"),
    "REDUNDANT_EXECUTION_RATE": ("redundant_executions", "executions"),
}
COST_OUTCOMES = {
    "correct_fact": ("required_fact", "BUSINESS_FACT_CORRECTNESS"),
    "strict_output": ("trial", "OUTPUT_CONTRACT_COMPLIANCE"),
    "verified_execution": ("trial", "EXECUTION_PROCESS_CORRECTNESS"),
    "qualified_business_completion": ("trial", "QUALIFIED_BUSINESS_COMPLETION"),
}
DEFINITIONS = {
    "BUSINESS_FACT_CORRECTNESS": (
        "Frozen synthetic read-only facts with exact expected values. Requires a terminal provider-linked answer, "
        "expected callback results, correct dependencies and verified delivery. A single whole-answer JSON fence "
        "is eligible. Facts outside the frozen keys are outside this proof."
    ),
    "OUTPUT_CONTRACT_COMPLIANCE": "Terminal bare JSON object with exactly the frozen keys and JSON value types.",
    "EXECUTION_PROCESS_CORRECTNESS": (
        "Exact linked executed action occurrences, expected callback outcomes, delivered prerequisite results, "
        "execution within the tool budget and unchanged sandbox authorization state."
    ),
    "STRICT_END_TO_END_SUCCESS": "Original sealed TC-V3 verdict (D25).",
    "FIRST_TOOL_CHOICE": "First provider tool name is available at the start of the frozen task, or valid no-tool case.",
    "REQUIRED_ACTION_COVERAGE": "Every frozen action occurrence is proposed with exact typed arguments.",
    "EXACT_ACTION_SEQUENCE": (
        "Provider proposals contain exactly the frozen occurrences in a dependency-respecting order. "
        "Independent actions can occur in either order or in one provider response."
    ),
    "DUPLICATE_PROPOSAL_RATE": "Repeated excess proposal occurrences divided by all decoded provider proposals.",
    "REDUNDANT_EXECUTION_RATE": "Repeated excess executions divided by all callback-linked EXECUTED occurrences.",
    "RESULT_DELIVERY": "Every required executed callback result is linked to its payload in the next provider request.",
    "RESULT_COMPREHENSION": (
        "Terminal provider answer matches every expected value after proof of required, correctly delivered results."
    ),
    "TERMINATION_CORRECTNESS": (
        "The first request with all required correct results ends with stop, or an immediate correct clarification."
    ),
    "QUALIFIED_BUSINESS_COMPLETION": (
        "Synthetic read-only fact, output, execution, exact sequence, delivery, comprehension and termination proof."
    ),
}


def distribution(outcomes):
    counts = Counter(outcomes)
    denominator = counts["PASS"] + counts["FAIL"]
    return {key: counts[key] for key in STATUS} | {
        "denominator": denominator, "rate": counts["PASS"] / denominator if denominator else None,
    }


def event_rate(rows, numerator, denominator):
    pairs = [tuple(row["call_counts"][key] for key in (numerator, denominator)) for row in rows]
    known = [(n, d) for n, d in pairs if n is not None and d is not None]
    count, opportunities = sum(n for n, _ in known), sum(d for _, d in known)
    missing = len(pairs) - len(known)
    status = "BLOCKED" if missing else "PASS" if opportunities else "NOT_RUN"
    return {"status": status, "numerator": count, "denominator": opportunities,
            "observed_trials": len(known), "missing_trials": missing,
            "rate": count / opportunities if status == "PASS" else None}


def cost_per_outcome(rows, outcomes, unit, telemetry_totals, excluded_trials):
    counts = {status: outcomes[status] for status in STATUS}
    denominator = counts["PASS"]
    fields = {}
    for field, (total, observed_trials) in telemetry_totals.items():
        missing = len(rows) - observed_trials
        status = "NOT_RUN" if not rows else "PASS" if denominator and not missing else "BLOCKED"
        fields[field] = {
            "status": status, "value": total / denominator if status == "PASS" else None,
            "observed_total": total, "observed_trials": observed_trials, "missing_trials": missing,
        }
    return {"denominator": denominator, "denominator_unit": unit, "outcome_units": counts,
            "sealed_cost_cohort_trials": len(rows), "out_of_outcome_scope_trials": excluded_trials,
            "telemetry": fields}


def summarize_cell(rows):
    metric_counts = {key: distribution(row["metrics"][key] for row in rows) for key in VERDICTS}
    fact_counts = Counter(status for row in rows for status in row["fact_outcomes"].values())
    outside_fact_scope = sum(not row["business_fact_scope_eligible"] for row in rows)
    telemetry_totals = {}
    for field in TELEMETRY:
        observed = [row["telemetry"][field] for row in rows if row["telemetry"][field] is not None]
        telemetry_totals[field] = (sum(observed) if observed else None, len(observed))
    costs = {}
    for label, (unit, metric) in COST_OUTCOMES.items():
        out_of_scope = outside_fact_scope if label in ("correct_fact", "qualified_business_completion") else 0
        costs[label] = cost_per_outcome(
            rows, fact_counts if label == "correct_fact" else metric_counts[metric], unit, telemetry_totals,
            out_of_scope,
        )
    return {"metrics": metric_counts, "fact_outcomes": {status: fact_counts[status] for status in STATUS},
            "rates": {key: event_rate(rows, *fields) for key, fields in RATE_COUNTS.items()},
            "provider_request_bindings": {key: sum(row["provider_request_bindings"][key] for row in rows)
                                          for key in REQUEST_BINDINGS},
            "cost_per_outcome": costs}


def build(archive=ARCHIVE):
    if not archive.is_dir():
        raise ValueError("published TC-V3 archive directory is missing")
    verify_freeze()
    require_registry()
    dataset_digest = digest(HERE / "manifest.json")
    registry_digest = digest(REGISTRY)
    roster = {row["trial_id"]: row for row in objects(HERE / "roster.jsonl")}
    public = {row["case_id"]: row for row in objects(HERE / "holdout-public.jsonl")}
    oracles = {row["case_id"]: row for row in objects(HERE / "holdout-oracle.jsonl")}
    seen, seals, rows = set(), {}, []
    for path in sorted(archive.glob("*/manifest.json")):
        manifest, records, peak_memory = load_seal(path)
        identity = manifest["identity"]
        enrollment = identity["enrollment"]
        if enrollment["dataset_manifest_sha256"] != dataset_digest:
            raise ValueError("sealed enrollment differs from the frozen TC-V3 dataset")
        if manifest["gpu_execution"] == "PASS" and enrollment["registry_sha256"] != registry_digest:
            raise ValueError("sealed enrollment differs from the TC-V3 mechanical registry")
        session = path.parent.name
        seal_digest = digest(path)
        seals[session] = {
            "candidate": identity["candidate"], "manifest_sha256": seal_digest,
            "trials_sha256": manifest["artifacts"]["trials.jsonl.gz"],
            "reservations": manifest["reservations"], "gpu_execution": manifest["gpu_execution"],
            "peak_gpu_committed_bytes": peak_memory,
        }
        for record in records:
            key = record["trial_id"]
            spec = roster.get(key)
            physical = record["physical_execution"]
            if (spec is None or spec["candidate"] != identity["candidate"] or key in seen
                    or physical not in STATUS or record["status"] not in STATUS):
                raise ValueError("duplicate, invalid or misrouted TC-V3 seal")
            seen.add(key)
            trace = record.get("trace")
            if trace is not None and any(trace.get(label) != spec[label]
                                         for label in ("trial_id", "case_id", "track", "seed")):
                raise ValueError("sealed trace differs from the frozen TC-V3 roster")
            if physical == "PASS" and (not trace or not record.get("private_capture_sha256")
                                       or manifest["gpu_execution"] != "PASS"):
                raise ValueError("physical seal lacks trial capture provenance")
            case = public[spec["case_id"]]
            oracle = oracles[spec["case_id"]]
            result = assess(trace if physical == "PASS" else None, oracle, record["status"],
                            verified_portable_seal=True)
            rows.append({
                "version": VERSION, **spec, "family": case["family"], "language": case["language"],
                "risk_scope": oracle["risk_scope"], "physical_run_id": session, "physical_execution": physical,
                "physical_manifest_sha256": seal_digest, "physical_trials_sha256": seals[session]["trials_sha256"],
                "private_capture_sha256": record.get("private_capture_sha256"),
                "sealed_status": record["status"], "sealed_component_assessment": record.get("component_assessment"),
                **result,
            })

    planned_models = Counter(spec["candidate"] for spec in roster.values())
    planned_cells = Counter((spec["candidate"], spec["track"]) for spec in roster.values())
    by_model, by_cell = defaultdict(list), defaultdict(list)
    for row in rows:
        candidate = row["candidate"]
        by_model[candidate].append(row)
        by_cell[candidate, row["track"]].append(row)

    def coverage(planned, entries):
        return {"planned": planned, "sealed": len(entries), "unsealed": planned - len(entries),
                "executed": sum(row["physical_execution"] == "PASS" for row in entries)}

    report = {
        "version": VERSION, "dataset_manifest_sha256": dataset_digest, "mechanical_registry_sha256": registry_digest,
        "sources": {name: digest(Path(__file__).with_name(name))
                    for name in ("tc_capability_metrics.py", "tc_capability_replay.py")},
        "sealed_manifests": seals, "totals": coverage(len(roster), rows) | summarize_cell(rows),
        "models": {candidate: coverage(total, by_model[candidate]) for candidate, total in planned_models.items()},
        "cells": {f"{model}/{track}": coverage(total, by_cell[model, track]) | summarize_cell(by_cell[model, track])
                  for (model, track), total in planned_cells.items()},
        "definitions": DEFINITIONS,
        "request_binding_definition": (
            "Requests retain the original SHA256. SDK system-content redaction may change its digest. "
            "A verified portable seal binds those changed requests when redaction markers are confined to system "
            "content. All replayed provider responses must still match their original SHA256."
        ),
        "cost_definition": (
            "Sum captured resource consumption across all sealed rows in the cell, including failed and "
            "out-of-outcome-scope trials, divided by the count of proved outcome units. "
            "A zero denominator or incomplete telemetry blocks the rate. Observed totals and missing trial "
            "counts describe partial data. No estimated latency, power or currency is substituted."
        ),
    }
    return rows, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--rows", type=Path, required=True, help="gzip-compressed JSONL derived assessments")
    parser.add_argument("--check", action="store_true", help="verify existing outputs against a fresh replay")
    args = parser.parse_args()
    destinations = {args.summary.resolve(), args.rows.resolve()}
    if len(destinations) != 2 or any(p.is_relative_to(root.resolve())
                                     for p in destinations for root in (args.archive, HERE)):
        parser.error("derived outputs require distinct paths outside the input archive and TC-V3 freeze")
    rows, report = build(args.archive)
    payload = b"".join(canonical(row) + b"\n" for row in rows)
    document = canonical(report | {"derived_rows_sha256": sha256(payload).hexdigest()}) + b"\n"
    check_text(payload)
    check_text(document)
    if args.check:
        if args.summary.read_bytes() != document or gzip.decompress(args.rows.read_bytes()) != payload:
            raise ValueError("published TC-V3 capability metrics differ from the sealed replay")
    else:
        for path in destinations:
            path.parent.mkdir(parents=True, exist_ok=True)
        args.rows.write_bytes(gzip.compress(payload, mtime=0))
        args.summary.write_bytes(document)
    print(json.dumps({"version": VERSION, "sealed": len(rows), "executed": report["totals"]["executed"]}))


if __name__ == "__main__":
    main()
