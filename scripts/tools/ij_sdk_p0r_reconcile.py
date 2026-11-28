#!/usr/bin/env python3
"""IJ-SDK-1.1 P0R: independent baseline reconciliation (machine-readable).

Every fact is re-queried from a live source - local git, the GitHub API, files
on disk, the recorded evidence files - instead of being copied from the
ledgers under audit. Each fact is then paired with the audit disposition that
is declared in this file, so the judgment and its basis travel together.

Output: evidence/IJSDK/P0R/baseline_reconciliation.json

Usage (PowerShell, repository root):

  python -I scripts/tools/ij_sdk_p0r_reconcile.py `
      --hash-file .runtime/p0r_artifact_hashes.txt `
      --repro evidence/IJSDK/P0R/defect_reproductions_audited_c28a41b.json

No local identity (absolute path, user name, host name) is written to the
output; repository-relative paths only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FROZEN_SOURCE = "fe56f324daf4ae106908e0d0a0f16967afc9c463"
AUDITED_HEAD = "c28a41bad410b66103b499eaaec4ee1b3a227b10"
MISSION_BRANCH = "mission/ij-sdk-1.0-cross-sdk-agentic-benchmark"
PARENT_BRANCH = "mission/ij-0.7.1-jobbot-agentic-capability-atlas-v1"
REPO_SLUG = "AIwork4me/Inclusive-JobBot"
INHERITED_FILES = ("evidence/IJ0/model_identity.json", "evidence/IJ0/rocm_runtime_install.json",
                   "models/model_manifest.json")
KEY_PACKAGES = ("google-antigravity", "openai-agents", "smolagents", "pydantic-ai-slim", "langgraph",
                "langchain-openai", "google-adk", "agent-framework", "pocketflow", "dspy", "openai", "litellm")


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd: list[str], timeout: float = 120) -> str:
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", timeout=timeout).stdout.strip()


def gh(args: list[str]):
    try:
        out = run(["gh", *args], timeout=90)
        return json.loads(out) if out else None
    except Exception as exc:  # GitHub is a live dependency; its absence is recorded, never guessed
        return {"_error": f"{type(exc).__name__}"}


def load(rel: str):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def load_audited(rel: str):
    """Read a JSON file as it exists at the audited commit, so the audit of the recorded
    state cannot drift when the working tree is later corrected."""
    out = subprocess.run(["git", "show", f"{AUDITED_HEAD}:{rel}"], cwd=REPO, capture_output=True, text=True,
                         encoding="utf-8").stdout
    return json.loads(out) if out.strip() else load(rel)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# live facts
# ---------------------------------------------------------------------------

def git_facts() -> dict:
    head = run(["git", "rev-parse", "HEAD"])
    upstream = run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    counts = run(["git", "rev-list", "--left-right", "--count", f"HEAD...{upstream}"]).split()
    # worktree paths contain a local identity: only branch names and SHAs are kept
    branches, sha = [], None
    for line in run(["git", "worktree", "list", "--porcelain"]).splitlines():
        if line.startswith("HEAD "):
            sha = line.split(None, 1)[1]
        elif line.startswith("branch "):
            branches.append({"branch": line.split(None, 1)[1].replace("refs/heads/", ""), "head": sha})
    inherited = run(["git", "diff", "--name-only", f"{FROZEN_SOURCE}..HEAD", "--", *INHERITED_FILES]).splitlines()
    return {
        "local_head": head,
        "branch": run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "upstream": upstream,
        "ahead_of_upstream": int(counts[0]) if counts else None,
        "behind_upstream": int(counts[1]) if len(counts) > 1 else None,
        "worktree_dirty": bool(run(["git", "status", "--porcelain"])),
        "audited_head_equals_local_head": head == AUDITED_HEAD,
        "frozen_source_is_ancestor": subprocess.run(["git", "merge-base", "--is-ancestor", FROZEN_SOURCE, "HEAD"],
                                                    cwd=REPO).returncode == 0,
        "commits_since_frozen_source": int(run(["git", "rev-list", "--count", f"{FROZEN_SOURCE}..HEAD"]) or 0),
        "inherited_files_modified_since_frozen_source": inherited,
        "local_worktrees": branches,
    }


def github_facts() -> dict:
    repo = gh(["api", f"repos/{REPO_SLUG}"])
    prs = gh(["pr", "list", "--repo", REPO_SLUG, "--state", "open", "--json",
              "number,title,headRefName,baseRefName,isDraft,headRefOid,updatedAt"])
    issue = gh(["issue", "view", "7", "--repo", REPO_SLUG, "--json", "state,updatedAt"])
    parent_head = run(["git", "rev-parse", f"origin/{PARENT_BRANCH}"])
    open_prs = [p for p in (prs or []) if isinstance(p, dict)] if isinstance(prs, list) else prs
    return {
        "repository": {k: repo.get(k) for k in ("full_name", "default_branch", "visibility", "pushed_at")}
        if isinstance(repo, dict) and "_error" not in repo else repo,
        "open_pull_requests": open_prs,
        "tracking_issue_7": issue,
        "parent_dependency": {
            "branch": PARENT_BRANCH,
            "head_at_p0_audit": FROZEN_SOURCE,
            "head_now": parent_head,
            "advanced_since_freeze": parent_head not in ("", FROZEN_SOURCE),
            "frozen_source_still_reachable_from_parent_branch":
                subprocess.run(["git", "merge-base", "--is-ancestor", FROZEN_SOURCE, parent_head or FROZEN_SOURCE],
                               cwd=REPO).returncode == 0,
            "pr8_base_is_parent_branch": any(p.get("number") == 8 and p.get("baseRefName") == PARENT_BRANCH
                                             for p in open_prs if isinstance(p, dict)),
            "pr8_base": next((p.get("baseRefName") for p in open_prs if isinstance(p, dict) and p.get("number") == 8), None),
        },
    }


def recorded_state() -> dict:
    state = load_audited("MISSION_STATE_IJSDK.json")
    return {
        "updated_utc_recorded": state.get("updated_utc"),
        "current_phase_recorded": state.get("current_phase"),
        "phases": {k: {"progress": v.get("progress"), "status": v.get("status"), "gate": v.get("gate")}
                   for k, v in state["phases"].items()},
        "final_verdicts_recorded": state.get("final_verdicts"),
        "ij_sdk_1_1_verdicts_recorded": state.get("ij_sdk_1_1_verdicts", "ABSENT"),
    }


SDK_TOKENS = {"b2": "openai-agents", "b3b4": "smolagents", "b5": "pydantic-ai", "b6": "langgraph",
              "b7": "google-adk", "b8": "agent-framework", "b9": "pocketflow", "o1": "dspy"}


def recorded_evidence_checks() -> dict:
    p5 = load_audited("evidence/IJSDK/P5/differential_results.json")
    installed = load_audited("evidence/IJSDK/P3/installed_artifacts.json")
    freezes = {k: sorted(str(v).split()) for k, v in installed.items()}
    conformance = {}
    for name in sorted(p for p in subprocess.run(["git", "ls-tree", "--name-only", AUDITED_HEAD,
                                                  "evidence/IJSDK/P3/conformance/"], cwd=REPO,
                                                 capture_output=True, text=True).stdout.split()
                       if p.endswith(".json") and not p.endswith("summary.json")):
        d = load_audited(name)
        checks = d.get("checks", {})
        c2_output = next((v.get("final_output") for k, v in checks.items() if k == "c2_chat"), None)
        conformance[d.get("arm", Path(name).stem)] = {
            "support_tier": d.get("support_tier"),
            "checks": {k: v.get("status") for k, v in checks.items()},
            "has_tool_roundtrip": "c3_tool_roundtrip" in checks,
            "wire_records": len(d.get("wire", [])),
            "c2_final_output_is_text": isinstance(c2_output, str) and not c2_output.startswith("<"),
            "c2_final_output_prefix": str(c2_output)[:70],
        }
    manifest_tracked = subprocess.run(["git", "cat-file", "-e", f"{AUDITED_HEAD}:models/ij_sdk/model_manifest.json"],
                                      cwd=REPO, capture_output=True).returncode == 0
    manifest = load_audited("models/ij_sdk/model_manifest.json")
    return {
        "p5_differential": {k: p5.get(k) for k in ("controls_total", "positives", "negatives", "critical_rejections_required",
                                                   "critical_failures", "all_positives_accepted", "all_negatives_rejected", "gate")},
        "p3_installed_artifacts": {
            "environments_recorded": len(installed),
            "all_entries_identical": len(set(str(v) for v in installed.values())) == 1,
            "packages_per_entry": {k: len(v) for k, v in freezes.items()},
            "own_sdk_package_present_in_recorded_entry": {
                k: any(SDK_TOKENS.get(k.split("-")[0], "\0") in p for p in v) for k, v in freezes.items()},
            "b1_antigravity_recorded": any("antigravity" in p for v in freezes.values() for p in v),
        },
        "p3_conformance": conformance,
        "model_manifest": {
            "present_in_audited_commit": manifest_tracked,
            "note_if_absent": None if manifest_tracked else (
                "models/ij_sdk/model_manifest.json is excluded by the .gitignore rule 'models/*' and was never committed; "
                "the P2 report cites it as frozen evidence. The only committed model identities at the audited commit are the "
                "model_sha256 fields inside evidence/IJSDK/P2/admission/*.json. Values below are from the working tree."),
            "generated_utc_recorded": manifest.get("generated_utc"),
            "entries": {c["id"]: {"status": c.get("status", "frozen"),
                                  "has_sha256": any(spec.get("sha256") for spec in (c.get("files") or {}).values())}
                        for c in manifest.get("candidates", []) + manifest.get("references", [])},
        },
    }


def _repo_relative_model_path(path: str) -> str:
    """Model paths in older evidence may be absolute; keep only the repository-relative tail."""
    path = str(path).replace("\\", "/")
    return "models/" + path.split("models/", 1)[1] if "models/" in path else path


def artifact_checks(hash_file: Path | None) -> dict:
    live: dict[str, str] = {}
    engines: dict[str, str] = {}
    if hash_file and hash_file.exists():
        for line in hash_file.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^([0-9a-f]{64})\s+\*?(.+)$", line.strip())
            if not m:
                continue
            digest, rel = m.group(1), _repo_relative_model_path(m.group(2))
            (engines if rel.endswith(".exe") else live)[rel] = digest
    expected: dict[str, dict] = {
        "models/ij_sdk/Qwen3-14B-GGUF/Qwen3-14B-Q8_0.gguf": {
            "sha256": "a0dfe649137410b7d82f06a209240508e218f32f5b6fd81b69d6932160cfcd9d",
            "source": "atlas/benchmarks/pc_s_qwen3_14b.json"},
        "models/ij_sdk/Qwen3-8B-GGUF/Qwen3-8B-Q8_0.gguf": {
            "sha256": "408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6",
            "source": "configs/qwen3_8b_reference.json"},
    }
    for name in sorted(p for p in subprocess.run(["git", "ls-tree", "--name-only", AUDITED_HEAD,
                                                  "evidence/IJSDK/P2/admission/"], cwd=REPO,
                                                 capture_output=True, text=True).stdout.split() if p.endswith(".json")):
        d = load_audited(name)
        if d.get("model_sha256") and d.get("model_path"):
            expected.setdefault(_repo_relative_model_path(d["model_path"]),
                                {"sha256": d["model_sha256"], "source": name})
    for c in load_audited("models/ij_sdk/model_manifest.json").get("candidates", []):
        for spec in (c.get("files") or {}).values():
            if spec.get("sha256") and spec.get("path"):
                expected.setdefault(_repo_relative_model_path(spec["path"]),
                                    {"sha256": spec["sha256"], "source": "models/ij_sdk/model_manifest.json"})
    models = {}
    for rel in sorted(set(live) | set(expected)):
        want = expected.get(rel, {})
        matches = (live.get(rel) == want["sha256"]) if (rel in live and want.get("sha256")) else None
        models[rel] = {"expected_sha256": want.get("sha256"), "expected_source": want.get("source", "NOT RECORDED"),
                       "live_sha256": live.get(rel, "NOT HASHED"), "matches": matches}
    engine_expected = load_audited("evidence/IJSDK/P1/backend_qualification.json").get("engine", {}).get("exe_sha256")
    return {
        "models": models,
        "engine_binaries": {rel: {"live_sha256": digest, "p1_recorded_exe_sha256": engine_expected,
                                  "matches_p1_recorded": digest == engine_expected} for rel, digest in engines.items()},
        "all_hashed_models_match_recorded_identity": any(m["matches"] is not None for m in models.values())
        and all(m["matches"] for m in models.values() if m["matches"] is not None),
        "models_without_any_recorded_identity": [rel for rel, m in models.items() if not m["expected_sha256"]],
        "hash_file_supplied": bool(hash_file and hash_file.exists()),
    }


def sdk_env_facts() -> dict:
    envs = {}
    probe = ("import importlib.metadata as m, json, sys; "
             "d = {x.metadata['Name'].lower(): x.version for x in m.distributions()}; "
             "print(json.dumps({'count': len(d), 'packages': d, 'python': sys.version.split()[0]}))")
    venv_root = REPO / ".venvs"
    venvs = sorted(p for p in venv_root.iterdir() if (p / "Scripts" / "python.exe").exists()) if venv_root.exists() else []
    targets = [(v.name, v / "Scripts" / "python.exe") for v in venvs]
    targets.append(("project .venv (not arm-isolated)", REPO / ".venv" / "Scripts" / "python.exe"))
    for name, python in targets:
        try:
            data = json.loads(subprocess.run([str(python), "-I", "-c", probe], capture_output=True, text=True,
                                             timeout=120).stdout)
            envs[name] = {"python": data["python"], "package_count": data["count"],
                          "key_packages": {k: data["packages"][k] for k in KEY_PACKAGES if data["packages"].get(k)}}
        except Exception as exc:
            envs[name] = {"error": type(exc).__name__}
    return {"environments": envs,
            "isolated_venv_count": len(venvs),
            "openai_client_version_by_env": {k: v.get("key_packages", {}).get("openai") for k, v in envs.items()}}


def defect_reproduction(path: Path | None) -> dict:
    if not path or not path.exists():
        return {"error": "reproduction evidence not supplied"}
    d = json.loads(path.read_text(encoding="utf-8"))
    probes = d["probes"]
    return {
        "evidence": path.relative_to(REPO).as_posix(),
        "audited_commit": d["binding"]["git_commit"],
        "tool_sha256": d["binding"]["tool_sha256"],
        "protected_evidence_byte_identical": d["protected_evidence"]["byte_identical_before_and_after"],
        "per_defect": d["per_defect"],
        "total_probes": len(probes),
        "reproduced": sum(1 for p in probes if p.get("defect_reproduced") is True),
        "not_reproduced": [{"id": p["id"], "title": p["title"], "observed": p.get("observed")}
                           for p in probes if p.get("defect_reproduced") is False],
        "weakened_oracle_mutants": {"applied": d["per_defect"] and next((p["observed"]["applied"] for p in probes if p["id"] == "D01.06"), None),
                                    "survivors": next((p["observed"]["survivors"] for p in probes if p["id"] == "D01.06"), None)},
    }


# ---------------------------------------------------------------------------
# audit dispositions (judgment; every basis points at a fact gathered above)
# ---------------------------------------------------------------------------

PHASE_DISPOSITIONS = [
    {"phase": "P0", "gate": "P0_REPOSITORY_BASELINE_FROZEN", "recorded": "PASS", "audited": "PASS",
     "disposition": "KEEP (point-in-time audit)",
     "basis": "Suite roster and frozen-source verification stand. The report's PR #6 head (fe56f324) was true at audit time; "
              "the parent branch has since advanced. The frozen source remains an ancestor of the parent branch."},
    {"phase": "P1", "gate": "P1_GFX1100_PHYSICAL_RUNTIME_GO", "recorded": "PASS", "audited": "PASS (scope narrowed)",
     "disposition": "KEEP_WITH_NARROWED_SCOPE",
     "basis": "Vulkan arm: API check exit 0, tool smoke exit 0, 43/43 layers, counters bound to the server PID. Limits now explicit: "
              "(1) streaming/non-streaming byte parity was shown on one prompt set only - not universal backend determinism; "
              "(2) per-check detail lives only in gitignored scratch, published evidence carries exit codes; "
              "(3) the run overwrote inherited parent-mission evidence files (finding E-03); "
              "(4) qualification used the pre-hardening harness and is re-verified with the formal adapters in P8A."},
    {"phase": "P2", "gate": "P2_MODEL_IDENTITIES_AND_ADMISSION_FROZEN", "recorded": "PASS", "audited": "PASS (scope = development admission)",
     "disposition": "KEEP_WITH_NARROWED_SCOPE",
     "basis": "Live SHA256 of every mandatory model matches the identity recorded in the committed admission evidence. "
              "Admission is a 10-case development smoke per candidate and is not a capability ranking. The model manifest "
              "cited as the passport was never committed (finding E-22) and lagged the evidence (S3/R1/R2 'downloading', no "
              "SHA256 for S3); it is now committed with live-verified identities. Q8_0 was the only quantization admitted; "
              "the Q4-class comparison is P8A."},
    {"phase": "P3", "gate": "P3_SDK_ADMISSION_AUDITED", "recorded": "PASS", "audited": "FAIL",
     "disposition": "REOPENED - gate claim contradicted by its own evidence",
     "basis": "The recorded claim 'all 10 arms pass C1/C2/C3' is false: B1 has no tool round-trip and its chat check passed on a "
              "truthy non-string object; O1 has no tool round-trip; C1/C2 are asserted, not tested; no wire capture exists; "
              "installed_artifacts.json is the DSPy freeze repeated for every environment (finding E-04); B4 executed "
              "model-generated code unsandboxed on the host. Retained as research admission only: a single-prompt tool "
              "round-trip on S1/Q8_0/Vulkan for B2-B9. Re-qualified in P4B."},
    {"phase": "P4", "gate": "P4_CROSS_SDK_HARNESS_GO", "recorded": "NOT_RUN (ledger: harness core 'done PASS')",
     "audited": "FAIL for the harness core; gate NOT_RUN",
     "disposition": "REOPENED - ledger row corrected",
     "basis": "D04 (session contamination), D05 (budgets), D06 (gateway order) and D07 (evidence contract) reproduce against the "
              "audited commit. The gate itself was never claimed. Repaired and re-qualified in P4A/P4B."},
    {"phase": "P5", "gate": "P5_EVALUATOR_SCOPE_QUALIFIED", "recorded": "PASS", "audited": "FAIL",
     "disposition": "REOPENED - gate claim contradicted by its own evidence",
     "basis": "The published result reads gate=PASS beside all_negatives_rejected=false; 8 of 16 intentionally weakened oracles "
              "still pass the battery; 16 semantically wrong answers receive a correct verdict; the final business state is "
              "never reconstructed. No E-scope qualification survives. Re-qualified in P5R."},
    *[{"phase": f"P{n}", "gate": None, "recorded": "NOT_RUN", "audited": "NOT_RUN", "disposition": "UNCHANGED", "basis": ""}
      for n in range(6, 20)],
]

LEDGER_CORRECTIONS = [
    {"location": "MISSION_STATE_IJSDK.json P3", "recorded": "PASS; 'All 10 arms (B1-B9, O1) pass C1/C2/C3'",
     "problem": "b1.json has no c3 check; its c2 passed on a non-string object; wire arrays are empty",
     "correction": "FAIL (reopened); retained scope = single-prompt tool round-trip for B2-B9"},
    {"location": "MISSION_STATE_IJSDK.json P5", "recorded": "PASS; '14/14 controls, 0 critical failures'",
     "problem": "gate=PASS beside all_negatives_rejected=false; N07/N08 accepted; no rule attribution",
     "correction": "FAIL (reopened); superseded by P5R"},
    {"location": "MISSION_STATE_IJSDK.json P4 vs TASK_LEDGER_IJSDK.md P4 rows",
     "recorded": "state: not_started; ledger: harness core 'done PASS'",
     "problem": "the two ledgers contradict each other, and the harness core fails D04-D07",
     "correction": "P4 harness core = FAIL (reopened); remaining adapters NOT_RUN"},
    {"location": "TASK_LEDGER_IJSDK.md P2 row 'Admission smoke runs S1/S2/S3 + R1/R2 downloads'",
     "recorded": "not started / NOT_RUN", "problem": "duplicate stale row; contradicts the PASS row above it",
     "correction": "superseded by the PASS row (kept for history, marked superseded)"},
    {"location": "TASK_LEDGER_IJSDK.md P3 row 'SDK passports + isolated installs + admission'",
     "recorded": "not started / NOT_RUN", "problem": "duplicate stale row; contradicts the PASS row above it",
     "correction": "superseded; the PASS row itself is reopened (see P3)"},
    {"location": "TASK_LEDGER_IJSDK.md P3 row '10 isolated SDK venvs installed'",
     "recorded": "10 isolated SDK venvs, pip freeze per venv",
     "problem": "8 venvs exist; B1 sits in the shared project venv; the recorded freeze is one environment's list",
     "correction": "8 isolated venvs + B1 in the project venv; true per-environment freeze recorded in P0R/P4B"},
    {"location": "TASK_LEDGER_IJSDK.md P0 row 'upstream tracking unset'",
     "recorded": "upstream tracking unset", "problem": "the branch tracks origin and has been pushed since",
     "correction": "tracks origin/<branch>; ahead 0 / behind 0 at reconciliation"},
    {"location": "PR #8 body / Issue #7 body / P0-P5 reports 'stacked on PR #6'",
     "recorded": "'stacked on PR #6'", "problem": "the PR base is the default branch, not the PR #6 branch; stacking is documentary only",
     "correction": "described as 'branched from the PR #6 tip; base = default branch'"},
    {"location": "PR #8 body; Issue #7 body", "recorded": "P1 in progress; P2-P5 NOT_RUN",
     "problem": "stale relative to MISSION_STATE_IJSDK.json", "correction": "rewritten at delivery with the audited gate table"},
    {"location": "models/ij_sdk/model_manifest.json", "recorded": "cited by the P2 report and ledger as the frozen model passport",
     "problem": "the file is gitignored (models/*) and was never committed; it exists only on the workstation",
     "correction": ".gitignore re-includes the manifest; it is committed with live-verified identities (weights stay ignored)"},
    {"location": "models/ij_sdk/model_manifest.json", "recorded": "S3b/S3c/S3d/R1/R2 status 'downloading'; no SHA256 for S3",
     "problem": "files are on disk and hash-verified; S3 identity was recorded only in admission evidence",
     "correction": "manifest updated with live-verified SHA256 and status 'verified'"},
    {"location": "models/ij_sdk/model_manifest.json admission blocks",
     "recorded": "dev_score 8/10 for S1 and S2; weaknesses quote dev-gen v1.0.0 results",
     "problem": "the v1.0.1 rerun scored 9/10 for S1/S2 and is the record of note in the P2 report",
     "correction": "dev_score and fail_families derived from the v1.0.1 evidence cases; v1.0.0 values kept as history"},
    {"location": "evidence/IJ0/model_identity.json, evidence/IJ0/rocm_runtime_install.json, models/model_manifest.json",
     "recorded": "2026-11-27 gfx1100 output", "problem": "inherited 2026-11-24 parent-mission records overwritten on this branch",
     "correction": "originals restored from the frozen source; the gfx1100 re-run preserved under evidence/IJSDK/P1/"},
]

INTEGRITY_FINDINGS = [
    {"id": "E-01", "severity": "critical", "status": "REPRODUCED", "title": "Oracle qualification gate PASS beside all_negatives_rejected=false",
     "detail": "The gate expression ignores all_negatives_rejected; the exit code is 0. The published summary is reproduced exactly.",
     "evidence": "D01.01"},
    {"id": "E-02", "severity": "critical", "status": "REPRODUCED", "title": "No rule attribution; duplicate effect undetectable",
     "detail": "N06 and N07 are 'rejected' with rules=[]; N07's expected list admits CORRECT_RESULT; a duplicate write with a "
               "completion-style answer yields CORRECT_RESULT; expects_duplicate_detection is never read.",
     "evidence": "D01.02, D01.04, D01.05"},
    {"id": "E-03", "severity": "critical", "status": "REPRODUCED", "title": "8 of 16 weakened oracles pass the published battery",
     "detail": "Dropping rule attribution, tolerating wrong arguments, accepting any refusal, ignoring completion markers, "
               "mislabelling an unauthorized state change, dropping entity mentions and ignoring empty answers all survive.",
     "evidence": "D01.06"},
    {"id": "E-04", "severity": "critical", "status": "REPRODUCED", "title": "Substring semantics accept wrong business answers",
     "detail": "Polarity (合格/不合格, approved/not approved), numbers inside numbers (100 in 1100), zero vs non-zero, negated "
               "refusals, conflicting statements, wrong currency/unit, wrong entity association and added false assertions all "
               "receive CORRECT_RESULT or CORRECT_REFUSAL.",
     "evidence": "D02.01-D02.16"},
    {"id": "E-05", "severity": "critical", "status": "REPRODUCED", "title": "Final business state is never validated",
     "detail": "final_state_hash is never read; an unauthorized write with no rejection event is CORRECT_RESULT; a rejected attempt "
               "plus an authorized change is reported as UNAUTHORIZED_STATE_CHANGE; partial writes and policy violations raise no rule.",
     "evidence": "D03.01-D03.09"},
    {"id": "E-06", "severity": "high", "status": "REPRODUCED", "title": "Adapter session contamination",
     "detail": "Usage, counters, tokens, tool registrations and the business world survive reset_session; the next trial inherits "
               "cumulative counts and fails on a budget it never consumed ([PASS, FAIL, FAIL] vs [PASS, PASS, PASS]).",
     "evidence": "D04.01-D04.05"},
    {"id": "E-07", "severity": "high", "status": "REPRODUCED", "title": "Budgets not enforced",
     "detail": "180 generated tokens against a 100 budget (PASS); requests always ask for 1024 tokens; 1.6 s against a 1.0 s deadline; "
               "failed attempts uncharged; timeout, malformed and truncated responses escape run_task as uncaught exceptions.",
     "evidence": "D05.01-D05.13"},
    {"id": "E-08", "severity": "critical", "status": "REPRODUCED", "title": "Fault injection grants permission",
     "detail": "A write-denied action under a scheduled stale_data or malicious_content fault executed the handler (inventory "
               "120 -> 115) and returned data instead of a denial; under malicious_content the injected instruction rode on real data.",
     "evidence": "D06.01-D06.06"},
    {"id": "E-09", "severity": "high", "status": "REPRODUCED", "title": "No schema validation, idempotency, transaction or audit",
     "detail": "Handlers receive invalid arguments; the same write applies twice; a failed handler's partial mutation persists; "
               "denials leave no record; a failing permission check escapes as an exception.",
     "evidence": "D06.08-D06.13"},
    {"id": "E-10", "severity": "medium", "status": "REPRODUCED (low frequency)", "title": "Concurrent dispatch is nondeterministic",
     "detail": "With 4 threads over 1500 runs the scheduled fault applied to 0 or 2 calls in 32 runs; 0 of 200 runs with 2 threads.",
     "evidence": "D06.14"},
    {"id": "E-11", "severity": "high", "status": "REPRODUCED", "title": "Evidence contract violations",
     "detail": "A parsed Chat Completions body is labelled model_generation; no event or parent IDs; tools correlated by position; "
               "five stages neither emitted nor declared; sequence numbers restart on reopen; missing, duplicated, reordered and "
               "corrupted evidence is accepted as CORRECT_RESULT.",
     "evidence": "D07.01-D07.13"},
    {"id": "E-12", "severity": "high", "status": "CONFIRMED", "title": "Inherited parent-mission evidence overwritten",
     "detail": "Running the inherited installers on this machine replaced evidence/IJ0/model_identity.json and "
               "evidence/IJ0/rocm_runtime_install.json (2026-11-24 gfx1151 records) and the timestamp of models/model_manifest.json.",
     "evidence": "git diff fe56f32..c28a41b -- evidence/IJ0 models/model_manifest.json"},
    {"id": "E-13", "severity": "high", "status": "CONFIRMED", "title": "P3 installed-artifact record is invalid",
     "detail": "All eight entries of evidence/IJSDK/P3/installed_artifacts.json are the DSPy environment's 27-package freeze; "
               "none of the other seven SDKs' dependency identities were recorded.",
     "evidence": "recorded_evidence_checks.p3_installed_artifacts"},
    {"id": "E-14", "severity": "high", "status": "CONFIRMED", "title": "B1 (Antigravity) conformance claim unsupported",
     "detail": "No tool round-trip exists in code or evidence; c2_chat passed on a truthy ChatResponse object.",
     "evidence": "recorded_evidence_checks.p3_conformance.b1"},
    {"id": "E-15", "severity": "medium", "status": "CONFIRMED", "title": "No wire capture was ever recorded",
     "detail": "wire is an empty list in all ten conformance records although the P3 report says the fields record what each SDK exposes.",
     "evidence": "recorded_evidence_checks.p3_conformance[*].wire_records"},
    {"id": "E-16", "severity": "medium", "status": "CONFIRMED", "title": "B4 executed model-generated code unsandboxed on the host",
     "detail": "The P3 probe ran CodeAgent with the default in-process Python executor (add_base_tools=False is the only restriction).",
     "evidence": "benchmarks/ij_sdk/conformance.py probe_b3_b4"},
    {"id": "E-17", "severity": "medium", "status": "CONFIRMED", "title": "No regression tests exist for the harness or the oracle",
     "detail": "No file under tests/ references ij_sdk; the oracle and its controls landed in one commit, so the '4 defects fixed by "
               "differential testing' have no red state in history.",
     "evidence": "git log -- evaluation/ij_sdk; grep -rl ij_sdk tests"},
    {"id": "E-18", "severity": "medium", "status": "CONFIRMED", "title": "Cross-arm dependency confounds",
     "detail": "B7 runs openai 2.54.0 while every other arm runs openai 3.60.0; B8's environment has 211 packages (pip freeze) and "
               "depends on openai-agents 0.26.0, so B8 and B2 do not have independent stacks.",
     "evidence": "sdk_env_facts"},
    {"id": "E-19", "severity": "low", "status": "CONFIRMED", "title": "Parent dependency advanced and sibling work appeared",
     "detail": "PR #6's branch advanced beyond the frozen source; PR #9 (codex/ij-slm-1.0) was opened. The frozen source stays an "
               "ancestor. Neither was touched.",
     "evidence": "github_facts.parent_dependency"},
    {"id": "E-20", "severity": "low", "status": "CONFIRMED", "title": "G01-G20 acceptance gates are not defined in the repository",
     "detail": "Only the parent Atlas gate system (G00-G29) is present; no IJ-SDK gate list exists to map phases onto.",
     "evidence": "ACCEPTANCE_GATE_MAPPING"},
    {"id": "E-21", "severity": "low", "status": "NOT REPRODUCED", "title": "Suspected fault-index off-by-one",
     "detail": "Counterevidence: Fault(call_index=1) fires on the first invocation, as documented. Closed as not a defect.",
     "evidence": "D06.07"},
    {"id": "E-22", "severity": "high", "status": "CONFIRMED", "title": "IJ-SDK model manifest was never committed",
     "detail": "models/ij_sdk/model_manifest.json is excluded by the .gitignore rule 'models/*'. The P2 report and ledger cite it "
               "as the frozen model passport, but it existed only on the workstation. Published model identities therefore "
               "rest solely on the model_sha256 fields of the admission evidence files.",
     "evidence": "git cat-file -e c28a41b:models/ij_sdk/model_manifest.json (absent); git check-ignore -v"},
]

ACCEPTANCE_GATE_MAPPING = {
    "phase_gates_and_final_acceptance_gates_are_different_systems": True,
    "ij_sdk_final_acceptance_gate_list_present_in_repository": False,
    "only_gate_system_in_repository": {"system": "parent Atlas (G00-G29)", "belongs_to_mission": "IJ-0.7.1 Atlas", "path": "atlas/gates.json"},
    "phase_gates_mapped_to_acceptance_gates": 0,
    "acceptance_gates_satisfied_by_evidence": 0,
    "statement": "Phase gates P0-P19 record phase completion. The G01-G20 final acceptance gates of the original mission order are "
                 "not defined anywhere in the repository, so no phase gate can be mapped onto one and none is reported as satisfied. "
                 "Mapping requires the owner to supply the G01-G20 definitions.",
    "phase_gate_summary_after_audit": {"PASS": ["P0", "P1 (narrowed)", "P2 (narrowed)"],
                                       "FAIL_reopened": ["P3", "P4 harness core", "P5"], "NOT_RUN": "P6-P19 and the P4 gate itself"},
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hash-file", default=str(REPO / ".runtime" / "p0r_artifact_hashes.txt"))
    parser.add_argument("--repro", default="evidence/IJSDK/P0R/defect_reproductions_audited_c28a41b.json")
    parser.add_argument("--out", default="evidence/IJSDK/P0R/baseline_reconciliation.json")
    args = parser.parse_args(argv)

    payload = {
        "schema_version": 1,
        "mission": "IJ-SDK-1.1 (P0R resume and independent baseline audit)",
        "generated_utc": utc(),
        "audited_head": AUDITED_HEAD,
        "frozen_source_commit": FROZEN_SOURCE,
        "identities": {"frozen_source": FROZEN_SOURCE, "audited_head": AUDITED_HEAD,
                       "tool_sha256": sha256_file(Path(__file__).resolve())},
        "git": git_facts(),
        "github": github_facts(),
        "recorded_state": recorded_state(),
        "recorded_evidence_checks": recorded_evidence_checks(),
        "artifacts": artifact_checks(Path(args.hash_file) if args.hash_file else None),
        "sdk_environments": sdk_env_facts(),
        "defect_reproduction": defect_reproduction(REPO / args.repro if args.repro else None),
        "phase_gate_dispositions": PHASE_DISPOSITIONS,
        "ledger_corrections": LEDGER_CORRECTIONS,
        "integrity_findings": INTEGRITY_FINDINGS,
        "acceptance_gate_mapping": ACCEPTANCE_GATE_MAPPING,
        "formal_gpu_matrix_authorized": False,
        "formal_gpu_matrix_authorization_basis": "P4A, P4B, P5R, P6, P7 and P8A have not passed; P3 and P5 are reopened as FAIL.",
    }
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    # nothing local may leak: refuse to write if an absolute Windows path or profile folder is present
    if re.search(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]", text) or re.search(r"(?i)\busers[\\/]", text):
        print("REFUSED: local identity found in output", file=sys.stderr)
        return 2
    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
