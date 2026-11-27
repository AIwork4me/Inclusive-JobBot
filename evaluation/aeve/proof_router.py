"""Plan an experimental proof route or a full independent semantic panel."""
from .contracts import DIMENSIONS, sha
from .history_routing import HEX256, RISKS, plan_panel


def proof_binding(proof):
    return tuple(proof.get(key) for key in ("scope", "proof_method_sha256", "qualification_sha256"))


def plan(packet, subject_family, workflow, risk, *, proof, verified_credentials, judge_profiles, experiment=False):
    """The proof is a verified adapter result. Credentials come from independent component or Q3 replay."""
    dimension = packet["dimension"]
    if not workflow or "/" in workflow or dimension not in DIMENSIONS or risk not in RISKS:
        raise ValueError("invalid proof route scope")
    if not subject_family.strip() or subject_family.casefold() in {"unknown", "unresolved"}:
        return {"route": "semantic", "status": "BLOCKED", "reason": "unresolved subject family"}
    refs = [event["id"] for event in packet["events"]]
    if len(refs) != len(set(refs)) or not refs:
        raise ValueError("invalid proof route exhibits")
    if proof:
        cycles = {"Q3", "PROOF"} if experiment else {"Q3"}
        scope, method, report = proof_binding(proof)
        cited = proof.get("evidence_refs")
        independent = (scope == f"{workflow}/{dimension}/{risk}"
                       and all(isinstance(value, str) and HEX256.fullmatch(value) for value in (method, report))
                       and any(row.get("status") == "PASS" and row.get("cycle") in cycles
                               and proof_binding(row) == (scope, method, report) for row in verified_credentials))
        if (independent and proof.get("status") == "PASS" and proof.get("verdict") in {"PASS", "FAIL"}
                and proof.get("packet_sha256") == sha(packet)
                and isinstance(cited, list) and all(isinstance(ref, str) for ref in cited)
                and cited and len(cited) == len(set(cited)) and set(cited) <= set(refs)):
            return {"route": "proof", "status": "PASS", "verdict": proof["verdict"],
                    "planned_llm_requests": 0, "evidence_refs": cited, "proof_sha256": sha(proof),
                    "qualification_sha256": report}
    panel = plan_panel(judge_profiles, subject_family, dimension, risk)
    if panel["status"] == "PASS":
        return {"route": "semantic", **panel, "planned_primary_requests": 2,
                "escalation": "independent_dispute"}
    return {"route": "semantic", **panel}
