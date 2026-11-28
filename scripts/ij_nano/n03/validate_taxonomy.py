#!/usr/bin/env python3
"""N03-B1 taxonomy contract validator (IJ-NANO-1.3S order 6.1).

Validates evaluation/ij_nano/n03/taxonomy.json against its schema with a
dependency-free structural check (schema file is authoritative; checks are
re-implemented here so the validator needs no external jsonschema package -
the two must stay in sync, pinned by the negative-control test suite).

Checks beyond schema shape:
- exactly C01..C32, each exactly once, batch grouping consistent with the
  frozen schedule (C01-C08=A, C09-C16=B, C17-C24=C, C25-C32=D);
- no duplicate capability names;
- every applicable protocol is a declared vocabulary key;
- isolation labels distinguish isolated/diagnostic capability from agentic
  autonomy claims, and diagnostic labels carry an explicit note;
- digest output (sha256) for freezing the taxonomy identity.

Exit 0 = valid; exit 1 = invalid (fail closed; findings on stderr).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
TAXONOMY = ROOT / "evaluation" / "ij_nano" / "n03" / "taxonomy.json"
SCHEMA = ROOT / "evaluation" / "ij_nano" / "n03" / "taxonomy.schema.json"

REQUIRED_FIELDS = [
    "primitive_id", "capability", "batch", "cognitive_definition",
    "required_observable_behavior", "capability_isolation",
    "public_task_information", "output_contract", "applicable_protocols",
    "independent_ground_truth", "correct_witnesses", "incorrect_witnesses",
    "valid_alternatives", "boundary_cases", "difficulty_dimensions",
    "failure_taxonomy", "additional_eae_dependencies",
]
BATCH_OF = {**{f"C{i:02d}": "A" for i in range(1, 9)},
            **{f"C{i:02d}": "B" for i in range(9, 17)},
            **{f"C{i:02d}": "C" for i in range(17, 25)},
            **{f"C{i:02d}": "D" for i in range(25, 33)}}
ISOLATION_LABELS = {"isolated_capability", "diagnostic_isolation",
                    "agentic_component"}


def _errors(doc: dict, schema: dict) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != "ij_nano.n03.taxonomy.v1":
        errs.append(f"schema tag mismatch: {doc.get('schema')!r}")
    primitives = doc.get("primitives")
    if not isinstance(primitives, dict) or len(primitives) != 32:
        errs.append(f"primitives: expected 32 entries, got "
                    f"{len(primitives) if isinstance(primitives, dict) else type(primitives).__name__}")
        return errs
    if set(primitives) != set(BATCH_OF):
        missing = sorted(set(BATCH_OF) - set(primitives))
        extra = sorted(set(primitives) - set(BATCH_OF))
        errs.append(f"primitive ids mismatch (missing={missing}, extra={extra})")
        return errs
    vocab = set(doc.get("protocol_vocabulary", {}))
    if not vocab:
        errs.append("protocol_vocabulary: empty")
    seen_capabilities: dict[str, str] = {}
    for pid, p in sorted(primitives.items()):
        where = f"primitives.{pid}"
        if not isinstance(p, dict):
            errs.append(f"{where}: not an object")
            continue
        for f in REQUIRED_FIELDS:
            if f not in p:
                errs.append(f"{where}: missing field {f!r}")
        if set(p) - set(REQUIRED_FIELDS):
            errs.append(f"{where}: unexpected fields "
                        f"{sorted(set(p) - set(REQUIRED_FIELDS))}")
        if p.get("primitive_id") != pid:
            errs.append(f"{where}: primitive_id mismatch "
                        f"{p.get('primitive_id')!r}")
        if p.get("batch") != BATCH_OF[pid]:
            errs.append(f"{where}: batch {p.get('batch')!r} != "
                        f"schedule {BATCH_OF[pid]!r}")
        cap = p.get("capability")
        if not isinstance(cap, str) or len(cap) < 3:
            errs.append(f"{where}: capability invalid")
        elif cap in seen_capabilities:
            errs.append(f"{where}: duplicate capability {cap!r} "
                        f"(also {seen_capabilities[cap]})")
        else:
            seen_capabilities[cap] = pid
        for f in ("cognitive_definition", "required_observable_behavior",
                  "public_task_information", "independent_ground_truth"):
            v = p.get(f)
            if not isinstance(v, str) or len(v) < 20:
                errs.append(f"{where}.{f}: too short/missing")
        iso = p.get("capability_isolation")
        if not isinstance(iso, dict) or set(iso) != {"label", "note"}:
            errs.append(f"{where}.capability_isolation: bad shape")
        else:
            if iso["label"] not in ISOLATION_LABELS:
                errs.append(f"{where}.capability_isolation.label: "
                            f"unknown {iso['label']!r}")
            if not isinstance(iso["note"], str) or len(iso["note"]) < 20:
                errs.append(f"{where}.capability_isolation.note: too short")
        oc = p.get("output_contract")
        if not isinstance(oc, dict) or set(oc) != {"representation",
                                                   "constraints"}:
            errs.append(f"{where}.output_contract: bad shape")
        elif not isinstance(oc["representation"], str) or \
                not isinstance(oc["constraints"], list) or \
                not oc["constraints"]:
            errs.append(f"{where}.output_contract: empty parts")
        protos = p.get("applicable_protocols")
        if not isinstance(protos, list) or not protos:
            errs.append(f"{where}.applicable_protocols: empty")
        else:
            bad = [x for x in protos if x not in vocab]
            if bad:
                errs.append(f"{where}.applicable_protocols: not in "
                            f"vocabulary: {bad}")
        for f, n in (("correct_witnesses", 2), ("incorrect_witnesses", 2),
                     ("valid_alternatives", 1), ("boundary_cases", 2),
                     ("difficulty_dimensions", 2), ("failure_taxonomy", 3)):
            v = p.get(f)
            if not isinstance(v, list) or len(v) < n or \
                    not all(isinstance(x, str) and x for x in v):
                errs.append(f"{where}.{f}: need >= {n} non-empty strings")
    return errs


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        doc = json.loads(TAXONOMY.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"TAXONOMY INVALID: unreadable {e}", file=sys.stderr)
        return 1
    errs = _errors(doc, schema)
    if errs:
        for e in errs:
            print(f"TAXONOMY INVALID: {e}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(TAXONOMY.read_bytes()).hexdigest()
    print(f"taxonomy VALID: 32/32 primitives, "
          f"sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
