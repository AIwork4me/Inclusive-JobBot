"""Index pinned historical evidence; rebuild with python -m evaluation.aeve.history.

Supply --local-runs to seal projections from the separately retained raw run
directories. Normal reproduction consumes the already sealed projections.
"""
import argparse
from collections import Counter
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from .history_scores import regrade
from .history_inputs import canonical, family_name, fingerprint, packet, evidence_v2, request_body, wire_episodes, decode_wire_row, first_decision

BASE = "88786ed8f01e9faf37ae458e66a6d9e953daba44"
OUT = Path("evidence/IJ073/aeve/history")
VALIDITY = "evidence/IJ072/benchmark_validity/"
STATES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}


def lines(path):
    with (gzip.open if path.suffix == ".gz" else open)(path, "rt", encoding="utf8") as stream:
        for line in stream:
            yield json.loads(line)


def document(path):
    with (gzip.open if path.suffix == ".gz" else open)(path, "rt", encoding="utf8") as stream:
        return json.load(stream)


@lru_cache(maxsize=600)
def metadata(path):
    return document(path) if path.is_file() else {}


def seal(path, rows):
    digest = hashlib.sha256()
    temporary = path.with_name(path.name + ".tmp-" + uuid4().hex)
    with temporary.open("wb") as output, gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0, compresslevel=6) as stream:
        for row in rows:
            data = canonical(row) + b"\n"
            stream.write(data)
            digest.update(data)
    temporary.replace(path)
    return digest.hexdigest()


def sid(run, case, attempt):
    return fingerprint([run, case, attempt])


def classification(path):
    name, rel = path.name, path.as_posix()
    if name == "result.json" and "competitive_slm" in path.parts or path.parent.name == "terminal" and name.endswith(".json"):
        return "single_terminal"
    if name == "tool_calling_smoke.json":
        return "protocol_smoke"
    if name == "server_api_check.json":
        return "api_smoke"
    if "aion_reference" in path.parts and name in {"cpu.json", "webgpu.json"}:
        return "aion_chat"
    if "aion_tools" in path.parts and name.endswith(".json") and name != "serial-comparison.json":
        return "aion_tools"
    if "ticket_tags_counterfactual" in path.parts and name == "report.json.gz":
        return "counterfactual"
    if "upstream_b12675" in path.parts and name == "report.json":
        return "upstream_reproduction"
    if name.startswith("planning-part-") or name == "raw.jsonl.gz" or name == "records.jsonl.gz":
        return "members"
    if name == "report.json" and any(x in path.parts for x in ("admission", "admission_strict")):
        return "admission"
    if name.startswith("local_tool_smoke_"):
        return "sdk_smoke"
    if name == "mutations.json" and path.parent.name == "evaluator_v2":
        return "test_mutations"
    if name in {"launch.json","provenance.json"}:
        return "supporting_asset"
    if name in {"terminal.jsonl.gz", "results.jsonl", "results.jsonl.gz"}:
        return "results"
    if name == "trials.jsonl.gz":
        return "proofs"
    if name == "legacy-job-ab-checkpoint.json":
        return "job_proofs"
    if name == "transport.json":
        return "transport"
    if "planning/" in rel and "/cases/" in rel and name.endswith(".json"):
        return "case"
    if "/rescoring/" in rel and name.endswith(".jsonl"):
        return "replay"
    if path.suffix in {".gz", ".json"} and ("controls" in name or "witness" in name or "mutations" in name or
        ("evidence/IJ073/oracle/" in rel) or name in {"fixtures.json","development.json","reference.json"} or
        ("/antigravity/" in rel and path.suffix == ".json") or ("admission/" in rel and name == "report.json")):
        return "nested"
    return "supporting_asset"


def verdict(row):
    for key in ("status", "trajectory_status", "oracle_status", "outcome", "old_status", "trace_representability"):
        if isinstance(row.get(key), str) and row[key] in STATES:
            return row[key]
    if isinstance(row.get("ok"), bool):
        return "PASS" if row["ok"] else "FAIL"
    return None


