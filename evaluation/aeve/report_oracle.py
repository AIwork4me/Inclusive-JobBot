"""Reproduce the paired clarification diagnostic solely from portable GPU sessions."""
import argparse
from collections import Counter
import json
from pathlib import Path

from benchmarks.agentic_planning_v2.runner import evaluate_raw
from benchmarks.tool_calling_v2.oracle import decode_object
from .archive import verify
from .history import lines
from .oracle_panel import panel
from .runtime import ROOT, fingerprint, write_json

RESULTS = ROOT / "evaluation/aeve/results"
ARMS = ("original", "clarification", "tools", "zero", "combined")
MODES = ("native", "constrained")


def portable_records(results, collections):
    """Return the physical line locator inside each selected, previously verified bundle."""
    for manifest_path in sorted((results / "sessions").glob("*/manifest.json")):
        folder = manifest_path.parent
        manifest = json.loads(manifest_path.read_bytes())
        outcomes = json.loads((folder / "outcomes.json").read_bytes())
        if not any(row["collection"] in collections for row in outcomes):
            continue
        if manifest["gpu_evidence"] != "PASS" or manifest["active_pid_counter_samples"] <= 0:
            raise ValueError(f"missing GPU evidence in {folder.name}")
        identity = json.loads((folder / "identity.json").read_bytes())
        if identity["run_id"] != folder.name or manifest["run_id"] != folder.name:
            raise ValueError("session identity mismatch")
        capture = folder / "captures.jsonl.gz"
        for line, row in enumerate(lines(capture), 1):
            if row["collection"] in collections:
                if identity["candidate"] != row["candidate"]:
                    raise ValueError("capture model differs from GPU session")
                yield row, {"path": capture.relative_to(results).as_posix(), "line": line,
                            "volume_sha256": manifest["sha256"][capture.name],
                            "job": row["job"], "attempt": row["attempt"], "run": row["run"]}


def grade_record(row):
    capture, spec = row["capture"], row["spec"]
    response = json.loads(capture["raw_response"]) if capture.get("raw_response") else {}
    choices = response.get("choices") or []
    choice = choices[0] if choices else {}
    raw = choice.get("message", {}).get("content")
    plan = {}
    if isinstance(raw, str):
        try:
            plan = decode_object(raw)
        except ValueError:
            pass
    actions = plan.get("actions") if isinstance(plan, dict) else None
    tools = [a.get("tool") if isinstance(a, dict) else None for a in actions] if isinstance(actions, list) else None
    result = row["evaluation"]
    if row["transport"] == "PASS":
        recomputed = evaluate_raw(raw, spec["contract"], [spec["world"]])
        if result != recomputed:
            raise ValueError(f"offline Oracle verdict differs for {row['job']}")
    public_tools = spec["contract"]["tools"]
    return {"transport": row["transport"], "status": result["status"], "errors": result.get("errors", []),
            "reason": result.get("reason"), "finish_reason": choice.get("finish_reason"), "tools": tools,
            "action_count": len(tools) if tools is not None else None,
            "invented_tools": [t for t in tools if t not in public_tools] if tools is not None else None,
            "request_sha256": fingerprint(spec["body"])}


def analyze(results):
    verify(results)
    frozen = {}
    for spec in panel():
        if spec["suite"] != "clarification":
            break
        frozen[spec["arm"], spec["mode"]] = spec
    observations = {}
    for row, evidence in portable_records(results, {"clarification"}):
        spec = row["spec"]
        key = spec["arm"], spec["mode"]
        if key in observations or spec != frozen[key]:
            raise ValueError("duplicate observation or request differs from the paired design")
        observations[key] = {**grade_record(row), "evidence": evidence}
    return [{"arm": arm, "mode": mode, **observations.get((arm, mode), {"status": "NOT_RUN",
             "request_sha256": fingerprint(frozen[arm, mode]["body"])})} for arm in ARMS for mode in MODES]


def render(rows):
    parts = ["# Qwen3-14B 零工具澄清配对实验", "",
             "同一条公开任务、同一个模型、给定目标、相同采样设置。五种合同分别使用 Native 与 Constrained，每格预注册一个请求。工具名从实际响应的 actions 读取，世界判定按归档请求和响应重放。", "",
             "| 合同 | 解码模式 | 传输 | 提议工具 | Oracle | 校验结果 |", "|---|---|---|---|---|---|"]
    for row in rows:
        tools = row.get("tools")
        names = "未观测" if tools is None else ", ".join(map(str, tools)) or "空数组"
        reason = ", ".join(dict.fromkeys(row.get("errors", []))) or row.get("reason") or "—"
        parts.append(f"| {row['arm']} | {row['mode']} | {row.get('transport', 'NOT_RUN')} | {names} | {row['status']} | {reason} |")
    parts.extend(["", "## 观测范围", ""])
    for mode in MODES:
        subset = [r for r in rows if r["mode"] == mode]
        valid = [r for r in subset if r.get("tools") is not None and r.get("transport") == "PASS"]
        counts = Counter(r["status"] for r in subset)
        fabricated = sum(bool(r["invented_tools"]) for r in valid)
        parts.append(f"- {mode} 有 {len(valid)}/5 个完整可解析提议，其中 {fabricated}/{len(valid)} 个使用未提供的工具。Oracle 通过 {counts['PASS']}/5，失败 {counts['FAIL']}/5，未运行 {counts['NOT_RUN']}/5。")
    parts.extend(["", "每格只有一个观测，同一个任务重复用于十个合同设置。这组数据能够定位该输入的合同和引用错误，无法估计跨任务成功率或重复运行可靠性。", "",
                  "## 逐项证据", "", "下列文件按 JSONL 解压后的行号定位，每行包含原始请求、响应、采样记录及判定。对应目录内的 manifest.json 保存文件哈希，identity.json 保存模型和引擎身份。", ""])
    for row in rows:
        if evidence := row.get("evidence"):
            parts.append(f"- {row['arm']} / {row['mode']} 第 {evidence['line']} 行，任务 `{evidence['job']}`。[物理记录](../evaluation/aeve/results/{evidence['path']})")
    return "\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--report", type=Path, default=ROOT / "reports/IJ073_QWEN3_14B_CLARIFICATION_AB.md")
    parser.add_argument("--data", type=Path, default=ROOT / "evidence/IJ073/oracle/clarification_ab.json")
    args = parser.parse_args()
    rows = analyze(args.results)
    args.data.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.data, {"schema_version": 1, "source": "portable_gpu_session", "arms": rows})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render(rows), encoding="utf8", newline="\n")


if __name__ == "__main__":
    main()
