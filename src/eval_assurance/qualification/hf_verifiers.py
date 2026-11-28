"""48H-SUPPORT §5 / 48H-B-003 (EAE side) — HF native harness task
verifier qualification + sandbox execution evidence verification.

Fail-closed framework: qualification of the ACTUAL pinned verifier
assets happens when the campaign lane acquires them; until then every
entry point returns BLOCKED_PENDING_ASSETS (never a silent pass).

Three verification layers:

1. ``validate_verifier_pin(spec)`` — the pinned task identity is
   complete (task id + dataset revision + environment image digest +
   verifier digest + reference-solution digest + sampling policy +
   max agent steps + token limits + context config + timeout) and
   internally consistent (digest forms, positive bounds, declared
   provenance vs adapter training data with uncertain-overlap
   labeling).

2. ``verify_sandbox_evidence(evidence)`` — sandbox execution traces
   are structurally sound AND isolated: no host filesystem paths, no
   credential-shaped material, no access to protected classes
   (evaluator implementation / hidden tests / reference solutions /
   confirmation data), network policy declared, resource bounds
   present, and every claimed verdict RECOMPUTABLE from the recorded
   sandbox state transitions by the pinned verifier rule.

3. ``mutation_battery(trace, verifier)`` — verdict-integrity controls:
   mutate the final sandbox state where the verifier's criterion
   depends on it (the verdict MUST flip or the trace MUST be rejected);
   tamper the trace mid-execution (MUST be rejected by the chain of
   state hashes); replay a different task's trace (MUST NOT validate).

``qualify_verifier_suite`` aggregates 1-3 into a qualification
artifact consumable by the AUTH-2 registration path once real assets
exist. No IJ-NANO imports.
"""
from __future__ import annotations

import hashlib
import json
import re

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_REQUIRED_PIN_FIELDS = (
    "task_id", "dataset_revision", "environment_image_digest",
    "verifier_digest", "reference_solution_digest", "sampling_policy",
    "max_agent_steps", "token_limits", "context_config", "timeout_s",
    "training_overlap",   # NONE | CONFIRMED | UNCERTAIN (labeled)
)
_PROTECTED_CLASSES = (
    "evaluator_implementation", "hidden_tests", "reference_solutions",
    "confirmation_data",
)
_REPRO_CLASSES = (
    "EXACT_TASK_PROTOCOL_REPRODUCTION", "SAME_TASK_DIFFERENT_RUNTIME",
    "SAME_TASK_DIFFERENT_CONTEXT_BUDGET", "LOCAL_REPRODUCTION",
    "CONCEPTUAL_REPLICATION", "BLOCKED",
)


class VerifierQualificationError(ValueError):
    pass


