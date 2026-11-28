"""Derive five-model capability passports and matched TC-V3 Pareto comparisons."""

import argparse
from collections import defaultdict
import gzip
from hashlib import sha256
import json

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import ROOT, canonical

from .sdk_ablation_summary import RESULT
from .tc_capability_metrics import distribution
from .tc_dashboard import percentile
from .tc_v3 import HERE

ATLAS = HERE.parent
SOURCE = ATLAS / "tc-capability-matrix.json"
ROWS = ROOT / "evidence/IJSLM/tc-capability/assessments.jsonl.gz"
PASSPORTS = ATLAS / "tc-capability-passports.json"
PARETO = ATLAS / "tc-quality-resource-pareto.json"
TRACKS = ("direct_first", "sdk_first", "sdk_streaming")
QUALITY = "QUALIFIED_BUSINESS_COMPLETION"
RESOURCE_FIELDS = ("provider_inference_ms", "total_tokens")
VERSION = "IJ-SLM-TC-ATLAS-VIEWS/1.0"


def paired_frontier(rows, sessions):
    by_case = defaultdict(dict)
    for row in rows:
        if row["track"] in TRACKS and row["physical_execution"] == "PASS":
            by_case[row["case_id"]][row["track"]] = row
    matches = [case for case in by_case.values() if set(case) == set(TRACKS)]
    complete = [case for case in matches if all(
        row["metrics"][QUALITY] in ("PASS", "FAIL")
        and all(row["telemetry"][field] is not None for field in RESOURCE_FIELDS)
        and sessions[row["physical_run_id"]]["peak_gpu_committed_bytes"] is not None
        for row in case.values())]
    points = {}
    for track in TRACKS:
        trials = [case[track] for case in complete]
        points[track] = {
            "quality": distribution(row["metrics"][QUALITY] for row in trials),
            **{field: percentile([row["telemetry"][field] for row in trials]) for field in RESOURCE_FIELDS},
            "session_peak_gpu_committed_bytes": percentile(
                [sessions[key]["peak_gpu_committed_bytes"] for key in sorted(
                    {row["physical_run_id"] for row in trials})]),
        }
    if complete:
        def objectives(point):
            return (-point["quality"]["rate"], *(point[field]["p50"] for field in RESOURCE_FIELDS))

        for track, point in points.items():
            own = objectives(point)
            dominates = []
            for other, comparison in points.items():
                values = list(zip(objectives(comparison), own, strict=True))
                if all(left <= right for left, right in values) and any(left < right for left, right in values):
                    dominates.append(other)
            point["dominated_by"] = dominates
            point["on_frontier"] = not dominates
    return {"status": "PASS" if complete else "BLOCKED", "matched_case_count": len(matches),
            "jointly_evaluable_cases": len(complete), "case_ids": sorted(next(iter(case.values()))["case_id"]
                                                                        for case in complete),
            "points": points}


def views():
    sources = (SOURCE, ROWS, RESULT, ATLAS / "model_registry.json", ATLAS / "sdk-adapter-profiles.json",
               ATLAS / "execution_plan.json")
    snapshot = json.loads(SOURCE.read_bytes())
    payload = gzip.decompress(ROWS.read_bytes())
    if sha256(payload).hexdigest() != snapshot["derived_rows_sha256"]:
        raise ValueError("capability rows differ from the verified assessment digest")
    if len(payload.splitlines()) != snapshot["totals"]["sealed"]:
        raise ValueError("capability row count differs from the verified assessment inventory")
    rows = defaultdict(list)
    for line in payload.splitlines():
        row = json.loads(line)
        rows[row["candidate"]].append(row)
    ablation = json.loads(RESULT.read_bytes())["models_and_arms"]
    models = json.loads((ATLAS / "model_registry.json").read_bytes())["models"]
    plan = json.loads((ATLAS / "execution_plan.json").read_bytes())
    context = {"version": VERSION, "sources": {path.relative_to(ROOT).as_posix(): digest(path) for path in sources}}
    passports, pareto = {}, {}
    for candidate in plan["panel"]:
        baseline = {track: snapshot["cells"][f"{candidate}/{track}"]
                    for track in (*TRACKS, "sdk_repeat")}
        diagnostic = {arm: ablation[f"{candidate}/{arm}"] for arm in ("A0", "SDK_CONTROL", "A5", "GUARD")
                      if f"{candidate}/{arm}" in ablation}
        passports[candidate] = {
            "model": models[candidate]["model"],
            "model_asset_sha256": models[candidate]["asset"]["expected_sha256"],
            "coverage": snapshot["models"][candidate],
            "native": baseline["direct_first"], "sdk": {track: baseline[track] for track in TRACKS[1:]},
            "sdk_repeat": baseline["sdk_repeat"],
            "specialization": {"physical_development": diagnostic, "independent_holdout": "NOT_RUN",
                               "production_qualification": "BLOCKED"},
            "autonomous_qualification": "BLOCKED",
        }
        pareto[candidate] = paired_frontier(rows[candidate], snapshot["sealed_manifests"])
    allocation = {suite: len(plan["panel"]) * sum(tracks.values()) for suite, tracks in plan["suites"].items()}
    if sum(allocation.values()) != plan["core_total"] or allocation["TC-V3"] != snapshot["totals"]["planned"]:
        raise ValueError("capability inventory diverges from the frozen core allocation")
    passports_document = context | {"core_allocation": allocation, "core_total": plan["core_total"],
                                    "core_physical_observed": snapshot["totals"]["executed"],
                                    "passports": passports}
    pareto_document = context | {
        "objectives": {"maximize": [QUALITY], "minimize": list(RESOURCE_FIELDS)},
        "scope": "Same model, seed and case across all three first-attempt tracks. Quality and both telemetry fields "
                 "must be observed on every included track. GPU memory is a shared session statistic. "
                 "Experimental SDK arms use a separate development dataset and scope.",
        "models": pareto,
    }
    return {PASSPORTS: passports_document, PARETO: pareto_document}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    for path, document in views().items():
        payload = canonical(document) + b"\n"
        check_text(payload)
        if args.write:
            path.write_bytes(payload)
        elif path.read_bytes() != payload:
            raise ValueError(f"{path.name} does not match capability replay")
    print("Capability passports and matched quality-resource comparisons verified")


if __name__ == "__main__":
    main()
