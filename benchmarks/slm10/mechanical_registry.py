"""Replay and enforce exact-scope TC-V3 mechanical qualification credentials."""

import argparse
from functools import lru_cache
from hashlib import sha256
import json

from evaluation.aeve.archive import digest
from evaluation.aeve.runtime import ROOT, canonical, fingerprint

from .qualification_controls import exhibits
from .tc_verification import COMPONENTS, EVIDENCE_REQUIREMENTS, component_verdicts, trace_evidence
from .tc_v3 import CONFIG, HERE, PROMPTS

REGISTRY = HERE.parent / "mechanical_qualification_registry.json"
REPORT = ROOT / "evidence/IJSLM/qualification/tc-v3-mechanical.json"
CONTRACT = HERE.parent / "evaluation_contract.json"
SOURCES = (
    "benchmarks/slm10/tc_verification.py",
    "benchmarks/slm10/qualification_controls.py",
    "benchmarks/slm10/mechanical_registry.py",
    "benchmarks/slm10/mechanical.py",
    "benchmarks/slm10/tc_v3.py",
    "benchmarks/ij06_sdk/wire_boundary.py",
    "benchmarks/root_cause/generation_capture.py",
    "benchmarks/tool_calling_v2/oracle.py",
    "src/model_gateway/openai_protocol.py",
    "src/model_gateway/streaming.py",
    "src/model_gateway/strict_json.py",
)
HISTORICAL = (
    "evidence/IJ072/benchmark_validity/tc-holdout-witness.json",
    "evidence/IJ072/benchmark_validity/multitool-witness.json.gz",
    "evidence/IJ073/oracle/witness_replay.json",
    "evidence/IJ073/oracle/mutation_replay.json",
)
WORKFLOWS = {
    "tool_selection": tuple(PROMPTS), "execution_budget": tuple(PROMPTS),
    "required_arguments": tuple(family for family in PROMPTS if family != "clarification"),
    "entity_binding": tuple(family for family in PROMPTS if family != "clarification"),
    "json_schema": tuple(PROMPTS),
    "tool_result": tuple(family for family in PROMPTS if family != "clarification"),
    "dependency_order": ("dependency", "scope_update", "recovery"),
    "parallel_equivalence": ("parallel",),
    "authorization": ("authorization",),
}


def qualification():
    data = []
    for name, oracle, exhibit, expected in exhibits():
        observed = component_verdicts(oracle, exhibit)
        got = {key: observed[key] for key in expected}
        data.append({"control": name, "expected": expected, "observed": got,
                     "exhibit_sha256": fingerprint([oracle, exhibit]),
                     "status": "PASS" if got == expected else "FAIL"})
    sources = {name: digest(ROOT / name) for name in SOURCES}
    contract_sha = digest(CONTRACT)
    manifest_sha = digest(HERE / "manifest.json")
    report = {
        "version": "IJ-SLM-TC-V3-MECHANICAL-1", "evidence_class": "synthetic independent software controls",
        "evaluation_contract_sha256": contract_sha, "dataset_manifest_sha256": manifest_sha, "sources": sources,
        "historical_reference_only": {name: digest(ROOT / name) for name in HISTORICAL},
        "controls": data, "status": "PASS" if all(row["status"] == "PASS" for row in data) else "FAIL",
    }
    report_bytes = canonical(report) + b"\n"
    entries = {}
    for verifier, dimension in COMPONENTS.items():
        workflows = WORKFLOWS.get(verifier, ())
        evidence = [row for row in data if verifier in row["expected"]]
        actual_controls = {row["expected"][verifier] for row in evidence if row["status"] == "PASS"}
        heldout_passed = any(row["control"].startswith("independent_holdout") and row["status"] == "PASS"
                             for row in evidence)
        status = "PASS" if (workflows and report["status"] == "PASS"
                            and actual_controls == {"PASS", "FAIL", "BLOCKED"} and heldout_passed) else "BLOCKED"
        entries[verifier] = {
            "verifier_id": f"tc-v3/{verifier}/1", "status": status,
            "source_sha256": sources["benchmarks/slm10/tc_verification.py"], "source_set_sha256": fingerprint(sources),
            "evaluation_contract_sha256": contract_sha, "benchmark_version": CONFIG["benchmark_version"],
            "capability_dimension": dimension, "independent_qualification_report": REPORT.relative_to(ROOT).as_posix(),
            "evidence_requirements": EVIDENCE_REQUIREMENTS[verifier],
            "applicability_rules": {
                "dataset_manifest_sha256": manifest_sha, "task_families": workflows, "workflows": workflows,
                "risk_scopes": (("simulated-deny-release",) if verifier == "authorization"
                                else ("synthetic-read-only", "simulated-deny-release")),
                "D25": "BLOCKED",
            },
        }
    registry = {"version": report["version"], "qualification_report_sha256": sha256(report_bytes).hexdigest(),
                "entries": entries}
    return report_bytes, canonical(registry) + b"\n"


@lru_cache(maxsize=1)
def require_registry():
    report, registry = qualification()
    if (REPORT.read_bytes(), REGISTRY.read_bytes()) != (report, registry):
        raise ValueError("mechanical qualification registry or report differs from verified sources")
    entries = json.loads(registry)["entries"]
    if any(entries[name]["status"] != "PASS" for name in WORKFLOWS):
        raise ValueError("TC-V3 scoped mechanical suite gate is BLOCKED")
    return entries


@lru_cache(maxsize=2)
def registered_cases(split):
    if split not in ("development", "holdout"):
        raise ValueError("unknown TC-V3 qualification partition")
    manifest = json.loads((HERE / "manifest.json").read_bytes())
    name = split + "-oracle.jsonl"
    if digest(HERE / name) != manifest["sha256"][name]:
        raise ValueError("frozen oracle digest differs from the qualified dataset")
    return {row["case_id"]: row for row in (json.loads(line) for line in (HERE / name).read_bytes().splitlines())}


def assess_trial(trial, split):
    """Apply qualified component decisions to a private, source-linked trial record."""
    registry = require_registry()
    oracle = registered_cases(split).get(trial.get("case_id"))
    if oracle is None:
        return dict.fromkeys((*COMPONENTS, "strict_end_to_end"), "BLOCKED")
    replay = component_verdicts(oracle, trace_evidence(trial))
    result = {"strict_end_to_end": "BLOCKED"}
    for name, entry in registry.items():
        rules = entry["applicability_rules"]
        if (entry["status"] == "PASS" and oracle["workflow"] in rules["task_families"]
                and oracle["workflow"] in rules["workflows"] and oracle["risk_scope"] in rules["risk_scopes"]):
            result[name] = replay[name]
        else:
            result[name] = "BLOCKED"
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--write", action="store_true")
    args = cli.parse_args()
    if args.write:
        report, registry = qualification()
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_bytes(report)
        REGISTRY.write_bytes(registry)
    entries = require_registry()
    print({name: row["status"] for name, row in entries.items()})


if __name__ == "__main__":
    main()
