"""Emit and verify the TC-V3-scoped NanoAgent evidence exchange."""

import argparse
from hashlib import sha256
import json

from jsonschema import Draft202012Validator

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import ROOT, canonical
from .tc_priority_milestone import HYPOTHESES, MODELS, OUT as PRIORITY

OUT = PRIORITY.parent.parent / "nanoagent-handoff"
SOURCE_HEAD = "b4d098a48e980f5862084238496b87630fb6cff4"
SCOPE = "TC-V3/1.0 synthetic Radeon tool-calling measurement"
VERSION = "1.0.0"
COMPARISON_ARMS = {
    "R0": "Direct llama.cpp",
    "R1": "Original Antigravity SDK",
    "R2": "Antigravity plus independently qualified adapter",
    "R3": "NanoAgent basic runtime",
    "R4": "NanoAgent capability-matched runtime",
    "R5": "NanoAgent with job skill or SOP",
    "R6": "Deterministic baseline without a model",
    "R7": "Stronger model reference",
}
# An empty metric indicates that the priority release does not qualify this failure frequency.
COMPONENTS = (
    ("goal", "Wrong goal", "Intent/Goal Resolver", "", "Request clarification if public intent is ambiguous."),
    ("tool", "Wrong tool", "Tool Router", "FIRST_TOOL_CHOICE", "Expose only in-scope tools without inserting Oracle actions."),
    ("argument", "Wrong argument", "Typed Slot Binder", "required_arguments", "Apply the selected tool's typed contract."),
    ("entity", "Entity confusion", "Entity Resolver", "entity_binding", "Bind every entity to the current public scope."),
    ("proposal", "Repeated proposal", "Action Ledger / State", "DUPLICATE_PROPOSAL_RATE",
     "Keep occurrence, scope, freshness and retry identities distinct."),
    ("execution", "Redundant execution", "Duplicate Guard", "REDUNDANT_EXECUTION_RATE",
     "Preserve legal retries and different entity bindings."),
    ("result", "Result misunderstanding", "Result Codec", "RESULT_COMPREHENSION",
     "Preserve semantics, provenance, uncertainty and freshness."),
    ("output", "Invalid output", "Structured Output Contract", "OUTPUT_CONTRACT_COMPLIANCE",
     "Preserve every value and reject ambiguous content."),
    ("dependency", "Broken dependency", "Conditional Action Graph", "",
     "Schedule only justified dependencies from public input and observed state."),
    ("termination", "Incorrect termination", "Goal/Budget Controller", "TERMINATION_CORRECTNESS",
     "Require proof of completion or return a bounded unresolved result."),
    ("recovery", "Recovery failure", "Typed Recovery Policy", "",
     "Retry only permitted failures and retain the original outcome."),
    ("authorization", "Unauthorized action", "Authorization Gateway", "authorization",
     "Require host-side scoped approval bound to the exact persisted draft version."),
)


def envelope(kind, data):
    return {"schema_version": VERSION, "kind": kind, "scope": SCOPE, "data": data}


def measurements(matrix, model, metric):
    source = matrix["models"][model]
    if metric in ("DUPLICATE_PROPOSAL_RATE", "REDUNDANT_EXECUTION_RATE"):
        return {track: value["event_rates"][metric] for track, value in source["tracks"].items()}
    return {row["track"]: {key: row[key] for key in ("FAIL", "BLOCKED", "NOT_RUN", "N/A", "observed", "full")}
            for row in matrix["cells"]
            if row["model"] == model and row["stratum"] == "all" and row["metric"] == metric}


