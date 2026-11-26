"""Rebuild historical comparisons from the public registry and sealed GPU captures."""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from .adjudication import assess
from .archive import digest
from .history import OUT, lines, seal
from .history_dimensions import read_addendum, apply_facts
from . import history_supplement_report as supplemental
from .intake import ALIASES, DIMENSIONS
from .local_judge import check
from .qualification import measure
from .report_oracle import RESULTS, portable_records
from .runtime import REGISTRY, ROOT, canonical, fingerprint, write_json

SCOPES = {"development": "history", "formal": "history-v2", "supplement": supplemental.COLLECTION}
STATES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
# Only compare old and new columns whose business meaning is shared.
PREVIOUS = {"business_state_status": "D23", "wire_protocol_status": "D21", "plan_protocol": "D19",
            "commit_authorization": "D24", "trace_status": "trace_status"}


def packet_index(path, recorded, formal, additional=None):
    result = {}
    checked = set()
    sources = [p for p in (path, additional) if p is not None and p.is_file()]
    for source in sources:
        seen = set()
        for row in lines(source):
            trial = row["trial_id"]
            if trial in seen:
                raise ValueError("duplicate semantic trial")
            seen.add(trial)
            dims = [ALIASES.get(dim,dim) for dim in row["dimensions"]]
            previous = result.setdefault(trial,[])
            if len(set(dims)) != len(dims) or set(previous).intersection(dims):
                raise ValueError("repeated dimension in packet inventory")
            previous.extend(dims)
            if trial not in recorded:
                continue
            events = [{"id":e["id"],"kind":e["kind"],"value":e["content"]} for e in row["events"]]
            by_id = {e["id"]:e for e in events}
            for dim,actual in recorded[trial].items():
                if dim not in dims:
                    continue
                selected = [by_id[i] for i in row["dimension_event_ids"][dim]] if formal else events
                expected = {"dimension":dim,"task":DIMENSIONS[dim],"events":selected}
                if actual != {fingerprint(expected)}:
                    raise ValueError("archived judge input differs from stage evidence")
                checked.add((trial,dim))
    if checked != {(trial,dim) for trial,dims in recorded.items() for dim in dims}:
        raise ValueError("recorded review lacks registered stage evidence")
    return result


def import_reviews(db, results, include_supplement=True):
    db.execute("""CREATE TABLE captures(id TEXT PRIMARY KEY,collection TEXT,item TEXT,candidate TEXT,
               dimension TEXT,spec BLOB,status TEXT,result TEXT,evidence TEXT)""")
    db.execute("CREATE INDEX captures_item ON captures(item)")
    db.execute("CREATE TEMP TABLE batch(item TEXT PRIMARY KEY)")
    db.execute("""CREATE TEMP VIEW jobs AS
                  SELECT captures.* FROM batch JOIN captures USING(item)
                  UNION ALL
                  SELECT child.* FROM batch JOIN captures parent ON parent.item=batch.item
                  JOIN captures child ON child.item=parent.id
                  WHERE child.collection IN ('history-v2-citations','history-supplement-v2-citations')""")
    collections = {name + suffix for name in SCOPES.values() for suffix in ("", "-dispute")}
    packets = {name: defaultdict(dict) for name in SCOPES.values()}
    collections.update({"history-v2-citations", supplemental.COLLECTION + "-citations"})
    if not include_supplement:
        collections = {c for c in collections if not c.startswith(supplemental.COLLECTION)}
    for row, ref in portable_records(results, collections):
        result, packet = row["evaluation"], row["spec"]["packet"]
        collection = row["collection"].removesuffix("-dispute")
        if not collection.endswith("-citations"):
            packets[collection][row["item"]].setdefault(row["dimension"], set()).add(fingerprint(packet))
        if row["transport"] == "PASS":
            choice = json.loads(row["capture"]["raw_response"])["choices"][0]
            try:
                actual = check(packet, choice["message"].get("content"))
            except (ValueError, KeyError, TypeError):
                actual = None
            if actual != result and (actual is not None or "verdict" in result):
                raise ValueError("stored vote differs from raw generation")
        elif "verdict" in result:
            raise ValueError("incomplete transport assigned a vote")
        db.execute("INSERT INTO captures VALUES(?,?,?,?,?,?,?,?,?)", (row["job"], row["collection"],
                   row["item"], row["candidate"], row["dimension"], gzip.compress(canonical({"packet": packet})),
                   "RECORDED", canonical(result).decode(), canonical(ref).decode()))
    bad_parent = db.execute("""SELECT child.id FROM captures child LEFT JOIN captures parent ON parent.id=child.item
                             WHERE child.collection IN ('history-v2-citations','history-supplement-v2-citations')
                             AND (parent.id IS NULL OR child.collection NOT IN (parent.collection || '-citations',
                                      replace(parent.collection,'-dispute','') || '-citations')
                                  OR child.candidate=parent.candidate OR child.dimension!=parent.dimension) LIMIT 1""").fetchone()
    if bad_parent:
        raise ValueError("citation review has no matching independent formal parent")
    db.commit()
    return packets


