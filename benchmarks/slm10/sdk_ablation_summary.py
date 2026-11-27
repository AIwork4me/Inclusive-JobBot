"""Replay physical SDK ablation comparisons from independently sealed artifacts."""

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import shutil

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import canonical

from .sdk_causal_metrics import analyze
from .sdk_causal_report import OUTPUT
from .tc_dashboard import objects, percentile
from .tc_v3 import HERE

RESULT = OUTPUT / "ablation-summary.json"
FULL = ("A0", "SDK_CONTROL", "A5", "GUARD")
REPLAY = ("A1", "A2", "A3", "A4")
COVERAGE = OUTPUT / "ablation-coverage.json"


def check_report(folder):
    raw = (folder / "report.json").read_bytes()
    check_text(raw)
    report = json.loads(raw)
    if report["formal_trials"] != 0:
        raise ValueError("diagnostic and formal results must have distinct identities")
    for name, expected in report["artifacts"].items():
        if Path(name).name != name or digest(folder / name) != expected:
            raise ValueError("diagnostic artifact digest mismatch")
        check_text(gzip.decompress((folder / name).read_bytes()))
    return report


def physical(arm):
    capture = arm.get("capture")
    if capture is None:
        return False
    wire = capture.get("wire", [capture])
    return any(event.get("native_evidence", {}).get("status") == "PASS" for event in wire)


def summarize(root, coverage=None):
    published = {}
    results = defaultdict(list)
    paired = defaultdict(Counter)
    metrics = {r["case_id"]: r for r in objects(HERE / "development-oracle.jsonl")}
    cases_seen = set()
    for path in sorted(root.glob("*/report.json")):
        report = check_report(path.parent)
        if "results" not in report:
            continue
        if report["gpu_execution"] != "PASS":
            raise ValueError("ablation report lacks scoped GPU proof")
        model = report["candidate"]
        published[path.parent.name] = digest(path)
        for case in report["results"]:
            case_id = case["case_id"]
            if (model, case_id) in cases_seen:
                raise ValueError("duplicate ablation case for same physical candidate")
            cases_seen.add((model, case_id))
            roster = {entry["arm"]: entry for entry in case["arms"]}
            if set(roster) != set((*FULL, *REPLAY)) or len(case["arms"]) != len(roster):
                raise ValueError("ablation report has an incomplete arm roster")
            original = roster["A1"]
            if "source_completion_id" in original:
                control = roster["SDK_CONTROL"]["capture"]
                source, = [event for event in control["wire"] if event.get("completion_id") == original["source_completion_id"]]
                if (source["provider_request_sha256"] != original["source_request_sha256"]
                        or source["response_sha256"] != original["source_response_sha256"]
                        or original["capture"]["provider_request_sha256"] != original["source_request_sha256"]):
                    raise ValueError("A1 no longer binds to its exact control request")
                source_native = source.get("source_generation", {}).get("pre_parser_bytes_hex")
                replay_native = original["capture"].get("source_generation", {}).get("pre_parser_bytes_hex")
                if source_native is None or replay_native is None:
                    key = "native_evidence_missing"
                else:
                    key = "same_native_generation" if source_native == replay_native else "different_native_generation"
                paired[model, "A1"][key] += 1
            for arm, entry in roster.items():
                row = {"status": entry.get("status", "BLOCKED"), "physical": physical(entry)}
                captured = entry.get("capture")
                if coverage is not None:
                    key = (model, case_id, arm)
                    if key not in coverage:
                        raise ValueError("diagnostic observation outside the registered development plan")
                    coverage[key].update({"physical_capture": "PASS" if row["physical"] else (
                        "BLOCKED" if captured is not None else row["status"]),
                        "run_id": report["run_id"], "report_sha256": published[path.parent.name],
                        "reason": entry.get("reason", entry.get("applicability"))})
                if arm in FULL and captured is not None:
                    observations = analyze(captured, metrics[case_id], model, {})
                    row.update(wall_ms=entry.get("wall_ms", captured.get("wall_ms")),
                               buffered_first_text_ms=captured.get("sdk_first_visible_text_ms_buffered"),
                               adapter_ms=sum(captured["request_adapter_ms"]) if "request_adapter_ms" in captured else None,
                               callback_ms=sum(captured["callback_ms"]) if "callback_ms" in captured else None,
                               guarded=len(captured.get("guard_protected_callbacks", ())),
                               proposals=len(observations["actions"]),
                               final=observations["metrics"]["final_answer"], requests=observations["model_requests"])
                elif arm in REPLAY and "next_finish_reason" in entry:
                    row.update(next_finish_reason=entry["next_finish_reason"], next_call_count=entry["next_call_count"],
                               exact_answer=entry["next_answer"]["final_answer"])
                    if arm != "A1" and all("next_finish_reason" in t for t in (original, entry)):
                        if entry["source_request_sha256"] != original["source_request_sha256"]:
                            raise ValueError("physical ablation differs in matched request source")
                        paired[model, arm][original["next_finish_reason"] + "/" + entry["next_finish_reason"]] += 1
                results[model, arm].append(row)
    cells = {}
    for (model, arm), rows in sorted(results.items()):
        cell = {
            "planned_cells": len(rows), "physical_observations": sum(row["physical"] for row in rows),
            "next_stop": sum(row.get("next_finish_reason") == "stop" for row in rows),
            "exact_final": sum(row.get("final") == "PASS" or row.get("exact_answer") == "PASS" for row in rows),
            "protected_callbacks": sum(row.get("guarded", 0) for row in rows),
        }
        if arm in FULL:
            for name in ("wall_ms", "buffered_first_text_ms", "adapter_ms", "callback_ms", "requests"):
                cell[name] = percentile([row[name] for row in rows if row.get(name) is not None])
        if (model, arm) in paired:
            name = "source_generation_replay" if arm == "A1" else "paired_finish_transitions_from_A1"
            cell[name] = dict(paired[model, arm])
        cells[model + "/" + arm] = cell
    return {"version": "IJ-SLM-SDK-ABLATION-SUMMARY/1.0", "formal_trials": 0, "paired_dev_cases": len(cases_seen),
            "physical_arm_observations": sum(r["physical_observations"] for r in cells.values()),
            "requested_six_arm_observations": sum(r["physical_observations"] for key, r in cells.items()
                                                  if key.split("/")[1] not in ("SDK_CONTROL", "GUARD")),
            "models_and_arms": cells, "sources": published,
            "scope": "full-task A0, SDK control, A5 and guard; matched next-decision A1-A4; held-out retest NOT_RUN"}


