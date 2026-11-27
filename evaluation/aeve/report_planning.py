"""Reproduce the 64-cell paired planning diagnostic from sealed GPU captures."""
import argparse
from collections import Counter
from itertools import product
import json
import os
from pathlib import Path
from urllib.parse import quote

from benchmarks.agentic_planning_v1.sandbox import SyntheticSandbox
from benchmarks.agentic_planning_v2.trace import assess as assess_trace
from benchmarks.tool_calling_v2.oracle import decode_object, equal
from .archive import verify
from .controller import grade, worlds
from .oracle_panel import panel
from .report_oracle import RESULTS, portable_records
from .runtime import ROOT, fingerprint, write_json

SUITE = "planning-development"
NOT_RUN = "NOT_RUN"


def frozen_panel():
    cases = {}
    for spec in panel():
        if spec["suite"] == SUITE:
            key = "/".join(spec[k] for k in ("case", "arm", "mode", "track"))
            if key in cases:
                raise ValueError("duplicate preregistered planning request")
            cases[key] = spec
    expected = set(product(range(8), ("en","zh"), ("native","constrained"), ("provided","inferred")))
    dimensions = {(s["level"],s["language"],s["mode"],s["track"]) for s in cases.values()}
    if len(cases) != len(expected) or dimensions != expected or len({s["case"] for s in cases.values()}) != 16:
        raise ValueError("planning panel differs from preregistered matrix")
    return cases


def predeclared(item, spec):
    public = json.loads(spec["body"]["messages"][1]["content"])
    limits = public["limits"]
    provided = spec["track"] == "provided"
    if (("goal" in public) != provided or (provided and public["goal"] != spec["contract"]["goal"])
            or ("response_format" in spec["body"]) != (spec["mode"] == "constrained")
            or spec["contract"]["action_budget"] != limits["tool_calls"]):
        raise ValueError("frozen public exposure, mode, or budget differs from contract")
    return {"case":spec["case"],"level":spec["level"],"language":spec["language"],
            "mode":spec["mode"],"track":spec["track"],"arm":spec["arm"],"cell":item,
            "request_sha256":fingerprint(spec["body"]), "status":NOT_RUN,"transport":NOT_RUN,
            "expected_job":fingerprint([SUITE,item,"J","plan","candidate",spec]),
            "fixture_world_sha256":fingerprint(worlds()[spec["case"]]),"limits":limits,
            "generation_token_limit":spec["body"]["max_tokens"],"goal_field_exposed":provided,
            "goal_literal_in_user_message":spec["contract"]["goal"] in spec["body"]["messages"][1]["content"],
            "goal_options_exposed":"goal_options" in public,"goal_literal_match":NOT_RUN,
            "trace":{"trace_replay":NOT_RUN,"actual_calls":None,"commit_authorization":NOT_RUN},
            "budget":{"context":NOT_RUN,"generation":NOT_RUN,"tool_calls":NOT_RUN,
                      "sealed_model_requests":NOT_RUN,"sealed_retries":NOT_RUN},
            "sealed_request_count":0,"validation_errors":[],"finish_reason":None,"evidence":None}


def measured(capture, response):
    usage = response.get("usage") or {}
    gen = capture["source_generation"]
    def count(name):
        v = gen.get(name)
        return len(v) if isinstance(v, list) else None
    return {"prompt_tokens":usage.get("prompt_tokens"), "completion_tokens":usage.get("completion_tokens"),
            "total_tokens":usage.get("total_tokens"), "prompt_token_ids_count":count("prompt_token_ids"),
            "sampled_token_ids_count":count("sampled_token_ids"), "truncated":gen.get("truncated")}


def limit_status(value, limit):
    if type(value) is not int:
        return NOT_RUN
    return "PASS" if value <= limit else "FAIL"


