#!/usr/bin/env python3
"""RS01 mandatory red reproduction (mission IJ-NANO-1.2R section 2).

Executes the EXACT audited offline-rescore path of
``scripts/ij_nano/n02r_rescore.py`` @ commit 26445d6 (read-only; nothing is
appended to any results.jsonl) on the published witness artifacts, then the
corrected key-based path, and records:

  1. the extracted stage/path/http_json/http_error/latency types,
  2. what the parser actually receives under the audited path,
  3. the verdict the audited path produced (as sealed in ec5b95357e960f99),
  4. the independently computed expected verdict (key-based replay + the
     source experiment's own physical verdict),
  5. the exact number of affected records among the 1,397 offline-rescored
     trials.

Writes evidence/IJNANO/N02RR/rs01_red_reproduction.json.
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
from n02r import arms_v2 as arms  # noqa: E402
from n02r import scorer  # noqa: E402

RUNS = rl.ROOT / "evidence" / "IJNANO" / "N02R" / "runs"
SRC_RUN = RUNS / "7a1b9d7d160202d8"
DST_RUN = RUNS / "ec5b95357e960f99"
WITNESS = "003abb9e2604141bd8b016ec"


def default_weights_root() -> str:
    """IJSDK sibling worktree (read-only weights host); overridable via
    the IJNANO_WEIGHTS_ROOT environment variable."""
    import os
    return os.environ.get("IJNANO_WEIGHTS_ROOT",
                          str(rl.ROOT.parent / "IJSDK"))


def audited_path_row(r: dict, c: ControllerV2) -> dict:
    """VERBATIM semantics of n02r_rescore.py@26445d6 main-loop body for one
    row (lines 63-114), minus the results.jsonl append. Do not 'fix' this
    function: it is the red specimen."""
    art_path = rl.ROOT / r["response_artifact"]
    if not art_path.exists():
        return {"skipped": "artifact missing"}
    blob = art_path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != r["response_artifact_sha256"]:
        return {"skipped": "hash mismatch"}
    art = json.loads(blob.decode("utf-8"))
    stage, path, http_json, http_error, latency = art["stages"][-1]
    parse_arm = {"T2": "M-P1", "P7S": "M-P3"}.get(r["arm"], r["arm"])
    task = next(t for t in c.suite if t["task_id"] == r["task_id"])
    try:
        parsed = arms.parse_response(parse_arm, task,
                                     http_json if isinstance(
                                         http_json, dict) else None,
                                     http_error)
        scored = scorer.score(task, parsed.get("payload"))
    except Exception as e:                     # never lose a trial
        parsed = {"structural_ok": False, "warnings":
                  [f"rescore parse error: {e!r}"], "payload": None,
                  "normalizations": []}
        scored = {"semantic_correct": False, "reasons": ["PARSE_INVALID"],
                  "tool_correct": False, "args_correct": False}
    tel = c._telemetry(r["arm"], http_json, http_error,
                       art["stages"][-1]["latency_s"])
    return {"stage": stage, "path": path, "http_json": http_json,
            "http_error": http_error, "latency": latency, "parsed": parsed,
            "scored": scored, "telemetry": tel}


def types(v) -> str:
    return type(v).__name__


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    # 0. repair status: the audited specimen contained the defective line
    # verbatim at HEAD 26445d6 (git-preserved); the canonical mutant lives
    # in rl.mutant_unpack_last_stage for the red suite. After the RS01
    # repair the live file no longer contains it as CODE. The docstring
    # quotes the line for documentation, so the check is AST-based: an
    # assignment of art["stages"][<expr>] to a 5-name tuple is the defect
    # signature.
    import ast as _ast
    audited_path = rl.ROOT / "scripts" / "ij_nano" / "n02r_rescore.py"
    fragment_present = False
    try:
        tree = _ast.parse(audited_path.read_text(encoding="utf-8"))
        for node in _ast.walk(tree):
            if (isinstance(node, _ast.Assign)
                    and isinstance(node.value, _ast.Subscript)
                    and isinstance(node.value.value, _ast.Subscript)
                    and isinstance(node.targets[0], _ast.Tuple)
                    and len(node.targets[0].elts) == 5):
                fragment_present = True
                break
    except SyntaxError:
        fragment_present = None            # file unparsable: report as such

    cargs = type("A", (), {"weights_root": default_weights_root(),
                       "models": "S1,S2,S3",
                           "backend": "vulkan", "port": 8096,
                           "phase": "main"})()
    c = ControllerV2(cargs)
    man = json.loads((DST_RUN / "manifest.json").read_text(encoding="utf-8"))
    identity_ok = (json.dumps(c.identity, sort_keys=True)
                   == json.dumps(man["identity"], sort_keys=True))
    if not identity_ok:
        print("REFUSED: sealed modules no longer reproduce ec5b95357e960f99")
        return 3

    engine = rl.ReplayEngine(c)
    src_rows = {r["trial_id"]: r for r in (
        json.loads(l) for l in (SRC_RUN / "results.jsonl")
        .read_text(encoding="utf-8").splitlines())}
    dst_rows = [json.loads(l) for l in (DST_RUN / "results.jsonl")
                .read_text(encoding="utf-8").splitlines()]
    rescore_rows = [r for r in dst_rows
                    if r.get("execution", {}).get("kind") == "offline_rescore"]

    # 1-5. witness demonstration -------------------------------------------------
    witnesses = []
    witness_row = next(r for r in rescore_rows
                       if r["response_artifact"].endswith(WITNESS + ".json"))
    srow = src_rows[witness_row["execution"]["source_trial_id"]]
    apath = rl.ROOT / witness_row["response_artifact"]
    art = json.loads(apath.read_text(encoding="utf-8"))
    st = art["stages"][-1]
    aud = audited_path_row(witness_row, c)
    corrected = engine.replay(witness_row, source_row=srow)
    witnesses.append({
        "artifact": witness_row["response_artifact"],
        "artifact_sha256_recorded": witness_row["response_artifact_sha256"],
        "artifact_sha256_actual":
            hashlib.sha256(apath.read_bytes()).hexdigest(),
        "last_stage_actual_types": {
            "stage": types(st["stage"]), "path": types(st["path"]),
            "http": types(st["http"]), "http_error": types(st["http_error"]),
            "latency_s": types(st["latency_s"])},
        "audited_unpack_values": {
            "stage": aud["stage"], "path": aud["path"],
            "http_json": aud["http_json"], "http_error": aud["http_error"],
            "latency": aud["latency"]},
        "audited_parser_received": (repr(aud["parsed"])
                                    if aud["scored"] is None or
                                    aud["parsed"].get("payload") is None
                                    and "http_error" in str(
                                        aud["parsed"].get("warnings")) else
                                    "response dict"),
        "audited_verdict": {
            "structural_ok": aud["parsed"]["structural_ok"],
            "warnings": aud["parsed"]["warnings"],
            "semantic_correct": aud["scored"]["semantic_correct"],
            "reasons": aud["scored"]["reasons"],
            "telemetry_usage": aud["telemetry"].get("usage"),
            "http_ok_field": aud["http_json"] is not None},
        "sealed_destination_verdict": {
            "structural_ok": witness_row["parser"]["structural_ok"],
            "reasons": witness_row["reasons"],
            "http_error": witness_row["http_error"],
            "usage": witness_row["telemetry"].get("usage")},
        "corrected_replay_verdict": {
            "structural_ok": corrected["parser"]["structural_ok"],
            "semantic_correct": corrected["semantic_correct"],
            "reasons": corrected["reasons"],
            "payload": corrected["parser"]["payload"],
            "telemetry_usage": corrected["telemetry"].get("usage"),
            "latency_s": corrected["telemetry"]["latency_s"]},
        "source_experiment_physical_verdict": {
            "structural_ok": srow["parser"]["structural_ok"],
            "semantic_correct": srow["semantic_correct"],
            "reasons": srow["reasons"]},
        "parser_input_is_none_demonstrated": (
            aud["parsed"]["warnings"] == ["http_error: http_error"]),
    })

    # additional witnesses: a real model-error row, a two-stage P7S row,
    # an empty-content row, a T2 row
    def pick(pred):
        for r in rescore_rows:
            if r is witness_row:
                continue
            sr = src_rows[r["execution"]["source_trial_id"]]
            if pred(sr, r):
                return r, sr
        return None, None
    extra_defs = [
        ("genuine_model_semantic_error",
         lambda sr, r: sr["semantic_correct"] is False
         and sr["parser"]["structural_ok"] is True),
        ("two_stage_p7s", lambda sr, r: r["arm"] == "P7S"
         and len(json.loads((rl.ROOT / r["response_artifact"])
                            .read_text(encoding="utf-8"))["stages"]) == 2),
        ("empty_final_content", lambda sr, r: sr["telemetry"].get("content")
         in (None, "") and not sr["telemetry"].get("tool_calls")),
        ("t2_reasoning_budget", lambda sr, r: r["arm"] == "T2"),
    ]
    for name, pred in extra_defs:
        r, sr = pick(pred)
        if r is None:
            continue
        a2 = audited_path_row(r, c)
        c2 = engine.replay(r, source_row=sr)
        witnesses.append({
            "case": name, "artifact": r["response_artifact"],
            "arm": r["arm"], "task_id": r["task_id"],
            "audited_verdict": {"semantic_correct":
                                a2["scored"]["semantic_correct"],
                                "reasons": a2["scored"]["reasons"]},
            "source_physical_verdict": {"semantic_correct":
                                        sr["semantic_correct"],
                                        "reasons": sr["reasons"]},
            "corrected_replay_verdict": {"semantic_correct":
                                         c2["semantic_correct"],
                                         "reasons": c2["reasons"]},
        })

    # 6. exact affected count among the 1,397 ------------------------------------
    affected = 0
    affected_breakdown = {"verdict_flip": 0, "structure_only": 0,
                          "telemetry_only": 0}
    fingerprints = 0
    for r in rescore_rows:
        sr = src_rows[r["execution"]["source_trial_id"]]
        a = audited_path_row(r, c)
        corr = engine.replay(r, source_row=sr)
        fp = (r.get("http_error") == "http_error"
              and r.get("reasons") == ["PARSE_INVALID"]
              and r.get("parser", {}).get("structural_ok") is False)
        fingerprints += int(fp)
        differs = (a["scored"]["semantic_correct"] != corr["semantic_correct"]
                   or a["parsed"]["structural_ok"]
                   != corr["parser"]["structural_ok"]
                   or a["scored"]["reasons"] != corr["reasons"]
                   or a["telemetry"].get("usage") != corr["telemetry"]
                   .get("usage")
                   or a["latency"] != corr["telemetry"]["latency_s"])
        if differs:
            affected += 1
            if (a["scored"]["semantic_correct"]
                    != corr["semantic_correct"]):
                affected_breakdown["verdict_flip"] += 1
            elif (a["parsed"]["structural_ok"]
                    != corr["parser"]["structural_ok"]):
                affected_breakdown["structure_only"] += 1
            else:
                affected_breakdown["telemetry_only"] += 1

    out = {
        "mission": "IJ-NANO-1.2R RS01",
        "audited_head": "26445d6f79949d51da7a9ce3f5669b032ab51efe",
        "audited_module": "scripts/ij_nano/n02r_rescore.py",
        "audited_defect_line": rl.AUDITED_DEFECT_LINE,
        "audited_fragment_in_live_file": fragment_present,
        "audited_fragment_note": "true at audited HEAD 26445d6 (git-"
                                 "preserved); false after the RS01 repair "
                                 "rewrote the tool; the verbatim semantics "
                                 "are preserved as the canonical mutant in "
                                 "n02rr_replay_lib.mutant_unpack_last_stage",
        "identity_reproduced": identity_ok,
        "corpus": {"rescored_trials": len(rescore_rows),
                   "source_experiment": SRC_RUN.name,
                   "destination_experiment": DST_RUN.name},
        "witnesses": witnesses,
        "affected_records": affected,
        "affected_breakdown": affected_breakdown,
        "defect_fingerprint_rows_in_sealed_destination": fingerprints,
        "conclusion": (
            "Dictionary unpacking of the persisted stage object yields the "
            "key names ('stage','path','http','http_error','latency_s'); the "
            "isinstance(http_json, dict) guard substitutes None, so the "
            "parser receives None instead of the stored response for every "
            "replayed trial. All offline-rescored records are affected; "
            "verdicts, failure reasons and telemetry in the sealed "
            "destination experiment are invalid for these rows until "
            "re-scored with the corrected key-based loader."),
    }
    outdir = rl.ROOT / "evidence" / "IJNANO" / "N02RR"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "rs01_red_reproduction.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: out[k] for k in
                      ("affected_records", "affected_breakdown",
                       "defect_fingerprint_rows_in_sealed_destination",
                       "audited_fragment_in_live_file")},
                     indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
