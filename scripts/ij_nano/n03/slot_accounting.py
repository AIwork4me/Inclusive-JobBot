#!/usr/bin/env python3
"""N03-D01 slot accounting (IJ-NANO-1.3S continuation order section 2).

All slot accounting is GENERATED from the frozen case roster x the model
registry - no independently editable totals anywhere. Emits
evidence/IJNANO/N03/dataset/slot_manifest.json and fails closed on missing,
duplicated or misclassified slots.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
BASE = ROOT / "evaluation" / "ij_nano" / "n03"
ROSTER = BASE / "dataset" / "public" / "n03_cases.public.jsonl"
REGISTRY = BASE / "model_registry.json"
OUT = ROOT / "evidence" / "IJNANO" / "N03" / "dataset" / "slot_manifest.json"

BATCH_OF = {**{f"C{i:02d}": "A" for i in range(1, 9)},
            **{f"C{i:02d}": "B" for i in range(9, 17)},
            **{f"C{i:02d}": "C" for i in range(17, 25)},
            **{f"C{i:02d}": "D" for i in range(25, 33)}}


def account(roster_rows: list[dict], registry: dict) -> tuple[dict, list[str]]:
    errors: list[str] = []
    models = [m["slot"] for m in registry["primary_models"]]
    per_model = registry["slot_policy"]["primary_slots_per_case"]
    pol = registry["slot_policy"]
    seen: set[str] = set()
    per_prim: dict[str, dict] = {}

    for r in roster_rows:
        cid, prim = r.get("case_id"), r.get("primitive")
        if not isinstance(cid, str) or not re.match(
                r"^n03-C\d\d-[a-z0-9_]+-[dc]\d{2}$", cid):
            errors.append(f"malformed case id {cid!r}")
            continue
        if cid in seen:
            errors.append(f"duplicate case id {cid}")
            continue
        seen.add(cid)
        if prim not in BATCH_OF:
            errors.append(f"{cid}: unknown primitive {prim!r}")
            continue
        if r.get("split") not in ("development", "confirmation"):
            errors.append(f"{cid}: misclassified split {r.get('split')!r}")
            continue
        if r.get("language") not in ("en", "zh"):
            errors.append(f"{cid}: bad language {r.get('language')!r}")
            continue
        slot = per_prim.setdefault(prim, {
            "batch": BATCH_OF[prim], "dev_cases": 0, "conf_cases": 0,
            "families": set(), "dev_families": set(), "conf_families": set()})
        if r["split"] == "development":
            slot["dev_cases"] += 1
            slot["dev_families"].add(r["family"])
        else:
            slot["conf_cases"] += 1
            slot["conf_families"].add(r["family"])
        slot["families"].add(r["family"])

    complete = True
    for prim in sorted(BATCH_OF):
        p = per_prim.get(prim)
        if p is None:
            complete = False
            continue
        if p["dev_cases"] != pol["dev_cases_per_primitive"]:
            errors.append(f"{prim}: {p['dev_cases']} dev cases != "
                          f"{pol['dev_cases_per_primitive']}")
        if p["conf_cases"] != pol["conf_cases_per_primitive"]:
            errors.append(f"{prim}: {p['conf_cases']} conf cases != "
                          f"{pol['conf_cases_per_primitive']}")
        if p["dev_families"] & p["conf_families"]:
            errors.append(f"{prim}: family shared across splits")
        p.pop("families"), p.pop("dev_families"), p.pop("conf_families")
        p["dev_slots"] = p["dev_cases"] * per_model
        p["conf_slots"] = p["conf_cases"] * per_model

    batches: dict[str, dict] = {}
    for prim, p in per_prim.items():
        b = batches.setdefault(p["batch"], {"primitives": 0, "dev_cases": 0,
                                            "conf_cases": 0, "dev_slots": 0,
                                            "conf_slots": 0})
        b["primitives"] += 1
        for k in ("dev_cases", "conf_cases", "dev_slots", "conf_slots"):
            b[k] += p[k]
    manifest = {
        "schema": "ij_nano.n03.slot_manifest.v1",
        "complete": complete and not errors,
        "models": models,
        "primitives_built": len(per_prim),
        "per_primitive": per_prim,
        "per_batch": batches,
        "totals": {
            "dev_cases": sum(p["dev_cases"] for p in per_prim.values()),
            "conf_cases": sum(p["conf_cases"] for p in per_prim.values()),
            "dev_slots": sum(p["dev_slots"] for p in per_prim.values()),
            "conf_slots": sum(p["conf_slots"] for p in per_prim.values()),
            "primary_slots": sum(p["dev_slots"] + p["conf_slots"]
                                 for p in per_prim.values())},
        "target_when_complete": {
            "dev_cases": 640, "conf_cases": 320,
            "dev_slots": pol["dev_cases_per_primitive"] * 32 * per_model,
            "conf_slots": pol["conf_cases_per_primitive"] * 32 * per_model,
            "primary_slots": pol["primary_total_target"]},
        "errors": errors,
    }
    return manifest, errors


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    roster = [json.loads(l) for l in
              ROSTER.read_text(encoding="utf-8").splitlines()]
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    manifest, errors = account(roster, registry)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    t = manifest["totals"]
    print(f"slot manifest: {manifest['primitives_built']}/32 primitives, "
          f"{t['dev_cases']} dev + {t['conf_cases']} conf cases, "
          f"{t['primary_slots']} primary slots "
          f"(complete={manifest['complete']}); errors={len(errors)}")
    for e in errors[:10]:
        print(f"  - {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