class Inventory:
    def __init__(self, local_runs, output=OUT):
        self.registry, self.packets, self.assets, self.conflicts = {}, {}, {}, []
        self.formal = {}
        self.journal_first = {}
        self.local = {}
        self.journals = {}
        self.journal_owners = {}
        if local_runs:
            for run_json in local_runs.glob("*/run.json"):
                run = metadata(run_json).get("run_id")
                if run:
                    self.local[run] = run_json.parent
        self.sealed = {}
        self.context_path = output / "sealed_projections.jsonl.gz"
        if not local_runs and self.context_path.is_file():
            self.sealed = {r["sha256"]: r for r in lines(self.context_path)}
        self.public = {r["case_id"]: r for r in lines(Path("benchmarks/agentic_planning_v1/datasets/holdout.jsonl"))}
        engine = document(Path("benchmarks/engine_qualification/workload.json"))
        for group in ("chat", "structured", "tasks"):
            for task in engine[group]:
                self.public[task["id"]] = {k:task[k] for k in ("prompt", "messages") if k in task}
        for filename in ("tool_calling_500", "tool_calling_dev"):
            for r in lines(Path("benchmarks/tool_calling/datasets") / (filename+".jsonl")):
                self.public[r["id"]] = {k:r[k] for k in ("messages","system","tools")}

    def add(self, path, loc, r, run, case, attempt, family, kind="physical_trial", configuration=None,
            explicit_sha=None, extra_packet=None, formal_packet=None):
        case, run, attempt = str(case), str(run), str(attempt)
        key = sid(run, case, attempt)
        sha = explicit_sha or fingerprint(r)
        source = [path.as_posix(), loc, sha]
        score = verdict(r)
        if key in self.registry:
            old = self.registry[key]
            if old["original_status"] != score and score and old["original_status"]:
                self.conflicts.append({"trial_id":key,"kind":"status_conflict","source":source})
            if old["configuration_sha256"] and configuration and old["configuration_sha256"] != configuration:
                raise ValueError(f"configuration collision {key}")
            if source not in old["sources"]:
                old["sources"].append(source)
        else:
            archived = {k:v for k,v in r.items() if k in {"business_state_status","strict_sop_status","trace_status","native_parser_status","wire_protocol_status","state_check","final_and_state","trace_replay","plan_protocol","commit_authorization"} and isinstance(v,str)}
            self.registry[key] = {"trial_id":key,"run_id":run,"case_id":case,"attempt_id":attempt,"class":kind,
                "repeat":r.get("phase")=="repeat" or "repeat" in attempt.lower() or "repeat" in path.parent.name,
                "configuration_sha256":configuration,"source_family":family,"original_status":score,
                "archived_dimensions":archived,"sources":[source]}
        if kind == "physical_trial" and key not in self.formal:
            captured = r
            first_request = self.journal_first.get((run, r.get("journal")))
            if first_request:
                captured = {**r, "requests":[{"request":first_request[0]}], "_first_decision":first_request[1]}
            view = formal_packet or evidence_v2(key, family, captured, self.public.get(case, {}), sha)
            if view:
                self.formal[key] = view
        if "deterministic" not in self.registry[key]:
            self.registry[key]["deterministic"] = r.get("_scores") or regrade(r, case)
        self.assets[path.as_posix()]["records_indexed"] += 1
        return key

    def raw_proof(self, run, case, key, directory, sha, family):
        if sha in self.sealed:
            return self.sealed[sha]
        projection = {"sha256":sha, "available":False}
        if run in self.local:
            raw = self.local[run] / directory / (key+".json")
            if raw.is_file():
                blob = raw.read_bytes()
                if hashlib.sha256(blob).hexdigest() != sha:
                    raise ValueError(f"local sealed evidence mismatch {run}/{key}")
                r = json.loads(blob)["row"]
                if r["run_id"] != run or r["case_id"] != case or r["key"] != key:
                    raise ValueError("local trial identity differs")
                projection.update(available=True, scores=regrade(r,case), packet=packet(sid(run,case,key),family,r,{},sha),
                    formal_packet=evidence_v2(sid(run,case,key),family,r,{},sha),
                    dimensions={k:r[k] for k in ("business_state_status","trace_status","strict_sop_status") if k in r})
        self.sealed[sha] = projection
        return projection

    def ingest(self, path, adapter):
        parent = path.parent
        meta_dir = parent.parent if adapter == "case" or parent.name == "terminal" else parent
        meta = metadata(meta_dir/"run.json")
        config = meta.get("configuration", {})
        diag = metadata(meta_dir/"diagnostic.json")
        family = family_name(diag.get("identity",{}).get("model") or config.get("model") or config.get("modelscope_model_id"))
        run = meta.get("run_id") or diag.get("run_id")
        cfg = meta.get("fingerprint") or diag.get("configuration_sha256")

        def result(r, loc, kind="physical_trial", case=None, attempt=None, family_hint=None):
            trial = r.get("trial", {})
            trial = trial if isinstance(trial,dict) else {}
            case = case or r.get("case_id") or r.get("id") or trial.get("case_id") or loc
            attempt = attempt or r.get("key") or trial.get("trial_id") or case
            family_used = family_hint or family
            if family_used=="unknown" and (path.parts[1] == "IJ0" or "historical_replay" in path.parts):
                family_used = "MiniCPM"
            if "gpu" in path.parts and path.parts[1]=="IJ0":
                attempt = f"{r['section']}/{case}/{loc}"
            self.add(path,loc,r,r.get("run_id") or run or parent.as_posix(),case,attempt,family_used,kind,
                     r.get("configuration_sha256") or r.get("run_fingerprint") or cfg)

        if adapter == "members":
            manifest = metadata(parent/"archive_manifest.json").get("sha256", {})
            if path.name=="raw.jsonl.gz":
                manifest={r["name"]:r["sha256"] for r in metadata(parent/"raw-manifest.json")["entries"]}
            for item in lines(path):
                name = item["name"]

                raw = item.get("utf8", item.get("raw_text",item.get("raw_json")))
                if manifest and hashlib.sha256(raw.encode()).hexdigest()!=manifest[name]:
                    raise ValueError(f"damaged member {path}:{name}")
                if name.startswith("attempts/") and name.endswith(".jsonl"):
                    records = map(json.loads,raw.splitlines())
                    first = next((e["body"] for e in records if e.get("kind") == "request" and isinstance(e.get("body"),dict)), None)
                    if first is not None:
                        first_capture = next((e["wire"] for e in records if e.get("kind")=="capture"),{})
                        self.journal_first[(run,name)] = ({k:first[k] for k in ("messages","tools","response_format") if k in first},
                                                          first_decision(first_capture))
                    self.journals[(run,name)] = [path.as_posix(),name,hashlib.sha256(raw.encode()).hexdigest()]
                    self.assets[path.as_posix()].setdefault("attempt_journals",0)
                    self.assets[path.as_posix()]["attempt_journals"] += 1
                    continue
                if not name.startswith(("cases/","trajectories/")) and not (name.startswith("JOB-") and name.endswith(".json")):
                    self.assets[path.as_posix()].setdefault("ancillary_members",0)
                    self.assets[path.as_posix()]["ancillary_members"] += 1
                    continue
                r=json.loads(raw)
                row = r.get("row",r)
                result(row,name,"no_llm_control" if row.get("arm") == "F" and row.get("model_calls") == 0 else "physical_trial")
                if row.get("journal") and row.get("trial",{}).get("trial_id"):
                    key = sid(row["run_id"],row["case_id"],row["trial"]["trial_id"])
                    self.journal_owners[(row["run_id"],row["journal"])] = (key,row["journal_sha256"])
        elif adapter in {"results","replay"}:
            for n,r in enumerate(lines(path),1):
                kind = "offline_replay" if adapter=="replay" else "fixture" if "parser" in path.parts else "physical_trial"
                if adapter == "replay":
                    self.add(path,n,r,path.as_posix(),r["id"],r["original_run_id"],"MiniCPM",kind)
                else:
                    source = r.get("row",r)
                    if source.get("key","").startswith("fixture--") and "fixture_status" in source:
                        kind = "fixture"
                    result(source,n,kind)
        elif adapter == "single_terminal":
            row = document(path)["row"]
            result(row,"row", attempt=row.get("key") or f"{row.get('phase','first')}/{row.get('attempt',1)}")
        elif adapter == "protocol_smoke":
            data = document(path)
            for n, entry in enumerate(data["trace"]):
                if entry["path"] != "/v1/chat/completions":
                    continue
                reply = entry["response"]
                msg = reply["choices"][0]["message"] if "choices" in reply else reply
                calls = [{"turn":0,"name":c["function"]["name"],"arguments":c["function"]["arguments"]}
                         for c in msg.get("tool_calls", [])]
                result({"requests":[entry], "final":msg.get("content"),"calls":calls},
                       f"trace/{n}",case=fingerprint(entry["request"]["messages"]),attempt=f"trace/{n}")
        elif adapter == "api_smoke":
            for n, entry in enumerate(document(path)["checks"]):
                if entry["name"] in {"chat_completions_stream","chat_completions_non_stream"}:
                    result(entry,f"checks/{n}",case=entry["name"])
        elif adapter == "aion_chat":
            row = document(path)
            result(row, "$", case=fingerprint(row["prompt"]), family_hint=family_name(row["model_id"]))
        elif adapter == "aion_tools":
            data = document(path)
            turns = data["trials"]
            # A trial list is a multi-turn exchange on a single task in this archive.
            row = {"run_id":data["run_id"], "status":data["status"],
                   "requests":[{"request":{"messages":t["messages"], "tools":data["tools"]}} for t in turns],
                   "calls":[]}
            for n, turn in enumerate(turns):
                generated = turn["whole_decode"]
                if generated.startswith("<|tool_call|>") and "<|/tool_call|>" in generated:
                    text = generated.split("<|tool_call|>",1)[1].split("<|/tool_call|>",1)[0]
                    try:
                        call=json.loads(text)
                    except ValueError:
                        row["final"] = generated
                        continue
                    if isinstance(call,dict) and call.get("name"):
                        row["calls"].append({"turn":n,"name":call["name"],"arguments":call.get("arguments"),
                                             "observation":turn.get("executed_synthetic_read")})
                else:
                    row["final"] = generated
            result(row,"trials",case=fingerprint(turns[0]["messages"]),family_hint="Aion")
        elif adapter == "upstream_reproduction":
            data = document(path)
            for n,r in enumerate(data["historical"]):
                result({**r,"run_id":data["run_id"]},f"historical/{n}",family_hint="MiniCPM")
            for n,r in enumerate(data["parser_fixtures"]):
                result({**r,"run_id":data["run_id"]},f"parser_fixtures/{n}",kind="fixture")
        elif adapter == "counterfactual":
            data = document(path)
            for variant,arm in data["variants"].items():
                for n,r in enumerate(arm["rows"]):
                    trace = r["original_style"]
                    result({**trace,"run_id":data["run_id"]}, f"variants/{variant}/rows/{n}",
                           attempt=f"{variant}/{r['case_id']}",family_hint="MiniCPM")
        elif adapter == "admission":
            data = document(path)
            for group in wire_episodes(data.get("wire",[])):
                first, last = group[0][0], group[-1][0]
                captures = [item for _,item in group]
                row = {**decode_wire_row(captures),"run_id":data["run_id"]}
                msg = request_body(captures[0]).get("messages") or []
                result(row, f"wire/{first}-{last}", case=fingerprint(msg),attempt=f"wire/{first}",
                       family_hint=family_name(data["model_id"]))
        elif adapter == "sdk_smoke":
            r = document(path)
            result({**r,"initial_input":r.get("prompt")}, "$", case="sdk-local-smoke",family_hint="MiniCPM")
        elif adapter == "test_mutations":
            for idx,r in enumerate(document(path)["tests"]):
                result(r,idx,kind="mutation")
        elif adapter == "case":
            result(document(path),"$")
        elif adapter == "proofs":
            info = metadata(parent/"archive.json")
            run, cfg = info["run_id"], info["configuration_sha256"]
            family_used = {"B":"LFM","D":"Qwen","F":"Mistral","G":"Gemma"}.get(info["candidate"],"unknown")
            for n,r in enumerate(lines(path),1):
                if not r.get("proof"):
                    item=self.assets[path.as_posix()]
                    item["without_terminal_proof"]=item.get("without_terminal_proof",0)+1
                    continue
                key = r["key"]
                case = next(part for part in key.split("--") if part.startswith("TCV2-"))
                proof = r["proof"]["trajectory_sha256"]
                x = self.raw_proof(run,case,key,"trajectories",proof,family_used)
                self.add(path,n,{**r,**x.get("dimensions",{}),"_scores":x.get("scores",{})},run,case,key,family_used,configuration=cfg,
                         explicit_sha=proof,extra_packet=x.get("packet"),formal_packet=x.get("formal_packet"))
        elif adapter == "job_proofs":
            for arm,info in document(path)["arms"].items():
                run=info["summary"]["run_id"]
                for case,r in info["sealed_checkpoints"].items():
                    x=self.raw_proof(run,case,case,"cases",r["sha256"],"MiniCPM")
                    self.add(path,f"arms/{arm}/{case}",{**r,**x.get("dimensions",{}),"_scores":x.get("scores",{})},run,case,case,"MiniCPM",
                             configuration=info["summary"]["configuration_sha256"],explicit_sha=r["sha256"],extra_packet=x.get("packet"),formal_packet=x.get("formal_packet"))
        elif adapter == "transport":
            info=document(path)
            for r in info["trials"]:
                c=r["capture"]
                proposal=json.loads(c["raw_response"])["choices"][0]["message"].get("content")
                result({"run_id":info["run_id"],"plan_raw":proposal,"requests":[c],"status":r["evaluation"]["status"]},
                       r["mode"],case=info["case_sha256"],attempt=r["mode"],family_hint="Qwen")
        elif adapter == "nested":
            info=document(path)
            groups=info.get("cohorts",{"":info})
            for group,x in groups.items():
                kind = ("mutation" if "mutation" in path.name else "software_witness" if "witness" in path.name or "controls" in path.name else
                        "offline_replay" if "oracle" in path.parts else "fixture" if "fixtures" in path.name else "physical_trial")
                for field in ("trials","cases","rows","results","repetitions"):
                    data=x.get(field)
                    if isinstance(data,dict):data=[{"id":k,**v} for k,v in data.items() if isinstance(v,dict)]
                    if not isinstance(data,list):continue
                    for n,r in enumerate(data):
                        if not isinstance(r,dict):continue
                        case=r.get("case_id") or r.get("id") or r.get("case") or n
                        loc=f"{group}/{field}/{n}"
                        arm_kind = kind
                        identity = info.get("identity",{}).get("server",{})
                        declared = (info.get("model_id") or identity.get("modelscope_id") or
                                    info.get("config",{}).get("modelscope_id"))
                        if r.get("wire") and not r.get("calls"):
                            wire = decode_wire_row(r["wire"])
                            r = {**r, "requests":wire["requests"], "calls":wire["calls"],
                                 "final":r.get("answer") or wire["final"]}
                        if not declared and r.get("wire"):
                            declared = request_body(r["wire"][0]).get("model")
                        if kind == "physical_trial" and r.get("status") in {"NOT_RUN","BLOCKED"} and not r.get("wire") and not r.get("requests"):
                            arm_kind = "derived_evidence"
                        if kind == "physical_trial" and r.get("model_calls") == 0:
                            arm_kind = "no_llm_control"
                        self.add(path,loc,r,info.get("run_id") or path.as_posix(),case,loc,
                                 family_name(declared),arm_kind)
                    break