def current_scores(trial, decisions):
    facts = trial["deterministic"]
    values = dict(facts)
    for dim, decision in decisions.items():
        if facts.get(dim, "NOT_RUN") == "NOT_RUN":
            values[dim] = decision["status"]
        elif facts[dim] == "PASS" and decision["status"] == "BLOCKED":
            # Preserve the measured fact and record the contested combined finding.
            values[dim] = "BLOCKED"
    vetoes = {}
    for old, dim in PREVIOUS.items():
        old_status = trial["archived_dimensions"].get(old)
        if old_status in {"FAIL","BLOCKED"} and values.get(dim) == "PASS":
            values[dim] = "BLOCKED"
            vetoes[dim] = f"conflicting archived {old}={old_status}"
    if values.get("D25") == "PASS":
        obstacles = [dim for dim in ("D19","D20","D21","D22","D23","D24") if values.get(dim) in {"FAIL","BLOCKED"}]
        if obstacles:
            values["D25"] = "FAIL" if any(values[d] == "FAIL" for d in obstacles) else "BLOCKED"
            vetoes["D25"] = "required layer: " + ",".join(obstacles)
    return values, vetoes


def compare(trial, scores):
    changes = []
    for old, dim in PREVIOUS.items():
        if old in trial["archived_dimensions"] and dim in scores:
            prior, now = trial["archived_dimensions"][old], scores[dim]
            changes.append({"old_field": old, "new_field": dim, "old": prior, "new": now})
    return changes