def import_waves(source):
    from .sdk_wave_queue import expected_wave, report_path, verified_run, verify_seal

    for wave in sorted(source.iterdir()):
        if not wave.is_dir() or wave.name.startswith("."):
            continue
        candidate, number = wave.name.split("-")
        expected = expected_wave(candidate, int(number))
        legacy = report_path(wave)
        if (wave / "wave-seal.json").is_file():
            reports = verify_seal(wave, expected)
        elif legacy.is_file():
            verified_run(legacy.parent, expected, expected["cases"])
            reports = [legacy.parent]
        else:
            continue
        for folder in reports:
            report = check_report(folder)
            fragment = "-" + folder.parent.name if folder.parent != wave else ""
            target = OUTPUT / ("wave-" + wave.name + fragment)
            target.mkdir(exist_ok=True)
            for name in ("report.json", *report["artifacts"]):
                new = folder / name
                old = target / name
                if old.exists():
                    if digest(old) != digest(new):
                        raise ValueError("diagnostic publication differs from sealed runtime copy")
                else:
                    shutil.copyfile(new, old)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--waves", type=Path)
    args = parser.parse_args()
    if args.waves:
        if not args.write:
            parser.error("--waves requires --write")
        import_waves(args.waves)
    profile_path = HERE.parent / "sdk-causal-experiment.json"
    profile = json.loads(profile_path.read_bytes())
    coverage = {(model, case, arm): {"candidate": model, "case_id": case, "arm": arm,
                "kind": "full-task" if arm in FULL else "next-decision", "physical_capture": "NOT_RUN"}
                for model in profile["models"] for case in profile["development_case_ids"] for arm in profile["arms"]}
    report = summarize(OUTPUT, coverage)
    coverage_data = {"version": "IJ-SLM-SDK-CAUSAL-COVERAGE/1.0", "formal_trials": 0,
                     "profile_sha256": digest(profile_path), "trials": list(coverage.values())}
    coverage_payload = canonical(coverage_data) + b"\n"
    payload = canonical(report) + b"\n"
    if args.write:
        RESULT.write_bytes(payload)
        COVERAGE.write_bytes(coverage_payload)
    elif RESULT.read_bytes() != payload or COVERAGE.read_bytes() != coverage_payload:
        raise ValueError("published ablation summary differs from sealed run replay")
    path = OUTPUT / "manifest.json"
    files = {artifact.relative_to(OUTPUT).as_posix(): digest(artifact)
             for artifact in sorted(OUTPUT.rglob("*")) if artifact.is_file() and artifact != path}
    offline = json.loads((HERE.parent / "sdk-causal-matrices.json").read_bytes())
    manifest = canonical({"files": files, "formal_trials_reassessed": offline["attempts"],
                          "development_in_core": 0}) + b"\n"
    if args.write:
        path.write_bytes(manifest)
    elif path.read_bytes() != manifest:
        raise ValueError("causal evidence manifest differs from the published artifacts")
    print(report["paired_dev_cases"], "development case/model cells;",
          report["requested_six_arm_observations"], "physical A0-A5 observations;",
          report["physical_arm_observations"], "physical observations including controls")


if __name__ == "__main__":
    main()