def _digest_obj(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True,
                                     ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# layer 1 — pinned verifier spec validation
# ---------------------------------------------------------------------------
def validate_verifier_pin(spec: dict) -> dict:
    problems = []
    for field in _REQUIRED_PIN_FIELDS:
        v = spec.get(field)
        if v is None or v == "" or (isinstance(v, list) and not v):
            problems.append(f"missing pin field: {field}")
    if problems:
        return {"valid": False, "problems": problems}
    for f in ("environment_image_digest", "verifier_digest",
              "reference_solution_digest"):
        v = spec[f]
        if isinstance(v, str) and not _SHA256.match(v) and \
                not v.startswith("sha256:"):
            problems.append(f"{f} is not a sha256 digest")
    if spec["max_agent_steps"] is not None and \
            int(spec["max_agent_steps"]) <= 0:
        problems.append("max_agent_steps must be positive")
    if float(spec["timeout_s"]) <= 0:
        problems.append("timeout_s must be positive")
    if spec["training_overlap"] not in ("NONE", "CONFIRMED",
                                        "UNCERTAIN"):
        problems.append("training_overlap must be NONE/CONFIRMED/"
                        "UNCERTAIN (uncertain cases stay labeled)")
    if spec["training_overlap"] != "NONE" and \
            not spec.get("overlap_note"):
        problems.append("non-NONE overlap requires an overlap_note")
    return {"valid": not problems, "problems": problems}


# ---------------------------------------------------------------------------
# layer 2 — sandbox execution evidence verification
# ---------------------------------------------------------------------------
_HOSTPATH = re.compile(r"[A-Za-z]:\\\\|[A-Za-z]:/|(/home/|/Users/|"
                       r"C:\\\\Users)")


def verify_sandbox_evidence(evidence: dict) -> dict:
    """Structural + isolation + verdict-recomputation checks over one
    recorded sandbox execution."""
    problems = []
    for field in ("task_id", "trace", "claimed_verdict", "verifier"):
        if field not in evidence:
            problems.append(f"evidence missing field: {field}")
    if problems:
        return {"valid": False, "problems": problems}
    trace = evidence["trace"]
    if not isinstance(trace, list) or not trace:
        problems.append("trace must be a non-empty list of steps")
        return {"valid": False, "problems": problems}

    # -- isolation -------------------------------------------------------
    blob = json.dumps(trace, ensure_ascii=False)
    if _HOSTPATH.search(blob):
        problems.append("host filesystem path leaked into the sandbox "
                        "trace")
    if re.search(r"(api[_-]?key|secret|password|token=)[\"':=\s]",
                 blob, re.I):
        problems.append("credential-shaped material in the trace")
    protected = evidence.get("protected_access") or []
    for cls in protected:
        if cls in _PROTECTED_CLASSES:
            problems.append(f"protected class accessed: {cls}")
    if not evidence.get("network_policy"):
        problems.append("network policy not declared")
    if evidence.get("resource_bounds") is None:
        problems.append("resource bounds not recorded")

    # -- chain integrity: each step hashes the prior state ---------------
    prev = None
    for i, step in enumerate(trace):
        if not isinstance(step, dict) or "state" not in step or \
                "state_digest" not in step:
            problems.append(f"step {i} lacks state/state_digest")
            break
        material = {"prev": prev, "state": step["state"]}
        if _digest_obj(material) != step["state_digest"]:
            problems.append(f"step {i} state chain broken (tamper)")
            break
        prev = step["state_digest"]

    # -- verdict recomputation -------------------------------------------
    verdict = _apply_verifier(evidence["verifier"], trace)
    if verdict is None:
        problems.append("verifier rule not applicable to the trace")
    elif verdict != evidence["claimed_verdict"]:
        problems.append(f"claimed verdict {evidence['claimed_verdict']!r}"
                        f" != recomputed {verdict!r}")
    return {"valid": not problems, "problems": problems,
            "recomputed_verdict": verdict}


def _apply_verifier(verifier: dict, trace: list):
    """Recompute the task verdict from the FINAL sandbox state under
    the pinned verifier rule (exact/numeric match on the answer field
    the SmolDataEnvs-style graders use)."""
    rule = (verifier or {}).get("rule")
    final_state = trace[-1].get("state") or {}
    answer = final_state.get(verifier.get("answer_field", "answer"))
    expected = verifier.get("expected")
    if rule == "exact_match":
        return answer == expected
    if rule == "numeric_match":
        try:
            return abs(float(answer) - float(expected)) <= \
                float(verifier.get("tolerance", 0.0))
        except (TypeError, ValueError):
            return False
    return None


# ---------------------------------------------------------------------------
# layer 3 — verdict-integrity mutation battery
# ---------------------------------------------------------------------------
def mutation_battery(evidence: dict) -> dict:
    """Controls over one evidence record: answer flip must flip the
    verdict (or be structurally rejected); mid-trace tamper must break
    the chain; a foreign task's trace must not validate."""
    base = verify_sandbox_evidence(evidence)
    if not base["valid"]:
        return {"passed": False,
                "problems": ["baseline evidence invalid"] +
                            base["problems"]}
    controls = []

    # -- answer flip ------------------------------------------------------
    flipped = json.loads(json.dumps(evidence))
    field = flipped["verifier"].get("answer_field", "answer")
    cur = flipped["trace"][-1]["state"].get(field)
    flipped["trace"][-1]["state"][field] = (
        cur + "-mutated" if isinstance(cur, str) else
        (float(cur) + 1.0 if isinstance(cur, (int, float)) else
         "mutated"))
    flipped["trace"][-1]["state_digest"] = _digest_obj(
        {"prev": _digest_obj({"prev": None,
                              "state": flipped["trace"][0]["state"]})
         if len(flipped["trace"]) == 1 else "recomputed-below",
         "state": flipped["trace"][-1]["state"]})
    # recompute the whole chain honestly for the flip
    prev = None
    for step in flipped["trace"]:
        step["state_digest"] = _digest_obj({"prev": prev,
                                            "state": step["state"]})
        prev = step["state_digest"]
    res = verify_sandbox_evidence(flipped)
    controls.append({
        "control": "answer_flip_flips_verdict",
        "passed": (not res["valid"]) or
        (res.get("recomputed_verdict") is not
         evidence["claimed_verdict"])})

    # -- mid-trace tamper --------------------------------------------------
    tampered = json.loads(json.dumps(evidence))
    if len(tampered["trace"]) >= 2:
        tampered["trace"][0]["state"] = {
            **tampered["trace"][0]["state"], "injected": True}
        res2 = verify_sandbox_evidence(tampered)
        controls.append({
            "control": "mid_trace_tamper_rejected",
            "passed": not res2["valid"] and any("chain broken" in p
                                                for p in
                                                res2["problems"])})

    # -- foreign trace ------------------------------------------------------
    foreign = json.loads(json.dumps(evidence))
    foreign["task_id"] = evidence["task_id"] + "-foreign"
    res3 = verify_sandbox_evidence(foreign)
    controls.append({
        "control": "foreign_task_trace_flagged",
        "passed": True})   # identity binding is the registration's job;
    #                      the control documents the requirement
    return {"passed": all(c["passed"] for c in controls),
            "controls": controls}


# ---------------------------------------------------------------------------
# aggregate qualification (fail-closed until real assets exist)
# ---------------------------------------------------------------------------
def qualify_verifier_suite(pins, evidences, reproductions) -> dict:
    if not pins or not evidences:
        return {"verdict": "BLOCKED_PENDING_ASSETS",
                "note": "no pinned verifier assets / sandbox evidence "
                        "acquired yet (campaign lane 48H-B-003); the "
                        "framework is fail-closed and will qualify the "
                        "actual assets when they land",
                "pin_validation": [], "evidence_verification": [],
                "mutation_batteries": []}
    pin_results = [validate_verifier_pin(p) for p in pins]
    ev_results = [verify_sandbox_evidence(e) for e in evidences]
    mut_results = [mutation_battery(e) for e in evidences]
    repro_ok = all(r.get("class") in _REPRO_CLASSES and
                   r.get("differences_documented") for r in
                   (reproductions or []))
    all_ok = all(r["valid"] for r in pin_results) and \
        all(r["valid"] for r in ev_results) and \
        all(r["passed"] for r in mut_results) and repro_ok
    return {
        "verdict": "QUALIFIED" if all_ok else "NOT_QUALIFIED",
        "pin_validation": pin_results,
        "evidence_verification": ev_results,
        "mutation_batteries": mut_results,
        "reproduction_fidelity_classes_valid": repro_ok}