def build(history, results, out):
    registry = history / "registry.jsonl.gz"
    coverage = json.loads((history / "coverage.json").read_bytes())
    for name, expected in coverage["registry_sha256_uncompressed"].items():
        if name not in {"registry", "judge_inputs", "judge_inputs_v2", "sealed_projections"}:
            raise ValueError("unknown historical coverage digest")
        with gzip.open(history / (name + ".jsonl.gz"), "rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                raise ValueError("historical inventory differs from its coverage manifest")
    packet_paths = {"development": history / "judge_inputs.jsonl.gz", "formal": history / "judge_inputs_v2.jsonl.gz"}
    extra_input, extra_facts = read_addendum(history)
    supplement, inventory = supplemental.inventory(history)
    present = inventory["status"] == "PASS"
    packet_paths["supplement"] = history / supplemental.INPUT
    qualification = measure(results)
    admitted = [c for c,r in qualification["admission"].items() if r["status"] == "PASS"]
    seen_supplement = set()
    observed_sources = {}
    covered_sources = set()
    families = {code: cfg["family"] for code,cfg in json.loads(REGISTRY.read_bytes())["candidates"].items()}
    scope_stats = {s: Counter() for s in SCOPES}
    stats, dims, transitions, reasons = Counter(), defaultdict(Counter), Counter(), Counter()
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out) as tmp, closing(sqlite3.connect(Path(tmp) / "reviews.sqlite")) as db:
        db.row_factory = sqlite3.Row
        recorded = import_reviews(db, results, include_supplement=present)
        packets = {s: packet_index(p, recorded[SCOPES[s]], s != "development", extra_input if s == "formal" else None)
                   if s != "supplement" or present else {} for s,p in packet_paths.items()}
        for scope, name in SCOPES.items():
            if set(recorded[name]) - set(packets[scope]):
                raise ValueError("reviewed historical trial lacks registered exhibits")
        capture_counts = dict(db.execute("SELECT collection,count(*) FROM captures GROUP BY collection"))
        formal_rows = sum(capture_counts.get(SCOPES[s] + suffix, 0) for s in ("formal", "supplement") for suffix in ("", "-dispute"))
        if formal_rows and (len(admitted) < 2 or not packet_paths["formal"].exists()):
            raise ValueError("formal reviews lack qualification or formal packet inventory")

        unmatched = {r[0] for r in db.execute("SELECT DISTINCT item FROM captures WHERE collection NOT IN ('history-v2-citations','history-supplement-v2-citations')")}

        def render_rows():
            stream = iter(lines(registry))
            while raw_batch := list(itertools.islice(stream, 256)):
                batch = [apply_facts(trial,extra_facts) for trial in raw_batch]
                db.execute("DELETE FROM batch")
                db.executemany("INSERT INTO batch VALUES(?)", ((t["trial_id"],) for t in batch))
                bound = {}
                for trial in batch:
                    tid = trial["trial_id"]
                    meta = supplemental.bind(trial, supplement, present)
                    if meta:
                        seen_supplement.add(tid)
                        bound[tid] = meta
                    if tid in packets["formal"] or tid in packets["supplement"]:
                        observed_sources[tid] = meta["subject_family"] if meta else trial["source_family"]
                votes = {}
                if db.execute("SELECT 1 FROM jobs LIMIT 1").fetchone():
                    shard = Path(tmp) / "batch.jsonl"
                    shard.write_bytes(b"".join(canonical(row) + b"\n" for row in batch))
                    for scope, name in SCOPES.items():
                        source = shard
                        if scope == "supplement":
                            source = Path(tmp) / "nonphysical-batch.jsonl"
                            source.write_bytes(b"".join(canonical({"trial_id":tid, "source_family": meta["subject_family"],
                                "deterministic":meta["deterministic"]}) + b"\n" for tid,meta in bound.items()
                                if meta["subject_family"] not in {"", "unknown", None}))
                        decisions = assess(db, source, collection=name, admitted=admitted if scope != "development" else None)
                        for (trial, dim), decision in decisions.items():
                            votes.setdefault((scope, trial), {})[dim] = decision
                for trial in batch:
                    tid = trial["trial_id"]
                    unmatched.discard(tid)
                    stats["trials"] += 1
                    if trial["original_status"] is None:
                        stats["without_legacy_status"] += 1
                    output = dict(trial)
                    reviews = {}
                    for scope in SCOPES:
                        if scope == "supplement" and trial["class"] == "physical_trial":
                            continue
                        stat = scope_stats[scope]
                        expected = packets[scope].get(tid, [])
                        decisions = votes.get((scope, tid), {})
                        if set(decisions) - set(expected):
                            raise ValueError("recorded vote outside registered dimensions")
                        stat["eligible_trials"] += bool(expected)
                        stat["eligible_dimensions"] += len(expected)
                        completed = 0
                        covered = 0
                        for dim, decision in decisions.items():
                            refs = {}
                            for candidate, job in decision["jobs"].items():
                                source = db.execute("SELECT result,evidence FROM captures WHERE id=?", (job,)).fetchone()
                                answer, evidence = json.loads(source[0]), json.loads(source[1])
                                refs[candidate] = {**evidence, "evidence_refs": answer.get("evidence_refs", []),
                                                   "reason": answer.get("reason_summary") or answer.get("reason")}
                                if scope != "development":
                                    children = db.execute("""SELECT candidate,result,evidence FROM jobs WHERE
                                                          collection=? AND item=?""", (SCOPES[scope]+"-citations", job))
                                    refs[candidate]["entailment_reviews"] = [
                                        {"reviewer": r["candidate"], "result": json.loads(r["result"]),
                                         "evidence": json.loads(r["evidence"])} for r in children]
                            decision["citations"] = refs
                            stat["primary_pairs_recorded"] += decision["primary_recorded"] == 2
                            stat["disputed"] += decision["disputed"]
                            stat["third_recorded"] += decision["third_recorded"]
                            stat["invalid_votes"] += len(decision["invalid"])
                            stat["recorded_votes"] += decision["recorded"]
                            stat["explicit_abstentions"] += sum(v == "BLOCKED" for v in decision["votes"].values())
                            stat["blocked_dimensions"] += decision["status"] == "BLOCKED"
                            if scope != "development":
                                subject = observed_sources.get(tid)
                                if subject and subject != "unknown":
                                    try:
                                        supplemental.require_independent_review(decision, admitted, families, subject)
                                    except ValueError:
                                        pass
                                    else:
                                        covered += 1
                            supported_votes = sum(
                                vote in {"PASS","FAIL"} and candidate not in decision["invalid"]
                                and (scope == "development" or decision["citation_support"].get(candidate) == "supported")
                                for candidate,vote in decision["votes"].items())
                            if (decision["status"] in {"PASS","FAIL"} and decision["primary_recorded"] == 2
                                    and supported_votes >= 2):
                                completed += 1
                        if scope != "development":
                            stat["independently_reviewed_dimensions"] += covered
                            if expected and covered == len(expected):
                                stat["fully_reviewed_trials"] += 1
                                covered_sources.add(tid)
                        stat["resolved_dimensions"] += completed
                        stat["fully_resolved_trials"] += bool(expected) and completed == len(expected)
                        reviews[scope] = {"expected": expected, "judgments": decisions}
                    scope = "formal" if trial["class"] == "physical_trial" else "supplement"
                    source = trial
                    if tid in bound:
                        meta = bound[tid]
                        output["supplement"] = {k: meta[k] for k in ("subject_family","semantic_disposition","source_trial_id","deterministic")}
                        source = {**trial, "deterministic": meta["deterministic"]}
                    scores, vetoes = current_scores(source, reviews[scope]["judgments"])
                    output.update(reviews=reviews, current=scores, vetoes=vetoes, comparisons=compare(trial,scores))
                    for pair in output["comparisons"]:
                        transitions[pair["new_field"], pair["old"], pair["new"]] += 1
                    for dim, value in scores.items():
                        dims["all", dim][value] += 1
                        dims[trial["class"], dim][value] += 1
                    if vetoes:
                        stats["trials_with_veto"] += 1
                    for decision in reviews[scope]["judgments"].values():
                        reasons[decision["reason"]] += 1
                    yield output

        table = Path(tmp) / "rescore.jsonl.gz"
        table_sha = seal(table, render_rows())
        if stats["trials"] != coverage["unique_trials"]:
            raise ValueError("historical output differs from registered trial count")
        if seen_supplement != set(supplement):
            raise ValueError("supplemental registry includes an unregistered nonphysical trial")
        for meta in supplement.values():
            origin = meta["source_trial_id"]
            if origin and (origin not in observed_sources or observed_sources[origin] != meta["subject_family"]):
                raise ValueError("derived record references an unknown or incompatible original")
        if unmatched:
            raise ValueError("portable reviews refer to a trial outside the registry")
        table.replace(out / table.name)
    if present:
        linked = [meta["source_trial_id"] for meta in supplement.values() if meta["source_trial_id"]]
        inventory["links_to_fully_reviewed_sources"] = sum(origin in covered_sources for origin in linked)
        complete = (len(admitted) >= 2 and inventory["links_to_fully_reviewed_sources"] == len(linked) and
                    scope_stats["supplement"]["fully_reviewed_trials"] == inventory["independent_inputs"])
        inventory["semantic_coverage_gate"] = "PASS" if complete else "BLOCKED"
    else:
        inventory["semantic_coverage_gate"] = "BLOCKED"
    summary = {"version": 2, "nonphysical_inventory": inventory, "trial_counts": dict(stats), "portable_captures": capture_counts,
               "current_dimension_statuses": {level: {dim: dict(v) for (s,dim),v in dims.items() if s == level}
                                               for level in sorted({s for s, _ in dims} | {"physical_trial"})},
               "physical_addendum_sha256": digest(history/"physical_addendum.json") if extra_input else None,
               "admitted_judges": admitted, "qualification_protocol": qualification["protocol_sha256"],
               "scope": {s: {**dict(scope_stats[s]), "packet_inventory_present": present if s == "supplement" else packet_paths[s].is_file()}
                         for s in SCOPES}, "formal_decision_reasons": dict(reasons),
               "transitions": [{"dimension": d, "old": a, "new": b, "n": n} for (d,a,b),n in sorted(transitions.items())],
               "hashes": {"rescore_sha256_uncompressed": table_sha, "registry_sha256": digest(registry),
                          **{s + "_packets_sha256": digest(p) for s,p in packet_paths.items() if p.exists()}}}
    write_json(out / "rescore_summary.json", summary)
    return summary


