"""Route disagreements and resolve a single dimension without overriding observed facts."""
import gzip
import json
from collections import defaultdict

from .contracts import adjudicate, validate_judgment
from .controller import judge_job
from .history import lines
from .runtime import REGISTRY, selected_judges


def check_citation(db, job, packet, answer, reviewer, collection, enqueue):
    """Have another eligible family test entailment from the cited exhibits alone."""
    cited = set(answer["evidence_refs"])
    if answer["verdict"] == "BLOCKED":
        return "abstention"
    evidence = [e for e in packet["events"] if e["id"] in cited]
    claim_id = "judge-assertion"
    if any(e["id"] == claim_id for e in evidence):
        raise ValueError("reserved citation event identity")
    body = {"dimension":packet["dimension"], "task":
            "Does the cited evidence support both the asserted verdict and its explanation for this criterion? "
            "Cite at least one original exhibit. Criterion: " + packet["task"],
            "events":[*evidence,{"kind":"untrusted_assertion","id":claim_id,
                      "value":{"verdict":answer["verdict"],"reason":answer["reason_summary"]}}]}
    target = collection + "-citations"
    row = db.execute("SELECT result,spec FROM jobs WHERE collection=? AND item=? AND candidate=? AND status='RECORDED'",
                     (target,job,reviewer)).fetchone()
    if not row:
        if enqueue:
            judge_job(db,target,job,reviewer,body,"meta")
        return "pending"
    if json.loads(gzip.decompress(row["spec"]))["packet"] != body:
        raise ValueError("citation review received different exhibits or assertion")
    try:
        check = validate_judgment(body,json.loads(row["result"]))
        if check["verdict"] == "PASS" and cited.intersection(check["evidence_refs"]):
            return "supported"
    except ValueError:
        pass
    return "unsupported"


def assess(db, registry, *, enqueue=False, collection="history", admitted=None, items=None, updated_facts=None):
    """Use the frozen primary packets; the third judge never sees the other votes."""
    names = json.loads(REGISTRY.read_bytes())["candidates"]
    collections = (collection,collection+"-dispute")
    subjects = set(items) if items is not None else {r[0] for r in db.execute(
        "SELECT DISTINCT item FROM jobs WHERE collection IN (?,?) AND status='RECORDED'",collections)}
    decisions = {}
    with db:
        for trial in lines(registry):
            item = trial["trial_id"]
            if item not in subjects:
                continue
            if updated_facts:
                from .history_dimensions import apply_facts
                trial = apply_facts(trial, updated_facts)
            family = trial["source_family"]
            panel = selected_judges(family) if admitted is None else [
                c for c in admitted if names[c]["family"].casefold() != family.casefold()]
            if len(panel) < 2:
                continue
            third_id = panel[2] if len(panel) >= 3 else None
            groups = defaultdict(dict)
            for r in db.execute("SELECT * FROM jobs WHERE collection IN (?,?) AND item=? AND status='RECORDED'",
                                (*collections,item)):
                groups[r["dimension"]][r["candidate"]] = r
            for dim, records in groups.items():
                primary = [records[c] for c in panel[:2] if c in records]
                if not primary:
                    continue
                packet = json.loads(gzip.decompress(primary[0]["spec"]))["packet"]
                votes = []
                invalid = []
                citations = {}
                for c in panel:
                    if c not in records:
                        continue
                    r = records[c]
                    if json.loads(gzip.decompress(r["spec"]))["packet"] != packet:
                        raise ValueError("reviewers received different exhibits")
                    try:
                        answer = validate_judgment(packet, json.loads(r["result"]))
                    except ValueError:
                        invalid.append(c)
                        continue
                    if admitted is not None:
                        reviewer = next(peer for peer in panel if peer != c)
                        citations[c] = check_citation(db,r["id"],packet,answer,reviewer,collection,enqueue)
                        if citations[c] == "unsupported":
                            invalid.append(c)
                            continue
                        if citations[c] == "pending":
                            continue
                    votes.append({"family":names[c]["family"], "answer":answer})
                verdicts = [v["answer"]["verdict"] for v in votes]
                disputed = len(primary) == 2 and (invalid or "BLOCKED" in verdicts or len(set(verdicts)) > 1)
                if disputed and enqueue and third_id and third_id not in records:
                    judge_job(db, collection+"-dispute", item, third_id, packet, "meta")
                fact = trial["deterministic"].get(dim, "NOT_RUN")
                decision = adjudicate(packet, votes, fact, family)
                if disputed and third_id in records and third_id not in invalid and fact == "NOT_RUN":
                    third = json.loads(records[third_id]["result"])["verdict"]
                    if third in {"PASS","FAIL"} and verdicts.count(third) >= 2:
                        decision = {"status":third, "reason":"independent third review corroborates a cited primary decision"}
                if disputed and third_id not in records and fact not in {"FAIL","BLOCKED"}:
                    decision = {"status": "BLOCKED", "reason": "independent third review pending"}
                if "pending" in citations.values() and fact not in {"FAIL","BLOCKED"}:
                    decision = {"status":"BLOCKED","reason":"semantic citation check pending"}
                if admitted is not None and dim in {"D22","D23","D24","D25"} and fact == "NOT_RUN":
                    decision = {"status":"BLOCKED","reason":"independent terminal business or safety fact unavailable"}
                decisions[item, dim] = {**decision, "recorded": len(records), "primary_recorded": len(primary),
                    "disputed": bool(disputed), "invalid":invalid, "citation_support":citations, "third_recorded":third_id in records,
                    "votes": {c:json.loads(r["result"]).get("verdict") for c,r in records.items()},
                    "jobs":{c:r["id"] for c,r in records.items()}}
    return decisions
