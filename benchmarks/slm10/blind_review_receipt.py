"""Verify a returned blind review before independent reconciliation and issuance."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from evaluation.aeve.archive import digest
from evaluation.aeve.runtime import canonical
from .blind_review_packets import OUT
from .planning_roster import object_json

STATUS = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
COLLECTION = ("MULTITOOL_V2_BLIND_REVIEW_PACKET", "PLANNING_V2_BLIND_REVIEW_PACKET")


def key(row):
    return row["case_id"], row["scenario_id"]


def coverage(cases, findings):
    cases = list(cases)
    if len({row["case_id"] for row in cases}) != len(cases):
        raise ValueError("duplicate case identity in review inputs")
    expected = set()
    for row in cases:
        scenarios = row.get("scenarios", [{"scenario_id": None}])
        if not scenarios or len({value["scenario_id"] for value in scenarios}) != len(scenarios):
            raise ValueError("missing or duplicate scenario in review inputs")
        expected.update((row["case_id"], value["scenario_id"]) for value in scenarios)
    seen = set()
    counts = Counter()
    for item in findings:
        identifier = key(item)
        if identifier in seen:
            raise ValueError("duplicate finding for a case and scenario")
        if identifier not in expected:
            raise ValueError("finding falls outside the review packet")
        seen.add(identifier)
        counts[item["status"]] += 1
    counts["NOT_RUN"] += len(expected - seen)
    return {status: counts[status] for status in STATUS}


def expectation_digest(findings):
    payload = [{field: row[field] for field in ("case_id", "scenario_id", "independent_expectation")}
               for row in sorted(findings, key=lambda r: (r["case_id"], r["scenario_id"] or ""))]
    return sha256(canonical(payload)).hexdigest()


def receipt(packet, verdict_path, recorded_sha256, *, phase_one_sha256=None):
    allowed = (OUT / COLLECTION[0], OUT / COLLECTION[1], OUT / COLLECTION[1] / "candidate-0.4-review-v2")
    if packet.resolve() not in allowed:
        raise ValueError("provide an exact repository review packet directory")
    if digest(verdict_path) != recorded_sha256:
        raise ValueError("submission digest differs from the issuer's intake record")
    schema = object_json((OUT / "review-verdict.schema.json").read_bytes())
    review = object_json(verdict_path.read_bytes())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(review)
    source = packet / "PACKET_MANIFEST.json"
    manifest = object_json(source.read_bytes())
    if (review["packet_manifest_sha256"] != digest(source) or review["packet"] != manifest["packet"]
            or review["expectations_sha256"] != expectation_digest(review["findings"])):
        raise ValueError("review does not bind the exact packet and independently recorded expectations")
    if "scenario_inputs_sha256" in manifest:
        if not phase_one_sha256 or review.get("phase_one_expectations_sha256") != phase_one_sha256:
            raise ValueError("Planning review is missing the prior independently frozen path expectation")
        if digest(packet / "SCENARIO_INPUTS.jsonl") != manifest["scenario_inputs_sha256"]:
            raise ValueError("scenario input digest differs from the pinned packet")
    inputs = packet / "REVIEW_INPUTS.jsonl"
    if digest(inputs) != manifest["review_inputs_sha256"]:
        raise ValueError("packet reviewer input digest differs from its manifest")
    cases = [object_json(line) for line in inputs.read_bytes().splitlines()]
    if len(cases) != manifest["cases"]:
        raise ValueError("case count differs from the pinned packet")
    counts = coverage(cases, review["findings"])
    if sum(counts.values()) != manifest["scenarios"]:
        raise ValueError("scenario count differs from the pinned packet")
    keys = {row["case_id"] for row in cases}
    if any(set(finding["case_ids"]) - keys for finding in review["semantic_duplicate_findings"]):
        raise ValueError("duplicate assessment refers to a case outside the packet")
    return {
        "packet_manifest_sha256": review["packet_manifest_sha256"],
        "candidate_manifest_sha256": manifest["candidate_manifest_sha256"],
        "review_file_sha256": recorded_sha256, "review_scope": review["review_scope"],
        "dispositions": counts, "partition_status": review["partition_status"],
        "semantic_duplicate_findings": len(review["semantic_duplicate_findings"]),
        "receipt_integrity": "PASS", "reviewer_identity_verification": "BLOCKED",
        "discrepancy_reconciliation": "NOT_RUN", "formal_dispatch": "BLOCKED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--verdict", type=Path, required=True)
    parser.add_argument("--received-sha256", required=True, help="digest recorded on authorized receipt")
    parser.add_argument("--phase-one-sha256", help="Planning path expectation receipt recorded before scenario release")
    args = parser.parse_args()
    result = receipt(args.packet, args.verdict, args.received_sha256, phase_one_sha256=args.phase_one_sha256)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
