"""Produce reviewer inputs with candidate answers and witness plans excluded."""

import argparse
from hashlib import sha256
import json

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import ROOT, canonical

from .multitool_v2_revised import FOLDER as MULTITOOL, candidate as multitool_cases
from .planning_l5_candidate import OUT as PLANNING, candidate as planning_cases
from .planning_partition_candidate import OUT as PLANNING_PARTITION, candidate as planning_partition
from .planning_roster import ATLAS, output_files

OUT = ATLAS / "release-review"
WRITE_TOOLS = {"stage", "commit", "request_confirmation"}


def event_input(event):
    # Preserve the evidence that an external grant exists without giving the value.
    return {k: v for k, v in event.items() if k != "approval"} | {"has_external_grant": "approval" in event}


def planning_rows(cases, proofs):
    for case, proof in zip(cases, proofs, strict=True):
        if case["case_id"] != proof["case_id"]:
            raise ValueError("Planning public and world cases do not match")
        case_id = case["case_id"]
        scenarios = []
        for world in proof["worlds"]:
            observations = sorted(
                [{k: step[k] for k in ("tool", "args", "result")} for step in world["steps"]
                 if step["tool"] not in WRITE_TOOLS], key=canonical,
            )
            events = [event_input(step["event"]) for step in world["steps"] if "event" in step]
            scenarios.append({"scenario_id": sha256(canonical([case_id, world["world_id"]])).hexdigest()[:20],
                              "service_inputs": observations, "external_events": events})
        contract = {k: v for k, v in case["contract"].items() if k != "goal"}
        yield {k: case[k] for k in ("case_id", "task", "language", "level", "limits", "public")} | {
            "public_tool_contract": contract, "scenarios": sorted(scenarios, key=lambda r: r["scenario_id"]),
        }


def multitool_rows():
    cases, _ = multitool_cases()
    for public, world, _ in cases:
        if public["case_id"] != world["case_id"]:
            raise ValueError("MULTITOOL public and world cases do not match")
        yield {k: public[k] for k in ("case_id", "category", "language", "message", "tools")} | {
            "service_records": world["records"], "external_event": world["event"],
        }


def packet(name, source, rows):
    rows = list(rows)
    if len({r["case_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate case in blind reviewer packet")
    cases = b"".join(canonical(row) + b"\n" for row in rows)
    check_text(cases)
    manifest = {
        "schema_version": "1.0", "packet": name, "candidate_source": source.relative_to(ROOT).as_posix(),
        "candidate_manifest_sha256": digest(source / "manifest.json"),
        "cases": len(rows), "review_inputs_sha256": sha256(cases).hexdigest(),
        "scenarios": sum(len(row.get("scenarios", [{}])) for row in rows),
        "review_status": "NOT_RUN", "dispatch": "BLOCKED",
    }
    return {"REVIEW_INPUTS.jsonl": cases, "PACKET_MANIFEST.json": canonical(manifest) + b"\n"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    packets = [
        ("MULTITOOL_V2_BLIND_REVIEW_PACKET", MULTITOOL, multitool_rows()),
        ("PLANNING_V2_BLIND_REVIEW_PACKET", PLANNING, planning_rows(*planning_cases())),
    ]
    for name, source, rows in packets:
        output_files(OUT / name, packet(name, source, rows), not args.write)
        print(f"{name} verified")
    cases, proofs, _ = planning_partition()
    name = "PLANNING_V2_BLIND_REVIEW_PACKET"
    output_files(OUT / name / "candidate-0.4",
                 packet(name, PLANNING_PARTITION, planning_rows(cases, proofs)), not args.write)
    print("Planning candidate 0.4 blind review packet verified")


if __name__ == "__main__":
    main()