def observed(spec, row, result, evidence):
    if row["job"] != result["expected_job"] or spec != row["spec"] or row["candidate"] != "J":
        raise ValueError("GPU record differs from frozen planning request")
    capture = row["capture"]
    try:
        response = json.loads(capture.get("raw_response") or "{}")
    except (ValueError, TypeError):
        response = {}
    if not isinstance(response, dict):
        response = {}
    choice = (response.get("choices") or [{}])[0]
    raw = choice.get("message", {}).get("content")
    finish = choice.get("finish_reason")
    measured_tokens = measured(capture, response)
    if capture["http_status"] != 200 or capture["render_status"] != 200 or measured_tokens["truncated"] is not False:
        transport = "BLOCKED"
    else:
        transport = "PASS" if isinstance(raw,str) and finish == "stop" else "FAIL"
    if transport != row["transport"]:
        raise ValueError("archived transport differs from response")
    if transport == "PASS":
        try:
            replay = grade(spec, raw)
        except (ValueError,TypeError,KeyError,RecursionError) as exc:
            replay = {"status":"FAIL","reason":"invalid_output","detail":str(exc)[:240]}
    else:
        replay = {"status":transport,"reason":"incomplete_generation_or_transport"}
    if replay != row["evaluation"]:
        raise ValueError("frozen planning score differs from offline replay")
    result.update(status=replay["status"], transport=transport, finish_reason=finish, sealed_request_count=1,
                  tokens=measured_tokens, evidence=evidence, reason=replay.get("reason"), detail=replay.get("detail"),
                  validation_errors=replay.get("errors", []))
    prompt, generated = measured_tokens["prompt_token_ids_count"], measured_tokens["sampled_token_ids_count"]
    total = measured_tokens["total_tokens"]
    if total is None and prompt is not None and generated is not None:
        total = prompt + generated
    result["context_tokens_observed"] = total
    result["budget"].update(sealed_model_requests=limit_status(1,result["limits"]["model_requests"]),
                            sealed_retries=limit_status(0,result["limits"]["retries"]),
                            context=limit_status(total,result["limits"]["peak_context_tokens"]),
                            generation=limit_status(measured_tokens["completion_tokens"] if
                                measured_tokens["completion_tokens"] is not None else generated,result["generation_token_limit"]))
    if transport == "PASS":
        try:
            proposal = decode_object(raw)
            result["proposed_goal"] = proposal.get("goal")
            result["goal_literal_match"] = "PASS" if proposal.get("goal") == spec["contract"]["goal"] else "FAIL"
        except ValueError:
            pass
    if "records" in replay:
        graph = worlds()[spec["case"]]
        calls = replay["records"]
        initial = SyntheticSandbox(graph["world"]).snapshot()
        trace = assess_trace({"action_budget":spec["contract"]["action_budget"],"tools":spec["contract"]["tools"]},
                             graph, {"records":calls, "before_state":initial,
                                     "after_state":replay["after_state"], "final_raw":replay["final"]})
        trace.update(call_tools=[c["tool"] for c in calls], observation_codes=[c["observation"]["code"] for c in calls],
                     external_event_keys=[sorted(c["observation"].get("external_event") or {}) for c in calls],
                     final_matches=equal(replay["final"],graph["final"]),
                     state_matches=equal(replay["after_state"],graph["goal_state"]),
                     before_state_source="frozen synthetic world",
                     records_sha256=fingerprint(calls))
        result["trace"] = trace
        result["budget"]["tool_calls"] = limit_status(len(calls), result["limits"]["tool_calls"])
    return result


def analyze(results):
    verify(results)
    roster = frozen_panel()
    rows = {item:predeclared(item,spec) for item,spec in roster.items()}
    for row, evidence in portable_records(results, {SUITE}):
        item = row["item"]
        if item not in roster or rows[item]["evidence"]:
            raise ValueError("unexpected or duplicate planning observation")
        observed(roster[item], row, rows[item], evidence)
    return list(rows.values())


