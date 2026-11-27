"""Run matched development-only repairs for Judge evidence disagreements."""
import argparse
from collections import Counter
from functools import lru_cache
import json
from pathlib import Path

from benchmarks.tool_calling_v2.oracle import decode_object
from .archive import digest, export, verify
from .contracts import DIMENSIONS
from .controller import DEFAULT, add, connect, work
from .gold import FOLDER, iter_gold
from .history import lines
from .local_judge import body_for, check, role_for
from .runtime import ROOT, fingerprint, write_json

REGISTRY = Path(__file__).with_name("q2_development_registry.json")
FREEZE = Path(__file__).with_name("q2_development_freeze.json")
COLLECTION = "gold-development-q2-d1"
ARMS = ("baseline", "evidence_roles", "combined")
DECISION_KINDS = frozenset({"final_answer", "plan", "trace", "parsed_call", "raw_generation", "arguments"})
STRATA = ("business_error", "false_success", "authorization", "semantic_equivalence", "injection", "objective")


@lru_cache(maxsize=1)
def config():
    return json.loads(REGISTRY.read_bytes())


def roster():
    entries = list(iter_gold("development"))
    chosen = {}
    for tag in STRATA:
        for verdict in ("PASS", "FAIL"):
            by_world = {}
            for case in entries:
                matches = tag in case["tags"] or (tag == "semantic_equivalence" and verdict == "FAIL" and case["dimension"] == "D05")
                if matches and case["expected"] == verdict and case["base_id"] not in chosen:
                    by_world.setdefault(case["base_id"], case)
            for case in list(by_world.values())[:2]:
                chosen[case["base_id"]] = case
    if len(chosen) != 24:
        raise ValueError("development roster no longer fills its strata")
    return list(chosen.values())


def request(case, candidate, arm):
    packet = case["packet"]
    dim = packet["dimension"]
    role = role_for(dim)
    body = body_for(candidate, packet, role)
    rule = " Evaluation criterion: " + DIMENSIONS[dim]["rubric"]
    body["messages"][0]["content"] += rule
    spec = {"packet": packet, "body": body, "arm": arm, "case_id": case["case_id"]}
    if arm == "baseline":
        return spec
    ids = [e["id"] for e in packet["events"]]
    decision = [e["id"] for e in packet["events"] if e["kind"] in DECISION_KINDS]
    source = [e for e in ids if e not in decision]
    schema = body["response_format"]["json_schema"]["schema"]
    props = schema["properties"]
    del props["evidence_refs"]
    props["decision_refs"] = {"type": "array", "items": {"type": "string", "enum": decision or ids}}
    props["source_refs"] = {"type": "array", "items": {"type": "string", "enum": source or ids}}
    schema["required"] = ["decision_refs", "source_refs", "reason_summary", "verdict"]
    exhibits = {"decision_candidates":decision,"reference_candidates":source}
    spec["exhibits"] = exhibits
    body["messages"][1]["content"] = json.dumps({**packet,"reference_roles":exhibits},ensure_ascii=False,sort_keys=True)
    body["messages"][0]["content"] += (
        " Use decision_refs for exhibits showing the candidate action, answer or plan. Use source_refs "
        "for policy, observed facts or comparison inputs. Cite only IDs essential to establish the result. "
        "Either list can be empty when that role does not establish the criterion.")
    if arm == "combined":
        body["messages"][0]["content"] += (
            " Before deciding, compare the exact entity, value, time and scope mentioned in the exhibits. "
            "Treat a claimed operation as a claim unless a recorded state or receipt proves it. "
            "Check conditional duties against their actual trigger. Use facts from the relevant exhibits only. "
            "In the reason, give the decisive comparison without inventing a field or requiring an irrelevant event.")
    return spec


