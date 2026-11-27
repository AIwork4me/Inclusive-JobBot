"""Verify and replay the completed IJ-SLM-1.1 Radeon follow-up captures offline."""

import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory

from benchmarks.competitive_slm.tc_v2_candidate import VULKAN_DEVICE, verify_launch
from benchmarks.ij06_sdk.wire_boundary import assemble_reply
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.gpu_handoff import HANDOFF
from evaluation.aeve.runtime import ROOT, canonical, fingerprint

from . import p0e_radeon, sdk_extension_execution as extension
from .native_diagnostics import OBSERVER_HASHES
from .portable import portable
from .sdk_adapter_holdout_report import holdout_report
from .sdk_wave_queue import verify_gpu_artifact

OUTPUT = ROOT / "evidence/IJSLM/physical-followup"
CAPTURE_GIT = "821a8ae34a113c4fe6d3f4972430e7b5eba5a3e8"
ARCHIVES = {"gpu.jsonl.gz", "native.jsonl.gz"}
HOLDOUT = "lfm3-holdout"
CANDIDATES = p0e_radeon.CANDIDATES
LOCATIONS = {
    HOLDOUT: "sdk-adapter-lfm3-holdout-physical-v1",
    **{f"p0e/{candidate}": f"p0e-radeon-v1/{candidate}" for candidate in CANDIDATES},
    **{f"sdk-extension/{split}/{candidate}": f"sdk-extension-physical-v1/{split}/{candidate}"
       for split in extension.SPLITS for candidate in CANDIDATES},
}
DERIVED = {"lfm3-paired-analysis.json", "summary.json", "manifest.json"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verified_payload(path, expected_sha):
    raw = path.read_bytes()
    require(sha256(raw).hexdigest() == expected_sha, f"portable digest mismatch: {path.name}")
    check_text(gzip.decompress(raw) if path.suffix == ".gz" else raw)
    return raw


def read_report(folder):
    raw = (folder / "report.json").read_bytes()
    check_text(raw)
    return json.loads(raw)


def file_inventory(root):
    return {path.relative_to(root).as_posix(): digest(path)
            for path in sorted(root.rglob("*")) if path.is_file() and path.relative_to(root).as_posix() not in DERIVED}


def archive_rows(folder, report, files):
    require(ARCHIVES <= files.keys(), "run is missing GPU or native archive")
    for name, expected in files.items():
        require(re.fullmatch(r"(?:gpu|native)\.jsonl\.gz|[a-f0-9]{64}\.json", name),
                "invalid portable artifact name")
        verified_payload(folder / name, expected)
    require({p.name for p in folder.iterdir()} == files.keys() | {"report.json"}, "unexpected portable files")
    verify_gpu_artifact(folder, "gpu.jsonl.gz", report["gpu"])
    rows = [json.loads(line) for line in gzip.decompress((folder / "native.jsonl.gz").read_bytes()).splitlines()]
    indexed = {row["completion_id"]: row for row in rows}
    require(bool(rows) and len(indexed) == len(rows), "missing or repeated native archive identities")
    return indexed


def runtime_identity(report, candidate, owner, prefix):
    identity = json.loads((ROOT / f"evidence/IJ07/model_identity/{candidate}.json").read_bytes())
    pinned = json.loads((ROOT / f"evidence/IJ07/model_identity/admission_strict/{candidate}/report.json").read_bytes())
    baseline_gpu = pinned["gpu"]
    asset = identity["runtime_asset"]
    model = {"official_model_id": identity["official_model_id"], "runtime_repo": asset["repo"],
             "runtime_revision": asset["revision"], "filename": asset["filename"],
             "model_sha256": asset["expected_sha256"], "quantization": "Q8_0",
             "upstream_config": identity["official_config_and_template"]}
    runtime = {"gpu": VULKAN_DEVICE, "engine": {"build": baseline_gpu["build"], "layers": baseline_gpu["layers_total"]},
               "template": {"sha256": baseline_gpu["template_sha256"]}}
    handoff = json.loads((ROOT / HANDOFF).read_bytes())["lease"]
    lease = report["gpu"]["gpu_lease"]
    harness = json.loads((ROOT / "evidence/IJSLM/sdk-causal/pilot-B/report.json").read_bytes())["harness_sha256"]
    require(report["candidate"] == candidate and report["git_sha"] == CAPTURE_GIT
            and re.fullmatch(prefix + r"[a-f0-9]{32}", report["run_id"])
            and report["handoff_sha256"] == digest(ROOT / HANDOFF)
            and report["gpu_execution"] == "PASS"
            and report["engine_sha256"] == pinned["gpu_engine"]["dll_sha256"] | OBSERVER_HASHES
            and all(lease[key] == handoff[key] for key in ("host_sha256", "gpu_physical_sha256"))
            and lease["runtime_session"] == report["run_id"] and lease["lease_owner"] == owner
            and lease["mission_id"] == "IJ-SLM-1.0"
            and re.fullmatch(r"[a-f0-9]{64}", report["private_report_sha256"]),
            "physical run identity differs from the pinned runtime")
    verify_launch(report["gpu"], runtime)
    return model, runtime, harness


def wire_observation(trial, native, used):
    provider_ids, proposals, redacted = set(), 0, 0
    require(bool(trial["wire"]), "trial lacks provider and native evidence")
    for event in trial["wire"]:
        completion = event["completion_id"]
        require(completion in native and completion not in used
                and event["source_generation"] == native[completion]
                and event["native_evidence"]["status"] == "PASS", "native completion differs or repeats")
        used.add(completion)
        request_id = event["provider_request_id"]
        require(event["trial_id"] == trial["trial_id"] and request_id not in provider_ids
                and event["http_status"] == 200
                and (trial["track"].startswith("direct_") or event["response_capture_complete"] is True),
                "provider request differs from the captured trial")
        provider_ids.add(request_id)
        for key in ("provider_request", "response"):
            original = event[key + "_sha256"]
            if sha256(event[key].encode()).hexdigest() != original:
                require(key == "provider_request" and "<REDACTED>" in event[key]
                        and re.fullmatch(r"[a-f0-9]{64}", original), "provider byte digest differs")
                redacted += 1
        reply = assemble_reply(event["content_type"], event["response"].encode())
        proposals += len(reply.calls)
    return {"requests": len(provider_ids), "proposals": proposals, "callbacks": len(trial["calls"]),
            "provider_finish": reply.finish_reason, "redacted_request_count": redacted}


def summarize_p0e(folder, candidate):
    report = read_report(folder)
    model, runtime, harness = runtime_identity(report, candidate, "p0e-development", "ijslm-p0e-")
    roster = p0e_radeon.planned()
    panel = p0e_radeon.panel
    sources = ("p0e_radeon.py", "p0e_development_preflight.py", "planning_matched_executor.py",
               "planning_matched_assessment.py", "multitool_stateful_transport.py", "multitool_stateful.py")
    require(report["version"] == panel.VERSION and report["model"] == model and report["backend"] == "vulkan"
            and report["engine_build"] == runtime["engine"]["build"] and report["sdk_version"] == "0.1.24"
            and report["sdk_harness_sha256"] == harness and report["formal_trial_attribution"] == 0
            and report["roster_sha256"] == fingerprint(roster)
            and report["sources"] == {name: digest(Path(__file__).with_name(name)) for name in sources}
            and len(report["results"]) == len(roster), "P0-E identity or roster differs")
    require(report["artifacts"].keys() == ARCHIVES, "unexpected P0-E artifacts")
    native = archive_rows(folder, report, report["artifacts"])
    used, observations = set(), []
    for slot, row in zip(roster, report["results"], strict=True):
        trace = row["trace"]
        control, profile = slot["control"], slot["profile"]
        require(all(row[key] == value for key, value in slot.items())
                and trace["trial_id"] == fingerprint([report["run_id"], slot])
                and trace["track"] == panel.PROFILES[profile] and trace["seed"] == slot["seed"]
                and trace["runtime_attribution"]["profile"] == profile and row["native_capture"] == "PASS",
                "P0-E trial differs from the frozen slot")
        assessment = panel.assess(control, trace)
        require(assessment == row["assessment"], "P0-E assessment differs from replay")
        state = row["state_readback"]
        applicable = control in ("draft_confirmed", "draft_declined")
        expected_state = {"applicable": False, "status": "NOT_RUN"}
        if applicable:
            snapshot = fingerprint(trace["after"])
            expected_state = {"applicable": True, "status": "PASS", "captured_snapshot_sha256": snapshot,
                              "reopened_snapshot_sha256": snapshot}
        require(state == expected_state, "P0-E SQLite readback receipt differs from the captured snapshot")
        wire = wire_observation(trace, native, used)
        observations.append({"control": control, "profile": profile, "trial_id": trace["trial_id"],
                             "assessment": assessment, "state_readback": state, "failure": trace["failure"],
                             "state_counts": {key: len(trace["after"][key]) for key in ("drafts", "decisions", "releases")}
                             if applicable else None, **wire})
    require(used == native.keys() and report["development_execution"] == "PASS",
            "P0-E development evidence has unlinked native completions")
    return {"candidate": candidate, "run_id": report["run_id"], "capture_verification": "PASS",
            "attempts": len(observations), "native_completions": len(native),
            "assessments": dict(Counter(row["assessment"]["status"] for row in observations)), "trials": observations}


def summarize_extension(folder, candidate, split, cohort, certificate):
    report = read_report(folder)
    model, runtime, harness = runtime_identity(report, candidate, "sdk-extension", "ijslm-sdk-extension-")
    baseline = report["baseline_runtime"]
    planned = [public["case_id"] for public, _ in cohort]
    require(report["version"] == extension.VERSION and report["suite"] == extension.sdk_extension.VERSION
            and baseline["model"] == model and baseline["backend"] == "vulkan" and baseline["gpu"] == runtime["gpu"]
            and all(baseline["engine"][key] == value for key, value in runtime["engine"].items())
            and baseline["template"]["sha256"] == runtime["template"]["sha256"]
            and report["sdk_version"] == "0.1.24" and report["harness_sha256"] == harness
            and report["dataset_manifest_sha256"] == digest(extension.sdk_extension.FOLDER / "manifest.json")
            and report["qualification_sha256"] == certificate and report["execution_sources"] == extension._source_hashes()
            and report["split"] == split and report["track"] == extension.TRACK and report["profile"] == extension.PROFILE
            and report["budgets"] == extension.BUDGET and report["system"] == extension.SYSTEM
            and report["formal_tc_v3_trials"] == 0 and report["planned_case_ids"] == planned
            and [row["case_id"] for row in report["results"]] == planned, "Extension identity or roster differs")
    files = report["portable_artifacts"]
    require(files.keys() == ARCHIVES | {row["trial_id"] + ".json" for row in report["results"]},
            "Extension trial artifacts differ from the roster")
    native = archive_rows(folder, report, files)
    used, observations = set(), []
    for (public, _), row in zip(cohort, report["results"], strict=True):
        trial_id = fingerprint([report["run_id"], candidate, split, public["case_id"]])
        trial = json.loads((folder / (trial_id + ".json")).read_bytes())
        require(trial["case_id"] == public["case_id"] and row["family"] == trial["family"] == public["family"]
                and row["trial_id"] == trial["trial_id"] == trial_id and trial["track"] == extension.TRACK
                and re.fullmatch(r"[a-f0-9]{64}", row["capture_sha256"]), "Extension trial identity differs")
        observations.append({"case_id": row["case_id"], "trial_id": trial_id, "mechanical": row["mechanical"],
                             "failure": trial["failure"], **wire_observation(trial, native, used)})
    statuses = Counter(row["mechanical"]["status"] for row in observations)
    require(statuses.keys() <= {"PASS", "FAIL", "BLOCKED"} and used == native.keys()
            and report["status"] == next(state for state in ("BLOCKED", "FAIL", "PASS") if statuses[state]),
            "Extension status differs from its captured verdicts or native linkage")
    return {"candidate": candidate, "split": split, "run_id": report["run_id"], "capture_verification": "PASS",
            "attempts": len(observations), "native_completions": len(native), "mechanical": dict(statuses),
            "portable_exact_scorer_replay": "BLOCKED", "trials": observations}


def describe(root):
    require({path.parent.relative_to(root).as_posix() for path in root.rglob("report.json")} == LOCATIONS.keys(),
            "physical run folders differ from the frozen follow-up roster")
    folder = root / HOLDOUT
    report = read_report(folder)
    require(report["git_sha"] == CAPTURE_GIT, "holdout execution source differs")
    paired = holdout_report(folder / "report.json")
    require(paired["physical_execution"] == "PASS" and paired["measured_trajectories"] == 24,
            "LFM3 holdout lacks the complete frozen physical cohort")
    native = archive_rows(folder, report, report["artifacts"])
    used = [completion for pair in paired["pairs"] for arm in ("reference", "treatment")
            for completion in pair[arm]["native_completion_ids"]]
    require(len(used) == len(native) and set(used) == native.keys(), "holdout native completions differ from replay")
    cohorts, _ = extension._frozen_partitions()
    certificate = extension._require_qualification(ROOT / "evidence/IJSLM/sdk-extension/qualification.json")
    summary = {"version": "IJ-SLM-PHYSICAL-FOLLOWUP/1.0", "git_sha": CAPTURE_GIT, "formal_trial_attribution": 0,
               "lfm3": {"run_id": paired["run_id"], "attempts": paired["measured_trajectories"],
                        "pairs": paired["measured_pairs"], "capture_verification": paired["physical_execution"],
                        "native_completions": len(native), "scoped_effect": paired["scoped_effect"]},
               "p0e": [summarize_p0e(root / "p0e" / candidate, candidate) for candidate in CANDIDATES],
               "extension": [summarize_extension(root / "sdk-extension" / split / candidate,
                                                 candidate, split, cohort, certificate)
                             for split, cohort in cohorts.items() for candidate in CANDIDATES]}
    require(len({row["run_id"] for row in [summary["lfm3"], *summary["p0e"], *summary["extension"]]}) == len(LOCATIONS),
            "physical run identity reused")
    return summary, paired


def verify_private(source, destination, experiment):
    """Compare original and portable bytes before publishing any report."""
    report = read_report(destination)
    original_file = source / "report.json"
    require(digest(original_file) == report["private_report_sha256"], "private report digest differs")
    original = json.loads(original_file.read_bytes())
    gpu = original["gpu"]
    require(gpu["counter_file"] == "vulkan-gpu.jsonl" and gpu["trace_file"] == "vulkan-generation.jsonl",
            "private evidence filenames differ from the Radeon launcher")
    is_extension = experiment.startswith("sdk-extension/")
    archive_field = "portable_artifacts" if is_extension else "artifacts"
    expected = portable(original) | {"private_report_sha256": digest(original_file),
                                     archive_field: report[archive_field]}
    require(expected == report, "portable report differs from its redacted private source")
    counters, trace = (source / gpu[key] for key in ("counter_file", "trace_file"))
    trace_digest = (original["artifacts"][trace.name] if is_extension else
                    original["private_native_trace_sha256" if experiment == HOLDOUT else "native_private_sha256"])
    require(digest(trace) == trace_digest, "private native trace digest differs")
    if is_extension:
        require(digest(counters) == original["artifacts"][counters.name], "private GPU counters digest differs")
    safe_trace = b"".join(canonical(portable(json.loads(line))) + b"\n" for line in trace.read_bytes().splitlines())
    for name, content in (("gpu.jsonl.gz", counters.read_bytes()), ("native.jsonl.gz", safe_trace)):
        raw = gzip.decompress((destination / name).read_bytes())
        check_text(raw)
        require(raw == content, "portable archive differs from its private source")
    if is_extension:
        cohort = extension._frozen_partitions()[0][original["split"]]
        for (_, graph), row in zip(cohort, original["results"], strict=True):
            trial_id = row["trial_id"]
            original_trial = source / trial_id / "trial.json"
            trial = json.loads(original_trial.read_bytes())
            safe = json.loads((destination / (trial_id + ".json")).read_bytes())
            require(digest(original_trial) == row["capture_sha256"] and portable(trial) == safe
                    and extension.score(graph, trial) == row["mechanical"], "Extension private exact scorer replay differs")


def replay_files(root):
    summary, paired = describe(root)
    files = {"summary.json": summary, "lfm3-paired-analysis.json": paired}
    return files | {"manifest.json": {"version": summary["version"], "formal_trial_attribution": 0,
                                      "files": file_inventory(root) | {
                                          name: sha256(canonical(data) + b"\n").hexdigest()
                                          for name, data in files.items()}}}


def verify(root):
    for name, data in replay_files(root).items():
        require((root / name).read_bytes() == canonical(data) + b"\n", f"published {name} differs from replay")


def publish(source, output):
    """Publish a verified redacted copy of the existing captures, with no model dispatch."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".physical-followup-", dir=output.parent) as temporary:
        staged = Path(temporary) / "evidence"
        for experiment, relative in LOCATIONS.items():
            private = source / relative
            destination = staged / experiment
            report = read_report(private / "portable")
            artifact_field = "portable_artifacts" if experiment.startswith("sdk-extension/") else "artifacts"
            destination.mkdir(parents=True)
            for name, expected in report[artifact_field].items():
                require(re.fullmatch(r"(?:gpu|native)\.jsonl\.gz|[a-f0-9]{64}\.json", name),
                        "invalid portable artifact name")
                (destination / name).write_bytes(verified_payload(private / "portable" / name, expected))
            shutil.copyfile(private / "portable" / "report.json", destination / "report.json")
            verify_private(private, destination, experiment)
        for name, data in replay_files(staged).items():
            raw = canonical(data) + b"\n"
            check_text(raw)
            (staged / name).write_bytes(raw)
        if output.exists():
            verify(output)
            require((staged / "manifest.json").read_bytes() == (output / "manifest.json").read_bytes(),
                    "existing publication differs from the verified private captures")
        else:
            staged.rename(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--publish-from", type=Path, help="private workstation follow-up runtime root")
    args = parser.parse_args()
    if args.publish_from:
        publish(args.publish_from, args.output)
    verify(args.output)
    print("Verified 24 LFM3, 42 P0-E and 15 SDK Extension Radeon captures with zero core attribution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
