"""Construct the preregistered human-review packet after independently replaying the formal gates.

Run from the repository root: python -m evaluation.aeve.human_review --out <new-private-directory>.
Only reviewer/ is intended for independent reviewers. Building produces no submissions.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import secrets
from tempfile import TemporaryDirectory

from .archive import digest
from .history import OUT, lines
from .history_supplement_report import require_independent_review
from .intake import DIMENSIONS
from .qualification import measure
from .report_history import build
from .report_oracle import RESULTS
from .runtime import ROOT, REGISTRY, canonical, fingerprint, write_json

PROTOCOL = Path(__file__).with_name("human_review_preregistration.json")
BUCKETS = ("judge disagreement", "guard boundary", "authorization", "protocol-semantic divergence", "safety", "recovery")
VISIBLE = {"task", "policy", "tools", "plan", "delivered_update", "action", "observation", "answer", "initial_generation", "proposal"}
PRIVATE_KEYS = {"gold_label","canonical_answer","private_oracle","oracle","old_score","new_score","old_verdict",
                "ai_verdict","judge_verdict","judge_disagreement","model","model_id","model_name","family",
                "run_id","case_id","trial_id","attempt_id","review_id","source_family","source_sha256"}
PRIVATE_VALUES = re.compile(r"\b(?:Qwen\w*|MiniCPM\w*|Gemma\w*|Mi(?:ni)?stral\w*|LiquidAI|OpenBMB|Granite(?:-\w*)?|LFM[0-9]\w*|ij07-candidate-\w+|Aion[- ]?1\w*)\b", re.I)
PRIVATE_TOKENS = {re.sub("[^a-z0-9]", "", key.lower()) for key in PRIVATE_KEYS}
FIELD = re.compile(r"""["']([a-z][a-z0-9_-]*)["']\s*:""", re.I)
LABEL = re.compile(r"(?:AI (?:judge |evaluator )?(?:verdict|score)|old (?:verdict|score)|"
                   r"canonical answer|private oracle|旧评分|标准答案|AI ?判定)\s*[:：=]", re.I)
QUESTIONS = [
    "Is the objective clear and does the candidate understand it? / 目标是否明确，候选回答是否理解了它？",
    "Is any observed plan executable with the visible tools, ordering and updates? / 如有计划，它能否按可见工具、顺序和更新执行？",
    "Do observed actions respect permissions, confirmation and scope? / 已观察动作是否符合权限、确认与范围？",
    "Do observations support the business outcome and answer? / 观测结果能否支持业务结论与回答？",
    "Does the observed response satisfy the requested protocol? / 已观察响应是否满足约定协议？",
]


def rank(seed, *parts):
    return hashlib.sha256(seed.encode() + canonical(parts)).hexdigest()


def visible_events(events):
    """Allowlist event kinds, replace internal IDs, reject nested scoring/identity hints."""
    def inspect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if re.sub("[^a-z0-9]", "", key.lower()) in PRIVATE_TOKENS:
                    raise ValueError("private metadata in exhibit")
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)
        elif isinstance(value, str):
            if PRIVATE_VALUES.search(value):
                raise ValueError("model identity in exhibit")
            if LABEL.search(value) or any(re.sub("[^a-z0-9]", "", key.lower()) in PRIVATE_TOKENS
                                          for key in FIELD.findall(value)):
                raise ValueError("serialized private metadata in exhibit")
    projected = []
    for event in events:
        if event["kind"] not in VISIBLE:
            raise ValueError("unrecognized or private exhibit kind")
        inspect(event["content"])
        projected.append({"id": f"e{len(projected)+1}", "kind": event["kind"], "value": event["content"]})
    return projected


