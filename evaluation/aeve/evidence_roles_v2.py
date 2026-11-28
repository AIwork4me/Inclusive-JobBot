"""Development contract that gives each exhibit exactly one citation slot."""
from copy import deepcopy
import json

from benchmarks.tool_calling_v2.oracle import decode_object
from .local_judge import check


def use_single_slots(spec):
    """Transform a role-structured Q2 request without changing the packet or labels."""
    result = deepcopy(spec)
    body = result["body"]
    schema = body["response_format"]["json_schema"]["schema"]
    for property_name, group in (("decision_refs","decision_candidates"),("source_refs","reference_candidates")):
        ids = result["exhibits"][group]
        schema["properties"][property_name] = {"type":"object","required":ids,"additionalProperties":False,
                                               "properties":{ident:{"type":"boolean"} for ident in ids}}
    body["messages"][0]["content"] += (
        " Each citation group is an object whose keys are the assigned IDs. "
        "Set an ID to true exactly when it is essential to the comparison. "
        "Return an empty object when the group has no IDs.")
    result["citation_contract"] = "evidence-single-slot/1"
    return result


def grade(spec, raw):
    answer = decode_object(raw)
    if set(answer) != {"decision_refs","source_refs","reason_summary","verdict"}:
        raise ValueError("invalid evidence role structure")
    selected = []
    for property_name, group in (("decision_refs","decision_candidates"),("source_refs","reference_candidates")):
        choices = answer[property_name]
        if not isinstance(choices,dict) or set(choices) != set(spec["exhibits"][group]):
            raise ValueError("citation fields differ from the assigned exhibit group")
        if any(type(slot) is not bool for slot in choices.values()):
            raise ValueError("citation choice must be Boolean")
        selected.extend(ident for ident, chosen in choices.items() if chosen)
    result = {"verdict":answer["verdict"],"reason_summary":answer["reason_summary"],"evidence_refs":selected}
    return check(spec["packet"],json.dumps(result))


COLLECTION = "gold-development-single-citation-slots-v1"


def seed(db):
    from .controller import add
    from .local_judge import role_for
    from .q2_development import config, request, roster
    with db:
        for case in roster():
            for model in config()["order"]:
                spec = use_single_slots(request(case,model,"combined"))
                dim = spec["packet"]["dimension"]
                add(db,COLLECTION,case["case_id"],model,dim,role_for(dim),spec)


def main():
    from argparse import ArgumentParser
    from pathlib import Path
    from .archive import export
    from .controller import DEFAULT, connect, work
    from .q2_development import REGISTRY, config
    from .runtime import ROOT
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("seed","run"))
    parser.add_argument("--state",type=Path,default=DEFAULT)
    parser.add_argument("--assets",type=Path,default=ROOT.parent.parent)
    parser.add_argument("--archive",type=Path,default=ROOT/"evaluation/aeve/results")
    parser.add_argument("--port",type=int,default=18744)
    args = parser.parse_args()
    db = connect(args.state)
    try:
        seed(db)
        if args.action == "run":
            for model in config()["order"]:
                n = work(db,args.state,args.assets,args.port,model,[COLLECTION],24,registry=REGISTRY,grader=grade)
                export(db,args.state,args.archive)
                print(model,n,flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
