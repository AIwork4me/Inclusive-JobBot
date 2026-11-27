"""Versioned SLM evaluation contract and deterministic proof admission."""

from hashlib import sha256
import json
from pathlib import Path

from benchmarks.agentic_planning_v2.oracle import verify
from evaluation.aeve.evaluation_skill import DIMENSIONS, compile_skill
from evaluation.aeve.gold_proof import prove
from evaluation.aeve.runtime import ROOT, fingerprint

SOURCE_PATHS = (
    "benchmarks/agentic_planning_v2/oracle.py",
    "benchmarks/agentic_planning_v2/contract.py",
    "benchmarks/agentic_planning_v2/execution.py",
    "benchmarks/agentic_planning_v2/events.py",
    "benchmarks/agentic_planning_v2/types.py",
    "schemas/conditional_plan_v2.schema.json",
    "schemas/conditional_plan_v2_typed.schema.json",
    "evaluation/aeve/evaluation_skill.py",
    "evaluation/aeve/gold_proof.py",
)
PROOF_DIMENSIONS = {"D20", "D22", "D23", "D24"}
CANDIDATE_METHODS = dict.fromkeys(PROOF_DIMENSIONS, "gold-proof") | {"D12": "conditional-planning"}


def contract():
    sources = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE_PATHS}
    return {
        "version": "IJ-SLM-MECHANICAL-1",
        "sources": sources,
        "dimensions": {dimension: {"skill_sha256": compile_skill(dimension)["sha256"],
                                   "candidate_method": CANDIDATE_METHODS.get(dimension),
                                   "formal_semantic_without_qualified_judge": "BLOCKED"}
                       for dimension in sorted(DIMENSIONS)},
        "control_requirements": ["executable_witness", "equivalent_witness", "wrong_effect",
                                 "missing_evidence", "unauthorized_effect", "independent_holdout"],
        "provenance": "Trusted and scoped source observations only; model assertions are untrusted.",
        "strict_end_to_end": "All applicable dimensions must have individually qualified evidence.",
    }


def mechanical_candidate(dimension, evidence):
    """Replay a candidate proof while keeping independent qualification separate."""
    method = CANDIDATE_METHODS.get(dimension)
    if method == "gold-proof" and evidence.get("dimension") == dimension:
        result = prove(evidence)
        return {"method": method, "replay_status": result["verdict"], "proof": result}
    if method == "conditional-planning" and {"plan", "contract", "worlds"} <= evidence.keys():
        result = verify(evidence["plan"], evidence["contract"], evidence["worlds"])
        return {"method": method, "replay_status": result["status"], "proof": result}
    return {"method": method, "replay_status": "BLOCKED", "proof": None}


def assess(dimension, evidence):
    active = contract()
    published = json.loads((ROOT / "atlas/slm/v1.0/evaluation_contract.json").read_bytes())
    if active != published:
        raise ValueError("mechanical contract source differs from its frozen bytes")
    if dimension not in active["dimensions"]:
        raise ValueError("unknown evaluation dimension")
    replay = mechanical_candidate(dimension, evidence)
    return {
        **replay, "contract_sha256": fingerprint(active), "dimension": dimension,
        "evidence_sha256": fingerprint(evidence), "status": "BLOCKED",
        "reason": "independent scope qualification required" if replay["method"]
                  else "semantic qualification pending",
    }
