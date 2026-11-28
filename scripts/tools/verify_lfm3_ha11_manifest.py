"""Write or check portable LFM3-HA-1.1 evidence identities and coverage."""

import argparse
from collections import Counter
import gzip
from hashlib import file_digest
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJSLM/lfm3-ha-1.1"
MANIFEST = EVIDENCE / "manifest.json"


def digest(path):
    with path.open("rb") as handle:
        return file_digest(handle, "sha256").hexdigest()


def read(name):
    return json.loads((EVIDENCE / name).read_bytes())


def verify_paired_archive(report):
    archive = report.get("paired_archive")
    if archive is None:
        return False
    name = archive["filename"]
    if Path(name).name != name or digest(EVIDENCE / name) != archive["sha256"]:
        raise ValueError("Portable paired archive digest differs")
    with gzip.open(EVIDENCE / name, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    if (len(rows) != report["executed"] or len(rows) != archive["rows"]
            or len({row["slot_id"] for row in rows}) != len(rows)):
        raise ValueError("Portable matched archive coverage differs")
    seals = {seal["run_id"]: seal for seal in report["batch_seals"]}
    by_track = report["suite"] != "transfer"
    arms = Counter(f'{row["weight"]}/{row["track"] if by_track else row["profile"]}' for row in rows)
    if (set(arms) - report["arms"].keys() or any(arms[key] != arm["observed"] for key, arm in report["arms"].items())
            or any(row["run_id"] not in seals
                   or any(seals[row["run_id"]].get(key) != row[key] for key in ("git_sha", "seal_sha256"))
                   or seals[row["run_id"]].get("weight", row["weight"]) != row["weight"] for row in rows)):
        raise ValueError("Portable matched archive differs from its sealed arms")
    return True


def verify_author_recipe(state):
    audit = read("author-recipe-audit.json")
    if (audit["historical_task_runs_verified"] != state["m8_historical_task_runs_verified"]
            or audit["core_trial_attribution"] != 0 or audit["physical_trials"] != 0
            or audit["reward"]["static_override_trace"] != state["m8_public_recipe_static_trace"]):
        raise ValueError("Author recipe evidence differs from its static-only disposition")
    for suite, count in (("traj2envs", state["m8_pinned_recipe_repo2rlenvs_ids"]),
                         ("smoldataenvs", state["m8_historical_snapshot_smoldataenvs_candidate_ids"])):
        cohort = audit["recipe_rosters"][suite]
        prefix = cohort["scanned_prefix"]
        ids = [row["task_id"] for row in prefix]
        eligible = [row["task_id"] for row in prefix if not cohort["difficulty_filter"]
                    or row["difficulty"] in cohort["difficulty_filter"]]
        if (len(eligible) != count or eligible != cohort["selected_task_ids"] or ids != sorted(set(ids))
                or cohort["historical_run_roster_binding"] != "BLOCKED"):
            raise ValueError("Author recipe roster order, difficulty cut or historical status differs")


def verify_runtime_followups(state):
    shortconv = read("shortconv-state-panel.json")
    cells = shortconv["cells"]
    modes = [mode for cell in cells.values() for mode in cell["modes"].values()]
    observed = sum(len(mode["states"]) for mode in modes)
    if (len(cells) != state["m3_shortconv_physical_cells"] or len(modes) != len(cells) * 2
            or observed != state["m3_shortconv_snapshots"] or observed != shortconv["local_native_snapshots_replayed"]
            or shortconv["status"] != state["m3_shortconv_state_inspection"] or shortconv["core_trial_attribution"] != 0
            or any(cell["gpu_execution"] != "PASS" for cell in cells.values())):
        raise ValueError("ShortConv replay coverage or physical identity differs from mission state")
    candidate = read("native-routing-candidate-controls.json")
    build = read("native-routing-candidate-build.json")
    if (candidate["cpu_http_controls"] != state["m3_native_id_candidate_cpu_http"]
            or candidate["radeon_inference"] != state["m3_native_id_candidate_radeon"]
            or candidate["backend"] != "CPU" or candidate["core_trial_attribution"] != 0
            or candidate["binary_sha256"] != build["binary_sha256"]
            or candidate["candidate_patch_sha256"] != build["candidate_patch_sha256"]
            or len(candidate["controls"]) != 22
            or any(control["status"] != "PASS" for control in candidate["controls"].values())):
        raise ValueError("Native route CPU controls differ from the pinned candidate")


def build():
    state = json.loads((ROOT / "MISSION_STATE.json").read_bytes())["lfm3_ha_1_1"]
    action = read("action-phase-retest.json")
    extension = read("extension-radeon.json")
    cache = read("cache-factorial.json")
    transport = read("tc-transport-admission.json")
    merge = read("high-precision-merge-artifacts.json")
    transfer = json.loads((ROOT / state["m4_evidence"]).read_bytes())
    compatibility = json.loads((ROOT / state["m5_evidence"]).read_bytes()) if state.get("m5_evidence") else None
    verify_author_recipe(state)
    verify_runtime_followups(state)
    verify_paired_archive(transfer)
    if compatibility is not None:
        has_archive = verify_paired_archive(compatibility)
        if compatibility["coverage"] != state["m5_status"]:
            raise ValueError("TC-V3 coverage status and mission state differ")
        if compatibility["coverage"] == "PASS" and (
                not has_archive or len(compatibility["batch_seals"]) != 200
                or len(compatibility["arms"]) != 16 or any(
                    arm["observed"] != arm["planned"] for arm in compatibility["arms"].values())):
            raise ValueError("Completed TC-V3 panel needs all 200 seals, 16 arms and its paired archive")
        if compatibility["coverage"] == "PASS":
            scoped = Counter()
            for arm in compatibility["arms"].values():
                scoped.update(arm["metric_counts"]["SCOPED_COMPLETION"])
            if dict(scoped) != state["m5_scoped_outcomes"]:
                raise ValueError("TC-V3 scoped dispositions differ from mission state")
    if (len(action["results"]) != state["m1_physical_retest_trials"]
            or len(extension["results"]) != 5 or len(cache["cells"]) != state["m3_cache_cells"]
            or len(transport["results"]) != state["m5_transport_diagnostic_trials"]
            or len(merge["arms"]) != 3 or merge["DX-M2"] != "NOT_RUN"
            or transfer["executed"] != state["m4_executed"] or transfer["planned"] != state["m4_planned"]
            or (compatibility is not None and (compatibility["executed"] != state["m5_executed"]
                                               or compatibility["planned"] != state["m5_planned"]
                                               or compatibility["core_attribution"] != 0))
            or cache["portable_numeric_archive_sha256"] != digest(EVIDENCE / "cache-factorial.json.gz")):
        raise ValueError("Portable LFM3-HA evidence counts and state differ")
    core = ("formal_core_trials", "core_trial_attribution", "core_attribution")
    if any(payload[key] != 0 for payload in (action, extension, cache, transport, merge, transfer)
           for key in core if key in payload):
        raise ValueError("Supplemental evidence cannot change the frozen core denominator")
    files = {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(EVIDENCE.iterdir())
             if path.is_file() and path != MANIFEST}
    return {
        "version": "LFM3-HA-EVIDENCE-MANIFEST/1.1", "reviewed_baseline": state["reviewed_baseline"],
        "files": files, "original_core_sealed": state["original_core_executed"],
        "original_core_denominator": state["original_core_required"], "gemma_sealed": state["gemma_executed"],
        "transfer_sealed": state["m4_executed"], "transfer_planned": state["m4_planned"],
        "tc_compatibility_sealed": state["m5_executed"], "tc_compatibility_planned": state["m5_planned"],
        "core_trial_attribution": 0, "selection": state["selection"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    document = build()
    payload = (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if args.write:
        MANIFEST.write_bytes(payload)
    elif MANIFEST.read_bytes() != payload:
        raise ValueError("Portable LFM3-HA manifest differs")
    print("PASS", len(document["files"]), "portable LFM3-HA-1.1 evidence digests")


if __name__ == "__main__":
    main()
