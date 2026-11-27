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


def scenario_id(case_id, world):
    return sha256(canonical([case_id, world["world_id"]])).hexdigest()[:20]


def planning_rows(cases, proofs, *, path_phase=False, omit_scenarios=False):
    for case, proof in zip(cases, proofs, strict=True):
        if case["case_id"] != proof["case_id"]:
            raise ValueError("Planning public and world cases do not match")
        case_id = case["case_id"]
        scenarios = []
        for world in proof["worlds"]:
            identifier = scenario_id(case_id, world)
            if path_phase:
                scenarios.append({"scenario_id": identifier})
                continue
            observations = sorted(
                [{k: step[k] for k in ("tool", "args", "result")} for step in world["steps"]
                 if step["tool"] not in WRITE_TOOLS], key=canonical,
            )
            events = [event_input(step["event"]) for step in world["steps"] if "event" in step]
            scenarios.append({"scenario_id": identifier,
                              "service_inputs": observations, "external_events": events})
        contract = {k: v for k, v in case["contract"].items() if k != "goal"}
        public = {k: case[k] for k in ("case_id", "task", "language", "level", "limits", "public")} | {
            "public_tool_contract": contract,
        }
        if not omit_scenarios:
            public["scenarios"] = sorted(scenarios, key=lambda r: r["scenario_id"])
        yield public


def planning_fixture_supplement(proofs):
    for proof in proofs:
        case_id = proof["case_id"]
        scenarios = []
        for world in proof["worlds"]:
            observations, events = [], []
            for step in world["steps"]:
                if step["tool"] not in WRITE_TOOLS:
                    observations.append(step["result"])
                elif step["tool"] == "request_confirmation":
                    observations.append({"confirmation_service_response": {
                        k: v for k, v in step["result"].items() if k != "approval"}})
                if "event" in step:
                    event = event_input(step["event"])
                    if "draft_id" in event:
                        event["draft_id"] = "the draft referenced by the host event"
                    events.append(event)
            scenarios.append({"scenario_id": scenario_id(case_id, world),
                              "service_observations": sorted(observations, key=canonical),
                              "external_events": events})
        yield {"case_id": case_id, "scenarios": sorted(scenarios, key=lambda item: item["scenario_id"])}


def multitool_rows():
    cases, _ = multitool_cases()
    for public, world, _ in cases:
        if public["case_id"] != world["case_id"]:
            raise ValueError("MULTITOOL public and world cases do not match")
        yield {k: public[k] for k in ("case_id", "category", "language", "message", "tools")} | {
            "service_records": world["records"], "external_event": world["event"],
        }


def packet(name, source, rows, *, supplement=None):
    rows = list(rows)
    if len({r["case_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate case in blind reviewer packet")
    cases = b"".join(canonical(row) + b"\n" for row in rows)
    check_text(cases)
    supplement = None if supplement is None else list(supplement)
    manifest = {
        "schema_version": "1.0", "packet": name, "candidate_source": source.relative_to(ROOT).as_posix(),
        "candidate_manifest_sha256": digest(source / "manifest.json"),
        "cases": len(rows), "review_inputs_sha256": sha256(cases).hexdigest(),
        "scenarios": sum(len(row.get("scenarios", [{}])) for row in (supplement or rows)),
        "review_status": "NOT_RUN", "dispatch": "BLOCKED",
    }
    files = {"REVIEW_INPUTS.jsonl": cases}
    if supplement is not None:
        raw = b"".join(canonical(row) + b"\n" for row in supplement)
        check_text(raw)
        files["SCENARIO_INPUTS.jsonl"] = raw
        del manifest["candidate_source"]
        manifest["path_phase"] = "independent expectations before scenario fixture receipt"
        manifest["scenario_inputs_sha256"] = sha256(raw).hexdigest()
    return files | {"PACKET_MANIFEST.json": canonical(manifest) + b"\n"}


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
    output_files(OUT / name / "candidate-0.4-review-v2",
                 packet(name, PLANNING_PARTITION, planning_rows(cases, proofs, path_phase=True),
                        supplement=planning_fixture_supplement(proofs)), not args.write)
    output_files(OUT / name / "candidate-0.4-review-v3",
                 packet(name, PLANNING_PARTITION, planning_rows(cases, proofs, path_phase=True, omit_scenarios=True),
                        supplement=planning_fixture_supplement(proofs)), not args.write)
    print("Planning candidate 0.4 blind review packet verified")


if __name__ == "__main__":
    main()
