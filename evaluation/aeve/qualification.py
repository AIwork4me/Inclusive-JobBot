"""Freeze the four physical Judge configurations and measure verified, sealed attempts."""
import argparse
import gzip
import json
from pathlib import Path

from .archive import digest, verify
from .contracts import ROOT, sha
from .gold import FOLDER, iter_gold
from .local_judge import body_for, check, role_for
from .metrics import audit_metrics
from .runtime import REGISTRY, canonical, fingerprint, write_json


def request_for(case,candidate):
    packet = case["packet"]
    dim = packet["dimension"]
    role = role_for(dim)
    body = body_for(candidate,packet,role)
    rubric = json.loads((ROOT/"evaluator_manifest.json").read_bytes())["dimensions"][dim]["rubric"]
    body["messages"][0]["content"] += " Evaluation criterion: " + rubric
    return role, {"packet":packet,"body":body}


def protocol():
    root = ROOT.parents[1]
    files = [ROOT/name for name in ("local_judge.py","contracts.py","evaluator_manifest.json","gold.py",
             "input.schema.json","judgment.schema.json","judge_registry.json","qualification.py","metrics.py")]
    files += [FOLDER/"manifest.json"]
    gold_hashes = json.loads((FOLDER/"manifest.json").read_bytes())["sha256"]
    for name, expected in gold_hashes.items():
        if digest(FOLDER/name) != expected:
            raise ValueError("gold split differs from manifest")
    return {"version":"AEVE-GOLD-R1-Q1","sources":{f.relative_to(root).as_posix():digest(f) for f in files},
            "candidates":list(json.loads(REGISTRY.read_bytes())["candidates"]),
            "order":"qualify all frozen candidates before scoring formal history",
            "citation_gate":"Cited source IDs must be the frozen proof and independently support the verdict polarity.",
            "abstentions":"No credit for nondecisions. Report coverage alongside citation accuracy.",
            "qualification_cases_per_candidate":sum(1 for _ in iter_gold("qualification")),
            "thresholds":json.loads((ROOT/"evaluator_manifest.json").read_bytes())["qualification_gates"]}


def require_freeze():
    path = ROOT/"qualification_freeze.json"
    expected = protocol()
    if json.loads(path.read_bytes()) != expected:
        raise ValueError("qualification protocol differs from preregistered bytes")
    return fingerprint(expected)


def seed(db):
    from .controller import add
    freeze = require_freeze()
    candidates = json.loads(REGISTRY.read_bytes())["candidates"]
    with db:
        for case in iter_gold("qualification"):
            for candidate in candidates:
                role,spec = request_for(case,candidate)
                spec["qualification_freeze"] = freeze
                add(db,"gold-qualification",case["case_id"],candidate,case["dimension"],role,spec)


def measure(results, split="qualification"):
    freeze = require_freeze()
    verify(results)
    entries = []
    seen = set()
    models = json.loads(REGISTRY.read_bytes())["candidates"]
    cases = {c["case_id"]:c for c in iter_gold(split)}
    for stamp in sorted((results/"sessions").glob("*/manifest.json")):
        file = stamp.parent/"captures.jsonl.gz"
        manifest = json.loads(stamp.read_bytes())
        ident = json.loads((file.parent/"identity.json").read_bytes())
        if manifest["gpu_evidence"] != "PASS" or not manifest["active_pid_counter_samples"]:
            continue
        with gzip.open(file,"rt",encoding="utf8") as stream:
            for line in stream:
                row = json.loads(line)
                if row["collection"] != "gold-"+split:
                    continue
                candidate, cid, spec = row["candidate"],row["item"],row["spec"]
                case = cases[cid]
                role,expected = request_for(case,candidate)
                if split == "qualification":
                    expected["qualification_freeze"] = freeze
                if (ident["candidate"] != candidate or ident["identity"]["model"]["model_sha256"] != models[candidate]["sha256"]
                        or spec != expected or row["role"] != role):
                    raise ValueError("sealed evaluator configuration differs")
                capture = row["capture"]
                body = {**expected["body"],"verbose":True,"return_tokens":True}
                if capture["request"] != body:
                    raise ValueError("captured wire differs from frozen request")
                if row["transport"] == "PASS":
                    raw = json.loads(capture["raw_response"])["choices"][0]["message"].get("content")
                    try:
                        reconstructed = check(spec["packet"],raw)
                    except (TypeError,ValueError,KeyError):
                        reconstructed = None
                    if reconstructed != row["evaluation"] and (reconstructed is not None or "verdict" in row["evaluation"]):
                        raise ValueError("archived judgment differs from raw generation")
                if (candidate,cid) in seen:
                    raise ValueError("duplicate sealed judgment")
                seen.add((candidate,cid))
                try:
                    usage = json.loads(capture["raw_response"]).get("usage",{})
                except (TypeError,ValueError):
                    usage = {}
                entries.append({"candidate":candidate,"case_id":cid,"answer":row["evaluation"],
                                "packet_sha256":sha(spec["packet"]),"latency_ms":capture["wall_ms"],
                                "input_tokens":usage.get("prompt_tokens"),"output_tokens":usage.get("completion_tokens")})
    report = audit_metrics(split,entries)
    gates = protocol()["thresholds"]
    admission = {}
    for candidate in models:
        result = report["models"].get(candidate,{})
        if result:
            rows = report["case_results"][candidate]
            attempted = sum(r["attempted_decision"] for r in rows)
            supported = sum(r["citation_correct"] and r["prediction"] == r["label"] for r in rows)
            result["citation_id_set_accuracy"] = result["citation_accuracy"]
            result["citation_accuracy"] = supported / attempted if attempted else None
            result["thresholds"]["citation_accuracy"]["observed"] = result["citation_accuracy"]
        complete = result.get("executed",0) == len(cases)
        missed = [k for k,v in gates.items() if k != "kappa" and
                  (result.get(k) is None or result[k] < v)]
        admission[candidate] = {"status":"NOT_RUN" if split != "qualification" or not complete else
                                 "FAIL" if missed else "BLOCKED","thresholds_missed":missed if complete else [],
                                 "recorded":result.get("executed",0),"required":len(cases)}
    if split == "qualification":
        for pair, values in report["cross_judge"].items():
            a,b = pair.split("/")
            if all(admission[c]["status"] in {"BLOCKED","PASS"} for c in (a,b)):
                if (values["cohens_kappa"] or 0) >= gates["kappa"]:
                    admission[a]["status"] = admission[b]["status"] = "PASS"
    report.update(admission=admission, protocol_sha256=freeze)
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--split",choices=("development","calibration","qualification"),default="qualification")
    cli.add_argument("--results",type=Path,default=ROOT/"results")
    cli.add_argument("--output",type=Path)
    args = cli.parse_args()
    report = measure(args.results,args.split)
    if args.output:
        write_json(args.output,report)
    print(json.dumps(report["admission"]))


if __name__ == "__main__":
    main()
