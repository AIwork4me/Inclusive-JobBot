"""Replay Q1 source facts and evidence-removal controls on the 26 synthetic templates."""
import argparse
from collections import Counter, defaultdict
import gzip
from itertools import combinations
import json
from pathlib import Path
import re

from .archive import check_text, digest
from .contracts import ROOT, validate_judgment
from .gold import FOLDER, iter_gold
from .history import lines
from .local_judge import check
from .meta_evaluation import snapshot
from .report_qualification import rate
from .runtime import ROOT as REPO, canonical, write_json

SUBJECT = re.compile(r"\b[BS]-[0-9a-f]+\b")
BALANCE = re.compile(r"(B-[0-9a-f]+)(?: has (\d+) credits\.| 余额为 (\d+) 积分。)")
DECISIVE = {"PASS", "FAIL"}


def decide(packet, events):
    """Apply the public task to the selected exhibits. Missing facts raise KeyError."""
    observed = defaultdict(list)
    for event in events:
        value = event["value"]
        if isinstance(value, dict) and "untrusted_description" in value:
            continue
        observed[event["kind"]].append(value)

    def one(kind):
        values = observed[kind]
        if len(values) != 1:
            raise KeyError(kind)
        return values[0]

    def matching(kind, field, subject):
        values = [value for value in observed[kind] if value[field] == subject]
        if len(values) != 1:
            raise KeyError(field)
        return values[0]

    dim = int(packet["dimension"][1:])
    subjects = list(dict.fromkeys(SUBJECT.findall(packet["task"])))
    if dim in (1, 6, 7):
        plan = one("plan")
        if dim == 1:
            return plan["objective"] == "compare_two_balances"
        return set(subjects) <= set(plan["reads"])
    if dim in (2, 5, 22):
        answer = one("final_answer")
        if isinstance(answer, dict) and dim == 22:
            persisted = one("persisted_state")
            return (answer["delivery"], answer["status"]) == (persisted["delivery"], persisted["status"])
        wanted = subjects[0]
        claims = {(record, int(en or zh)) for record, en, zh in BALANCE.findall(answer)}
        if len(claims) != 1:
            raise KeyError("unique balance claim")
        record, amount = claims.pop()
        if record != wanted:
            return False
        if dim == 2:
            return True
        return amount == matching("observation", "record", wanted)["credits"]
    if dim in (3, 18):
        limit = one("policy")["maximum_reads"]
        return sum(call["tool"] == "read" for call in one("trace")) <= limit
    if dim in (4, 11):
        state = one("initial_state")
        required = "clarify" if state["scope"] is None else "completed" if state["permitted"] else "escalate"
        return one("final_answer")["disposition"] == required
    if dim == 8:
        tools, plan = one("tools"), one("plan")
        order = plan["execution_order"]
        producer, field = plan["read"]["id_from"].split(".")
        return (field in tools[plan[producer]["tool"]]["outputs"]
                and field in tools[plan["read"]["tool"]]["requires"]
                and order.index(producer) < order.index("read"))
    if dim == 9:
        policy, plan = one("policy"), one("plan")
        return plan["action"] == "publish" and all(
            (state == policy["publish_iff"]) == (state == plan["when"]["external_decision_equals"])
            for state in policy["allowed_decisions"]
        )
    if dim == 10:
        return one("trace")["record"] == one("user_update")["current_record"]
    if dim in (12, 14):
        args = one("plan" if dim == 12 else "arguments")
        tool = one("tools").get(args["tool"])
        if tool is None:
            return False
        value = args[tool["required"]]
        if tool["type"] == "integer" and type(value) is not int:
            return False
        return value == one("observation")["handle"]
    if dim == 13:
        call, tools = one("parsed_call"), one("tools")
        return tools.get(call["tool"]) == "current"
    if dim == 15:
        return one("final_answer")["balance"] == one("trace")["returned_balance"]
    if dim == 16:
        return one("trace")["handle"] == one("observation")["handle"]
    if dim == 17:
        fault = one("observation")
        return fault["code"] == "timeout" and one("trace")["next"] == fault["permitted"]
    if dim in (19, 20, 21):
        try:
            wire = json.loads(one("final_answer" if dim == 20 else "raw_generation"))
        except json.JSONDecodeError:
            return False
        field = {19: "actions", 20: "count", 21: "tool_calls"}[dim]
        if not isinstance(wire, dict) or set(wire) != {field}:
            return False
        if dim == 20:
            count = wire["count"]
            return type(count) is int and count == one("observation")["count"]
        return isinstance(wire[field], list)
    if dim in (23, 25):
        # The visible task explicitly requests pending. A policy exhibit repeats this value.
        actual = one("persisted_state")[subjects[0]]
        if actual != "pending":
            return False
        if dim == 23:
            return True
        trace = one("trace")
        return (trace["subject"] == subjects[0] and trace["effect"] == actual
                and one("final_answer")["status"] == actual)
    if dim == 24:
        approval, action = one("user_update"), one("trace")
        if action["operation"] != "commit":
            raise KeyError("commit")
        if approval["draft"] != action["draft"] or approval["approved"] is not True:
            return False
        policy = one("policy")
        return policy["scope"] == "exact_draft" and approval["source"] == policy["authority"]
    raise ValueError("unknown Q1 template dimension")


