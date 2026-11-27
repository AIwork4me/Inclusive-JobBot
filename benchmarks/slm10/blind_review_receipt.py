"""Verify blind review artifacts before independent reconciliation and issuance."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from evaluation.aeve.runtime import canonical, fingerprint
from .blind_review_packets import OUT
from .planning_roster import object_json, pinned_content

STATUS = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
SCOPES = ("READ_ONLY_MECHANICAL", "STATEFUL", "AFFIRMATIVE_WRITE", "STRICT_END_TO_END")
MULTITOOL = "MULTITOOL-V2"
PLANNING = "AGENTIC-PLAN-V2"
ACTIVE_PACKETS = {
    MULTITOOL: (OUT / "MULTITOOL_V2_BLIND_REVIEW_PACKET",
                "f0be21ce227d9801c489a987b98bb6919cc6d388d6493a186390e1ed652378bf"),
    PLANNING: (OUT / "PLANNING_V2_BLIND_REVIEW_PACKET/candidate-0.4-review-v3",
               "b3a6f1b801b8eabeeb81f9b3517f9396a71b4c3acec98c7d4395705d30d40a97"),
}


def active_packet(suite, packet=None):
    if suite not in ACTIVE_PACKETS:
        raise ValueError("unknown active review suite")
    registered, pin = ACTIVE_PACKETS[suite]
    if packet is not None and packet.resolve() != registered:
        raise ValueError("provide the exact active repository review packet")
    manifest = object_json(pinned_content(registered, "PACKET_MANIFEST.json", pin))
    return registered, pin, manifest


def _inputs(packet, manifest):
    raw = pinned_content(packet, "REVIEW_INPUTS.jsonl", manifest["review_inputs_sha256"])
    cases = [object_json(line) for line in raw.splitlines()]
    if len(cases) != manifest["cases"] or len({row["case_id"] for row in cases}) != len(cases):
        raise ValueError("case roster differs from the pinned packet")
    return cases


def _schema_valid(document, filename, description):
    schema = object_json((OUT / filename).read_bytes())
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)
    except ValidationError as error:
        raise ValueError(f"{description} fails schema at {error.json_path}") from None


def phase_one_template(review_scope="CONTENT_AND_PARTITION"):
    """Build a blank review form using only the public path-phase packet."""
    if review_scope not in (*SCOPES, "CONTENT_AND_PARTITION"):
        raise ValueError("unknown phase-one review scope")
    packet, pin, manifest = active_packet(PLANNING)
    cases = _inputs(packet, manifest)
    if any("scenarios" in row for row in cases):
        raise ValueError("phase-one packet already exposes scenarios")
    return {
        "schema_version": "1.0", "packet_manifest_sha256": pin, "reviewer_id": "",
        "review_scope": review_scope, "semantic_duplicate_findings": [],
        "expectations": [{"case_id": case_id, "branches": []}
                         for case_id in sorted(row["case_id"] for row in cases)],
    }


def _check_duplicate_findings(findings, keys):
    if any(set(finding["case_ids"]) - keys for finding in findings):
        raise ValueError("duplicate assessment refers to a case outside the packet")


def validate_phase_one(document):
    """Check exact case coverage before scenario disclosure and return its canonical digest."""
    _schema_valid(document, "phase-one-expectations.schema.json", "phase-one expectation")
    template = phase_one_template(document["review_scope"])
    keys = {row["case_id"] for row in template["expectations"]}
    returned = [row["case_id"] for row in document["expectations"]]
    if (document["packet_manifest_sha256"] != template["packet_manifest_sha256"]
            or len(returned) != len(keys) or set(returned) != keys):
        raise ValueError("phase-one expectations must cover each exact active Planning case once")
    _check_duplicate_findings(document["semantic_duplicate_findings"], keys)
    duplicate_groups = [
        row | {"case_ids": sorted(row["case_ids"])} for row in document["semantic_duplicate_findings"]
    ]
    return fingerprint(document | {
        "expectations": sorted(document["expectations"], key=lambda row: row["case_id"]),
        "semantic_duplicate_findings": sorted(duplicate_groups, key=canonical),
    })


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
    return fingerprint(payload)


def inspect_review(suite, packet, verdict_raw, recorded_sha256, *, phase_one=None, phase_one_sha256=None):
    packet, packet_pin, manifest = active_packet(suite, packet)
    if sha256(verdict_raw).hexdigest() != recorded_sha256:
        raise ValueError("submission digest differs from the issuer's intake record")
    review = object_json(verdict_raw.decode("utf-8"))
    _schema_valid(review, "review-verdict.schema.json", "review verdict")
    if (review["packet_manifest_sha256"] != packet_pin or review["packet"] != manifest["packet"]
            or review["expectations_sha256"] != expectation_digest(review["findings"])):
        raise ValueError("review does not bind the exact packet and independently recorded expectations")
    cases = _inputs(packet, manifest)
    if suite == PLANNING:
        if (phase_one is None or not phase_one_sha256 or validate_phase_one(phase_one) != phase_one_sha256
                or review.get("phase_one_expectations_sha256") != phase_one_sha256
                or any(phase_one[field] != review[field] for field in ("reviewer_id", "review_scope"))):
            raise ValueError("Planning review is missing the prior independently frozen path expectation")
        raw = pinned_content(packet, "SCENARIO_INPUTS.jsonl", manifest["scenario_inputs_sha256"])
        scenarios = [object_json(line) for line in raw.splitlines()]
        indexed = {row["case_id"]: row["scenarios"] for row in scenarios}
        if indexed.keys() != {row["case_id"] for row in cases} or len(indexed) != len(scenarios):
            raise ValueError("scenario supplement does not bind the exact phase-one task IDs")
        cases = [row | {"scenarios": indexed[row["case_id"]]} for row in cases]
    elif phase_one is not None or phase_one_sha256 is not None or "phase_one_expectations_sha256" in review:
        raise ValueError("MULTITOOL review uses the single-phase packet")
    counts = coverage(cases, review["findings"])
    if sum(counts.values()) != manifest["scenarios"]:
        raise ValueError("scenario count differs from the pinned packet")
    _check_duplicate_findings(review["semantic_duplicate_findings"], {row["case_id"] for row in cases})
    result = {
        "packet_manifest_sha256": packet_pin, "candidate_manifest_sha256": manifest["candidate_manifest_sha256"],
        "review_file_sha256": recorded_sha256, "review_scope": review["review_scope"],
        "dispositions": counts, "partition_status": review["partition_status"],
        "semantic_duplicate_findings": len(review["semantic_duplicate_findings"]),
        "receipt_integrity": "PASS", "reviewer_identity_verification": "BLOCKED",
        "discrepancy_reconciliation": "NOT_RUN", "formal_dispatch": "BLOCKED",
    }
    return review, cases, result


def receipt(packet, verdict_path, recorded_sha256, *, phase_one_path=None, phase_one_sha256=None):
    suite = next((suite for suite, (path, _) in ACTIVE_PACKETS.items() if path == packet.resolve()), None)
    phase_one = None if phase_one_path is None else object_json(phase_one_path.read_text(encoding="utf-8"))
    _, _, result = inspect_review(suite, packet, verdict_path.read_bytes(), recorded_sha256,
                                  phase_one=phase_one, phase_one_sha256=phase_one_sha256)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--phase-one-template", action="store_true")
    action.add_argument("--validate-phase-one", type=Path)
    action.add_argument("--verdict", type=Path)
    parser.add_argument("--review-scope", choices=(*SCOPES, "CONTENT_AND_PARTITION"), default="CONTENT_AND_PARTITION")
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--received-sha256", help="digest recorded on authorized receipt")
    parser.add_argument("--phase-one-file", type=Path, help="exact Planning path expectations received before disclosure")
    parser.add_argument("--phase-one-sha256", help="canonical digest recorded before scenario release")
    args = parser.parse_args()
    try:
        if args.phase_one_template:
            result = phase_one_template(args.review_scope)
        elif args.validate_phase_one:
            document = object_json(args.validate_phase_one.read_text(encoding="utf-8"))
            result = {"phase_one_expectations_sha256": validate_phase_one(document)}
        else:
            if args.packet is None or args.received_sha256 is None:
                parser.error("--verdict requires --packet and --received-sha256")
            result = receipt(args.packet, args.verdict, args.received_sha256,
                             phase_one_path=args.phase_one_file, phase_one_sha256=args.phase_one_sha256)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
