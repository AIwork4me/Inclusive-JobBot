"""Qualify the new TC-V3 SDK JSON and repeat transports on Radeon development cases."""

import argparse
from collections import defaultdict
from itertools import product
import json
from pathlib import Path
from uuid import uuid4

from audit import write_evidence
from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT, fingerprint
from scripts.tools.verify_ij06_evidence import verify_gpu

from . import lfm3_ha_admission as ha
from .admission import git_head
from .ha11_panel import COMPATIBILITY, CORRECTED
from .ha11_preflight import FLAGS, FixedChatClient, checked_runtime, trial
from .tc_capability_replay import assess, read_wire
from .tc_v3 import FIRST_SEED, HERE, REPEAT_SEEDS, verify_freeze


TRACKS = ("sdk_first", "sdk_repeat")
FAMILIES = ("single", "dependency", "clarification")


def cases():
    verify_freeze()
    inputs = [[json.loads(line) for line in (HERE / f"development-{key}.jsonl").read_bytes().splitlines()]
              for key in ("public", "worlds", "oracle")]
    cohort = {public["case_id"]: (public, world, oracle)
              for public, world, oracle in zip(*inputs, strict=True)
              if public["family"] in FAMILIES and public["case_id"].endswith("-000")}
    if len(cohort) != len(FAMILIES):
        raise ValueError("Compatibility development cases differ from the frozen roster")
    return cohort


def planned(cohort):
    return [(case_id, track, seed) for case_id, track in product(cohort, TRACKS)
            for seed in ((FIRST_SEED,) if track == "sdk_first" else REPEAT_SEEDS)]


def verify(folder):
    report = json.loads((folder / "report.json").read_bytes())
    cohort = cases()
    pin = json.loads((ha.ATLAS / "EVIDENCE_MANIFEST.json").read_bytes())["runtime"]
    if (report["scope"] != COMPATIBILITY or report["runtime"] != pin
            or report["dataset_sha256"] != fingerprint(list(cohort.values()))
            or [(row["case_id"], row["track"], row["seed"]) for row in report["results"]] != planned(cohort)
            or report["gpu_execution"] != "PASS"
            or any(digest(folder / name) != value for name, value in report["artifacts"].items())
            or not verify_gpu({"gpu_launch": folder / "launch.json", "gpu_counters": folder / "gpu.jsonl"}, "vulkan")):
        raise ValueError("Compatibility admission identity, roster or GPU evidence differs")
    outcomes = defaultdict(list)
    for row in report["results"]:
        path = folder / (row["trial_id"] + ".json")
        capture = json.loads(path.read_bytes())
        if digest(path) != row["capture_sha256"] or capture["trial_id"] != row["trial_id"]:
            raise ValueError("Compatibility admission trace hash differs")
        turns, proposals = read_wire(capture, False)
        requests_ok = bool(turns) and all(
            "reply" in turn and event["native_evidence"]["status"] == "PASS"
            and json.loads(event["request"])["stream"] is True
            and json.loads(event["provider_request"])["stream"] is False
            and json.loads(event["provider_request"])["seed"] == row["seed"]
            and event["sdk_content_type"].startswith("text/event-stream")
            for event, turn in zip(capture["wire"], turns, strict=True))
        ids = {callback["call_id"] for callback in capture["callbacks"] if callback["status"] == "PASS"}
        bindings_ok = ids == {call["call_id"] for call in proposals}
        assessment = assess(capture, cohort[row["case_id"]][2], "BLOCKED")
        if row["assessment"] != assessment:
            raise ValueError("Compatibility admission independent assessment differs")
        outcomes[row["track"]].append((requests_ok and bindings_ok, bool(ids),
                                       assessment["answer_kind"] != "missing"))
    # Require linked real tool actions and an observed terminal response on each transport.
    status = {track: "PASS" if all(row[0] for row in entries) and any(row[1] for row in entries)
              and any(row[2] for row in entries) else "BLOCKED" for track, entries in outcomes.items()}
    return report | {"transport": status, "replay": "PASS"}


def run(assets, output, port):
    registry, pin, model, binary, harness = checked_runtime(assets)
    handoff = require_handoff(ROOT)
    cohort = cases()
    output.mkdir(parents=True, exist_ok=False)
    trace = output / "native.jsonl"
    run_id = "lfm3-ha11-tc-transport-" + uuid4().hex
    report = {"scope": COMPATIBILITY, "run_id": run_id, "git_sha": git_head(), "runtime": pin,
              "base": registry["base"]["asset"], "dataset_sha256": fingerprint(list(cohort.values())),
              "handoff_sha256": digest(ROOT / HANDOFF), "gpu_execution": "NOT_RUN",
              "registered_trials": 0, "core_trial_attribution": 0, "results": []}
    with ha.server(binary, model, None, port, output, pin, run_id, handoff, launch_flags=FLAGS,
                   trace_path=trace, sampler_seconds=900) as (_, launch):
        client = FixedChatClient(port, trace, max_nonstream_calls=12)
        for case_id, track, seed in planned(cohort):
            public, world, oracle = cohort[case_id]
            ident = fingerprint([run_id, case_id, track, seed])
            result = trial(client, public, world, CORRECTED, ident, output / ident, harness, seed=seed, track=track)
            path = output / (ident + ".json")
            write_evidence(path, result)
            report["results"].append({"case_id": case_id, "track": track, "seed": seed, "trial_id": ident,
                                      "capture_sha256": digest(path),
                                      "assessment": assess(result, oracle, "BLOCKED")})
    launch_path = output / "launch.json"
    counters = output / "gpu.jsonl"
    write_evidence(launch_path, launch)
    report["gpu_execution"] = "PASS" if verify_gpu(
        {"gpu_launch": launch_path, "gpu_counters": counters}, "vulkan") else "BLOCKED"
    report["artifacts"] = {path.name: digest(path) for path in (launch_path, counters, trace)}
    write_evidence(output / "report.json", report)
    result = verify(output)
    print(result["transport"], len(result["results"]), result["run_id"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18757)
    args = parser.parse_args()
    run(args.assets.resolve(strict=True), args.output.resolve(), args.port)


if __name__ == "__main__":
    main()