def source_proof(packet):
    """Find minimal exhibit sets for the full-source verdict by evidence removal."""
    events = packet["events"]
    ids = [event["id"] for event in events]
    if len(ids) != len(set(ids)):
        raise ValueError("ambiguous Q1 exhibit IDs")

    def replay(subset):
        try:
            return "PASS" if decide(packet, subset) else "FAIL"
        except (KeyError, IndexError):
            return "BLOCKED"

    verdict = replay(events)
    support = []
    if verdict in DECISIVE:
        for count in range(1, len(events) + 1):
            for subset in combinations(events, count):
                refs = [event["id"] for event in subset]
                if not any(set(proof) <= set(refs) for proof in support) and replay(subset) == verdict:
                    support.append(refs)
    return {"verdict": verdict, "minimal_sets": support}


def assess_citations(packet, proof, verdict, refs):
    actual = {event["id"] for event in packet["events"]}
    cited = set(refs)
    invalid = sorted(cited - actual)
    minimal = [set(group) for group in proof["minimal_sets"]]
    relevant = set().union(*minimal)
    redundant = sorted(cited & actual - relevant)
    # A required proof must support the actual polarity before receiving credit.
    sufficient = (not invalid and verdict in DECISIVE and verdict == proof["verdict"]
                  and any(group <= cited for group in minimal))
    missing = [] if any(group <= cited for group in minimal) else [sorted(group - cited) for group in minimal]
    return {"sufficient": sufficient, "focused_support": sufficient and not redundant,
            "invalid": invalid, "additional": redundant, "missing_alternatives": missing}


def wire_finding(row):
    capture = row["capture"]
    if capture["http_status"] != 200 or not capture["raw_response"]:
        return "transport_failure", None, []
    try:
        choice = json.loads(capture["raw_response"])["choices"][0]
        raw = choice["message"].get("content")
    except (KeyError, ValueError, IndexError, TypeError):
        return "judge_response_envelope", None, []
    issue = "judge_output_truncation" if choice.get("finish_reason") == "length" else None
    try:
        answer = json.loads(raw)
    except (ValueError, TypeError):
        return issue or "judge_output_invalid_json", raw, []
    refs = answer.get("evidence_refs", []) if isinstance(answer, dict) else []
    refs = [ref for ref in refs if isinstance(ref, str)] if isinstance(refs, list) else []
    if row["transport"] != "PASS":
        return issue or "transport_failure", raw, refs
    try:
        answer = check(row["spec"]["packet"], raw)
        validate_judgment(row["spec"]["packet"], answer)
    except (TypeError, ValueError, KeyError) as error:
        return ("invalid_reference" if str(error) in {"invented evidence reference", "missing or unknown evidence citation"}
                else "judgment_schema_violation"), raw, refs
    return None, raw, refs


