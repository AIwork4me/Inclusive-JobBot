from evaluation.aeve.contracts import sha
from evaluation.aeve.evaluation_skill import compile_skill, treatment
from evaluation.aeve.proof_router import plan
from test_aeve_history_routing import profile


def inputs():
    packet = {"dimension": "D20", "task": "Return exact JSON", "events": [
        {"id": "wire", "kind": "final_answer", "value": "{}"},
    ]}
    proof = {"status": "PASS", "verdict": "FAIL", "packet_sha256": sha(packet),
             "proof_method_sha256": "1" * 64, "qualification_sha256": "2" * 64,
             "evidence_refs": ["wire"], "scope": "workflow-a/D20/read"}
    credential = {"status": "PASS", "cycle": "Q3", "proof_method_sha256": "1" * 64,
                  "qualification_sha256": "2" * 64, "scope": "workflow-a/D20/read"}
    judges = [profile(code, family, ("D20/read",)) for code, family in (("A", "Phi"), ("B", "Llama"), ("C", "OpenAI"))]
    return packet, proof, credential, judges


def test_proof_router_is_a_separate_full_coverage_arm():
    arm = treatment("E7", compile_skill("D20"), independently_mechanical=False)
    assert arm["eligible"] and arm["primary_judges"] == 2 and arm["dispute_escalation"]


def test_only_packet_bound_independently_qualified_proof_skips_judges():
    packet, proof, credential, judges = inputs()
    args = packet, "Qwen", "workflow-a", "read"
    result = plan(*args, proof=proof, verified_credentials=[credential], judge_profiles=judges)
    assert result["route"] == "proof" and result["verdict"] == "FAIL"
    assert result["planned_llm_requests"] == 0
    result = plan(*args, proof=proof, verified_credentials=[], judge_profiles=judges)
    assert result["route"] == "semantic" and result["primary"] == ["A", "B"] and result["dispute"] == "C"
    packet["events"][0]["value"] = '{"changed":true}'
    result = plan(*args, proof=proof, verified_credentials=[credential], judge_profiles=judges)
    assert result["route"] == "semantic"


def test_routing_retains_blocked_denominator_without_independent_third_family():
    packet, proof, credential, judges = inputs()
    result = plan(packet, "Phi", "workflow-b", "read", proof=proof,
                  verified_credentials=[credential], judge_profiles=judges)
    assert result["route"] == "semantic" and result["status"] == "BLOCKED"
    assert result["eligible_distinct_families"] == ["Llama", "OpenAI"]


def test_component_qualification_is_restricted_to_the_experiment():
    packet, proof, credential, judges = inputs()
    credential["cycle"] = "PROOF"
    args = packet, "Qwen", "workflow-a", "read"
    options = dict(proof=proof, verified_credentials=[credential], judge_profiles=judges)
    assert plan(*args, **options)["route"] == "semantic"
    assert plan(*args, experiment=True, **options)["route"] == "proof"
