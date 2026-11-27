"""Evaluate nonphysical evidence on its own denominators; run after the physical inventory."""
import hashlib
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from .history import OUT, canonical, document, lines, seal, sid
from .history_inputs import evidence_v2, fingerprint
from .history_controls import reproduced_rows
from .history_scores import job_cases, multi_cases, planning_tasks, tc_cases


@lru_cache(maxsize=None)
def public_case(case, track):
    if case.startswith("AP1-") and case in planning_tasks():
        from benchmarks.agentic_planning_v1.contract import request
        return request(planning_tasks()[case],track)
    if case.startswith("MT-") and case in multi_cases():
        return multi_cases()[case].model_input()
    if case.startswith("JOB-") and case in job_cases():
        initial = job_cases()[case].input_initial()
        return {"prompt":initial, "policy":initial["shared_rules"]}
    if case.startswith("TCV2-"):
        from benchmarks.tool_calling_v2.holdout.host import SYSTEM, wire_tools
        data = tc_cases("dev" if case.startswith("TCV2-D-") else "holdout").get(case)
        if data:
            return {"prompt":data["prompt"],"policy":SYSTEM,"tools":wire_tools(data)}
    return {}


def source_rows(path, adapter):
    """Yield only source locators consumed by the primary registry."""
    if adapter in {"replay","results"}:
        for n,r in enumerate(lines(path),1):
            yield n,r.get("row",r)
        return
    if adapter == "members":
        import json
        for item in lines(path):
            name = item["name"]
            if name.startswith(("cases/","JOB-")) and name.endswith(".json"):
                raw = item.get("raw_json",item.get("raw_text",item.get("utf8")))
                r = json.loads(raw)
                yield name,r.get("row",r)
        return
    doc = document(path)
    if adapter == "upstream_reproduction":
        for n,r in enumerate(doc["parser_fixtures"]):
            yield f"parser_fixtures/{n}",r
        return
    if adapter == "test_mutations":
        yield from enumerate(doc["tests"])
        return
    for cohort,node in doc.get("cohorts",{"":doc}).items():
        for field in ("trials","cases","rows","results","repetitions"):
            records = node.get(field)
            if isinstance(records,dict):
                records = [{"id":k,**v} for k,v in records.items() if isinstance(v,dict)]
            if not isinstance(records,list):
                continue
            for n,r in enumerate(records):
                if isinstance(r,dict):
                    yield f"{cohort}/{field}/{n}",r
            break


@lru_cache(maxsize=1)
def parser_contract():
    from benchmarks.tool_calling_v2.parser.assessment import validators_for
    from benchmarks.tool_calling_v2.parser.fixtures import build
    data = build(True)
    return {r["id"]:r for r in data["fixtures"]}, validators_for(data["tools"])


def fixture_fact(row):
    from benchmarks.tool_calling_v2.parser.assessment import assess
    fixtures,validators = parser_contract()
    full, streamed = row.get("complete"),row.get("stream")
    if row.get("id") not in fixtures or not isinstance(full,dict) or not isinstance(streamed,dict):
        return {}
    if any(r.get("blocked") or not (r.get("parser_rejected") or r.get("eos_only")) for r in (full,streamed)):
        return {"D21":"BLOCKED"}
    inputs = {"parser_rejected":full.get("parser_rejected"),"message":full.get("message"),
              "stream_rejected":streamed.get("parser_rejected"),"stream_message":streamed.get("message")}
    scores = assess(fixtures[row["id"]],inputs,validators)
    statuses = [scores["native"],scores["parser_stream_parity"],full.get("wire"),streamed.get("wire")]
    return {"D21":"FAIL" if "FAIL" in statuses else "PASS" if all(s=="PASS" for s in statuses) else "BLOCKED"}


def origin_link(path, row, registered, indexes):
    physical,original_tc,alignment = indexes
    if path.name == "archive_replay.json":
        trial = row["trial"]
        key = sid(row["run_id"],trial["case_id"],trial["trial_id"])
        return key if key in physical else None
    if "rescoring" in path.parts:
        candidates = original_tc.get((row["original_run_id"],row["id"]),[])
        return candidates[0] if len(candidates)==1 else None
    if path.name == "legacy_alignment.json":
        return alignment.get(registered["case_id"])
    return None


def software_packet(meta,row):
    if meta["class"] not in {"no_llm_control","software_witness","mutation"}:
        return None
    case = meta["case_id"]
    # A status, count or mutation label contains no observable answer. Some
    # software controls explicitly archive a complete answer under "witness".
    actual = dict(row)
    if isinstance(row.get("witness"),dict) and "disposition" in row["witness"] and "facts" in row["witness"]:
        actual["final"] = row["witness"]
    if isinstance(row.get("initial_plan"),dict):
        actual["plan_raw"] = row["initial_plan"]
    if not isinstance(actual.get("calls"),list):
        actual["calls"] = []
    track = "P" if "plan_raw" in actual else "A"
    public = public_case(case,track)
    if not actual.get("initial_input") and not public:
        return None
    return evidence_v2(meta["trial_id"],"no-model",actual,public,meta["sources"][0][2])


