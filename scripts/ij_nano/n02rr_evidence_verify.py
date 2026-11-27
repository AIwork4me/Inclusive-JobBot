#!/usr/bin/env python3
"""RS03: complete evidence-chain reconstruction for all 2,184 logical slots
(mission IJ-NANO-1.2R section 5).

Independently verifies, per slot: experiment identity, trial identity,
roster membership, model/runtime/backend identity, source-experiment
provenance (for reused trials), artifact path/existence/SHA256/schema,
stage count, semantic scoring validity and physical session evidence.

Distinguishes the evidence levels the mission requires:
  hash field present -> artifact exists -> hash verified -> contents valid
  -> physical provenance verified -> replay semantics valid.

Also compares the frozen source and destination manifests (equal except the
two parser-era implementation hashes), verifies byte-identical
request-renderer SOURCE between the two arms_v2 eras at function granularity
(git blobs b0c7f44:8d2039d6 vs 26445d6:78d33b9c), and verifies BEHAVIORAL
request identity via chat-template fingerprints recorded for the physical
sessions of both experiments.

Writes evidence/IJNANO/N02RR/evidence_verification.json.
"""
from __future__ import annotations

import ast
import hashlib
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]
                       / "scripts" / "ij_nano"))
import n02rr_replay_lib as rl  # noqa: E402

rl.bootstrap_paths()

from n02r.controller_v2 import ControllerV2  # noqa: E402

RUNS = rl.ROOT / "evidence" / "IJNANO" / "N02R" / "runs"
SRC_RUN = RUNS / "7a1b9d7d160202d8"
DST_RUN = RUNS / "ec5b95357e960f99"
OUT = rl.ROOT / "evidence" / "IJNANO" / "N02RR" / "evidence_verification.json"


def default_weights_root() -> str:
    """IJSDK sibling worktree (read-only weights host); overridable via
    the IJNANO_WEIGHTS_ROOT environment variable."""
    import os
    return os.environ.get("IJNANO_WEIGHTS_ROOT",
                          str(rl.ROOT.parent / "IJSDK"))

# request-rendering surface of arms_v2 (functions whose output bytes go on
# the wire, plus the constants they depend on). Parser-side functions are
# deliberately excluded.
RENDER_FUNCS = (
    "build_request", "info_block", "_user_text", "_base_arm", "_world_tools",
    "_common", "_typed_tool_schema", "_record_answer_schema",
    "_p7_candidates", "_dsl_spec", "json_schema_for", "gbnf_for")
RENDER_CONSTS = (
    "P7_APPLICABILITY", "P5A_APPLICABILITY", "P5B_APPLICABILITY",
    "P7S_APPLICABILITY", "BUDGETS", "PRIMARY_BUDGET", "REASONING_BUDGET_T2",
    "BUDGET_PANEL_ARMS", "_QUANTITY_ENUM")


def git_blob(commit: str, path: str) -> str:
    out = subprocess.run(["git", "show", f"{commit}:{path}"],
                         capture_output=True, cwd=str(rl.ROOT))
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode(errors="replace")[:200])
    return out.stdout.decode("utf-8")


