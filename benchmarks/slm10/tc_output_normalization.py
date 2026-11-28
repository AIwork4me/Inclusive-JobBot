"""Replay a host-only fenced JSON extraction against immutable TC-V3 output."""

import argparse
from collections import defaultdict
from hashlib import sha256
import json

from benchmarks.tool_calling_v2.oracle import equal
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import canonical
from model_gateway.errors import GatewayError
from model_gateway.strict_json import strict_object

from .sdk_adapters import MAX_RESULT_BYTES
from .tc_capability_replay import FENCE, final_object
from .tc_dashboard import ARCHIVE, load_seal, objects, proportion
from .tc_five_model_report import index
from .tc_v3 import HERE

OUT = HERE.parent / "tc-output-normalization-replay.json"
MODELS = ("D", "F")


def extract_object(raw, *, terminal_allowed):
    """Return only the exact object text inside one unambiguous fenced answer."""
    if terminal_allowed is not True or not isinstance(raw, str):
        return None
    try:
        if len(raw.encode("utf-8")) > MAX_RESULT_BYTES:
            return None
    except UnicodeEncodeError:
        return None
    match = FENCE.fullmatch(raw)
    if match is None:
        return None
    try:
        strict_object(match[1], max_bytes=MAX_RESULT_BYTES)
    except GatewayError:
        return None
    return match[1]


def compile_replay():
    matrix, roster, derived = index()
    oracles = {row["case_id"]: row for row in objects(HERE / "holdout-oracle.jsonl")}
    cells, candidates = defaultdict(list), []
    for run, seal in matrix["sealed_manifests"].items():
        model = seal["candidate"]
        if model not in MODELS:
            continue
        path = ARCHIVE / run / "manifest.json"
        manifest, captures, _ = load_seal(path)
        if digest(path) != seal["manifest_sha256"] or manifest["identity"]["candidate"] != model:
            raise ValueError("normalization input does not match the published assessment manifest")
        for capture in captures:
            trial = capture["trial_id"]
            row = derived[trial]
            if row["physical_run_id"] != run or roster[trial]["candidate"] != model:
                raise ValueError("normalization input does not match its physical trial identity")
            baseline = row["metrics"]["OUTPUT_CONTRACT_COMPLIANCE"]
            key = model, row["track"]
            cells[key].append([baseline, baseline, "UNCHANGED"])
            if (row["metrics"]["BUSINESS_FACT_CORRECTNESS"] != "PASS"
                    or baseline != "FAIL" or row["answer_kind"] != "fenced_json"):
                continue
            original = capture["trace"]["answer"]
            transformed = extract_object(original, terminal_allowed=True)
            if transformed is None:
                cells[key][-1][2] = "REJECTED"
                continue
            # Scoring is offline and independent of extraction. Preserve exact provider bytes.
            raw_object, _ = final_object(original)
            candidate, kind = final_object(transformed)
            contract = oracles[row["case_id"]]["answer"]
            if kind != "bare_json" or not equal(raw_object, candidate):
                raise ValueError("normalization changed model-provided content")
            valid = candidate.keys() == contract.keys() and all(type(candidate[k]) is type(v) for k, v in contract.items())
            status = "PASS" if valid else "FAIL"
            cells[key][-1] = [baseline, status, "HOST_NORMALIZED"]
            candidates.append({
                "candidate": model, "case_id": row["case_id"], "track": row["track"], "trial_id": trial,
                "run_id": run, "manifest_sha256": seal["manifest_sha256"], "preserves_values": "PASS",
                "raw_output_contract": baseline, "replayed_output_contract": status,
                "raw_answer_sha256": sha256(original.encode()).hexdigest(),
                "normalized_answer_sha256": sha256(transformed.encode()).hexdigest(),
            })
    summaries = {}
    for (model, track), entries in sorted(cells.items()):
        full = sum(spec["candidate"] == model and spec["track"] == track for spec in roster.values())
        missing = ["NOT_RUN"] * (full - len(entries))
        summaries[f"{model}/{track}"] = {
            "planned": full, "sealed": len(entries),
            "physical_output_contract": proportion([entry[0] for entry in entries] + missing),
            "offline_output_contract": proportion([entry[1] for entry in entries] + missing),
            "host_normalized": sum(entry[2] == "HOST_NORMALIZED" for entry in entries),
            "rejected": sum(entry[2] == "REJECTED" for entry in entries),
        }
    return {
        "schema_version": "1.0", "attribution": "HOST_NORMALIZED", "formal_trial_attribution": 0,
        "status": "PASS", "physical_intervention": "NOT_RUN", "strict_d25": "BLOCKED",
        "scope": "Retrospective counterfactual software check on existing physically sealed outputs with proven "
                 "business facts. The transformation could change only the output contract in this replay.",
        "unchanged_experiment": "Original provider answers, tool executions and physical verdicts remain immutable.",
        "resource_overhead": "NOT_RUN", "source_assessments_sha256": matrix["derived_rows_sha256"],
        "normalization_profiles": {
            "MODEL_NATIVE": "Original sealed output", "HOST_NORMALIZED": "Offline extraction",
            "RUNTIME_CONSTRAINED": "NOT_RUN", "RETRY_ASSISTED": "NOT_RUN",
        },
        "summaries": summaries, "normalization_candidates": candidates,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = compile_replay()
    raw = canonical(report) + b"\n"
    check_text(raw)
    if args.write:
        OUT.write_bytes(raw)
    elif OUT.read_bytes() != raw:
        raise ValueError("offline output normalization differs from the checked TC-V3 seals")
    print(f"Verified {len(report['normalization_candidates'])} host normalization opportunities from sealed outputs")


if __name__ == "__main__":
    main()
