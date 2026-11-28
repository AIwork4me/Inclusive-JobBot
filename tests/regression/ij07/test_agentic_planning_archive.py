from hashlib import sha256
import json

import pytest

from benchmarks.agentic_planning_v1.freeze import FROZEN, encode, verify
from scripts.tools.archive_ij07_planning import analyze, archive


def sha(value):
    return sha256(value).hexdigest()


def make_run(directory, targets, *, scores, panel="primary"):
    first_seeds = [41909] if panel == "primary" else [41909, 81563, 170003]
    trials = [{"trial_id": f"{case}-{track}-{repeat:02}", "case_id": case, "track": track,
               "repeat_index": repeat, "seed": seed}
              for case, track in targets for repeat, seed in enumerate(first_seeds, 1)]
    config = {"manifest": verify(FROZEN), "panel": panel, "selection": "diagnostic", "trials": trials,
              "backend": "fixture", "model": {"alias": "fixture"}, "git": {"commit": None}}
    run = {"run_id": "software-fixture", "configuration": config, "fingerprint": sha(encode(config)),
           "sessions": [{"backend": "fixture"}]}
    directory.mkdir()
    (directory / "run.json").write_bytes(encode(run))
    (directory / "attempts").mkdir()
    (directory / "cases").mkdir()
    paths = []
    for trial, status in zip(trials, scores):
        code = "INITIAL_PLAN_REJECTED" if trial["track"] == "P" else "PROPOSAL_REJECTED"
        findings = [{"code": code}] if status == "FAIL" else []
        journal = f"attempts/{trial['trial_id']}.{'a'*32}.jsonl"
        head = {"kind": "attempt", "trial": trial, "run_id": run["run_id"],
                "configuration_sha256": run["fingerprint"], "server_session": 1}
        journal_bytes = encode(head) + encode({"kind": "terminal", "status": status, "findings": findings})
        (directory / journal).write_bytes(journal_bytes)
        row = {"run_id": run["run_id"], "run_fingerprint": run["fingerprint"], "server_session": 1, "trial": trial,
               "status": status, "journal": journal, "journal_sha256": sha(journal_bytes), "findings": findings,
               "case_id": trial["case_id"], "track": trial["track"], "seed": trial["seed"], "stream": False,
               "records": [], "metrics": {"final_verified_goal_satisfaction": status == "PASS"}, "errors": [],
               "attribution": {"host": 0, "sop": 0}, "safety": {}}
        path = directory / f"cases/{trial['trial_id']}.json"
        path.write_bytes(encode({**row, "artifact_sha256": sha(encode(row))}))
        paths.append(directory / journal)
    return paths


def test_level_and_track_report_preserves_selected_and_suite_denominators(tmp_path):
    source = tmp_path / "fixture"
    make_run(source, [("AP1-L2-001", "A"), ("AP1-L2-001", "P"), ("AP1-L2-002", "A"), ("AP1-L2-002", "P")],
             scores=["PASS", "FAIL", "BLOCKED"])
    report = analyze(source)
    assert report["overall"]["counts"] == {"PASS": 1, "FAIL": 1, "BLOCKED": 1, "NOT_RUN": 1}
    assert report["coverage"] == {"nominal_suite_trials": 1600, "scheduled_trials": 4, "suite_trials_outside_run": 1596}
    acting = report["levels"]["A"]["L2"]
    assert acting["nominal_suite_cases"] == 100 and acting["selected_cases"] == 2
    assert acting["first_pass"]["verified_success_per_planned"] == 0.5
    assert acting["first_pass"]["success_bounds_including_unknown"] == [0.5, 1.0]
    assert acting["first_pass"]["assessable_n"] == 1
    assert report["levels"]["P"]["L2"]["failure_indicators"]["INITIAL_PLAN_REJECTED"] == 1
    assert report["levels"]["A"]["L7"]["evidence_status"] == "NOT_RUN"
    assert acting["qualification"]["status"] == "NOT_RUN"
    assert report["evidence"]["physical_execution_status"] == "BLOCKED"


def test_archive_copies_exact_files_and_rejects_tampered_journal(tmp_path):
    source, output = tmp_path / "fixture", tmp_path / "archive"
    journals = make_run(source, [("AP1-L2-001", "A")], scores=["FAIL"])
    report = archive(source, output)
    assert report["overall"]["counts"]["FAIL"] == 1
    archived = output / journals[0].relative_to(source)
    assert archived.read_bytes() == journals[0].read_bytes()
    index = json.loads((output / "archive_manifest.json").read_bytes())
    assert index["sha256"][archived.relative_to(output).as_posix()] == sha(archived.read_bytes())
    assert analyze(output)["overall"]["counts"] == report["overall"]["counts"]
    with archived.open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(ValueError, match="journal digest|archive digest"):
        analyze(output)


def test_repeat_panel_counts_first_any_all_and_unknown_separately(tmp_path):
    source = tmp_path / "repeat-fixture"
    selected = json.loads((FROZEN / "datasets/repeat_panel.json").read_bytes())["cases"][0]
    make_run(source, [(selected["case_id"], "A")], scores=["FAIL", "PASS"], panel="repeat")
    level = analyze(source)["levels"]["A"][selected["level"]]
    assert level["reliability"]["first_pass"]["verified_success_per_planned"] == 0
    assert level["reliability"]["pass_at_three"]["verified_success_per_planned"] == 1
    assert level["reliability"]["pass_all_three"]["verified_success_per_planned"] == 0
    assert level["reliability"]["transitions"] == {"FAIL->PASS": 1, "PASS->NOT_RUN": 1}