def render(rows, results, data, report):
    def link(path):
        return quote(Path(os.path.relpath(path, report.parent)).as_posix())
    recorded = [r for r in rows if r["evidence"]]
    counts = Counter(r["status"] for r in rows)
    text = ["# Qwen3-14B 条件规划双轨诊断", "",
            f"16 个不同任务覆盖 L0–L7 和中英文，每个任务配对 Native、Constrained 与给定目标、推断目标，共 64 个预注册请求。当前有 {len(recorded)}/64 个已封存的物理请求。Oracle 判定 PASS {counts['PASS']}，FAIL {counts['FAIL']}，BLOCKED {counts['BLOCKED']}，NOT_RUN {counts['NOT_RUN']}。", "",
            "冻结评分器先验证计划结构和 goal，再在固定的合成业务世界内执行可通过校验的计划。inferred 隐去顶层目标字段，评分器仍要求 goal 与合同标签逐字一致。语义等价的目标表述可能被拒绝。逐案数据另列标签是否出现在其余公开请求文本中。此面板无法给出自然语言目标理解准确率。", "",
            "每格计划 1 次模型请求、0 次重试，输出上限 768 tokens。下表列出各任务的工具预算与上下文上限。已封存请求的 token 用量来自实际传输；工具记录来自固定世界中的软件执行。请求与重试计数以封存包为边界，未封存尝试不可核验。没有工具记录时保持未观测。每格仅一次，不估计跨任务总体成功率或重复可靠性。", "",
            "| 任务 | 级别/语言 | 模式/目标 | 工具/上下文上限 | 实测上下文 | 传输 | Oracle | 字面目标 | 已执行调用 | 轨迹复核 | 校验/执行原因 | 原始证据 |",
            "|---|---|---|---:|---:|---|---|---|---:|---|---|---|"]
    for r in rows:
        limits = r["limits"]
        calls = r["trace"]["actual_calls"]
        total = r.get("context_tokens_observed")
        ref = "未封存"
        if e := r["evidence"]:
            ref = f"[卷内第 {e['line']} 行]({link(results/e['path'])})"
        why = ", ".join(dict.fromkeys(r["validation_errors"])) or r.get("reason") or "—"
        text.append(f"| {r['case']} | L{r['level']}/{r['language']} | {r['mode']}/{r['track']} | {limits['tool_calls']}/{limits['peak_context_tokens']} | {total if total is not None else '—'} | {r['transport']} | {r['status']} | {r['goal_literal_match']} | {calls if calls is not None else '—'} | {r['trace']['trace_replay']} | {why} | {ref} |")
    text.extend(["", "## 配对分母", "", "| 模式/目标 | 封存/预注册 | Oracle 通过/封存 | 双语均已封存的级别 |",
                 "|---|---:|---:|---:|"])
    for mode, track in product(("native","constrained"),("provided","inferred")):
        group = [r for r in recorded if r["mode"] == mode and r["track"] == track]
        complete = sum(len({r["language"] for r in group if r["level"] == level}) == 2 for level in range(8))
        passed = sum(r["status"] == "PASS" for r in group)
        rate = f"{passed}/{len(group)}" if group else "无分母"
        text.append(f"| {mode}/{track} | {len(group)}/16 | {rate} | {complete}/8 |")
    text.extend(["", "## 失败原因和实际检查分母", ""])
    failed = Counter()
    for r in recorded:
        if r["status"] != "PASS":
            for reason in set(r["validation_errors"] or [r.get("reason") or r["status"]]):
                failed[reason] += 1
    for reason, n in sorted(failed.items()):
        text.append(f"- {reason} 出现在 {n} 个已封存请求中。")
    if not failed:
        text.append("当前没有已封存的失败记录。")
    text.append("")
    for name, title in (("sealed_model_requests","封存模型请求"),("sealed_retries","同一任务在封存包内的额外尝试"),
                        ("context","上下文"),("generation","生成长度"),("tool_calls","合成世界工具调用")):
        c = Counter(r["budget"][name] for r in rows)
        text.append(f"- {title}预算可核验 {c['PASS']+c['FAIL']}/64，超限 {c['FAIL']}。")
    text += ["", "轨迹复核使用冻结世界重建初态，逐一重放实际记录的工具、参数和观测，并比较记录的终态。工具记录为空时没有可复核调用，终答与业务状态另行比较。未通过结构校验或传输失败的记录保留原始诊断。", "",
             f"[逐案预算、证据哈希及原因]({link(data)}) · [面板选择和请求构造]({link(ROOT/'evaluation/aeve/oracle_panel.py')}) · [冻结控制世界]({link(ROOT/'benchmarks/agentic_planning_v1/task_graphs/holdout.jsonl')})", ""]
    return "\n".join(text)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--results",type=Path,default=RESULTS)
    cli.add_argument("--data",type=Path,default=ROOT/"evidence/IJ073/oracle/planning_development.json")
    cli.add_argument("--report",type=Path,default=ROOT/"reports/IJ073_QWEN3_14B_PLANNING_DEVELOPMENT.md")
    args = cli.parse_args()
    rows = analyze(args.results)
    args.data.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.data,{"version":1,"suite":SUITE,"cells":rows})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render(rows,args.results,args.data,args.report),encoding="utf8",newline="\n")


if __name__ == "__main__":
    main()
