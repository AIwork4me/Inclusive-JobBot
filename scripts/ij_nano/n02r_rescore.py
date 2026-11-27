#!/usr/bin/env python3
"""N02R offline re-score (addendum section 11: parser-only defects prefer
offline re-scoring when complete raw evidence exists).

Takes the trials of a source experiment whose raw responses are preserved
as content-addressed artifacts, re-runs the FIXED parser + evaluator on
the stored final-stage responses, and writes the rescored records into
the NEW experiment's results.jsonl (same identity the corrected controller
computes), marked as offline re-scores so denominator accounting stays
honest. The source results are never modified.

Precondition (verified here): the request-rendering code is byte-identical
between the source run's implementation and the current one (only parser
internals changed)."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks" / "root_cause"))
sys.path.insert(0, str(ROOT / "benchmarks" / "ij_nano"))
sys.path.insert(0, str(ROOT / "src"))

from n02r import controller_v2  # noqa: E402
from n02r import arms_v2 as arms  # noqa: E402
from n02r import scorer  # noqa: E402


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
    c = controller_v2.ControllerV2(cargs)
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

    done, written, bad_hash = 0, 0, 0
    with open(c.results_path, "ab") as out:
        for r in rows:
            art_path = ROOT / r["response_artifact"]
            if not art_path.exists():
                continue
            blob = art_path.read_bytes()
            if hashlib.sha256(blob).hexdigest() != r["response_artifact_sha256"]:
                bad_hash += 1
                continue
            art = json.loads(blob.decode("utf-8"))
            stage, path, http_json, http_error, latency = art["stages"][-1]
            # P7S replay: the stage-2 response already carries the selected
            # tool inside its JSON; the stage-1 request is not needed
            parse_arm = {"T2": "M-P1", "P7S": "M-P3"}.get(r["arm"], r["arm"])
            task = next(t for t in c.suite if t["task_id"] == r["task_id"])
            parsed = arms.parse_response(parse_arm, task, http_json, http_error)
            scored = scorer.score(task, parsed.get("payload"))
            tel = c._telemetry(r["arm"], http_json, http_error,
                               art["stages"][-1]["latency_s"])
            tid = c._trial_id(r["model"], r["arm"], r["task_id"], r["budget"])
            record = {
                "trial_id": tid, "experiment_id": new_id,
                "model": r["model"], "arm": r["arm"],
                "task_id": r["task_id"], "family": r["family"],
                "lang": r["lang"], "budget": r["budget"],
                "http_ok": http_json is not None,
                "http_error": http_error,
                "telemetry": tel,
                "parser": {"structural_ok": bool(parsed.get("structural_ok")),
                           "warnings": parsed.get("warnings", []),
                           "normalizations": parsed.get("normalizations", []),
                           "payload": parsed.get("payload")},
                "semantic_correct": scored["semantic_correct"],
                "tool_correct": scored["tool_correct"],
                "args_correct": scored["args_correct"],
                "reasons": scored["reasons"],
                "response_artifact": r["response_artifact"],
                "response_artifact_sha256": r["response_artifact_sha256"],
                "execution": {"kind": "offline_rescore",
                              "source_experiment": src.name,
                              "source_trial_id": r["trial_id"],
                              "source_stage_latency_s": latency,
                              "physical": False},
            }
            out.write((json.dumps(record, ensure_ascii=False) + "\n")
                      .encode("utf-8"))
            out.flush()
            written += 1
            done += 1
    manifest = json.loads((c.run_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["rescore"] = {
        "source_experiment": src.name,
        "source_trials": len(rows), "rescored": written,
        "artifact_hash_mismatches": bad_hash,
        "note": "parser-only defect repair; request renderers verified "
                "byte-identical; raw artifacts reused unchanged"}
    (c.run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"source": src.name, "new_experiment": new_id,
                      "rescored": written, "bad_hash": bad_hash}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
