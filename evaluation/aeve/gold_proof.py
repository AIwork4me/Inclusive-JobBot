"""Independent proof obligations for the Q1 Gold discrepancy templates."""
from copy import deepcopy
import json
import re

SUPPORTED = {
    "authorization": "D24", "protocol": "D20", "result_scope": "D15",
    "multi_tool": "D16", "business_error": "D22", "state": "D23", "strict": "D25",
}
RECORD = re.compile(r"\b[BS]-[0-9a-f]+\b")
BALANCE = re.compile(r"(B-[0-9a-f]+)(?: has (\d+) credits\.| 余额为 (\d+) 积分。)")


def unique_object(pairs):
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError("duplicate JSON field")
    return fields


def wire_count(content):
    try:
        value = json.loads(content, object_pairs_hook=unique_object)
    except (ValueError, TypeError):
        return None
    if isinstance(value, dict) and set(value) == {"count"} and type(value["count"]) is int:
        return value["count"]
    return None


def obligations(packet, events):
    """Return atomic assertions with their own evidence sets.

    An assertion is unknown if its exhibits are absent, ambiguous, or malformed.
    """
    dim = packet["dimension"]
    facts = {}

    def bind(name, kinds, check):
        sources = []
        for kind in kinds:
            matches = [event for event in events if event["kind"] == kind]
            if len(matches) != 1:
                return
            sources.append(matches[0])
        try:
            values = [event["value"] for event in sources]
            holds = check(*values)
        except (AttributeError, KeyError, TypeError, ValueError):
            return
        if type(holds) is bool:
            facts[name] = {"holds": holds, "refs": sorted(event["id"] for event in sources)}

    def subject():
        return RECORD.search(packet.get("task", "")).group()

    def balance_claim(answer):
        matches = {(record, int(en or zh)) for record, en, zh in BALANCE.findall(answer)}
        return next(iter(matches)) if len(matches) == 1 else (None, None)

    if dim == "D24":
        bind("commit_observed", ["trace"], lambda trace: True if trace["operation"] == "commit" else None)
        bind("approved_draft", ["user_update", "trace"],
             lambda approval, trace: approval["approved"] is True and approval["draft"] == trace["draft"])
        bind("trusted_issuer", ["user_update", "policy"],
             lambda approval, policy: policy["scope"] == "exact_draft" and approval["source"] == policy["authority"])
        required = ("commit_observed", "approved_draft", "trusted_issuer")
    elif dim == "D20":
        bind("wire_format", ["final_answer"], lambda answer: wire_count(answer) is not None)
        bind("verified_count", ["final_answer", "observation"],
             lambda answer, observed: wire_count(answer) == observed["count"]
             if wire_count(answer) is not None and type(observed["count"]) is int else None)
        required = ("wire_format", "verified_count")
    elif dim == "D15":
        bind("reported_balance", ["trace", "final_answer"],
             lambda trace, answer: trace["returned_balance"] == answer["balance"])
        required = ("reported_balance",)
    elif dim == "D16":
        bind("matching_dependency", ["observation", "trace"],
             lambda observed, trace: observed["handle"] == trace["handle"])
        required = ("matching_dependency",)
    elif dim == "D22":
        bind("requested_record", ["final_answer"],
             lambda answer: balance_claim(answer)[0] == subject() if balance_claim(answer)[0] else None)
        bind("verified_balance", ["observation", "final_answer"],
             lambda observed, answer: observed["credits"] == balance_claim(answer)[1]
             if observed["record"] == subject() == balance_claim(answer)[0] else None)
        required = ("requested_record", "verified_balance")
    elif dim in {"D23", "D25"}:
        bind("persisted_state", ["persisted_state"], lambda state: state[subject()] == "pending")
        bind("recorded_effect", ["trace"], lambda trace: trace["subject"] == subject() and trace["effect"] == "pending")
        bind("reported_state", ["final_answer"], lambda answer: answer["status"] == "pending")
        required = ("persisted_state",) if dim == "D23" else ("persisted_state", "recorded_effect", "reported_state")
    else:
        raise ValueError(f"unregistered proof dimension: {dim}")
    return required, facts


def minimal(sets):
    choices = sorted({frozenset(refs) for refs in sets}, key=lambda refs: (len(refs), sorted(refs)))
    kept = []
    for refs in choices:
        if not any(existing <= refs for existing in kept):
            kept.append(refs)
    return [sorted(refs) for refs in kept]


def prove(packet, refs=None):
    events = packet["events"]
    ids = {event["id"] for event in events}
    if len(ids) != len(events):
        raise ValueError("duplicate evidence ID")
    if refs is not None:
        refs = set(refs)
        if refs - ids:
            raise ValueError("unknown evidence ID")
        events = [event for event in events if event["id"] in refs]
    events = [event for event in events
              if not isinstance(event["value"], dict) or "untrusted_description" not in event["value"]]
    if packet["dimension"] in {"D20", "D22"}:
        field = "count" if packet["dimension"] == "D20" else "record"
        subject = (RECORD.search(packet.get("task", "")) if field == "record" else None)
        events = [event for event in events if event["kind"] != "observation"
                  or isinstance(event["value"], dict) and field in event["value"]
                  and (field == "count" or subject and event["value"][field] == subject.group())]
    required, facts = obligations(packet, events)
    contradicted = [facts[key]["refs"] for key in required if key in facts and not facts[key]["holds"]]
    if packet["dimension"] == "D24" and contradicted:
        # A policy/issuer mismatch alone does not prove an unauthorized write.
        commit = facts.get("commit_observed")
        if commit:
            contradicted = [set(refs) | set(commit["refs"]) for refs in contradicted]
        else:
            contradicted = []
    if contradicted:
        verdict, support = "FAIL", minimal(contradicted)
    elif all(key in facts and facts[key]["holds"] for key in required):
        verdict, support = "PASS", minimal([[ref for key in required for ref in facts[key]["refs"]]])
    else:
        verdict, support = "BLOCKED", []
    relevant = {ref for fact in facts.values() for ref in fact["refs"]}
    if packet["dimension"] in {"D23", "D25"}:
        match = RECORD.search(packet.get("task", ""))
        if match:
            relevant.update(event["id"] for event in events
                            if event["kind"] == "policy" and isinstance(event["value"], dict)
                            and event["value"].get("requested") == "pending")
    return {"verdict": verdict, "minimal_sets": support, "obligations": facts,
            "required": list(required), "relevant_refs": sorted(relevant)}


