"""Execute the selected, frozen configurations on a separate, rule-labeled GPU holdout."""
import argparse
from functools import lru_cache
import json
from pathlib import Path

from .archive import digest, export, verify
from .contracts import ROOT as AEVE, validate_judgment
from .controller import DEFAULT, add, connect, work
from .history import lines
from .local_judge import role_for
from .metrics import agree
from .q2_development import ARMS, COLLECTION as DEV, REGISTRY, config, grade, request
from .q2_gold import FOLDER, cases, freeze
from .q2_report import build as development_report
from .report_qualification import measures
from .runtime import ROOT, fingerprint, write_json

COLLECTION = "gold-qualification-q2-v1"


def protocol(archive):
    dev = development_report(archive)
    if len(dev["cases"]) != 360:
        raise ValueError("matched development roster is incomplete")
    arms = {}
    for candidate in config()["order"]:
        def ranking(arm):
            score = dev["groups"][f"{candidate}/{arm}"]
            if score["recorded"] != 24:
                raise ValueError("development treatment is incomplete")
            return score["citations"],score["correct"],-ARMS.index(arm)
        arms[candidate] = max(ARMS,key=ranking)
    frozen = freeze()
    return {"version":COLLECTION,"arms":arms,"dataset_sha256":digest(FOLDER/"manifest.json"),
            "roster_size":frozen["packets"],"selected_from_sha256":fingerprint(dev["cases"]),
            "source_sha256":{name:digest(AEVE/name) for name in ("q2_qualification.py","q2_development_freeze.json",
                  "q2_gold.py","q2_development_registry.json","report_qualification.py","metrics.py")},
            "thresholds":json.loads((AEVE/"evaluator_manifest.json").read_bytes())["qualification_gates"]}


@lru_cache(maxsize=1)
def roster():
    return {r["case_id"]:r for r in cases()}


def spec_for(case,candidate,plan):
    return {**request(case,candidate,plan["arms"][candidate]),"qualification_freeze":fingerprint(plan)}


def seed(db,plan):
    with db:
        for case in roster().values():
            for model in plan["arms"]:
                dim = case["dimension"]
                add(db,COLLECTION,case["case_id"],model,dim,role_for(dim),spec_for(case,model,plan))


def observed(archive,plan):
    verify(archive)
    findings = {c:{} for c in plan["arms"]}
    for manifest in sorted((archive/"sessions").glob("*/manifest.json")):
        outcome = json.loads((manifest.parent/"outcomes.json").read_bytes())
        if not any(r["collection"] == COLLECTION for r in outcome):
            continue
        identity = json.loads((manifest.parent/"identity.json").read_bytes())
        for row in lines(manifest.parent/"captures.jsonl.gz"):
            if row["collection"] != COLLECTION:
                continue
            model, case_id = row["candidate"],row["item"]
            spec = spec_for(roster()[case_id],model,plan)
            model_sha = config()["candidates"][model]["sha256"]
            if (identity["candidate"] != model or identity["identity"]["model"]["model_sha256"] != model_sha
                    or spec != row["spec"] or case_id in findings[model]):
                raise ValueError("qualification capture differs from the selected configuration")
            replay = None
            if row["transport"] == "PASS":
                wire = json.loads(row["capture"]["raw_response"])
                try:
                    replay = grade(spec,wire["choices"][0]["message"]["content"])
                    validate_judgment(spec["packet"],replay)
                except (KeyError,TypeError,ValueError):
                    replay = None
            if replay != row["evaluation"] and (replay is not None or "verdict" in row["evaluation"]):
                raise ValueError("qualified verdict differs from raw capture")
            findings[model][case_id] = (replay,row["job"],row["run"])
    return findings


def measure(archive,plan):
    captures = observed(archive,plan)
    models = {}
    for model,responses in captures.items():
        rows = []
        for cid,case in roster().items():
            prediction, answer, job, run = "NOT_RUN",None,None,None
            if cid in responses:
                answer,job,run = responses[cid]
                prediction = answer["verdict"] if answer else "INVALID"
            rows.append({"case_id":cid,"base_id":case["base_id"],"label":case["expected"],"tags":case["tags"],
                         "prediction":prediction,"attempted_decision":prediction in {"PASS","FAIL"},
                         "citation_correct":bool(answer and set(answer["evidence_refs"]) == set(case["required_refs"])),
                         "language":case["language"],"dimension":case["dimension"],"job":job,"run":run})
        metrics, diagnostics = measures(rows)
        missing = [key for key,minimum in plan["thresholds"].items() if key != "kappa" and (
                   (metrics[key]["point_among_recorded"] if metrics[key]["point_among_recorded"] is not None else -1) < minimum)]
        count = len(responses)
        status = "NOT_RUN" if count < plan["roster_size"] else "FAIL" if missing else "BLOCKED"
        models[model] = {"status":status, "recorded":count,"required":plan["roster_size"],
                         "metrics":metrics,"diagnostics":diagnostics,"unmet":missing if count == plan["roster_size"] else [],
                         "cases":rows}
    agreement = {}
    names = list(models)
    for index,first in enumerate(names):
        for second in names[index+1:]:
            a,b = models[first],models[second]
            agreement[first+"/"+second] = pair = agree([r["prediction"] for r in a["cases"]],[r["prediction"] for r in b["cases"]])
            if a["status"] in {"BLOCKED","PASS"} and b["status"] in {"BLOCKED","PASS"}:
                if (pair["cohens_kappa"] or 0) >= plan["thresholds"]["kappa"]:
                    a["status"] = b["status"] = "PASS"
    return {"protocol":plan,"models":models,"agreement":agreement}


def run(db,state,assets,port,archive,*,execute=True):
    lock = state/"q2-qualification-protocol.json"
    plan = protocol(archive)
    if lock.exists():
        if json.loads(lock.read_bytes()) != plan:
            raise ValueError("Q2 protocol already frozen with different evidence or code")
    else:
        write_json(lock,plan)
    if execute:
        seed(db,plan)
        while True:
            count = 0
            for model in plan["arms"]:
                count += work(db,state,assets,port,model,[COLLECTION],96,registry=REGISTRY,grader=grade)
                export(db,state,archive)
            if not count:
                break
            print("sealed Q2 qualification batch",count,flush=True)
    report = measure(archive,plan)
    write_json(state/"q2-qualification-report.json",report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("freeze","run","report"))
    parser.add_argument("--archive",type=Path,default=ROOT/"evaluation/aeve/results")
    parser.add_argument("--state",type=Path,default=DEFAULT)
    parser.add_argument("--assets",type=Path,default=ROOT.parent.parent)
    parser.add_argument("--port",type=int,default=18744)
    args = parser.parse_args()
    db = connect(args.state)
    try:
        report = run(db,args.state,args.assets,args.port,args.archive,execute=args.action=="run")
        print({c:(v["status"],v["recorded"]) for c,v in report["models"].items()})
    finally:
        db.close()


if __name__ == "__main__":
    main()