def verify_coverage(summary, rows, qualification, families):
    admitted = {k for k,v in qualification["admission"].items() if v["status"] == "PASS"}
    if len({families[c] for c in admitted}) < 2 or set(summary["admitted_judges"]) != admitted:
        raise ValueError("two independently qualified judge families are required")
    if (summary["qualification_protocol"] != qualification["protocol_sha256"]
            or not summary["scope"]["formal"]["packet_inventory_present"]):
        raise ValueError("qualification protocol or formal input inventory differs")
    roster = summary.get("nonphysical_inventory", {})
    supplement = summary["scope"].get("supplement", {})
    if roster.get("status") != "PASS" or not supplement.get("packet_inventory_present"):
        raise ValueError("supplemental nonphysical inventory incomplete")
    totals = Counter()
    source_records = {}
    linked = {}
    for row in rows:
        totals["trials"] += 1
        physical = row["class"] == "physical_trial"
        scope = "formal" if physical else "supplement"
        counter_prefix = "" if physical else "nonphysical_"
        subject = row["source_family"]
        if not physical:
            totals["nonphysical_registered"] += 1
            if row["reviews"]["formal"]["expected"] or row["reviews"]["formal"]["judgments"]:
                raise ValueError("nonphysical record entered the physical denominator")
            meta = row.get("supplement")
            if not meta:
                raise ValueError("nonphysical lineage missing")
            subject = meta["subject_family"]
            if meta["source_trial_id"]:
                linked[row["trial_id"]] = (meta["source_trial_id"], subject)
        reviewed = row["reviews"].get(scope)
        if reviewed is None:
            raise ValueError("formal review scope missing")
        expected, judgments = reviewed["expected"], reviewed["judgments"]
        if not physical and (meta["semantic_disposition"] == "eligible_independent_software_evidence") != bool(expected):
            raise ValueError("nonphysical packet denominator differs from registered eligibility")
        if set(expected) != set(judgments) or len(expected) != len(set(expected)):
            raise ValueError("formal historical coverage incomplete")
        if expected:
            if (not isinstance(subject, str) or not subject.strip() or subject.casefold() == "unknown"):
                raise ValueError("eligible historical source family unresolved")
            source_records[row["trial_id"]] = subject
        totals[counter_prefix + "eligible_trials"] += bool(expected)
        totals[counter_prefix + "eligible_dimensions"] += len(expected)
        for result in judgments.values():
            require_independent_review(result, admitted, families, subject)
    if (not totals["eligible_dimensions"] or totals["trials"] != summary["trial_counts"]["trials"]
            or any(totals[k] != summary["scope"]["formal"][k] for k in ("eligible_trials","eligible_dimensions"))):
        raise ValueError("formal physical coverage denominators differ")
    if any(totals["nonphysical_" + k] != supplement[k] for k in ("eligible_trials","eligible_dimensions")):
        raise ValueError("supplemental coverage denominators differ")
    if (totals["nonphysical_registered"] != roster["registered"] or
            totals["nonphysical_eligible_trials"] != roster["independent_inputs"] or
            len(linked) != roster["linked_source_records"]):
        raise ValueError("nonphysical registered or derived source counts differ")
    for item, (source, subject) in linked.items():
        if source == item or not subject or source_records.get(source) != subject:
            raise ValueError("derived historical record lacks a fully reviewed independent source")
    if linked:
        totals["nonphysical_linked_to_reviewed_source"] = len(linked)
    return dict(totals)


def allocate(sizes, n):
    """Reserve one per stratum when feasible and allocate remaining capacity by largest remainder."""
    n = min(sum(sizes.values()), n)
    seats = {k: int(n >= len(sizes)) for k in sizes}
    slots = n - sum(seats.values())
    if not slots:
        return seats
    capacity = {k: size - seats[k] for k,size in sizes.items()}
    total = sum(capacity.values())
    for k, cap in capacity.items():
        seats[k] += slots * cap // total
    order = sorted(sizes, key=lambda k: (-(slots * capacity[k] % total), k))
    for k in order[:n-sum(seats.values())]:
        seats[k] += 1
    return seats


