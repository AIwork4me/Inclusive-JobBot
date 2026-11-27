#!/usr/bin/env python3
"""N02R offline re-score — REPAIRED (mission IJ-NANO-1.2R RS01).

ROOT CAUSE (audited implementation @ 26445d6, sealed defective evidence in
ec5b95357e960f99): the persisted stage object is a DICTIONARY, and the
audited line

    stage, path, http_json, http_error, latency = art["stages"][-1]

iterated the dict, assigning the KEY NAMES ("stage", "path", "http",
"http_error", "latency_s"). The isinstance(http_json, dict) guard then
substituted None, so every replayed trial reached the parser as None and
was sealed PARSE_INVALID with corrupted telemetry. All 1,397 offline
re-scores of ec5b95357e960f99 were affected (588 verdict flips, all false
negatives). See evidence/IJNANO/N02RR/rs01_red_reproduction.json and
reports/IJNANO_02RR_OFFLINE_RESCORE_ROOT_CAUSE.md.

REPAIR (this file):
- stage fields are read explicitly by key via the qualified loader
  (scripts/ij_nano/n02rr_replay_lib.py);
- the artifact schema is validated BEFORE replay (hash, trial identity,
  stage schema/types/order, http/http_error consistency);
- integrity rejections raise ArtifactIntegrityError and are recorded as
  EVIDENCE_INSUFFICIENT — never converted into ordinary model failures;
- the tool refuses to append into an experiment whose results already
  contain the trial (the original silent-append design is what let 1,397
  defective rows enter a sealed experiment);
- P7S two-stage trials are replayed causally (stage-1 selection
  recomputed, stage-2 payload checked against the ACTUAL selection).

The corrected corpus re-score lives in scripts/ij_nano/n02rr_rescore.py
(analysis-replay identity, reconciliation output). This repaired tool is
kept for future experiment-filling rescores.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ij_nano"))
import n02rr_replay_lib as rl  # noqa: E402

rl.bootstrap_paths()

from n02r.controller_v2 import ControllerV2  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-run", required=True)
    ap.add_argument("--weights-root", required=True)
    ap.add_argument("--models", default="S1,S2,S3")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    src = pathlib.Path(args.source_run)
    rows = [json.loads(l) for l in
            (src / "results.jsonl").read_text(encoding="utf-8").splitlines()]

    cargs = type("A", (), {"weights_root": args.weights_root,
                           "models": args.models, "backend": "vulkan",
                           "port": 8096, "phase": "main"})()
    c = ControllerV2(cargs)
    new_id = c.identity["experiment_id"]
    if new_id == src.name:
        print("source run already has the current identity; nothing to do")
        return 0
    if not (c.run_dir / "manifest.json").exists():
        c.run_dir.mkdir(parents=True, exist_ok=True)
        (c.run_dir / "manifest.json").write_text(
            json.dumps({"identity": c.identity, "created_utc": "rescore"},
                       indent=1, ensure_ascii=False), encoding="utf-8")
    (c.run_dir / "responses").mkdir(parents=True, exist_ok=True)

    # fail-closed: never append duplicates into existing results
    existing = set()
    if c.results_path.exists():
        for line in c.results_path.read_text(encoding="utf-8").splitlines():
            try:
                existing.add(json.loads(line)["trial_id"])
            except Exception:
                continue

    engine = rl.ReplayEngine(c)
    written = rejected = skipped = 0
    rejects: list[dict] = []
    with open(c.results_path, "ab") as out:
        for r in rows:
            tid = c._trial_id(r["model"], r["arm"], r["task_id"], r["budget"])
            if tid in existing:
                skipped += 1
                continue
            try:
                rec = engine.replay({**r, "trial_id": tid,
                                     "experiment_id": new_id},
                                    source_row=r)
            except rl.ArtifactIntegrityError as e:
                # evidence-integrity failure: separately classified, NEVER
                # an ordinary model failure
                rejects.append({"source_trial": r["trial_id"], "code": e.code,
                                "detail": e.detail})
                rejected += 1
                continue
            record = {
                "trial_id": tid, "experiment_id": new_id,
                "model": r["model"], "arm": r["arm"],
                "task_id": r["task_id"], "family": r["family"],
                "lang": r["lang"], "budget": r["budget"],
                "http_ok": rec["http_ok"], "http_error": rec["http_error"],
                "telemetry": rec["telemetry"],
                "telemetry_totals": {
                    k: v for k, v in rec["telemetry_totals"].items()
                    if k != "per_stage"},
                "parser": rec["parser"],
                "semantic_correct": rec["semantic_correct"],
                "tool_correct": rec["tool_correct"],
                "args_correct": rec["args_correct"],
                "reasons": rec["reasons"],
                "failure_class": rl.classify_failure(rec),
                "response_artifact": r["response_artifact"],
                "response_artifact_sha256": r["response_artifact_sha256"],
                "execution": {"kind": "offline_rescore",
                              "source_experiment": src.name,
                              "source_trial_id": r["trial_id"],
                              "source_stage_latency_s":
                                  rec["telemetry"]["latency_s"],
                              "loader": "n02rr_replay_lib (key-based, "
                                        "schema-validated)",
                              "physical": False},
            }
            out.write((json.dumps(record, ensure_ascii=False) + "\n")
                      .encode("utf-8"))
            out.flush()
            written += 1
            existing.add(tid)
    manifest = json.loads((c.run_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["rescore"] = {
        "source_experiment": src.name,
        "source_trials": len(rows), "rescored": written,
        "skipped_already_present": skipped,
        "evidence_integrity_rejects": rejected,
        "rejects": rejects,
        "loader": "n02rr_replay_lib key-based schema-validated (IJ-NANO-1.2R "
                  "RS01 repair; the audited positional-unpacking defect is "
                  "reproduced red in evidence/IJNANO/N02RR/"
                  "rs01_red_reproduction.json)"}
    (c.run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"source": src.name, "new_experiment": new_id,
                      "rescored": written, "skipped": skipped,
                      "integrity_rejects": rejected}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