def build():
    assets = document(OUT/"assets.json")
    registry = list(lines(OUT/"registry.jsonl.gz"))
    physical = {r["trial_id"]:r for r in registry if r["class"]=="physical_trial"}
    physical_by_case = defaultdict(list)
    for r in physical.values():
        physical_by_case[r["run_id"],r["case_id"]].append(r["trial_id"])
    alignment = {r["case_id"]:r["trial_id"] for r in registry
                 if Path(r["sources"][0][0]).name == "planning-plan-controls.json.gz"}
    subjects = defaultdict(dict)
    for r in registry:
        if r["class"] != "physical_trial":
            path,loc,_ = r["sources"][0]
            subjects[Path(path)][loc] = r
    eligible = {}
    links = {}
    inputs = []
    seen_content = {}
    eligibility = defaultdict(Counter)
    origin_counts = defaultdict(Counter)
    scores = defaultdict(Counter)
    for path,selected in sorted(subjects.items()):
        asset = assets[path.as_posix()]
        # Bind the bytes actually read here to the pinned tree independently.
        blob = path.read_bytes()
        digest = hashlib.sha1(f"blob {len(blob)}\0".encode()+blob).hexdigest()
        if digest != asset["git_blob"]:
            raise ValueError(f"Source asset differs: {path}")
        regenerated = reproduced_rows(path)
        remaining = set(selected)
        for loc,raw in source_rows(path,asset["adapter"]):
            if loc not in selected:
                continue
            remaining.remove(loc)
            r = selected[loc]
            key,kind = r["trial_id"],r["class"]
            origin = origin_link(path,raw,r,(physical,physical_by_case,alignment))
            if origin:
                subject = physical[origin]["source_family"] if origin in physical else "no-model"
                reason = "reuse_source_semantic_evaluation"
                links[key] = origin
            else:
                packet = software_packet(r,raw)
                subject = "unknown" if kind == "offline_replay" and ("original_run_id" in raw or "run_id" in raw) else "no-model"
                reason = {"fixture":"parser_fixture_without_business_decision",
                          "derived_evidence":"gate_summary_without_candidate_generation",
                          "offline_replay":"derived_checks_without_original_decision",
                          "software_witness":"assertions_or_counts_without_citable_decision",
                          "mutation":"mutation_verdict_without_candidate_output",
                          "no_llm_control":"no_citable_control_decision"}[kind]
                if packet:
                    # Same narrative alone does not establish common provenance.
                    # Preserve a separate denominator for each independently observed
                    # run. Link repeated copies only on identical case + actual source.
                    unique = (r["case_id"],r["sources"][0][2],fingerprint(packet["events"]))
                    other = seen_content.get(unique)
                    if other:
                        reason = "reuse_identical_captured_software_evidence"
                        links[key] = other
                    else:
                        seen_content[unique] = key
                        packet["record_class"] = kind
                        inputs.append(packet)
                        reason = "eligible_independent_software_evidence"
            facts = dict(r["deterministic"])
            if regenerated:
                if loc not in regenerated:
                    raise ValueError(f"Independent software execution lacks {path}:{loc}")
                # Equality records a change to an archived red/green result
                # separately from the observed business verdict.
                facts["software_reproduction"] = "PASS" if canonical(regenerated[loc]) == canonical(raw) else "FAIL"
            if kind == "fixture":
                facts.update(fixture_fact(raw) or {"D21":"NOT_RUN"})
            for dim,result in facts.items():
                scores[kind][dim+"/"+result] += 1
            eligible[key] = {"trial_id":key, "record_class":kind, "subject_family":subject,
                             "semantic_disposition":reason,"source_trial_id":links.get(key),
                             "deterministic":facts,"source":r["sources"][0]}
            eligibility[kind][reason] += 1
            origin_counts[kind][subject] += 1
        if remaining:
            raise ValueError(f"Source rows missing: {path} {list(remaining)[:3]}")
    inputs.sort(key=lambda r:r["trial_id"])
    inventory_sha = seal(OUT/"nonphysical_evaluability.jsonl.gz",(eligible[k] for k in sorted(eligible)))
    inputs_sha = seal(OUT/"judge_inputs_nonphysical_v2.jsonl.gz",inputs)
    summary = {"version":2,"registered":len(eligible),"unique_semantic_packets":len(inputs),
               "linked_source_records":len(links),"dimensions":dict(Counter(d for r in inputs for d in r["dimensions"])),
               "denominators":{k:dict(v) for k,v in eligibility.items()},
               "subject_origins":{k:dict(v) for k,v in origin_counts.items()},
               "deterministic_results":{k:dict(v) for k,v in scores.items()},
               "sha256_uncompressed":{"registry":inventory_sha,"inputs":inputs_sha}}
    (OUT/"nonphysical_coverage.json").write_bytes(canonical(summary)+b"\n")
    return summary


if __name__=="__main__":
    print(build())