def exchange(matrix, evidence):
    matrix_source = (PRIORITY / "CAPABILITY_MATRIX.json").relative_to(ROOT).as_posix()
    manifest_source = (PRIORITY / "EVIDENCE_MANIFEST.json").relative_to(ROOT).as_posix()
    capabilities, failures, mapping, resources = {}, [], [], {}
    for model, entry in matrix["models"].items():
        capabilities[model] = {"configurations": entry["configurations"], "architecture": entry["architecture"],
                               "official_parameter_count": entry["official_parameter_count"],
                               "metrics": [r for r in matrix["cells"] if r["model"] == model and r["stratum"] == "all"],
                               "strict_d25": "BLOCKED"}
        resources[model] = {"tracks": entry["tracks"], "matched_frontier": entry["pareto"]}
        for slug, description, component, metric, invariant in COMPONENTS:
            failure_id = f"{model}-{slug}"
            frequency = measurements(matrix, model, metric)
            failure = {"failure_id": failure_id, "model": model, "description": description,
                       "metric": metric or None, "failure_frequency": frequency,
                       "frequency_status": "PASS" if frequency else "NOT_RUN",
                       "task_family": "all priority TC-V3 families; strata in source matrix",
                       "source_evidence": {"matrix": matrix_source, "manifest": manifest_source,
                                           "reproduction_model": model, "metric": metric or None},
                       "examples": {key: value for key, value in entry["failure_examples"].items()
                                    if key.endswith("/" + metric) and value}}
            failures.append(failure)
            hypothesis = HYPOTHESES[model][2] if component in (
                "Action Ledger / State", "Goal/Budget Controller", "Result Codec", "Structured Output Contract"
            ) and ((model, slug) in {("A", "proposal"), ("A", "termination"), ("B", "result"), ("D", "output")}) else (
                "Pair same case, world and seed with the component disabled and enabled. Include a negative control "
                "for the invariant and measure preserved behavior and resource overhead.")
            mapping.append(failure | {"runtime_identity_ref": f"MODEL_CAPABILITIES.json#/data/{model}/configurations",
                                      "confirmed_root_cause": None, "intervention_status": "HYPOTHESIS",
                                      "unverified_hypothesis": f"{component} can reduce {description.lower()} under its invariant.",
                                      "proposed_component": component, "required_invariant": invariant,
                                      "expected_benefit": f"Lower occurrence of {description.lower()} at equal coverage.",
                                      "validation_experiment": hypothesis, "observed_benefit": "NOT_RUN",
                                      "resource_overhead": "NOT_RUN",
                                      "remaining_risks": ["Scope or coverage regression", "Unmeasured resource overhead"],
                                      "qualification_scope": SCOPE})
    matched = {
        "status": "NOT_RUN",
        "arms": COMPARISON_ARMS,
        "pair_key": ["model_asset_sha256", "case_id", "world_sha256", "seed", "hardware_identity"],
        "hold_constant": ["Case, world and user input", "Tool schema and visible tool results",
                          "Evaluation contract and safety policy", "Context and execution budgets",
                          "Model, quantization and hardware within same-model comparison"],
        "reference_exceptions": {"R6": "No model or provider call", "R7": "Different registered model asset"},
        "capture": ["Model proposals", "Host and SOP actions separately", "Provider requests and results",
                    "Authenticated approval and state changes", "Terminal facts and output schema",
                    "Input and output tokens", "User turns and model requests", "Provider and end-to-end latency",
                    "Process-attributed GPU memory"],
        "evaluation": ["Same-case and same-world paired effects with complete disposition counts",
                       "Intervals clustered by independently authored task family",
                       "Exact McNemar test for paired binary outcomes where applicable",
                       "Compare resource use at matching quality and scope",
                       "Keep gfx1151 and gfx1100 in independent hardware strata",
                       "Run latency comparisons on the same physical device",
                       "Keep deterministic SOP and model attribution separate"],
    }
    return {
        "MODEL_CAPABILITIES": capabilities,
        "SDK_CAPABILITY_DELTA": {m: matrix["models"][m]["matched"] for m in MODELS},
        "MODEL_FAILURE_SIGNATURES": failures,
        "CAPABILITY_DEFICITS": [{"failure_id": f["failure_id"], "metric": f["metric"],
                                 "qualification_scope": SCOPE} for f in failures],
        "COMPENSATION_COMPONENTS": [{"component": arm[2], "required_invariant": arm[4],
                                     "qualification": "HYPOTHESIS"} for arm in COMPONENTS],
        "CAPABILITY_COMPONENT_MAPPING": mapping,
        "MATCHED_BENCHMARK_CONTRACT": matched,
        "RESOURCE_BASELINES": resources,
        "AUTONOMY_PERMISSION_MATRIX": {
            "model_proposals": "Host validates typed tool, argument, entity, scope, budget and freshness",
            "sandbox_read": "Only with host policy and scoped evaluation",
            "draft": "Deterministic host owns persisted state and exact version",
            "commit": "Requires independently authenticated human approval of the exact draft and transaction",
            "permission_expansion": "BLOCKED",
            "qualified_autonomy": "BLOCKED",
        },
        "OPEN_RISKS": {"D25": "BLOCKED", "production": "BLOCKED", "AG11": "BLOCKED",
                       "planning_and_complexity": "BLOCKED", "npu_physical": "NOT_RUN",
                       "intervention_acceptance": "NOT_RUN"},
        "EVIDENCE_MANIFEST": {
            "source_git_sha": SOURCE_HEAD, "coverage": {k: matrix[k] for k in ("planned", "executed", "sealed")},
            "files": {path.relative_to(ROOT).as_posix(): digest(path) for path in
                      (PRIORITY / "CAPABILITY_MATRIX.json", PRIORITY / "EVIDENCE_MANIFEST.json")},
            "derived_priority_rows_sha256": evidence["derived_priority_rows_sha256"],
            "raw_portable_sessions": {run: {"path": seal["path"], "manifest_sha256": seal["manifest_sha256"]}
                                      for run, seal in evidence["sessions"].items()},
        },
    }


def validator():
    schema = json.loads((OUT / "HANDOFF.schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    matrix = json.loads((PRIORITY / "CAPABILITY_MATRIX.json").read_bytes())
    evidence = json.loads((PRIORITY / "EVIDENCE_MANIFEST.json").read_bytes())
    docs = exchange(matrix, evidence)
    for seal in docs["EVIDENCE_MANIFEST"]["raw_portable_sessions"].values():
        if digest(ROOT / seal["path"]) != seal["manifest_sha256"]:
            raise ValueError(f"Published raw seal digest differs for {seal['path']}")
    files = {}
    validate = validator()
    for kind, data in docs.items():
        doc = envelope(kind, data)
        validate.validate(doc)
        files[kind + ".json"] = canonical(doc) + b"\n"
    manifest = envelope("HANDOFF_MANIFEST", {
        "source_git_sha": SOURCE_HEAD, "core_trial_attribution": 0,
        "files": {name: sha256(content).hexdigest() for name, content in files.items()}
        | {name: digest(OUT / name) for name in ("HANDOFF.schema.json", "NANOAGENT_ENGINEERING_HANDOFF.md")},
    })
    validate.validate(manifest)
    files["HANDOFF_MANIFEST.json"] = canonical(manifest) + b"\n"
    for name, data in files.items():
        check_text(data)
        path = OUT / name
        if args.write:
            path.write_bytes(data)
        elif path.read_bytes() != data:
            raise ValueError(f"NanoAgent exchange differs for {name}")
    print(f"Verified {len(files)} NanoAgent exchange documents and {len(evidence['sessions'])} priority seals")


if __name__ == "__main__":
    main()
