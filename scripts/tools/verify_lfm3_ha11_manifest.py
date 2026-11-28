"""Write or check portable LFM3-HA-1.1 evidence identities and coverage."""

import argparse
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
        return
    name = archive["filename"]
    if Path(name).name != name or digest(EVIDENCE / name) != archive["sha256"]:
        raise ValueError("Portable paired archive digest differs")
    with gzip.open(EVIDENCE / name, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    if (len(rows) != report["executed"] or len(rows) != archive["rows"]
            or len({row["slot_id"] for row in rows}) != len(rows)):
        raise ValueError("Portable matched archive coverage differs")


def build():
    state = json.loads((ROOT / "MISSION_STATE.json").read_bytes())["lfm3_ha_1_1"]
    action = read("action-phase-retest.json")
    extension = read("extension-radeon.json")
    cache = read("cache-factorial.json")
    transport = read("tc-transport-admission.json")
    merge = read("high-precision-merge-artifacts.json")
    transfer = json.loads((ROOT / state["m4_evidence"]).read_bytes())
    compatibility = json.loads((ROOT / state["m5_evidence"]).read_bytes()) if state.get("m5_evidence") else None
    verify_paired_archive(transfer)
    if compatibility is not None:
        verify_paired_archive(compatibility)
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