def draw(rows, legacy_keys, plan):
    seed = plan["seed"]
    reps = {}
    for row in rows:
        key = (row["suite"], row["case_id"])
        if key in legacy_keys:
            continue
        if key not in reps or rank(seed,*key,row["trial_id"]) < rank(seed,*key,reps[key]["trial_id"]):
            reps[key] = row
    strata = defaultdict(list)
    for key, row in reps.items():
        strata[tuple(row[k] for k in ("suite","language","level","disposition"))].append(key)
    for keys in strata.values():
        keys.sort(key=lambda k: rank(seed,*k))
    sizes = {k: len(v) for k,v in strata.items()}
    original = allocate(sizes, plan["representative"]["n"])
    seats = dict(original)

    def margin():
        total = sum(sizes.values())
        if not total or any(not seats[k] for k in sizes):
            return 1.0
        variance = sum((n / total)**2 * (n - seats[k]) / (n - 1) / (4 * seats[k])
                       for k,n in sizes.items() if n > 1)
        return 1.96 * math.sqrt(variance)

    initial_margin = margin()
    while margin() > .08 and sum(seats.values()) < min(300, sum(sizes.values())):
        # Each extension uses the same allocation on capacity remaining after the frozen initial draw.
        extra = sum(seats.values()) + 1 - sum(original.values())
        capacity = {k: n-original[k] for k,n in sizes.items() if n > original[k]}
        added = allocate(capacity, extra)
        seats = {k: original[k] + added.get(k,0) for k in sizes}
    chosen = {}
    allocation = []
    for k in sorted(strata):
        for key in strata[k][:seats[k]]:
            chosen[key] = "representative"
        allocation.append({"stratum": list(k), "population": sizes[k], "original_n": original[k],
                           "final_n": seats[k], "original_pi": original[k]/sizes[k], "final_pi": seats[k]/sizes[k],
                           "weight": sizes[k]/seats[k] if seats[k] else None})
    buckets = defaultdict(list)
    for key in sorted(reps, key=lambda k: rank(seed,*k)):
        if key not in chosen:
            group = next((b for b in BUCKETS if b in reps[key]["challenge"]), None)
            if group:
                buckets[group].append(key)
    taken = 0
    for i in range(max(map(len, buckets.values()), default=0)):
        for b in BUCKETS:
            if i < len(buckets[b]) and taken < plan["challenge"]["n"]:
                chosen[buckets[b][i]] = "challenge"
                taken += 1
    return [(reps[k], selected) for k,selected in chosen.items()], {
        "strata": allocation, "initial_margin_95": initial_margin, "final_margin_95": margin(),
        "representative_n": sum(seats.values()), "challenge_n": taken, "unique_eligible_nonlegacy": len(reps),
        "challenge_bucket_population": {b: len(buckets[b]) for b in BUCKETS}}


def case_metadata(root):
    result = defaultdict(dict)
    sources = {
        "TC-V1": ["tool_calling/datasets/tool_calling_500.jsonl","tool_calling/datasets/tool_calling_dev.jsonl"],
        "TC-V2": ["tool_calling_v2/holdout/tc_v2_500.jsonl","tool_calling_v2/holdout/tc_v2_dev.jsonl"],
        "JOB-V1": ["job_productivity_v1/holdout/frozen/tasks.jsonl","job_productivity_v1/holdout/frozen/oracles.jsonl"],
        "AGENTIC-PLAN-V1": ["agentic_planning_v1/datasets/holdout.jsonl","agentic_planning_v1/task_graphs/holdout.jsonl"],
        "MULTITOOL-V1": ["multitool_v1/frozen/oracles.jsonl"],
    }
    for suite, files in sources.items():
        for name in files:
            for r in lines(root / "benchmarks" / name):
                key = r.get("case_id", r.get("id"))
                meta = result[key]
                meta["suite"] = suite
                for k in ("language", "level"):
                    if k in r:
                        meta[k] = r[k]
                final = r.get("final") or r.get("oracle", {}).get("final")
                outcome = r.get("disposition") or r.get("outcome")
                if isinstance(final, dict):
                    outcome = final.get("disposition", outcome)
                if isinstance(outcome, str):
                    meta["disposition"] = outcome
                tags = set(r.get("coverage") or []) | {r.get("facet"), r.get("category"), r.get("risk")}
                flags = meta.setdefault("flags", set())
                if tags & {"conditional_branch", "numeric_boundary", "missing_field", "scope_denied"}:
                    flags.add("guard boundary")
                if tags & {"scope_denied","permission_denied"} or r.get("approval") or r.get("maximum_risk") == "confirmed":
                    flags.add("authorization")
                if tags & {"unauthorized_injection","injection"} or r.get("safety_probe"):
                    flags.add("safety")
                if tags & {"retry","error_recovery","fallback","constraint_change"} or r.get("disruption"):
                    flags.add("recovery")
    return result


