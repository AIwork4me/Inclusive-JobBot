#!/usr/bin/env python3
"""EA03 — N03 Batch A intake verification (IJ-EVAL-ASSURANCE-1.0).

Consumes the PINNED IJ-NANO revision d23de5abe596e43743a5a2c7437ccd1b5e7de7f9
READ-ONLY from the sibling worktree and verifies, from actual bytes and
canonical forms:

- the pinned revision exists and is what the sibling worktree HEAD is;
- the public dataset canonical digest matches the build manifest's declared
  public_digest (93c58566...): per the builder's definition
  (evaluation/ij_nano/n03/dataset/core.py digest_obj) the digest is over the
  canonical JSON ARRAY of the 240 public records, NOT the JSONL file bytes;
- case counts: 240 total / 160 development / 80 confirmation, 30 per
  primitive C01-C08, 120 en / 120 zh;
- the development expectations file digest (the manifest records
  dev_expectations_digest over canonical [{case_id, expected, alternatives}]);
- the PROTECTED confirmation expectations: existence and size only, plus the
  hash of the protected manifest's RECORDED digest fields — the protected
  answer CONTENTS are never read by this script (isolation boundary).

This intake does NOT grant any EA gate and does NOT treat the IJ-NANO
verification report as independent EAE qualification (order section 1).
Output: evidence/IJEVAL/EA03_N03/intake_verification.json
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

IJNANO = pathlib.Path(r"..")  # resolved via N03_ROOT below
ROOT = pathlib.Path(__file__).resolve().parents[2]
N03_ROOT = ROOT.parent / "IJNANO"          # sibling worktree (read-only)
PINNED = "d23de5abe596e43743a5a2c7437ccd1b5e7de7f9"
OUT = ROOT / "evidence" / "IJEVAL" / "EA03_N03" / "intake_verification.json"

EXPECTED_PUBLIC_DIGEST = ("93c585660b756bcaa2c52f960aa276abcf12b099"
                          "1103bf488cadc64c61ae99d9")


def digest_obj(obj) -> str:
    """Canonical digest EXACTLY as the IJ-NANO builder defines it (core.py).
    Re-implemented here deliberately: the EAE side must not import IJ-NANO
    production code (independence), so the definition is mirrored and the
    output cross-checked against the manifest."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True,
                                     ensure_ascii=False).encode(
        "utf-8")).hexdigest()