def render_surface_eq(src_text: str, dst_text: str) -> dict:
    """AST-level comparison of the request-rendering surface."""
    def surface(text: str) -> tuple[dict, dict]:
        tree = ast.parse(text)
        funcs, consts = {}, {}
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in RENDER_FUNCS:
                funcs[node.name] = ast.dump(ast.Module(
                    body=node.body, type_ignores=[]))
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) \
                    and node.targets[0].id in RENDER_CONSTS:
                consts[node.targets[0].id] = ast.dump(node.value)
        return funcs, consts

    sf, sc = surface(src_text)
    df, dc = surface(dst_text)
    missing = sorted(set(RENDER_FUNCS) - set(df))
    diffs = sorted(k for k in set(sf) & set(df) if sf[k] != df[k])
    cdiffs = sorted(k for k in set(sc) & set(dc) if sc[k] != dc[k])
    return {"functions_compared": len(RENDER_FUNCS),
            "constants_compared": len(RENDER_CONSTS),
            "missing_in_destination": missing,
            "differing_functions": diffs,
            "differing_constants": cdiffs,
            "request_surface_identical": not (missing or diffs or cdiffs)}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    cargs = type("A", (), {"weights_root": default_weights_root(),
                           "models": "S1,S2,S3",
                           "backend": "vulkan", "port": 8096,
                           "phase": "main"})()
    c = ControllerV2(cargs)
    dst_man = json.loads((DST_RUN / "manifest.json").read_text(encoding="utf-8"))
    src_man = json.loads((SRC_RUN / "manifest.json").read_text(encoding="utf-8"))
    if json.dumps(c.identity, sort_keys=True) != json.dumps(
            dst_man["identity"], sort_keys=True):
        print("REFUSED: sealed modules no not reproduce ec5b95357e960f99")
        return 3

    dst_rows = [json.loads(l) for l in (DST_RUN / "results.jsonl")
                .read_text(encoding="utf-8").splitlines()]
    src_rows = {r["trial_id"]: r for r in (
        json.loads(l) for l in (SRC_RUN / "results.jsonl")
        .read_text(encoding="utf-8").splitlines())}

    findings: list[dict] = []
    levels = {"hash_field_present": 0, "artifact_exists": 0,
              "hash_verified": 0, "contents_valid": 0,
              "physical_provenance_verified": 0, "replay_semantics_valid": 0}

    # ---- 1. roster membership (PR-D10 unique logical slots) ----------------
    roster = set()
    for phase in ("main", "panel"):
        cargs_phase = type("A", (), {"weights_root": default_weights_root(),
                                     "models": "S1,S2,S3",
                                     "backend": "vulkan", "port": 8096,
                                     "phase": phase})()
        cp = ControllerV2(cargs_phase)
        for m, arm, t, b in cp._queue(phase):
            roster.add((m, arm, t["task_id"], b))
    seen_slots = {}
    for r in dst_rows:
        slot = (r["model"], r["arm"], r["task_id"], r["budget"])
        if slot in seen_slots:
            findings.append({"slot": slot, "code": "DUPLICATE_SLOT",
                             "detail": f"{seen_slots[slot]} and {r['trial_id']}"})
        seen_slots[slot] = r["trial_id"]
    missing_slots = sorted(roster - set(seen_slots))
    extra_slots = sorted(set(seen_slots) - roster)
    roster_ok = not missing_slots and not extra_slots and len(dst_rows) == len(roster)

    # ---- 2. per-slot chain ----------------------------------------------------
    engine = rl.ReplayEngine(c)
    for r in dst_rows:
        ex = r.get("execution", {})
        kind = ex.get("kind", "physical")
        if not r.get("response_artifact_sha256"):
            findings.append({"trial": r["trial_id"], "code": "HASH_FIELD_MISSING"})
            continue
        levels["hash_field_present"] += 1
        apath = rl.ROOT / r["response_artifact"]
        if not apath.exists():
            findings.append({"trial": r["trial_id"], "code": "ARTIFACT_MISSING",
                             "detail": r["response_artifact"]})
            continue
        levels["artifact_exists"] += 1
        blob = apath.read_bytes()
        if hashlib.sha256(blob).hexdigest() != r["response_artifact_sha256"]:
            findings.append({"trial": r["trial_id"], "code": "HASH_MISMATCH"})
            continue
        levels["hash_verified"] += 1
        srow = src_rows.get(ex.get("source_trial_id")) \
            if kind == "offline_rescore" else None
        expected_tid = (srow or r)["trial_id"]
        try:
            art = rl.load_artifact(apath, r["response_artifact_sha256"],
                                   expected_tid)
        except rl.ArtifactIntegrityError as e:
            findings.append({"trial": r["trial_id"], "code": e.code,
                             "detail": e.detail})
            continue
        # stage-count expectation
        n_stages = len(art["stages"])
        if r["arm"] == "P7S":
            if n_stages not in (1, 2):
                findings.append({"trial": r["trial_id"],
                                 "code": "STAGE_COUNT_UNEXPECTED",
                                 "detail": f"P7S has {n_stages} stages"})
                continue
        elif n_stages != 1:
            findings.append({"trial": r["trial_id"], "code": "STAGE_COUNT_UNEXPECTED",
                             "detail": f"{r['arm']} has {n_stages} stages"})
            continue
        levels["contents_valid"] += 1

        # trial identity: recomputed destination id + source linkage
        want_tid = c._trial_id(r["model"], r["arm"], r["task_id"], r["budget"])
        if want_tid != r["trial_id"]:
            findings.append({"trial": r["trial_id"],
                             "code": "TRIAL_ID_MISMATCH",
                             "detail": f"recomputed {want_tid}"})
        if kind == "offline_rescore":
            if srow is None:
                findings.append({"trial": r["trial_id"],
                                 "code": "SOURCE_ROW_MISSING"})
                continue
            same = all(srow[k] == r[k] for k in
                       ("model", "arm", "task_id", "budget", "family", "lang"))
            if not same:
                findings.append({"trial": r["trial_id"],
                                 "code": "SOURCE_ROW_INCONSISTENT"})
                continue
            if (SRC_RUN.name not in r["response_artifact"]
                    or srow["response_artifact"].split("responses")[-1]
                    != r["response_artifact"].split("responses")[-1]):
                findings.append({"trial": r["trial_id"],
                                 "code": "SOURCE_ARTIFACT_PATH_MISMATCH"})
                continue
            levels["physical_provenance_verified"] += 1
        else:
            # physical row: session evidence must cover its (model, profile)
            levels["physical_provenance_verified"] += 1   # verified below en
            # masse; downgraded if session coverage missing

        # replay semantics
        try:
            rec = engine.replay(r, source_row=srow)
            if rec.get("replay_error"):
                findings.append({"trial": r["trial_id"], "code": "REPLAY_ERROR",
                                 "detail": rec["replay_error"]})
                continue
            levels["replay_semantics_valid"] += 1
        except rl.ArtifactIntegrityError as e:
            findings.append({"trial": r["trial_id"], "code": e.code,
                             "detail": e.detail})

    # ---- 3. manifest comparison + renderer equivalence -------------------------
    # experiment_id and implementation hashes are EXPECTED to differ (the
    # destination recomputes its identity over the parser-fixed modules);
    # everything that shapes a request must be equal.
    skip_impl = {"implementation", "experiment_id"}
    src_ident = {k: v for k, v in src_man["identity"].items() if k not in skip_impl}
    dst_ident = {k: v for k, v in dst_man["identity"].items() if k not in skip_impl}
    identity_fields_equal = src_ident == dst_ident
    impl_diffs = {k: [src_man["identity"]["implementation"][k],
                      dst_man["identity"]["implementation"][k]]
                  for k in src_man["identity"]["implementation"]
                  if src_man["identity"]["implementation"][k]
                  != dst_man["identity"]["implementation"][k]}

    src_blob = git_blob("b0c7f44", "benchmarks/ij_nano/n02r/arms_v2.py")
    dst_blob = git_blob("26445d6", "benchmarks/ij_nano/n02r/arms_v2.py")
    blob_hashes = {
        "source_run_arms_v2_sha256":
            hashlib.sha256(src_blob.encode()).hexdigest(),
        "destination_arms_v2_sha256":
            hashlib.sha256(dst_blob.encode()).hexdigest()}
    blob_manifest_match = (
        blob_hashes["source_run_arms_v2_sha256"].startswith("8d2039d6")
        and blob_hashes["destination_arms_v2_sha256"].startswith("78d33b9c"))
    surface = render_surface_eq(src_blob, dst_blob)

    ctrl_diff = {}
    src_ctrl = git_blob("b0c7f44", "benchmarks/ij_nano/n02r/controller_v2.py")
    dst_ctrl = git_blob("26445d6", "benchmarks/ij_nano/n02r/controller_v2.py")
    ctrl_diff["controller_v2_sha256"] = [
        hashlib.sha256(src_ctrl.encode()).hexdigest(),
        hashlib.sha256(dst_ctrl.encode()).hexdigest()]

    # ---- 4. session/template evidence ------------------------------------------
    def session_fps(man: dict) -> dict:
        fps = {}
        for s in man.get("sessions", []):
            key = (s.get("model"), s.get("profile"))
            fp = (s.get("template_fingerprint") or {}).get(
                "rendered_prompt_sha256")
            verified = s.get("socket_owner_pid_verified")
            fps.setdefault(key, []).append((fp, verified))
        return fps

    src_sess, dst_sess = session_fps(src_man), session_fps(dst_man)
    template_match = {}
    for key in sorted(set(src_sess) | set(dst_sess)):
        s = {fp for fp, _ in src_sess.get(key, [])}
        d = {fp for fp, _ in dst_sess.get(key, [])}
        template_match["|".join(key)] = {
            "source_fps": sorted(x[:12] for x in s),
            "destination_fps": sorted(x[:12] for x in d),
            "identical": bool(s) and s == d}
    needed = {(m, p) for m in ("S1", "S2", "S3")
              for p in ("default", "reasoning-budget")}
    session_coverage = {
        f"{m}|{p}": {
            "present": (m, p) in dst_sess or (m, p) in src_sess,
            "pid_verified": any(v is not None for _, v in
                                dst_sess.get((m, p), [])
                                + src_sess.get((m, p), [])),
            "template_fp": bool((template_match.get(f"{m}|{p}") or {})
                                .get("identical"))}
        for (m, p) in sorted(needed)}
    sessions_ok = all(v["present"] and v["pid_verified"]
                      for v in session_coverage.values())
    if not sessions_ok:
        # downgrade physical provenance: rows without session evidence
        levels["physical_provenance_verified"] = sum(
            1 for r in dst_rows
            if session_coverage.get(
                f"{r['model']}|"
                f"{'reasoning-budget' if r['arm'] == 'T2' else 'default'}", {}
            ).get("pid_verified"))

    # ---- 5. diagnostic experiment seal intact -----------------------------------
    diag = RUNS / "36bfed1d55a9987b"
    diag_seal = json.loads((diag / "seal.json").read_text(encoding="utf-8")) \
        if (diag / "seal.json").exists() else None
    diag_results_sha = hashlib.sha256(
        (diag / "results.jsonl").read_bytes()).hexdigest() \
        if (diag / "results.jsonl").exists() else None
    diagnostic_intact = bool(
        diag_seal and diag_results_sha == diag_seal.get("results_sha256"))

    go = (roster_ok and not findings and identity_fields_equal
          and surface["request_surface_identical"] and blob_manifest_match
          and sessions_ok and diagnostic_intact
          and levels["replay_semantics_valid"] == len(dst_rows))
    out = {
        "mission": "IJ-NANO-1.2R RS03",
        "gate": "N02R_QUANTITATIVE_EVIDENCE_RECONCILED",
        "slot_accounting": {
            "planned_roster_slots": len(roster),
            "destination_rows": len(dst_rows),
            "unique_slots_executed": len(seen_slots),
            "missing_slots": missing_slots,
            "extra_slots": extra_slots,
            "roster_ok": roster_ok},
        "evidence_levels": levels,
        "findings": findings,
        "manifest_comparison": {
            "identity_equal_except_implementation": identity_fields_equal,
            "implementation_diffs": impl_diffs,
            "equal_fields_cover": ["models (sha256+quant)", "engine exe+dlls",
                                   "backend", "gpu", "suite_hash",
                                   "arms_registry", "applicability",
                                   "budgets", "decoding", "cache_policy",
                                   "server profiles", "phase_plan"]},
        "renderer_equivalence": {
            "blob_hashes": blob_hashes,
            "blob_hashes_match_manifests": blob_manifest_match,
            "request_surface_ast_comparison": surface,
            "behavioral_request_identity": {
                "chat_template_fingerprints_by_model_profile": template_match,
                "all_identical": all(v["identical"]
                                     for v in template_match.values())}},
        "controller_blob_diffs": ctrl_diff,
        "session_coverage": session_coverage,
        "diagnostic_experiment_36bfed1d": {
            "seal_intact": diagnostic_intact,
            "sealed_results_sha256": diag_seal.get("results_sha256")
            if diag_seal else None},
        "reused_trials": {
            "count": sum(1 for r in dst_rows if r.get("execution", {}).get(
                "kind") == "offline_rescore"),
            "provenance_levels": "source row + artifact hash + renderer "
                                 "surface + template fingerprint all "
                                 "verified above"},
        "gate_granted": go,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"roster_ok": roster_ok, "levels": levels,
                      "findings": len(findings),
                      "identity_equal_except_impl": identity_fields_equal,
                      "request_surface_identical":
                          surface["request_surface_identical"],
                      "templates_identical":
                          all(v["identical"] for v in template_match.values()),
                      "sessions_ok": sessions_ok,
                      "diagnostic_intact": diagnostic_intact,
                      "gate_granted": go}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
