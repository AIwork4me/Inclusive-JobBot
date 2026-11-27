"""Advance the remaining frozen TC-V3 candidates after the priority cohort seals."""

import argparse
from pathlib import Path

from benchmarks.root_cause.historical_replay import legacy
from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF
from evaluation.aeve.runtime import ROOT

from .mechanical_registry import REGISTRY, require_registry
from .tc_admission_evidence import verify_admission
from .tc_execution import development, records
from .tc_queue import PRIORITY, SOURCE_FILES, connect, progress, run_batches, seal_session
from .tc_v3 import HERE, verify_freeze


def candidate_preflight(candidate, assets, parent, port):
    folder = parent / "development"
    if not folder.exists():
        development(candidate, assets, folder, port)
    sealed = folder / "portable"
    verify_admission(sealed, candidate)
    return digest(sealed / "report.json")


def run(assets, port):
    root = assets / ".runtime/ij-slm-1.0"
    verify_freeze()
    require_registry()
    roster = records("roster.jsonl")
    priority = progress(root / "tc-v3-formal", [row for row in roster if row["candidate"] in PRIORITY])
    if any(row["executed"] != 1650 or row["sealed"] != 1650 for row in priority["models"].values()):
        print("BLOCKED: priority cohort must have 4,950 verified physical seals before F and G dispatch.")
        return 2
    sources = {name: digest(Path(__file__).with_name(name)) for name in SOURCE_FILES if name != "wire_boundary.py"}
    sources["wire_boundary.py"] = digest(ROOT / "benchmarks/ij06_sdk/wire_boundary.py")
    sources[Path(__file__).name] = digest(Path(__file__))
    sources["tc_admission_evidence.py"] = digest(Path(__file__).with_name("tc_admission_evidence.py"))
    blocked = False
    for candidate in ("F", "G"):
        candidate_folder = root / "tc-v3-additional" / candidate
        candidate_folder.mkdir(parents=True, exist_ok=True)
        with legacy.output_lock(candidate_folder):
            try:
                admission = candidate_preflight(candidate, assets, candidate_folder, port)
            except (OSError, ValueError, KeyError) as failure:
                blocked = True
                print(candidate, "BLOCKED", type(failure).__name__, str(failure), flush=True)
                continue
            enrollment = {"dataset_manifest_sha256": digest(HERE / "manifest.json"),
                          "registry_sha256": digest(REGISTRY), "development_manifest_sha256": admission,
                          "gpu_handoff_sha256": digest(ROOT / HANDOFF), "execution_sources": sources}
            chosen = [row for row in roster if row["candidate"] == candidate]
            with connect(candidate_folder, chosen, enrollment) as database:
                for (session,) in database.execute("SELECT DISTINCT session FROM trials WHERE session IS NOT NULL "
                                                   "AND seal_sha256 IS NULL").fetchall():
                    seal_session(candidate_folder, candidate_folder / "sessions" / session, database)
                run_batches(candidate_folder, assets, candidate, database,
                            {row["trial_id"]: row for row in chosen}, enrollment,
                            batch_size=36, limit=None, port=port)
    return 2 if blocked else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18754)
    args = parser.parse_args()
    return run(args.assets.resolve(), args.port)


if __name__ == "__main__":
    raise SystemExit(main())