def main(argv=None, *, output=OUT):
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--local-runs",type=Path)
    args=cli.parse_args(argv)
    output.mkdir(parents=True,exist_ok=True)
    store=Inventory(args.local_runs,output)
    tree=subprocess.check_output(["git","ls-tree","-rl",BASE,"evidence"]).decode()
    for line in tree.splitlines():
        header,name=line.split("\t",1)
        path=Path(name)
        if not name.startswith("evidence/IJ0"):continue
        _,_,blob,size=header.split()
        adapter=classification(path)
        item={"git_blob":blob,"size":int(size),"adapter":adapter,"records_indexed":0}
        if path.stat().st_size!=int(size):raise ValueError(f"source size mismatch: {name}")
        h=hashlib.sha1(f"blob {size}\0".encode())
        with path.open("rb") as stream:
            for block in iter(lambda:stream.read(1<<20),b""):h.update(block)
        if h.hexdigest()!=blob:raise ValueError(f"source bytes mismatch: {name}")
        store.assets[name]=item
        if adapter!="supporting_asset":
            store.ingest(path,adapter)

    for journal, (trial, expected) in store.journal_owners.items():
        source = store.journals.get(journal)
        if source:
            if source[-1] != expected:
                raise ValueError("attempt journal digest differs from terminal record")
            if source not in store.registry[trial]["sources"]:
                store.registry[trial]["sources"].append(source)
    for key, row in store.registry.items():
        if row["class"] in {"fixture","mutation","software_witness","no_llm_control"} and row["source_family"] == "unknown":
            row["source_family"] = "no-model"
    for key,row in store.registry.items():
        if row["class"] != "physical_trial":
            row["semantic_eligibility"] = "separate_evidence_class"
        elif key not in store.formal:
            row["semantic_eligibility"] = "insufficient_citable_decision_evidence"
        elif row["source_family"] == "unknown":
            row["semantic_eligibility"] = "unresolved_subject_family"
        else:
            row["semantic_eligibility"] = "eligible"
    projections_digest = seal(store.context_path,(v for _,v in sorted(store.sealed.items())))
    totals={"sealed_projections":projections_digest}
    # The v1 GPU development cohort is sealed. Its queue identities and old
    # verdicts survive projection corrections in the independently versioned v2.
    legacy = output / "judge_inputs.jsonl.gz"
    expected_v1 = "7ffadb95f8a18f96d3eac6692081db624a999b428556f52c918cdb6301d4bf0b"
    with gzip.open(legacy, "rb") as original:
        if hashlib.file_digest(original, "sha256").hexdigest() != expected_v1:
            raise ValueError("frozen v1 input packet digest differs")
    totals["judge_inputs"] = expected_v1
    for name,items in (("registry",store.registry),("judge_inputs_v2",store.formal)):
        totals[name]=seal(output/(name+".jsonl.gz"),(r for _,r in sorted(items.items())))
    summary={"baseline":BASE,"asset_count":len(store.assets),"registry_sha256_uncompressed":totals,
        "distinct_case_ids":len({r["case_id"] for r in store.registry.values()}),
        "local_proofs":dict(Counter("available" if r["available"] else "unavailable" for r in store.sealed.values())),
        "semantic_eligibility":dict(Counter(r["semantic_eligibility"] for r in store.registry.values())),
        "repeat_trials":sum(r["repeat"] for r in store.registry.values()),
        "unmatched_attempt_journals":[v for k,v in sorted(store.journals.items(),key=lambda a:str(a[0])) if k not in store.journal_owners],
        "unique_trials":len(store.registry),"semantic_packets_v1_frozen":19868,
        "formal_physical_packets":len(store.formal),
        "formal_physical_known_family":sum(r["source_family"]!="unknown" for r in store.formal.values()),
        "formal_physical_without_packet":sum(r["class"]=="physical_trial" and k not in store.formal for k,r in store.registry.items()),
        "insufficient_evidence_by_source":dict(Counter(r["sources"][0][0] for r in store.registry.values()
                     if r["semantic_eligibility"]=="insufficient_citable_decision_evidence")),
        "formal_dimensions":dict(Counter(d for p in store.formal.values() for d in p["dimensions"])),
        "source_families":dict(Counter(r["source_family"] for r in store.registry.values() if r["class"]=="physical_trial")),
        "deterministic_dimensions":{dim:dict(Counter(r["deterministic"].get(dim,"NOT_RUN") for r in store.registry.values()
                                      if r["class"]=="physical_trial")) for dim in ("D18","D19","D20","D22","D23","D24","D25")},
        "class_counts":dict(Counter(r["class"] for r in store.registry.values())),
        "original_status_conflicts":store.conflicts,

        "unclassified_assets":[p for p,r in store.assets.items() if r["adapter"]!="supporting_asset" and not (r["records_indexed"] or r.get("attempt_journals") or r.get("ancillary_members"))],
        "judge_evaluations_completed_by_registry":0}
    (output/"assets.json").write_bytes(canonical(store.assets)+b"\n")
    (output/"coverage.json").write_bytes(json.dumps(summary,indent=2,sort_keys=True).encode()+b"\n")
    print({k:v for k,v in summary.items() if k not in {"original_status_conflicts","unclassified_assets"}})


if __name__=="__main__":
    main()