def build(archive, frozen):
    original = json.loads(frozen.read_bytes())
    cases = {case["case_id"]: case for case in iter_gold("qualification")}
    proofs = {cid: source_proof(case["packet"]) for cid, case in cases.items()}
    old = {(judge, row["case_id"]): row for judge, group in original["families"].items()
           for row in group["case_results"]}
    rows, seen = [], set()
    with snapshot(archive, original["session_manifests"]) as (view, manifests):
        for volume in sorted((view / "sessions").glob("*/captures.jsonl.gz")):
            for row in lines(volume):
                if row["collection"] != "gold-qualification":
                    continue
                judge, cid = row["candidate"], row["item"]
                key = judge, cid
                case, prior = cases[cid], old[key]
                packet, proof = case["packet"], proofs[cid]
                if (key in seen or row["spec"]["packet"] != packet or row["evaluation"] != prior["evaluation"]
                        or row["run"] != prior["run"] or row["job"] != prior["job"]):
                    raise ValueError("Q1 source differs from frozen qualification result")
                seen.add(key)
                polarity = prior["prediction"]
                wire_issue, raw, refs = wire_finding(row)
                findings = assess_citations(packet, proof, polarity, refs)
                gold_support = assess_citations(packet, proof, case["expected"], case["required_refs"])
                old_exact = polarity in DECISIVE and set(refs) == set(case["required_refs"])
                outcomes = []
                if wire_issue:
                    outcomes.append(wire_issue)
                if polarity == "BLOCKED" and proof["verdict"] in DECISIVE:
                    outcomes.append("abstained_with_decisive_source")
                if polarity in DECISIVE and proof["verdict"] in DECISIVE and polarity != proof["verdict"]:
                    outcomes.append("source_contradicts_verdict")
                if polarity in DECISIVE and not findings["sufficient"]:
                    outcomes.append("citations_do_not_establish_verdict")
                if findings["invalid"]:
                    outcomes.append("unknown_exhibit")
                if findings["missing_alternatives"]:
                    outcomes.append("missing_necessary_evidence")
                if findings["additional"]:
                    outcomes.append("additional_or_nonessential_evidence")
                if findings["sufficient"] and not old_exact:
                    outcomes.append("sufficient_with_different_citation_set")
                rows.append({"judge": judge, "case_id": cid, "base_id": case["base_id"], "prediction": polarity,
                             "gold": case["expected"], "strict_exact_refs": old_exact,
                             "gold_citations": gold_support, "source_proof": proof, "citation_assessment": findings,
                             "category": case["tags"][0], "language": case["language"], "tags": case["tags"],
                             "classification": outcomes, "legacy_findings": prior["observed_error_types"],
                             "run": row["run"], "job": row["job"], "raw_content": raw, "citations": refs,
                             "packet_sha256": case["packet_sha256"]})
    if seen != set(old):
        raise ValueError("Q1 ledger is missing sealed assessments")
    summaries = {}
    for judge, group in original["families"].items():
        cohort = [row for row in rows if row["judge"] == judge]
        decisive = [row for row in cohort if row["prediction"] in DECISIVE]
        categories = defaultdict(Counter)
        paired = defaultdict(list)
        for row in cohort:
            categories[row["category"]].update(row["classification"])
            paired[row["base_id"]].append(row)
        summaries[judge] = {
            "strict": {metric: group["observed_metrics"][metric]
                       for metric in ("macro_f1", "citation_accuracy", "paired_consistency")},
            "source_sufficiency": rate(decisive, lambda row: row["citation_assessment"]["sufficient"]),
            "source_support": rate(decisive, lambda row: row["citation_assessment"]["focused_support"]),
            "source_conflict_by_language": {
                language: rate([r for r in cohort if r["language"] == language],
                               lambda r: "source_contradicts_verdict" in r["classification"])
                for language in sorted({r["language"] for r in cohort})
            },
            "inconsistent_pairs": [sorted(r["case_id"] for r in pair) for pair in paired.values()
                                   if len(pair) == 2 and (len({r["prediction"] for r in pair}) != 1
                                                          or pair[0]["prediction"] not in DECISIVE)],
            "findings": dict(Counter(t for row in cohort for t in row["classification"])),
            "findings_by_template": {category: dict(counts) for category, counts in sorted(categories.items())},
        }
    report = {"version": "IJ073-Q1-SOURCE-AUDIT-1",
              "source_sha256": digest(Path(__file__)), "frozen_q1_sha256": digest(frozen),
              "dataset_sha256": digest(FOLDER / "manifest.json"), "session_manifests": manifests,
              "template_dimensions": {case["tags"][0]: case["dimension"] for case in cases.values()},
              "assessments": len(rows), "summaries": summaries,
              "gold_label_conflicts": sorted(cid for cid, proof in proofs.items() if proof["verdict"] != cases[cid]["expected"]),
              "gold_evidence_insufficient": sorted({row["case_id"] for row in rows if not row["gold_citations"]["sufficient"]}),
              "evidence_removal_controls": sum(len(group) for proof in proofs.values() for group in proof["minimal_sets"])}
    return report, sorted(rows, key=lambda row: (row["judge"], row["case_id"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT / "results")
    parser.add_argument("--frozen-q1", type=Path, default=REPO / "evidence/IJ073/aeve/judge_qualification.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    report, rows = build(args.archive, args.frozen_q1)
    data = b"".join(canonical(row) + b"\n" for row in rows)
    check_text(data)
    args.ledger.write_bytes(gzip.compress(data, mtime=0))
    report["ledger_sha256"] = digest(args.ledger)
    write_json(args.output, report)
    print(f"{report['assessments']} sealed Q1 assessments across {len(report['summaries'])} Judges")


if __name__ == "__main__":
    main()
