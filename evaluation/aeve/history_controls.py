"""Regenerate software controls with the repository's own historical entry points."""
from functools import lru_cache
from importlib import import_module
from pathlib import Path
import json
import subprocess
import sys
from xml.etree import ElementTree
from tempfile import TemporaryDirectory

MODULES = {
    "archive_replay.json": ("ij073_archive_replay","audit",{}),
    "legacy_alignment.json": ("ij073_plan_alignment","audit",{}),
    "mutation_replay.json": ("ij073_mutation_replay","run",{}),
    "witness_replay.json": ("ij073_witness_replay","audit",{}),
    "executable_witness.json": ("ij073_executable_witness","audit",{}),
    "guard_controls.json": ("ij073_guard_controls","audit",{}),
    "public_worlds.json": ("ij073_public_worlds","run",{}),
    "planning-plan-controls.json.gz": ("atlas_planning_plan_controls","execute",{}),
    "planning-intent-controls.json": ("atlas_planning_intent_controls","execute",{}),
    "planning-read-controls.json": ("atlas_planning_read_controls","execute",{}),
    "planning-advanced-controls.json": ("atlas_planning_advanced_controls","execute",{}),
    "planning-advanced-mutations.json.gz": ("atlas_planning_write_controls","run",{}),
    "planning-precondition-controls.json": ("atlas_audit_plan_ambiguity","audit_preconditions",{}),
    "quote-controls.json": ("atlas_quote_controls","execute",{}),
    "job-witness.json.gz": ("atlas_job_witness","execute",{}),
    "job-extended-controls.json.gz": ("atlas_job_witness","execute",{"extended":True}),
    "tc-holdout-witness.json": ("atlas_tc_holdout_witness","execute",{}),
    "tc-holdout-extended-controls.json.gz": ("atlas_tc_holdout_witness","execute",{"extended":True}),
    "multitool-witness.json.gz": ("atlas_multitool_witness","execute",{}),
    "multitool-extended-controls.json.gz": ("atlas_multitool_witness","execute",{"extended":True}),
    "multitool-unicode-controls.json.gz": ("atlas_multitool_witness","execute",{"unicode":True}),
    "multitool-observed-draft-controls.json.gz": ("atlas_multitool_witness","execute",{"observed_draft":True}),
}


@lru_cache(maxsize=1)
def current_controls():
    from scripts.tools.atlas_controls import run
    with TemporaryDirectory(prefix="aeve-software-controls-") as directory:
        return run(Path(directory))


def mutation_test_rows(path):
    tests = json.loads(path.read_bytes())["tests"]
    nodes = []
    for record in tests:
        module, case = record["id"].split("::",1)
        nodes.append(module.replace(".","/")+".py::"+case)
    with TemporaryDirectory(prefix="aeve-mutations-") as directory:
        junit = Path(directory)/"results.xml"
        process = subprocess.run([sys.executable,"-m","pytest","-q","-p","no:cacheprovider",
                                  "--junitxml",str(junit),*nodes],capture_output=True,text=True)
        if process.returncode not in {0,1} or not junit.is_file():
            raise RuntimeError("Could not execute archived mutation tests: "+process.stdout[-1500:])
        outcomes = {}
        for case in ElementTree.parse(junit).iter("testcase"):
            key = case.attrib["classname"]+"::"+case.attrib["name"]
            if key in outcomes:
                raise ValueError("Duplicate pytest result: "+key)
            outcome = "BLOCKED" if case.find("skipped") is not None else (
                "FAIL" if case.find("error") is not None or case.find("failure") is not None else "PASS")
            outcomes[key] = outcome
        if set(outcomes) != {r["id"] for r in tests}:
            raise ValueError("Collected mutation tests differ from the archived node IDs")
        return {i:{"id":r["id"],"status":outcomes[r["id"]]} for i,r in enumerate(tests)}


@lru_cache(maxsize=1)
def replay_documents():
    from benchmarks.tool_calling_v2.rescore import evidence
    return evidence()


def reproduced_rows(path):
    if path.parent.name == "rescoring" and path.suffix == ".jsonl":
        return {n:json.loads(line) for n,line in enumerate(replay_documents()[path.name].splitlines(),1)}
    if path.name == "mutations.json" and path.parent.name == "evaluator_v2":
        return mutation_test_rows(path)
    if path.name in {"controls-draft-red.json.gz","controls-reconciled.json.gz"}:
        doc = current_controls()
    elif path.name in MODULES:
        module,entry,kwargs = MODULES[path.name]
        doc = getattr(import_module("scripts.tools."+module),entry)(**kwargs)
    else:
        return {}
    output = {}
    for name,group in doc.get("cohorts",{"":doc}).items():
        for field in ("rows","trials","cases","results","repetitions"):
            if isinstance(group.get(field),list):
                for i,r in enumerate(group[field]):
                    output[f"{name}/{field}/{i}"] = r
                break
    return output