def grade(spec, raw):
    if spec["arm"] == "baseline":
        return check(spec["packet"],raw)
    answer = decode_object(raw)
    if set(answer) != {"decision_refs","source_refs","reason_summary","verdict"}:
        raise ValueError("invalid evidence role structure")
    references = []
    for key, group in (("decision_refs","decision_candidates"),("source_refs","reference_candidates")):
        refs = answer[key]
        allowed = spec["exhibits"][group]
        if not isinstance(refs,list) or any(not isinstance(ref,str) or ref not in allowed for ref in refs):
            raise ValueError("evidence reference has the wrong role")
        references.extend(refs)
    normalized = {"verdict":answer["verdict"],"reason_summary":answer["reason_summary"],"evidence_refs":references}
    return check(spec["packet"],json.dumps(normalized))


def manifest():
    data = {"version":config()["version"],"eligible_arms":list(ARMS),"cases":[r["case_id"] for r in roster()],
            "gold_manifest_sha256":digest(FOLDER/"manifest.json"),
            "registry_sha256":digest(REGISTRY),"source_sha256":digest(Path(__file__)),
            "request_sha256": {c:fingerprint([request(case,c,arm) for case in roster() for arm in ARMS])
                               for c in config()["order"]}}
    return data


def freeze():
    data = manifest()
    if data != json.loads(FREEZE.read_bytes()):
        raise ValueError("development experiment differs from its preregistration")
    return data


def seed(db):
    stamp = fingerprint(freeze())
    with db:
        for case in roster():
            packet = case["packet"]
            for arm in ARMS:
                item = case["case_id"] + "/" + arm
                for model in config()["order"]:
                    spec = request(case,model,arm)
                    add(db,COLLECTION,item,model,packet["dimension"],role_for(packet["dimension"]),
                        {**spec,"development_freeze":stamp})


def summarize(out):
    stamp = fingerprint(freeze())
    verify(out)
    keys = {r["case_id"]:r for r in roster()}
    counts = {f"{model}/{arm}":Counter({"planned":len(keys)}) for model in config()["order"] for arm in ARMS}
    rows = []
    for manifest in sorted((out/"sessions").glob("*/manifest.json")):
        identity = json.loads((manifest.parent/"identity.json").read_bytes())
        members = json.loads((manifest.parent/"outcomes.json").read_bytes())
        if not any(r["collection"] == COLLECTION for r in members):
            continue
        for row in lines(manifest.parent/"captures.jsonl.gz"):
            if row["collection"] != COLLECTION:
                continue
            spec, model, result = row["spec"], row["candidate"], row["evaluation"]
            case = keys[spec["case_id"]]
            if identity["candidate"] != model or identity["identity"]["model"]["model_sha256"] != config()["candidates"][model]["sha256"]:
                raise ValueError("physical judge differs from development freeze")
            if spec != {**request(case,model,spec["arm"]),"development_freeze":stamp}:
                raise ValueError("source request differs from development freeze")
            verdict = result.get("verdict")
            correct = verdict == case["expected"]
            citations = correct and set(result.get("evidence_refs",[])) == set(case["required_refs"])
            stats = counts[f'{model}/{spec["arm"]}']
            stats.update(recorded=1,correct=int(correct),citations=int(citations),
                         abstained=int(verdict=="BLOCKED"),invalid=int(verdict is None))
            rows.append(dict(candidate=model,arm=spec["arm"],case_id=case["case_id"],expected=case["expected"],
                             verdict=verdict,correct_citations=citations,run=row["run"], job=row["job"]))
    return {"version":config()["version"],"admission":"NOT_RUN","groups":counts,"cases":rows}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action",choices=("seed","run","report"))
    cli.add_argument("--state",type=Path,default=DEFAULT)
    cli.add_argument("--assets",type=Path,default=ROOT.parent.parent)
    cli.add_argument("--results",type=Path,default=ROOT/"evaluation/aeve/results")
    cli.add_argument("--output",type=Path)
    cli.add_argument("--port",type=int,default=18744)
    args = cli.parse_args()
    if args.action == "report":
        report = summarize(args.results)
        if args.output:
            write_json(args.output,report)
        print(json.dumps(report["groups"],sort_keys=True))
        return
    db = connect(args.state)
    try:
        seed(db)
        if args.action == "run":
            for model in config()["order"]:
                n = work(db,args.state,args.assets,args.port,model,[COLLECTION],72,registry=REGISTRY,grader=grade)
                print(model,n,export(db,args.state,args.results),flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
