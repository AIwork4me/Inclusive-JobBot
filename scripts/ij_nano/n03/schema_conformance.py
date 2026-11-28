#!/usr/bin/env python3
"""N03-D02 taxonomy schema conformance (IJ-NANO-1.3S continuation order
section 3).

Establishes EITHER actual JSON Schema validation (when the jsonschema
package is available) OR a verified mutation-equivalence contract between
taxonomy.schema.json and the dependency-free validator. The claim written
to evidence names exactly which one executed - JSON Schema validation is
never claimed without execution. The taxonomy identity (sha256) is checked
unchanged; any correction requires a new versioned identity.
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "ij_nano" / "n03"))

TAXONOMY = ROOT / "evaluation" / "ij_nano" / "n03" / "taxonomy.json"
SCHEMA = ROOT / "evaluation" / "ij_nano" / "n03" / "taxonomy.schema.json"
OUT = ROOT / "evidence" / "IJNANO" / "N03" / "dataset" / \
    "schema_conformance.json"
PINNED_TAXONOMY_SHA = "cb800bce6efc01723e1e34ad10e159d3a95c44ed" \
                      "8592a3c0112c17e74f23861c"

import validate_taxonomy as vt  # noqa: E402


def _mutants(doc: dict) -> list[tuple[str, dict]]:
    """Defect battery: (name, mutated copy). Every mutant must be rejected
    by whichever engines are under test."""
    out = []

    def add(name, fn):
        d = copy.deepcopy(doc)
        fn(d)
        out.append((name, d))

    add("missing-primitive", lambda d: d["primitives"].pop("C17"))
    add("extra-field", lambda d: d["primitives"]["C01"].update(
        {"surprise": 1}))
    add("bad-batch", lambda d: d["primitives"]["C09"].update({"batch": "A"}))
    add("bad-primitive-id", lambda d: d["primitives"].update(
        {"X01": d["primitives"].pop("C01")}))
    add("unknown-protocol", lambda d: d["primitives"]["C02"][
        "applicable_protocols"].append("telepathy"))
    add("empty-protocols", lambda d: d["primitives"]["C02"].update(
        {"applicable_protocols": []}))
    add("bad-isolation-label", lambda d: d["primitives"]["C08"][
        "capability_isolation"].update({"label": "autonomous_superiority"}))
    add("short-definition", lambda d: d["primitives"]["C05"].update(
        {"cognitive_definition": "too short"}))
    add("witness-depleted", lambda d: d["primitives"]["C22"].update(
        {"correct_witnesses": ["one"]}))
    add("one-failure-class", lambda d: d["primitives"]["C31"].update(
        {"failure_taxonomy": ["only-one"]}))
    add("output-contract-empty", lambda d: d["primitives"]["C09"].update(
        {"output_contract": {"representation": "", "constraints": []}}))
    add("duplicate-capability", lambda d: d["primitives"]["C06"].update(
        {"capability": d["primitives"]["C05"]["capability"]}))
    add("bad-schema-tag", lambda d: d.update({"schema": "other.v0"}))
    add("missing-ground-truth", lambda d: d["primitives"]["C14"].pop(
        "independent_ground_truth"))
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import hashlib
    doc = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    sha = hashlib.sha256(TAXONOMY.read_bytes()).hexdigest()
    report: dict = {"schema": "ij_nano.n03.schema_conformance.v1",
                    "taxonomy_sha256": sha,
                    "taxonomy_identity_unchanged": sha == PINNED_TAXONOMY_SHA}
    if not report["taxonomy_identity_unchanged"]:
        report["result"] = "FAIL"
        report["problems"] = ["taxonomy identity drifted from the pinned "
                              "frozen digest; a correction requires a new "
                              "versioned identity"]
        _write(report)
        return 1

    # engine 1: dependency-free structural validator (always available)
    v_errs = vt._errors(doc, schema)
    report["structural_validator"] = {"committed_document": not v_errs}

    # engine 2: real JSON Schema validation, only if the package exists
    js = None
    try:
        import jsonschema
        js = jsonschema.Draft7Validator(schema)
        js_errs = list(js.iter_errors(doc))
        report["jsonschema_engine"] = {
            "available": True, "version": jsonschema.__version__,
            "committed_document_valid": not js_errs,
            "first_errors": [e.message[:200] for e in js_errs[:5]]}
    except ImportError:
        report["jsonschema_engine"] = {"available": False}

    # mutation-equivalence battery across available engines
    battery = []
    for name, mut in _mutants(doc):
        s_reject = bool(vt._errors(mut, schema))
        j_reject = None
        if js is not None:
            j_reject = bool(list(js.iter_errors(mut)))
            agree = s_reject == j_reject
        else:
            agree = s_reject            # single-engine mode
        battery.append({"mutant": name, "structural_rejects": s_reject,
                        "jsonschema_rejects": j_reject, "agree": agree})
    disagree = [b for b in battery if not b["agree"]]
    missed = [b["mutant"] for b in battery if not b["structural_rejects"]]

    if js is not None:
        claim = ("actual JSON Schema Draft-07 validation executed AND "
                 "mutation-equivalent with the dependency-free validator "
                 f"({len(battery) - len(disagree)}/{len(battery)} mutants "
                 "agree)")
    else:
        claim = ("jsonschema package unavailable: verified equivalence "
                 "contract is the dependency-free validator's mutation "
                 f"detection ({len(battery) - len(missed)}/{len(battery)} "
                 "mutants rejected); JSON Schema validation NOT claimed")
    ok = (not v_errs and not missed and not disagree and
          (js is None or report["jsonschema_engine"]
           ["committed_document_valid"]))
    report.update({"result": "PASS" if ok else "FAIL",
                   "claim": claim,
                   "mutation_battery": battery,
                   "problems": [f"mutant not rejected: {m}" for m in missed] +
                               [f"engine disagreement: {d['mutant']}"
                                for d in disagree]})
    _write(report)
    print(f"schema conformance {report['result']}: {claim}")
    return 0 if ok else 1


def _write(report: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
