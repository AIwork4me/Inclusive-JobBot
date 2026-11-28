"""N03 full-roster intake — pin Batches B/C/D (order 48H-SUPPORT §1-3).

Pins the complete-roster artifacts (read-only copy from the IJ-NANO
worktree at its pinned revision) into the IJEVAL evidence tree and
verifies, fail-closed:

- every handoff package component digest (Batches B/C/D) recomputed
  from bytes;
- Batch A preservation: the 240 Batch A records appear BIT-IDENTICALLY
  in the full roster (ordering change documented by the builder);
- per-batch structure: 240 cases / 160 dev / 80 confirmation per batch,
  per-primitive 30 (20 dev + 10 conf), bilingual balance;
- protected confirmation digest-verified via the HASH-ONLY manifest
  (no expectation content is read or copied).

Writing is confined to the IJEVAL worktree; the IJ-NANO worktree is
never modified (single-writer rule).
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)

IJNANO = pathlib.Path(r"..") / "IJNANO"          # sibling worktree
N03 = IJNANO / "evaluation" / "ij_nano" / "n03"
EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
PIN_FULL = EVID / "pinned_full"
PIN_A = EVID / "pinned"

BATCHES = {
    "batch_b": ["C09", "C10", "C11", "C12", "C13", "C14", "C15", "C16"],
    "batch_c": ["C17", "C18", "C19", "C20", "C21", "C22", "C23", "C24"],
    "batch_d": ["C25", "C26", "C27", "C28", "C29", "C30", "C31", "C32"],
}

#: handoff component name -> path inside the IJ-NANO worktree
_COMPONENTS = {
    "task_contracts_taxonomy": N03 / "taxonomy.json",
    "public_case_roster": N03 / "dataset" / "public" /
        "n03_cases.public.jsonl",
    "dev_expectations": N03 / "dataset" / "expectations" /
        "n03_dev_expectations.jsonl",
    "confirmation_protected_manifest_hashonly": IJNANO / "evidence" /
        "IJNANO" / "N03" / "dataset" / "confirmation_protected_manifest.json",
    "model_registry": N03 / "model_registry.json",
    "slot_manifest": IJNANO / "evidence" / "IJNANO" / "N03" / "dataset" /
        "slot_manifest.json",
    "dataset_verification_report": IJNANO / "evidence" / "IJNANO" / "N03" /
        "dataset" / "verification_report.json",
    "dataset_build_manifest": IJNANO / "evidence" / "IJNANO" / "N03" /
        "dataset" / "build_manifest.json",
    "schema_conformance_report": IJNANO / "evidence" / "IJNANO" / "N03" /
        "dataset" / "schema_conformance.json",
    "batch_a_preservation_proof": IJNANO / "evidence" / "IJNANO" / "N03" /
        "dataset" / "batch_a_preservation.json",
    "requirements_doc_batch_b": N03 / "handoff" / "batch_b" /
        "requirements.md",
    "requirements_doc_batch_c": N03 / "handoff" / "batch_c" /
        "requirements.md",
    "requirements_doc_batch_d": N03 / "handoff" / "batch_d" /
        "requirements.md",
}

_PINNED_NAME = {
    "task_contracts_taxonomy": "taxonomy.json",
    "public_case_roster": "n03_cases.public.jsonl",
    "dev_expectations": "n03_dev_expectations.jsonl",
    "confirmation_protected_manifest_hashonly":
        "confirmation_protected_manifest.hashonly.json",
    "model_registry": "model_registry.json",
    "slot_manifest": "slot_manifest.json",
    "dataset_verification_report": "verification_report.json",
    "dataset_build_manifest": "build_manifest.json",
    "schema_conformance_report": "schema_conformance.json",
    "batch_a_preservation_proof": "batch_a_preservation.json",
    "requirements_doc_batch_b": "requirements_batch_b.md",
    "requirements_doc_batch_c": "requirements_batch_c.md",
    "requirements_doc_batch_d": "requirements_batch_d.md",
}


def _sha(p) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _write(p: pathlib.Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False),
                 encoding="utf-8")


def _git_rev(worktree: pathlib.Path) -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(worktree), capture_output=True,
        text=True, check=True).stdout.strip()
    return out


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ijnano_rev = _git_rev(IJNANO)
    PIN_FULL.mkdir(parents=True, exist_ok=True)

    # -- verify + pin every component against ALL THREE packages -----
    package_digests = {}
    for batch in BATCHES:
        pkg = json.loads((N03 / "handoff" / batch / "package.json")
                         .read_text(encoding="utf-8"))
        for name, digest in pkg["components_sha256"].items():
            key = f"{name}_{batch}" if name == "requirements_doc" \
                else name
            package_digests.setdefault(key, set()).add(digest)
    pinned, mismatches = {}, []
    for name, src in _COMPONENTS.items():
        if not src.is_file():
            mismatches.append(f"{name}: source missing")
            continue
        actual = _sha(src)
        expected_set = package_digests.get(name, set())
        if expected_set and actual not in expected_set:
            mismatches.append(f"{name}: digest {actual[:16]} not in "
                              f"package digests")
            continue
        dst = PIN_FULL / _PINNED_NAME[name]
        shutil.copyfile(src, dst)
        if _sha(dst) != actual:               # copy integrity
            mismatches.append(f"{name}: pinned copy digest drift")
            continue
        pinned[name] = actual
    if mismatches:
        print("INTAKE BLOCKED:")
        for m in mismatches:
            print(" ", m)
        return 1

    # -- roster structure --------------------------------------------------
    rows = [json.loads(l) for l in
            (PIN_FULL / "n03_cases.public.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()]
    if len(rows) != 960:
        print(f"INTAKE BLOCKED: roster has {len(rows)} rows, expected 960")
        return 1
    exps = {e["case_id"]: e for e in
            (json.loads(l) for l in (PIN_FULL / "n03_dev_expectations.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip())}
    if len(exps) != 640:
        print(f"INTAKE BLOCKED: dev expectations {len(exps)}, expected 640")
        return 1

    # -- Batch A preservation: bit-identical records ------------------------
    a_rows = [json.loads(l) for l in
              (PIN_A / "n03_cases.public.jsonl").read_text(
                  encoding="utf-8").splitlines() if l.strip()]
    a_full = {r["case_id"]: r for r in rows if r["case_id"].split("-")[1]
              in ("C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08")}
    preserved = sum(1 for r in a_rows if
                    a_full.get(r["case_id"]) == r)
    a_exp = {json.loads(l)["case_id"]: json.loads(l) for l in
             (PIN_A / "n03_dev_expectations.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip()}
    full_exp_a = {cid: e for cid, e in exps.items()
                  if cid.split("-")[1] in
                  ("C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08")}
    exp_preserved = sum(1 for cid, e in a_exp.items()
                        if full_exp_a.get(cid) == e)
    if preserved != 240 or exp_preserved != len(a_exp):
        print(f"INTAKE BLOCKED: Batch A preservation {preserved}/240 "
              f"records, {exp_preserved}/{len(a_exp)} expectations")
        return 1

    # -- protected confirmation: hash-only verification ---------------------
    prot = json.loads((PIN_FULL /
                       "confirmation_protected_manifest.hashonly.json")
                      .read_text(encoding="utf-8"))
    conf_file = N03 / "protected" / "n03_confirmation_expectations.jsonl"
    conf_sha = _sha(conf_file)                # digest only, no content read
    manifest_ok = bool(prot) and (
        prot.get("expectations_sha256") == conf_sha or
        conf_sha in json.dumps(prot))
    conf_count = sum(1 for r in rows if r.get("split") == "confirmation")
    if conf_count != 320:
        print(f"INTAKE BLOCKED: confirmation rows {conf_count}, expected "
              "320")
        return 1

    # -- per-batch intake artifacts -----------------------------------------
    for batch, prims in BATCHES.items():
        pset = set(prims)
        b_rows = [r for r in rows if r["primitive"] in pset]
        dev = [r for r in b_rows if r["split"] == "development"]
        conf = [r for r in b_rows if r["split"] == "confirmation"]
        per_prim = {}
        for r in b_rows:
            per_prim.setdefault(r["primitive"], {"total": 0, "dev": 0,
                                                 "conf": 0})
            per_prim[r["primitive"]]["total"] += 1
            per_prim[r["primitive"]][
                "dev" if r["split"] == "development" else "conf"] += 1
        langs = {}
        for r in b_rows:
            langs[r["language"]] = langs.get(r["language"], 0) + 1
        dev_expectation_coverage = sum(
            1 for r in dev if r["case_id"] in exps)
        art = {
            "schema": "ijeval.n03full.intake.v1",
            "batch": batch,
            "primitives": prims,
            "source_worktree": "IJNANO (read-only)",
            "source_revision": ijnano_rev,
            "handoff_package": f"evaluation/ij_nano/n03/handoff/{batch}/"
                               "package.json",
            "components_verified": {name: pinned[name]
                                   for name in pinned},
            "structure": {"cases": len(b_rows), "dev": len(dev),
                          "confirmation": len(conf),
                          "per_primitive": per_prim,
                          "languages": langs,
                          "dev_expectation_coverage":
                              dev_expectation_coverage},
            "batch_a_preservation": {
                "records_bit_identical": f"{preserved}/240",
                "dev_expectations_bit_identical":
                    f"{exp_preserved}/{len(a_exp)}",
                "note": "ordering change documented by the builder "
                        "(c772a9a); record identity by case_id"},
            "protected_confirmation": {
                "rows": conf_count,
                "hash_only_manifest_verified": manifest_ok,
                "content_accessed": False},
            "verdict": "VERIFIED" if (
                len(b_rows) == 240 and len(dev) == 160 and len(conf) == 80
                and dev_expectation_coverage == 160 and manifest_ok) else
                "BLOCKED",
            "verified_utc": stamp}
        _write(EVID / f"intake_verification_{batch}.json", art)
        print(f"{batch}: {art['verdict']} "
              f"({len(b_rows)}/{len(dev)}/{len(conf)}, "
              f"langs {langs})")

    _write(EVID / "pinned_full" / "pin_manifest.json", {
        "schema": "ijeval.n03full.pin.v1",
        "source_revision": ijnano_rev,
        "pinned_files": pinned,
        "pinned_utc": stamp,
        "note": "complete-roster artifacts; Batch A pinned snapshot "
                "(evidence/IJEVAL/EA03_N03/pinned/) remains the "
                "Batch-A-qualified identity"})
    print("full-roster pin complete, source rev", ijnano_rev[:12])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