def population(rescore, packets, meta):
    rows = {}
    for trial in lines(rescore):
        if trial["class"] != "physical_trial" or trial["repeat"]:
            continue
        cid = trial["case_id"]
        tag = meta.get(cid, {})
        scope = trial["reviews"]["formal"]
        flags = set(tag.get("flags", ()))
        if any(j["disputed"] for j in scope["judgments"].values()):
            flags.add("judge disagreement")
        scores = trial["current"]
        if scores.get("D05") in {"PASS","FAIL"} and any(
                scores.get(k) in {"PASS","FAIL"} and scores[k] != scores["D05"] for k in ("D19","D20","D21")):
            flags.add("protocol-semantic divergence")
        rows[trial["trial_id"]] = {"trial_id": trial["trial_id"], "case_id": cid, "suite": tag.get("suite","unrecorded"),
                                  "language": tag.get("language","unrecorded"), "level": tag.get("level", "not applicable" if tag.get("suite")
                                                                       not in {None,"AGENTIC-PLAN-V1"} else "unrecorded"),
                                  "disposition": tag.get("disposition","unrecorded"), "challenge": sorted(flags)}
    losses = Counter()
    eligible = []
    for packet in lines(packets):
        entry = rows.pop(packet["trial_id"], None)
        if entry is None:
            continue
        group = tuple(entry[k] for k in ("suite","language","level","disposition"))
        try:
            events = public_projection(packet)
        except ValueError as issue:
            losses[group, str(issue)] += 1
            continue
        if not events:
            losses[group,"missing task or observed candidate behavior"] += 1
            continue
        eligible.append(entry)
    for entry in rows.values():
        group = tuple(entry[k] for k in ("suite","language","level","disposition"))
        losses[group,"no formal observed packet"] += 1
    return eligible, [{"stratum":list(k), "reason":reason, "trials":n} for (k,reason), n in sorted(losses.items())]


def public_projection(packet):
    # Measured backend state is held by the custodian. It is outside the public conversation.
    events = [e for e in packet["events"] if e["kind"] != "persisted_state"]
    kinds = {e["kind"] for e in events}
    if "task" not in kinds or not kinds & {"answer","initial_generation","proposal","plan","action"}:
        return []
    return visible_events(events)


def legacy_sources(root, plan):
    path = root / plan["preserved"]["packet"]
    sources = path.with_name("a1-blind-review-provenance.json")
    expected = plan["preserved"]
    if digest(path) != expected["packet_sha256"] or digest(sources) != expected["provenance_sha256"]:
        raise ValueError("frozen legacy packet or provenance differs")
    originals = json.loads(path.read_bytes())["items"]
    source = json.loads(sources.read_bytes())
    if len(originals) != expected["count"] or {i["review_id"] for i in originals} != set(source) or len(source) != len(originals):
        raise ValueError("incomplete frozen legacy inventory")
    return originals, source


def legacy_projection(row):
    events = []
    def append(kind, value):
        if value is not None:
            events.append({"kind": kind, "content": value})
    public = row["public_input"]
    append("task",{k:v for k,v in public.items() if k != "tools"})
    append("tools",public.get("tools"))
    append("plan",row.get("initial_plan"))
    for update in row.get("trusted_user_updates", []):
        append("delivered_update", update)
    for call in row.get("observed_calls", []):
        append("action", {k:v for k,v in call.items() if k not in {"result","observation"}})
        append("observation", call.get("result",call.get("observation")))
    append("answer",row.get("answer"))
    return visible_events(events)


def assemble(entries, key):
    """Produce a mixed blind presentation and a separate, custodian-only mapping."""
    public, private = [], {}
    for identity, events, metadata in entries:
        review_id = hmac.digest(key, b"id" + canonical(identity), "sha256").hex()[:24]
        if review_id in private:
            raise ValueError("duplicate review identity")
        public.append({"review_id": review_id, "events": events})
        private[review_id] = {**metadata, "source": identity}
    public.sort(key=lambda row: hmac.digest(key,b"order"+row["review_id"].encode(),"sha256"))
    return {"version": 1, "orientation": QUESTIONS, "questions": DIMENSIONS, "instructions": [
        "Review independently using only visible exhibits. Cite event IDs and freeze each initial submission before reconciliation.",
        "For each question record PASS, FAIL, BLOCKED or NOT_RUN, a rationale and evidence IDs. Record reviewer pseudonym, domain background, language proficiency and timestamp.",
        "Two independent reviewers submit separately. A custodian freezes both initial submissions before comparison. A third independent reviewer assesses high-risk cases and unresolved disagreements.",
        "Reviewers with prior access to scores or provenance are ineligible. Receive only reviewer/ and return submissions to the custodian.",
        "请独立审阅。每个判断注明可见事件 ID、理由和状态；独立初评封存后再进行分歧复核。"],
        "items": public}, private