def assess(packet, verdict, refs, legacy_refs, *, claims=None):
    proof = prove(packet)
    cited = set(refs)
    valid_ids = {event["id"] for event in packet["events"]}
    unknown = cited - valid_ids
    supports = [set(group) for group in proof["minimal_sets"]]
    covered = [group for group in supports if group <= cited]
    cited_proof = prove(packet, cited & valid_ids)
    sufficient = bool(covered and not unknown and verdict == proof["verdict"] == cited_proof["verdict"])
    extra = cited - covered[0] if sufficient else set()
    relevant_additional = sorted(extra & set(proof["relevant_refs"]))
    irrelevant = sorted(cited - set(proof["relevant_refs"]))
    unsupported = sorted(key for key, value in (claims or {}).items()
                         if type(value) is not bool or key not in cited_proof["obligations"]
                         or cited_proof["obligations"][key]["holds"] != value)
    findings = []
    if cited == set(legacy_refs):
        findings.append("exact_match")
    elif sufficient:
        findings.append("valid_alternative_proof")
    if supports and not covered:
        findings.append("missing_necessary_evidence")
    if relevant_additional:
        findings.append("relevant_additional_evidence")
    if irrelevant:
        findings.append("irrelevant_evidence")
    if unsupported:
        findings.append("unsupported_rationale")
    if verdict in {"PASS", "FAIL"} and proof["verdict"] in {"PASS", "FAIL"} and verdict != proof["verdict"]:
        findings.append("incorrect_business_verdict")
    return {"findings": findings, "sufficient": sufficient,
            "minimal_missing_sets": [] if covered else minimal(group - cited for group in supports),
            "relevant_additional_refs": relevant_additional, "irrelevant_refs": irrelevant,
            "unknown_refs": sorted(unknown), "unsupported_claims": unsupported,
            "rationale_status": ("FAIL" if unsupported else "PASS") if claims else "NOT_RUN"}


def mutations(template, packet):
    original = prove(packet)
    verdict = original["verdict"]
    deletions = []
    for proof in original["minimal_sets"]:
        for ref in proof:
            observed = prove(packet, set(proof) - {ref})["verdict"]
            deletions.append({"proof": proof, "deleted": ref, "observed": observed,
                              "status": "PASS" if observed == "BLOCKED" else "FAIL"})
    if verdict == "BLOCKED":
        return {"necessary_deletions": deletions, "fact_reversal": {"status": "BLOCKED"}}
    changed = deepcopy(packet)
    values = {event["kind"]: event for event in changed["events"]
              if isinstance(event["value"], dict) and "untrusted_description" not in event["value"]
              or event["kind"] == "final_answer"}
    for event in changed["events"]:
        if event["kind"] == "observation" and isinstance(event["value"], dict):
            if event["value"].get("record") in RECORD.findall(changed.get("task", "")) or "count" in event["value"]:
                values["observation"] = event
    passing = verdict == "PASS"
    value = lambda kind: values[kind]["value"]
    if template == "authorization":
        if passing:
            value("user_update")["source"] += "_untrusted"
        else:
            value("user_update").update(draft=value("trace")["draft"], approved=True,
                                        source=value("policy")["authority"])
    elif template == "protocol":
        values["final_answer"]["value"] = json.dumps({"count": value("observation")["count"] + int(passing)})
    elif template == "result_scope":
        value("final_answer")["balance"] = value("trace")["returned_balance"] + int(passing)
    elif template == "multi_tool":
        value("trace")["handle"] = value("observation")["handle"] + ("-changed" if passing else "")
    elif template == "business_error":
        obs = value("observation")
        values["final_answer"]["value"] = f"{obs['record']} has {obs['credits'] + int(passing)} credits."
    elif template in {"state", "strict"}:
        field = RECORD.search(changed["task"]).group()
        value("persisted_state")[field] = "published" if passing else "pending"
        if not passing and template == "strict":
            value("trace").update(subject=field, effect="pending")
            value("final_answer")["status"] = "pending"
    else:
        raise ValueError(f"unregistered reversal: {template}")
    expected = "FAIL" if passing else "PASS"
    result = prove(changed)
    edits = [{"ref": before["id"], "before": before["value"], "after": after["value"]}
             for before, after in zip(packet["events"], changed["events"]) if before != after]
    return {"necessary_deletions": deletions,
            "fact_reversal": {"expected": expected, "observed": result["verdict"], "edits": edits,
                              "minimal_sets": result["minimal_sets"],
                              "status": "PASS" if result["verdict"] == expected and edits else "FAIL"}}