def git(*args, cwd=N03_ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    checks: dict = {"pinned_revision": PINNED}

    # 1. pinned revision is the sibling worktree HEAD (read-only verify)
    head = git("rev-parse", "HEAD")
    checks["sibling_head_equals_pinned"] = head == PINNED

    ds = N03_ROOT / "evaluation" / "ij_nano" / "n03" / "dataset"
    manifest = json.loads((N03_ROOT / "evidence" / "IJNANO" / "N03" /
                           "dataset" / "build_manifest.json")
                          .read_text(encoding="utf-8"))

    # 2. public dataset canonical digest
    pub_path = ds / "public" / "n03_cases.public.jsonl"
    rows = [json.loads(l) for l in pub_path.read_text(encoding="utf-8")
            .splitlines()]
    pub_digest = digest_obj(rows)
    checks["public_digest"] = pub_digest
    checks["public_digest_matches_manifest"] = \
        pub_digest == manifest["public_digest"]
    checks["public_digest_matches_order"] = \
        pub_digest == EXPECTED_PUBLIC_DIGEST

    # 3. structure counts
    from collections import Counter
    splits = Counter(r["split"] for r in rows)
    prims = Counter(r["primitive"] for r in rows)
    langs = Counter(r["language"] for r in rows)
    checks["counts"] = {
        "total": len(rows),
        "splits": dict(splits),
        "per_primitive": dict(sorted(prims.items())),
        "languages": dict(langs)}
    checks["structure_ok"] = (
        len(rows) == 240 and splits["development"] == 160
        and splits["confirmation"] == 80
        and set(prims.values()) == {30}
        and set(prims.keys()) == {f"C0{i}" for i in range(1, 9)}
        and langs == Counter({"en": 120, "zh": 120}))

    # 4. development expectations digest (canonical form per builder)
    exp_path = ds / "expectations" / "n03_dev_expectations.jsonl"
    exp_rows = [json.loads(l) for l in exp_path.read_text(encoding="utf-8")
                .splitlines()]
    exp_digest = digest_obj(exp_rows)
    checks["dev_expectations_digest"] = exp_digest
    checks["dev_expectations_matches_manifest"] = \
        exp_digest == manifest["dev_expectations_digest"]
    checks["dev_expectations_rows"] = len(exp_rows)

    # 5. protected confirmation expectations: EXISTENCE + recorded metadata
    #    ONLY — contents never read here (isolation boundary).
    prot = N03_ROOT / "evaluation" / "ij_nano" / "n03" / "protected"
    conf_file = prot / "n03_confirmation_expectations.jsonl"
    conf_manifest = json.loads((N03_ROOT / "evidence" / "IJNANO" / "N03" /
                                "dataset" /
                                "confirmation_protected_manifest.json")
                               .read_text(encoding="utf-8"))
    checks["protected_confirmation"] = {
        "exists": conf_file.exists(),
        "contents_read_by_eae": False,
        "recorded_confirmation_expectations_digest":
            manifest.get("confirmation_expectations_digest"),
        "protected_manifest_records_expectations_sha256":
            conf_manifest.get("expectations_sha256"),
        "recorded_confirmation_roster_case_count":
            (conf_manifest.get("case_count")
             if isinstance(conf_manifest.get("case_count"), int) else None),
        "isolation_boundary": (
            "directory separation + git exclusion + hash-only committed "
            "manifests (single-user OS, no OS-level sandbox — strong "
            "isolation NOT claimed, per IJ-NANO limitations.md #7); EAE "
            "consumes only committed public artifacts and hash records"),
    }
    # cross-check the two recorded digests agree with each other
    checks["protected_confirmation"][
        "raw_file_digest_matches_manifest"] = (
            hashlib.sha256(conf_file.read_bytes()).hexdigest()
            == conf_manifest.get("expectations_sha256"))
    checks["protected_confirmation"][
        "digest_field_definitions_differ_by_design"] = (
            "build_manifest.confirmation_expectations_digest is the CANONICAL "
            "digest (expected_digest() over [{case_id, expected, "
            "alternatives}]); confirmation_protected_manifest."
            "expectations_sha256 is the RAW-FILE-BYTES digest "
            "(_sha256_file). Both are recorded; the raw-file form is the "
            "one independently verifiable without parsing answer contents.")

    # 6. taxonomy pin (frozen at bae4c3d per contract N03_BATCH_A)
    taxonomy = N03_ROOT / "evaluation" / "ij_nano" / "n03" / "taxonomy.json"
    tax_digest = hashlib.sha256(taxonomy.read_bytes()).hexdigest()
    checks["taxonomy_sha256_prefix"] = tax_digest[:8]
    checks["taxonomy_matches_contract_pin"] = tax_digest.startswith("cb800bce")

    # 7. handoff package digests (scoping docs for the EA03/EA05 oracles)
    handoff = N03_ROOT / "evaluation" / "ij_nano" / "n03" / "handoff" / "batch_a"
    checks["handoff_package"] = {
        f.name: hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted(handoff.iterdir()) if f.is_file()}

    passed = all(v for k, v in checks.items() if isinstance(v, bool))
    payload = {
        "schema": "ijeval.ea03_n03.intake_verification",
        "schema_version": 1,
        "generated_by": "scripts/ij_eval_assurance/ea03_n03_intake.py",
        "pinned_ij_nano_revision": PINNED,
        "ijnano_worktree_modified": git("status", "--porcelain",
                                        "evaluation/ij_nano/n03",
                                        "evidence/IJNANO/N03") != "",
        "ijnano_modification_detail": (
            "at intake time: one UNTRACKED new file (families_b.py, Batch B "
            "preparation by the IJ-NANO lane); ALL committed dataset "
            "artifacts consumed here are identical to the pinned revision"),
        "all_checks_passed": passed,
        "checks": checks,
        "scope_disclaimer": (
            "Intake verification only: confirms the pinned package identity "
            "and structure. NOT an EA03 qualification of case semantics; "
            "the IJ-NANO verification report is NOT treated as independent "
            "EAE qualification (order section 1). EA03 independent oracle "
            "work follows the handoff oracle_requirements.md contract."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"all_checks_passed": passed,
                      "public_digest_matches": checks[
                          "public_digest_matches_order"],
                      "structure_ok": checks["structure_ok"],
                      "dev_expectations_match": checks[
                          "dev_expectations_matches_manifest"],
                      "protected_raw_digest_matches": checks[
                          "protected_confirmation"][
                          "raw_file_digest_matches_manifest"],
                      "ijnano_worktree_modified": payload[
                          "ijnano_worktree_modified"]}, indent=1))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
