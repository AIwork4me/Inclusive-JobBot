#!/usr/bin/env python3
"""N03-B2 dataset build (IJ-NANO-1.3S).

Deterministic: the development roster derives from the committed DEV_SEED;
the confirmation roster derives from a PROTECTED seed file that never enters
git (answer-bearing). Public payloads never contain expectations. Outputs:

  evaluation/ij_nano/n03/dataset/public/n03_cases.public.jsonl
  evaluation/ij_nano/n03/dataset/expectations/n03_dev_expectations.jsonl
  evaluation/ij_nano/n03/protected/n03_confirmation_expectations.jsonl  (local)
  evidence/IJNANO/N03/dataset/build_manifest.json
  evidence/IJNANO/N03/dataset/confirmation_protected_manifest.json (hashes)

Usage: python -I evaluation/ij_nano/n03/dataset/build.py [--dev-only]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BASE = ROOT / "evaluation" / "ij_nano" / "n03"
sys.path.insert(0, str(ROOT))

from evaluation.ij_nano.n03.dataset import (CONF_SEED_FILE_NAME,  # noqa: E402
                                            DEV_SEED, FAMILIES_BY_PRIMITIVE)
from evaluation.ij_nano.n03.dataset.core import (digest_obj, expected_digest,  # noqa: E402
                                                 roster_digest,
                                                 split_lang_counts)

CASES_PER_FAMILY = 10
PUBLIC_DIR = BASE / "dataset" / "public"
EXPECT_DIR = BASE / "dataset" / "expectations"
PROT_DIR = BASE / "protected"
EVID_DIR = ROOT / "evidence" / "IJNANO" / "N03" / "dataset"


def emit_family(fam, seed_key: str, include: bool) -> list:
    if not include:
        return []
    cases = []
    for seq in range(CASES_PER_FAMILY):
        language = "en" if seq % 2 == 0 else "zh"
        rng = random.Random(f"{seed_key}:{fam.family_id}:{seq}")
        cases.append(fam.emit(rng, language, seq))
    return cases


def write_jsonl(path: pathlib.Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev-only", action="store_true",
                    help="skip confirmation build (protected seed absent)")
    args = ap.parse_args()

    prot_seed_file = PROT_DIR / CONF_SEED_FILE_NAME
    conf_available = prot_seed_file.is_file() and not args.dev_only
    if not conf_available and not args.dev_only:
        print(f"NOTE: protected seed {prot_seed_file} absent -> dev-only "
              f"build (confirmation expectations not regenerated)")

    dev_cases: list = []
    conf_cases: list = []
    for prim in sorted(FAMILIES_BY_PRIMITIVE):
        for fam in FAMILIES_BY_PRIMITIVE[prim]:
            target = dev_cases if fam.split == "development" else conf_cases
            seed = DEV_SEED if fam.split == "development" else \
                prot_seed_file.read_text(encoding="utf-8")
            target.extend(emit_family(fam, seed, True))

    write_jsonl(PUBLIC_DIR / "n03_cases.public.jsonl",
                [c.public_view() for c in dev_cases + conf_cases])
    write_jsonl(EXPECT_DIR / "n03_dev_expectations.jsonl",
                [{"case_id": c.case_id, "expected": c.expected,
                  "alternatives": c.alternatives} for c in dev_cases])

    prims_built = sorted(FAMILIES_BY_PRIMITIVE)
    manifest = {
        "schema": "ij_nano.n03.dataset.build_manifest.v1",
        "batches_built": sorted({("A" if p <= "C08" else
                                  "B" if p <= "C16" else
                                  "C" if p <= "C24" else "D")
                                 for p in prims_built}),
        "primitives": prims_built,
        "dev_seed_policy": "committed constant DEV_SEED (answers derivable "
                           "only from expectations artifacts; dev answers "
                           "are publishable by design)",
        "confirmation_seed_policy": (
            "protected file never committed; without it the confirmation "
            "roster cannot be regenerated (answer-bearing seed)"
            if conf_available else
            "protected seed absent: dev-only build"),
        "dev_cases": len(dev_cases),
        "confirmation_cases": len(conf_cases),
        "counts": split_lang_counts(dev_cases + conf_cases),
        "public_digest": roster_digest(dev_cases + conf_cases),
        "dev_expectations_digest": expected_digest(dev_cases),
        "confirmation_expectations_digest": (
            expected_digest(conf_cases) if conf_cases else None),
        "cases_per_family": CASES_PER_FAMILY,
    }
    EVID_DIR.mkdir(parents=True, exist_ok=True)
    if conf_cases:
        write_jsonl(PROT_DIR / "n03_confirmation_expectations.jsonl",
                    [{"case_id": c.case_id, "expected": c.expected,
                      "alternatives": c.alternatives} for c in conf_cases])
        conf_file = PROT_DIR / "n03_confirmation_expectations.jsonl"
        (EVID_DIR / "confirmation_protected_manifest.json").write_text(
            json.dumps({
                "schema": "ij_nano.n03.confirmation_protected_manifest.v1",
                "note": "hash-only manifest; the expectation file itself is "
                        "local-only and never published",
                "case_count": len(conf_cases),
                "case_ids_digest": digest_obj([c.case_id for c in conf_cases]),
                "expectations_sha256": _sha256_file(conf_file),
            }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (EVID_DIR / "build_manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"built: {len(dev_cases)} dev + {len(conf_cases)} confirmation "
          f"cases; manifest -> {EVID_DIR / 'build_manifest.json'}")
    return 0


def _sha256_file(p: pathlib.Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
