#!/usr/bin/env python3
"""N02RR corrected full-corpus re-score + row-level reconciliation (mission
IJ-NANO-1.2R sections 5-6).

Re-scores ALL 2,184 logical slots of ec5b95357e960f99 from their
hash-verified artifacts with the corrected key-based loader (n02rr_replay_lib):

- the 1,397 defective offline-rescored rows are repaired;
- the 787 physically executed rows are re-scored as an independent
  consistency verification (corrected replay MUST reproduce their sealed
  verdicts exactly; any divergence is escalated, never averaged away);

Original experiments 36bfed1d55a9987b / 7a1b9d7d160202d8 / ec5b95357e960f99
are preserved byte-for-byte (read-only). The replay runs under a NEW
immutable analysis identity recorded in evidence/IJNANO/N02RR/manifest.json.

Outputs:
  evidence/IJNANO/N02RR/trial_reconciliation.jsonl   (one row per trial)
  evidence/IJNANO/N02RR/manifest.json                (replay identity+seal)

No GPU is used: recoverable offline scoring errors are repaired offline
(mission: do not spend GPU time on recoverable scoring errors).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]
                       / "scripts" / "ij_nano"))
import n02rr_replay_lib as rl  # noqa: E402

rl.bootstrap_paths()

from n02r.controller_v2 import ControllerV2  # noqa: E402

RUNS = rl.ROOT / "evidence" / "IJNANO" / "N02R" / "runs"
SRC_RUN = RUNS / "7a1b9d7d160202d8"
DST_RUN = RUNS / "ec5b95357e960f99"
OUT_DIR = rl.ROOT / "evidence" / "IJNANO" / "N02RR"


def default_weights_root() -> str:
    """IJSDK sibling worktree (read-only weights host); overridable via
    the IJNANO_WEIGHTS_ROOT environment variable."""
    import os
    return os.environ.get("IJNANO_WEIGHTS_ROOT",
                          str(rl.ROOT.parent / "IJSDK"))


def tel_summary(tel: dict) -> dict:
    if not isinstance(tel, dict):
        return {"invalid": repr(tel)[:80]}
    usage = tel.get("usage")
    content = tel.get("content")
    return {
        "latency_s": tel.get("latency_s"),
        "usage": usage if isinstance(usage, dict) else repr(usage)[:80],
        "finish_reason": tel.get("finish_reason"),
        "truncated": tel.get("truncated"),
        "content_chars": len(content) if isinstance(content, str) else None,
        "tool_calls_n": len(tel["tool_calls"])
        if isinstance(tel.get("tool_calls"), list) else None,
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    cargs = type("A", (), {"weights_root": default_weights_root(),
                           "models": "S1,S2,S3",
                           "backend": "vulkan", "port": 8096,
                           "phase": "main"})()
    c = ControllerV2(cargs)
    dst_man = json.loads((DST_RUN / "manifest.json").read_text(encoding="utf-8"))
    if json.dumps(c.identity, sort_keys=True) != json.dumps(
            dst_man["identity"], sort_keys=True):
        print("REFUSED: sealed modules no longer reproduce ec5b95357e960f99")
        return 3
    src_man = json.loads((SRC_RUN / "manifest.json").read_text(encoding="utf-8"))

    engine = rl.ReplayEngine(c)
    src_rows = {r["trial_id"]: r for r in (
        json.loads(l) for l in (SRC_RUN / "results.jsonl")
        .read_text(encoding="utf-8").splitlines())}
    dst_rows = [json.loads(l) for l in (DST_RUN / "results.jsonl")
                .read_text(encoding="utf-8").splitlines()]

    # immutable replay identity: binds this replay implementation to the
    # sealed inputs it reads (any edit to either side forks the identity)
    def _sha(p: pathlib.Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    replay_spec = {
        "mission": "IJ-NANO-1.2R",
        "replay_lib_sha256": _sha(rl.ROOT / "scripts" / "ij_nano"
                                  / "n02rr_replay_lib.py"),
        "rescore_script_sha256": _sha(pathlib.Path(__file__)),
        "sealed_inputs": {
            "source_experiment": {
                "id": src_man["identity"]["experiment_id"],
                "identity_sha256": hashlib.sha256(json.dumps(
                    src_man["identity"], sort_keys=True,
                    ensure_ascii=False).encode()).hexdigest(),
                "results_sha256": _sha(SRC_RUN / "results.jsonl"),
                "seal": json.loads((SRC_RUN / "seal.json")
                                   .read_text(encoding="utf-8"))},
            "destination_experiment": {
                "id": dst_man["identity"]["experiment_id"],
                "identity_sha256": hashlib.sha256(json.dumps(
                    dst_man["identity"], sort_keys=True,
                    ensure_ascii=False).encode()).hexdigest(),
                "results_sha256": _sha(DST_RUN / "results.jsonl"),
                "seal": json.loads((DST_RUN / "seal.json")
                                   .read_text(encoding="utf-8"))},
        },
        "runtime_modules_sha256": {
            rel: _sha(rl.ROOT / rel) for rel in (
                "benchmarks/ij_nano/n02r/controller_v2.py",
                "benchmarks/ij_nano/n02r/arms_v2.py",
                "benchmarks/ij_nano/n02r/tasks.py",
                "benchmarks/ij_nano/n02r/scorer.py",
                "src/nanoagent/eval/contracts.py",
                "src/nanoagent/eval/comparators.py",
                "src/nanoagent/eval/units.py")},
    }
    replay_id = hashlib.sha256(json.dumps(replay_spec, sort_keys=True,
                                          ensure_ascii=False)
                               .encode()).hexdigest()[:16]

    out_path = OUT_DIR / "trial_reconciliation.jsonl"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    physical_consistency = {"match": 0, "divergent": 0}
    rescore_source_agreement = {"match": 0, "divergent": 0}
    integrity_rejects: list[dict] = []

    with out_path.open("w", encoding="utf-8") as out:
        for row in dst_rows:
            ex = row.get("execution", {})
            kind = ex.get("kind", "physical")
            srow = src_rows.get(ex.get("source_trial_id")) \
                if kind == "offline_rescore" else None
            base = {
                "replay_id": replay_id,
                "trial_id": row["trial_id"],
                "model": row["model"], "arm": row["arm"],
                "task_id": row["task_id"], "family": row["family"],
                "budget": row["budget"], "execution_kind": kind,
                "source_experiment": ex.get("source_experiment"),
                "source_trial_id": ex.get("source_trial_id"),
            }
            try:
                corr = engine.replay(row, source_row=srow)
            except rl.ArtifactIntegrityError as e:
                rec = {**base,
                       "change_classification": "EVIDENCE_INSUFFICIENT",
                       "integrity_code": e.code, "integrity_detail": str(e)}
                counts["EVIDENCE_INSUFFICIENT"] = \
                    counts.get("EVIDENCE_INSUFFICIENT", 0) + 1
                integrity_rejects.append({**base, "code": e.code})
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                continue

            failure_class = rl.classify_failure(corr)
            classification = rl.change_classification(
                row["semantic_correct"], corr["semantic_correct"], row, corr)
            counts[classification] = counts.get(classification, 0) + 1

            # consistency verifications
            if kind == "physical":
                same = (corr["semantic_correct"] == row["semantic_correct"]
                        and corr["tool_correct"] == row["tool_correct"]
                        and corr["args_correct"] == row["args_correct"]
                        and corr["reasons"] == row["reasons"]
                        and bool(corr["parser"]["structural_ok"])
                        == bool(row["parser"]["structural_ok"])
                        and corr["parser"]["payload"]
                        == row["parser"]["payload"])
                physical_consistency["match" if same else "divergent"] += 1
            else:
                # the corrected replay must restore the source experiment's
                # own physical verdict (parser eras are behaviorally equal
                # on non-raising inputs; any divergence is escalated)
                same = (srow is not None
                        and corr["semantic_correct"]
                        == srow["semantic_correct"]
                        and bool(corr["parser"]["structural_ok"])
                        == bool(srow["parser"]["structural_ok"])
                        and corr["parser"]["payload"]
                        == srow["parser"]["payload"])
                rescore_source_agreement[
                    "match" if same else "divergent"] += 1

            rec = {
                **base,
                "original_published": {
                    "verdict": row["semantic_correct"],
                    "parser_output": row["parser"]["payload"],
                    "structural_ok": row["parser"]["structural_ok"],
                    "failure_reasons": row["reasons"],
                    "telemetry": tel_summary(row["telemetry"]),
                    "defective": kind == "offline_rescore",
                },
                "original_source": ({
                    "verdict": srow["semantic_correct"],
                    "parser_output": srow["parser"]["payload"],
                    "structural_ok": srow["parser"]["structural_ok"],
                    "failure_reasons": srow["reasons"],
                    "telemetry": tel_summary(srow["telemetry"]),
                } if srow else None),
                "corrected": {
                    "verdict": corr["semantic_correct"],
                    "parser_output": corr["parser"]["payload"],
                    "structural_ok": corr["parser"]["structural_ok"],
                    "failure_reasons": corr["reasons"],
                    "telemetry": tel_summary(corr["telemetry"]),
                    "telemetry_totals": {
                        k: v for k, v in
                        corr["telemetry_totals"].items() if k != "per_stage"},
                    "failure_class": failure_class,
                    "p7s": corr.get("p7s_reconstruction"),
                    "stage1_selection_wrong_tool":
                        corr.get("stage1_selection_wrong_tool"),
                },
                "source_evidence": {
                    "artifact": row["response_artifact"],
                    "sha256_recorded": row["response_artifact_sha256"],
                    "sha256_verified": True,
                    "stage_count": corr["replay_checks"]["artifact_stages"],
                },
                "change_classification": classification,
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    manifest = {
        "replay_id": replay_id,
        "kind": "offline_analysis_replay",
        "physical": False,
        "spec": replay_spec,
        "inputs_read_only": True,
        "counts": {
            "total_rows": len(dst_rows),
            "change_classifications": counts,
            "physical_consistency_verification": physical_consistency,
            "rescore_source_agreement": rescore_source_agreement,
            "integrity_rejects": integrity_rejects,
        },
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest["counts"], indent=1))
    print(f"replay_id={replay_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