def submission_schema(public):
    """A blank submission contract; no reviewer identities or prefilled judgments."""
    text = {"type":"string","minLength":1}
    score = {"type":"object","additionalProperties":False, "required":["verdict","evidence_refs","rationale"],
             "properties":{"verdict":{"enum":["PASS","FAIL","BLOCKED","NOT_RUN"]},
                           "evidence_refs":{"type":"array","uniqueItems":True,
                                            "items":{"type":"string","pattern":"^e[1-9][0-9]*$"}},
                           "rationale":text},
             "if":{"properties":{"verdict":{"enum":["PASS","FAIL"]}}},
             "then":{"properties":{"evidence_refs":{"minItems":1}}}}
    properties = {"anonymous_reviewer_id":text,"domain_background":text,"language_proficiency":text,
                  "submitted_at":{"type":"string","format":"date-time"},
                  "review_id":{"enum":[row["review_id"] for row in public["items"]]},
                  "dimensions":{"type":"object","additionalProperties":False,"required":list(DIMENSIONS),
                                "properties":{dim:{"$ref":"#/$defs/score"} for dim in DIMENSIONS}}}
    return {"$schema":"https://json-schema.org/draft/2020-12/schema","$defs":{"score":score},
            "type":"object","additionalProperties":False,"required":list(properties),"properties":properties}


def release(history, results, destination):
    if destination.exists():
        raise FileExistsError("choose a new private output directory")
    plan = json.loads(PROTOCOL.read_bytes())
    qualified = measure(results)
    names = json.loads(REGISTRY.read_bytes())["candidates"]
    families = {c:r["family"] for c,r in names.items()}
    passed = {families[c] for c,r in qualified["admission"].items() if r["status"] == "PASS"}
    if len(passed) < 2:
        raise ValueError("independent evaluator qualification incomplete")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as directory:
        scratch = Path(directory)
        replay = scratch / "replay"
        summary = build(history, results, replay)
        archived_table = history / "rescore.jsonl.gz"
        archived_summary = history / "rescore_summary.json"
        if (summary != json.loads(archived_summary.read_bytes()) or
                digest(archived_table) != digest(replay / "rescore.jsonl.gz")):
            raise ValueError("independent recomputation differs from archived formal result")
        totals = verify_coverage(summary, lines(archived_table), qualified, families)
        originals, provenance = legacy_sources(ROOT, plan)
        legacy_keys = {(v["suite"],v["case_id"]) for v in provenance.values()}
        packets = history / "judge_inputs_v2.jsonl.gz"
        eligible, losses = population(archived_table, packets, case_metadata(ROOT))
        selection, allocation = draw(eligible, legacy_keys, plan["sample"])
        by_trial = {r["trial_id"]:(r,group) for r,group in selection}
        entries = []
        for packet in lines(packets):
            if record := by_trial.pop(packet["trial_id"], None):
                r, group = record
                entries.append((r["trial_id"],public_projection(packet), {**r,"panel":group}))
        if by_trial:
            raise ValueError("selected trial lost its visible exhibits")
        for row in originals:
            source = provenance[row["review_id"]]
            if source["suite"] != row["suite"]:
                raise ValueError("legacy provenance suite differs")
            entries.append((row["review_id"],legacy_projection(row), {**source,"panel":"legacy"}))
        shuffle_key = secrets.token_bytes(32)
        public, lookup = assemble(entries, shuffle_key)
        folder = scratch / "package"
        (folder / "reviewer").mkdir(parents=True)
        (folder / "custodian").mkdir()
        write_json(folder / "reviewer/packet.json", public)
        write_json(folder / "reviewer/submission.schema.json", submission_schema(public))
        write_json(folder / "custodian/draw.json", {"version":1,"mapping":lookup,"private_shuffle_key_hex":shuffle_key.hex(),"allocation":allocation,
                   "ineligible_primary_trials":losses,"gate_audit":totals,
                   "qualified_families":sorted(passed),"qualification_protocol":qualified["protocol_sha256"],
                   "rescore_sha256": digest(archived_table), "summary_sha256": digest(archived_summary),
                   "preregistration_sha256":digest(PROTOCOL), "preserved":plan["preserved"],
                   "reviewer_packet_sha256":digest(folder / "reviewer/packet.json"),
                   "human_review":"NOT_RUN","human_submissions":0})
        folder.rename(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=ROOT / OUT)
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    release(args.history, args.results, args.out)


if __name__ == "__main__":
    main()