def rate(numerator, denominator):
    if not denominator:
        return "无分母"
    percent = 100 * numerator / denominator
    display = "<0.01%" if 0 < percent < 0.01 else f"{percent:.2f}%"
    return f"{numerator}/{denominator} ({display})"


def reports(summary, out, destination):
    import os
    from urllib.parse import quote
    destination.mkdir(parents=True, exist_ok=True)
    table = quote(Path(os.path.relpath(out / "rescore.jsonl.gz", destination)).as_posix())
    index = quote(Path(os.path.relpath(out / "rescore_summary.json", destination)).as_posix())
    links = [f"[逐试次数据]({table}) · [分母、状态计数及哈希]({index})", ""]
    scopes = summary["scope"]
    parts = ["# IJ-0 至 IJ-0.7.3 历史 AI 评价", "",
             f"注册表收录 {summary['trial_counts']['trials']:,} 条独立试次身份。封存资格中通过的 Judge 有 {len(summary['admitted_judges'])} 个。",
             "", "| 范围 | 有评价输入的试次 | 适用维度 | 双主审已记录 | 有结论的维度 | 全部适用维度有结论的试次 |",
             "|---|---:|---:|---:|---:|---:|"]
    scope_labels = (("开发", "development"), ("物理试次正式评价", "formal"), ("非物理独立证据正式评价", "supplement"))
    for label, scope in scope_labels:
        s = Counter(scopes[scope])
        if s["packet_inventory_present"]:
            parts.append(f"| {label} | {s['eligible_trials']} | {s['eligible_dimensions']} | {s['primary_pairs_recorded']} | {rate(s['resolved_dimensions'],s['eligible_dimensions'])} | {rate(s['fully_resolved_trials'],s['eligible_trials'])} |")
        else:
            parts.append(f"| {label} | 输入清单待归档 | 未知 | {s['primary_pairs_recorded']} | 未知 | 未知 |")
    parts.extend(["", "开发试验与资格准入后正式评价分别计数。只有实际到达的主审、仲裁和确定性检查可产生观测。每个试次的 expected 字段列出适用维度，缺少判断的维度记作 NOT_RUN。", "",
                  "| 范围 | 实际判读尝试 | Judge 明确弃权 | 无有效判决的尝试 | 维度争议 | 第三 Judge 已返回 | 维度仍为 BLOCKED |",
                  "|---|---:|---:|---:|---:|---:|---:|"])
    for label, scope in scope_labels:
        s = Counter(scopes[scope])
        parts.append(f"| {label} | {s['recorded_votes']} | {rate(s['explicit_abstentions'],s['recorded_votes'])} | {s['invalid_votes']} | {s['disputed']} | {s['third_recorded']} | {s['blocked_dimensions']} |")
    meta = summary["nonphysical_inventory"]
    parts.extend(["", f"非物理证据登记完整性为 {meta['status']}。独立软件包 {meta.get('independent_inputs','待核验')} 个，"
                  f"补充轨独立评价覆盖门禁为 {meta['semantic_coverage_gate']}。已指向全面完成独立判读来源的派生记录有 {meta.get('links_to_fully_reviewed_sources','待核验')} 条。"
                  f"通过原记录引用复用的派生证据 {meta.get('linked_source_records','待核验')} 条。"
                  "逐案 supplement.source_trial_id 指向被复用试次，引用行不额外增加判读分母。"])
    parts.extend(["", f"非物理独立引用支持性复核已归档 {summary['portable_captures'].get(supplemental.COLLECTION+'-citations', 0)} 次。", "",
                  f"正式独立引用支持性复核已归档 {summary['portable_captures'].get('history-v2-citations', 0)} 次，单独计数。", "", "明确弃权对应 Judge 输出 BLOCKED。传输失败、截断或无法验证的引用归入无有效判决。每个实体试次的来源文件、记录定位符和哈希均保存在逐试次数据中。AI 决策含独立判断、分歧原因和对应原始证据位置。", "",
                  "## 可观测正确率", "",
                  "下表只计入 physical_trial。正确率分母为该维度已有 PASS 或 FAIL 的试次。软件 Witness、Mutation、Fixture 和离线重放的计数可从汇总文件独立查询。", "",
                  "| 维度 | 有结论记录中的通过率 | BLOCKED | 显式 NOT_RUN |", "|---|---:|---:|---:|"])
    for dim, label in (("D05","语义"),("D19","初始计划协议"),("D20","最终响应协议"),("D21","原生线协议"),
                       ("D22","业务结果"),("D23","持久化状态"),("D24","授权安全"),("D25","端到端严格成功")):
        counts = Counter(summary["current_dimension_statuses"]["physical_trial"].get(dim, {}))
        parts.append(f"| {dim} {label} | {rate(counts['PASS'],counts['PASS']+counts['FAIL'])} | {counts['BLOCKED']} | {counts['NOT_RUN']} |")
    parts += ["", "没有已观测分母的项目暂不能估计正确率。未测维度以及超出证据可观测范围的动作不进入分母。", ""] + links
    (destination / "IJ073_FULL_AI_SELF_EVALUATION_CN.md").write_text("\n".join(parts), encoding="utf8", newline="\n")
    parts = ["# IJ-0 至 IJ-0.7.3 历史逐案复评分差异", "",
             "逐试次文件采用 gzip 压缩的 JSONL。每行包含 Run ID、Case ID、Attempt ID、配置指纹、证据类型和来源。original_status 和 archived_dimensions 保存旧值，deterministic 保存本轮重算值，current 保存各维度当前可观测结果。物理正式判定存入 reviews.formal，非物理独立证据的正式判定存入 reviews.supplement，开发记录存入 reviews.development。", "",
             "同义字段构成 comparisons 列。原有整体状态和 strict_sop_status 保持原实验含义，无法据此推定任一层级的表现。硬事实冲突及当前严格成功所需层级的否决保存在 vetoes。", "",
             "| 可比维度 | 旧值 | 新值 | 试次 |", "|---|---|---|---:|"]
    for t in summary["transitions"]:
        parts.append(f"| {t['dimension']} | {t['old']} | {t['new']} | {t['n']} |")
    parts += ["", f"缺少原有整体状态的试次有 {summary['trial_counts'].get('without_legacy_status',0)} 条，当前存在硬事实冲突或严格成功否决的试次有 {summary['trial_counts'].get('trials_with_veto',0)} 条。只有归档事实和正式裁决进入 current。", "",
              "逐试次数据中的 evidence_refs 指向该 Judge 输入内的事件；citations 提供原始响应所在卷、解压后的 JSONL 行号、尝试 ID 与 SHA256。裁决理由描述证据可支持的问题，缺失的后续业务动作保持未观测。", ""] + links
    (destination / "IJ073_HISTORICAL_RESCORE_COMPARISON.md").write_text("\n".join(parts), encoding="utf8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=ROOT / OUT)
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--out", type=Path, default=ROOT / OUT)
    parser.add_argument("--reports", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    summary = build(args.history, args.results, args.out)
    reports(summary, args.out, args.reports)


if __name__ == "__main__":
    main()
