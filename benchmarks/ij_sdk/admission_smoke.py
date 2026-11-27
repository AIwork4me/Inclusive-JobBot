#!/usr/bin/env python3
"""IJ-SDK-1.0 P2: preregistered runtime admission smoke suite.

Implements exactly the ten case families frozen in
configs/ij_sdk/model_admission_protocol.json (frozen 2026-11-27, before any
candidate result was observed). Deterministic scoring; case inputs are fixed
in code so the same inputs are reproducible everywhere.

This is RUNTIME ADMISSION, not capability qualification: functional
weaknesses are research outcomes; mandatory models (S1/S2) are admitted with
their weaknesses recorded. S3 selection uses the preregistered score only
(dev-score ranking; no holdout data consulted).

Usage:
    python -I benchmarks/ij_sdk/admission_smoke.py \
        --candidate S1 --model models/MiniCPM5-2B-GGUF/MiniCPM5-2B-Q8_0.gguf \
        --alias minicpm5-2b --backend vulkan \
        --output evidence/IJSDK/P2/admission/S1.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
PS = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32",
                  "WindowsPowerShell", "v1.0", "powershell.exe")

TOOLS = [
    {"type": "function", "function": {"name": "get_purchase_order", "description": "按订单号查询采购订单，返回供应商编号、商品明细和总金额。",
     "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "采购订单号，例如 PO-2026-0001"}}, "required": ["order_id"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_supplier", "description": "按供应商编号查询供应商信息，包括名称和是否在合格供应商名单。",
     "parameters": {"type": "object", "properties": {"supplier_id": {"type": "string", "description": "供应商编号，例如 SUP-007"}}, "required": ["supplier_id"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_inventory", "description": "按商品编号查询当前库存数量和仓库位置。",
     "parameters": {"type": "object", "properties": {"sku": {"type": "string", "description": "商品编号，例如 SKU-1001"}}, "required": ["sku"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_policy", "description": "按政策编号检索业务政策条文。",
     "parameters": {"type": "object", "properties": {"policy_id": {"type": "string", "description": "政策编号，例如 POL-302"}}, "required": ["policy_id"], "additionalProperties": False}}},
]

SIMULATED = {
    "get_purchase_order": {
        "PO-2026-0001": {"supplier_id": "SUP-007", "total_amount": 17420.50, "items": [{"sku": "SKU-1001", "qty": 40}]},
        "PO-2026-0002": {"supplier_id": "SUP-011", "total_amount": 980.00, "items": [{"sku": "SKU-2002", "qty": 5}]},
    },
    "get_supplier": {
        "SUP-007": {"name": "华信精密", "approved": True},
        "SUP-011": {"name": "蓝枫贸易", "approved": False},
    },
    "get_inventory": {
        "SKU-1001": {"qty": 120, "warehouse": "W-华东"},
        "SKU-2002": {"qty": 0, "warehouse": "W-华南"},
    },
    "get_policy": {
        "POL-302": "采购金额超过 10,000 元时需要二级审批。",
        "POL-118": "不合格供应商的订单必须暂停并上报。",
    },
}

SYSTEM_MSG = "你是单据审核助手。需要查询数据时调用工具，不要编造数据。"


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def post(base_url: str, path: str, body: dict, timeout: int = 240) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base_url + path, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as reply:
        return json.load(reply)


def chat(base_url, messages, tools=None, max_tokens=512, tool_choice="auto", temperature=0, response_format=None):
    body = {"model": "candidate", "messages": messages, "max_tokens": max_tokens,
            "temperature": temperature, "top_p": 1.0, "stream": False,
            "chat_template_kwargs": {"enable_thinking": False}}
    if tools is not None:
        body["tools"] = tools
        body["tool_choice"] = tool_choice
    if response_format is not None:
        body["response_format"] = response_format
    reply = post(base_url, "/v1/chat/completions", body)
    usage = reply.get("usage") or {}
    USAGE_TOTALS["prompt_tokens"] += usage.get("prompt_tokens", 0) or 0
    USAGE_TOTALS["completion_tokens"] += usage.get("completion_tokens", 0) or 0
    return reply


USAGE_TOTALS = {"prompt_tokens": 0, "completion_tokens": 0}


def tool_calls(reply):
    msg = reply["choices"][0]["message"]
    return msg.get("tool_calls") or []


def parse_call_args(call):
    fn = (call or {}).get("function", {})
    raw = fn.get("arguments", "")
    try:
        args = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except json.JSONDecodeError:
        args = None
    return fn.get("name"), args


def append_tool_result(messages, calls, result: dict):
    messages.append({"role": "assistant", "content": None, "tool_calls": calls})
    messages.append({"role": "tool", "tool_call_id": calls[0]["id"], "content": json.dumps(result, ensure_ascii=False)})


# ---------------------------------------------------------------------------
# Server lifecycle: direct launch with the pinned flags, D-010 proof from the
# server's own log, kill by Windows PID (D-011).
# ---------------------------------------------------------------------------

def start_candidate_server(model_path: pathlib.Path, alias: str, backend: str, port: int, work_dir: pathlib.Path) -> dict:
    binary = ROOT / "runtime" / "llama-cpp" / backend / "llama-server.exe"
    if not binary.exists():
        raise RuntimeError(f"backend binary missing: {binary}")
    stdout_log = (work_dir / "server.stdout.log").open("wb")
    stderr_log = (work_dir / "server.stderr.log").open("wb")
    args = [str(binary), "-m", str(model_path), "--host", "127.0.0.1", "--port", str(port),
            "--alias", alias, "--ctx-size", "8192", "--parallel", "1", "--jinja", "--offline",
            "--no-webui", "--log-verbosity", "4", "--n-gpu-layers", "0" if backend == "cpu" else "99"]
    env = None
    if backend == "rocm":
        libs = ROOT / "runtime" / "llama-cpp" / "rocm-libs" / "Lib" / "site-packages"
        env = dict(os.environ)
        env["PATH"] = f"{libs / '_rocm_sdk_libraries' / 'bin'};{libs / '_rocm_sdk_core' / 'bin'};" + env["PATH"]
    proc = subprocess.Popen(args, cwd=str(binary.parent), stdout=stdout_log, stderr=stderr_log,
                            creationflags=subprocess.CREATE_NO_WINDOW, env=env)
    deadline = time.time() + 600
    state = {"pid": proc.pid, "port": port, "ready": False}
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"llama-server exited early with code {proc.returncode}; see {work_dir}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as r:
                if json.load(r).get("status") == "ok":
                    state["ready"] = True
                    break
        except Exception:
            time.sleep(1)
    stderr_log.close()
    stdout_log.close()
    if not state["ready"]:
        proc.kill()
        raise RuntimeError("server did not become ready in 600s")
    text = (work_dir / "server.stderr.log").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"offloaded (\d+)/(\d+) layers to GPU", text)
    state["layers_offloaded"] = int(match.group(1)) if match else None
    state["layers_total"] = int(match.group(2)) if match else None
    return state


def stop_candidate_server(pid: int):
    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)


# ---------------------------------------------------------------------------
# The ten preregistered case families. Deterministic checks only.
# ---------------------------------------------------------------------------

def case_basic_instruction(base_url):
    checks = []
    prompts = [
        ("用一句话说明什么是采购订单，然后另起一行列出它的两个必要字段。",
         lambda t: ("采购订单" in t) and len([ln for ln in t.strip().splitlines() if ln.strip()]) >= 2),
        ("Answer with exactly two lines. Line 1: the word APPROVED or DENIED. Line 2: one short reason why a purchase order above 10,000 CNY usually needs extra approval.",
         lambda t: len([ln for ln in t.strip().splitlines() if ln.strip()]) == 2
         and ("APPROVED" in t.upper() or "DENIED" in t.upper())),
    ]
    for text, check in prompts:
        reply = chat(base_url, [{"role": "user", "content": text}], max_tokens=256)
        out = reply["choices"][0]["message"].get("content") or ""
        checks.append(bool(check(out)))
    return {"pass": all(checks), "detail": checks}


def case_json_generation(base_url, n=12):
    # DEV-GEN v1.0.1: v1.0.0 embedded an unframed example input ("示例输入: ...")
    # that several models interpreted as a SECOND order to process and emitted
    # a JSON array - a task-ambiguity defect (F19), confirmed by minimal
    # reproduction on R1/S2 (see P2 report). The example is now explicitly
    # marked as format-only. Original v1.0.0 results preserved under their
    # own identity; repaired results are the admission record of note.
    schema_hint = ('只输出一个 JSON 对象，不要输出数组，不要输出其他文字。'
                   '字段: order_id (字符串), amount (数字), approved (布尔值)。'
                   '格式示例（仅供参考，不是要处理的订单）: {"order_id": "PO-YYYY-NNNN", "amount": 0, "approved": true}。'
                   '处理下面这一笔订单：')
    valid, schema_ok = 0, 0
    for i in range(n):
        reply = chat(base_url, [{"role": "user", "content": f"{schema_hint} 订单 PO-2026-{i:04d}，金额 {1000 + 7 * i} 元，已批准。"}], max_tokens=256)
        out = (reply["choices"][0]["message"].get("content") or "").strip()
        match = re.search(r"\{.*\}", out, re.S)
        if match:
            try:
                obj = json.loads(match.group(0))
                if isinstance(obj, dict) and "order_id" in obj and "amount" in obj:
                    valid += 1
                    if isinstance(obj.get("approved"), bool):
                        schema_ok += 1
            except json.JSONDecodeError:
                pass
    return {"pass": valid / n >= 0.9, "valid": valid, "schema_ok": schema_ok, "n": n}


def case_zero_tool_response(base_url, n=6):
    ok = 0
    prompts = ["采购订单的定义是什么？不要调用任何工具，直接回答。", "3 加 4 等于几？直接回答数字即可。"]
    for prompt in prompts:
        for _ in range(n // 2):
            reply = chat(base_url, [{"role": "user", "content": prompt}], tools=TOOLS, max_tokens=256)
            ok += 1 if len(tool_calls(reply)) == 0 and (reply["choices"][0]["message"].get("content") or "").strip() else 0
    return {"pass": ok == n, "ok": ok, "n": n}


def case_single_tool(base_url, n=8):
    ok = 0
    orders = ["PO-2026-0001", "PO-2026-0002"]
    for i in range(n):
        order = orders[i % 2]
        reply = chat(base_url, [
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": f"请查询采购订单 {order} 的信息。"}], tools=TOOLS, max_tokens=256)
        calls = tool_calls(reply)
        name, args = parse_call_args(calls[0]) if calls else (None, None)
        ok += bool(name == "get_purchase_order" and isinstance(args, dict) and args.get("order_id") == order)
    return {"pass": ok / n >= 0.8, "ok": ok, "n": n}


def case_tool_continuation(base_url, n=6):
    ok = 0
    for i in range(n):
        order = "PO-2026-0001" if i % 2 == 0 else "PO-2026-0002"
        messages = [
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": f"查询采购订单 {order} 的供应商，然后告诉我该供应商是否在合格名单。"}]
        reply = chat(base_url, messages, tools=TOOLS, max_tokens=384)
        calls = tool_calls(reply)
        if not calls:
            continue
        name, args = parse_call_args(calls[0])
        if name != "get_purchase_order":
            continue
        result = SIMULATED["get_purchase_order"].get((args or {}).get("order_id", ""), {})
        if not result:
            continue
        append_tool_result(messages, calls, result)
        reply2 = chat(base_url, messages, tools=TOOLS, max_tokens=384)
        calls2 = tool_calls(reply2)
        name2, args2 = parse_call_args(calls2[0]) if calls2 else (None, None)
        supplier = result["supplier_id"]
        good = name2 == "get_supplier" and isinstance(args2, dict) and args2.get("supplier_id") == supplier
        if not good and reply2["choices"][0]["finish_reason"] == "stop":
            text = reply2["choices"][0]["message"].get("content") or ""
            good = supplier in text
        ok += bool(good)
    return {"pass": ok / n >= 0.7, "ok": ok, "n": n}


def case_sequential_tools(base_url, n=6):
    ok = 0
    for i in range(n):
        order = "PO-2026-0001" if i % 2 == 0 else "PO-2026-0002"
        messages = [
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": f"查询采购订单 {order}，然后查询该订单供应商是否合格，最后查询订单中第一个商品的库存。"}]
        po_result = SIMULATED["get_purchase_order"][order]
        good = True
        for step in range(3):
            reply = chat(base_url, messages, tools=TOOLS, max_tokens=320)
            calls = tool_calls(reply)
            if not calls:
                good = False
                break
            name, args = parse_call_args(calls[0])
            args = args if isinstance(args, dict) else {}
            if step == 0:
                good = name == "get_purchase_order" and args.get("order_id") == order
                result = SIMULATED["get_purchase_order"].get(args.get("order_id", ""), po_result)
            elif step == 1:
                good = name == "get_supplier" and args.get("supplier_id") == po_result["supplier_id"]
                result = SIMULATED["get_supplier"].get(args.get("supplier_id", ""), {})
            else:
                first_sku = po_result["items"][0]["sku"]
                good = name == "get_inventory" and args.get("sku") == first_sku
                result = SIMULATED["get_inventory"].get(args.get("sku", ""), {})
            if not good:
                break
            append_tool_result(messages, calls, result)
        ok += bool(good)
    return {"pass": ok / n >= 0.5, "ok": ok, "n": n}


def case_structured_output(base_url):
    schema = {"type": "object", "properties": {"risk": {"type": "string", "enum": ["low", "medium", "high"]},
                                                "reason": {"type": "string"}}, "required": ["risk", "reason"],
              "additionalProperties": False}
    try:
        reply = chat(base_url, [{"role": "user", "content": "供应商 SUP-011 不在合格名单，但其订单金额只有 980 元。给出风险评估。"}],
                     max_tokens=256, response_format={"type": "json_schema",
                                                      "json_schema": {"name": "risk", "strict": True, "schema": schema}})
        out = (reply["choices"][0]["message"].get("content") or "").strip()
        obj = json.loads(out)
        passed = obj.get("risk") in ("low", "medium", "high") and isinstance(obj.get("reason"), str)
    except Exception:
        passed = False
    return {"pass": passed}


def case_invalid_argument_recovery(base_url):
    messages = [
        {"role": "system", "content": SYSTEM_MSG},
        {"role": "user", "content": "查询采购订单 PO-2026-0001 的信息。"}]
    reply = chat(base_url, messages, tools=TOOLS, max_tokens=256)
    calls = tool_calls(reply)
    if not calls:
        return {"pass": False, "detail": "no first call"}
    messages.append({"role": "assistant", "content": None, "tool_calls": calls})
    messages.append({"role": "tool", "tool_call_id": calls[0]["id"],
                     "content": json.dumps({"error": "invalid_argument", "detail": "order_id format must be PO-YYYY-NNNN"}, ensure_ascii=False)})
    reply2 = chat(base_url, messages, tools=TOOLS, max_tokens=320)
    calls2 = tool_calls(reply2)
    name2, args2 = parse_call_args(calls2[0]) if calls2 else (None, None)
    passed = name2 == "get_purchase_order" and isinstance(args2, dict) and args2.get("order_id") == "PO-2026-0001"
    return {"pass": passed, "second_call": {"name": name2, "args": args2}}


def case_context_handling(base_url):
    filler = "库存记录备注：" + "、".join(f"SKU-{9000 + i} 在 W-华北 仓库，数量 {i + 3}" for i in range(120))
    question = "根据上文库存记录，SKU-9119 的数量是多少？只回答数字。"
    reply = chat(base_url, [{"role": "user", "content": filler + "\n\n" + question}], max_tokens=64)
    out = (reply["choices"][0]["message"].get("content") or "")
    return {"pass": "122" in out}  # SKU-9119 -> i=119 -> qty 122


def case_stop_conditions(base_url):
    reply = chat(base_url, [{"role": "user", "content": "请从 1 数到 10000，每行一个数字。"}], max_tokens=96)
    finish = reply["choices"][0].get("finish_reason")
    completed = reply.get("usage", {}).get("completion_tokens", 0)
    return {"pass": finish in ("length", "stop") and 0 < completed <= 96,
            "finish_reason": finish, "completion_tokens": completed}


CASES = [
    ("basic_instruction", case_basic_instruction),
    ("json_generation", case_json_generation),
    ("zero_tool_response", case_zero_tool_response),
    ("single_tool_invocation", case_single_tool),
    ("tool_result_continuation", case_tool_continuation),
    ("multiple_sequential_tools", case_sequential_tools),
    ("structured_output", case_structured_output),
    ("invalid_argument_recovery", case_invalid_argument_recovery),
    ("context_handling", case_context_handling),
    ("stop_conditions", case_stop_conditions),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, help="S1/S2/S3a/S3b/.../R1/R2 label")
    parser.add_argument("--model", required=True, help="path to the GGUF file")
    parser.add_argument("--alias", required=True)
    parser.add_argument("--backend", default="vulkan", choices=["cpu", "vulkan", "rocm"])
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--output", required=True)
    parser.add_argument("--skip-cases", default="", help="comma-separated case ids to skip (recorded as SKIPPED)")
    args = parser.parse_args()

    model_path = pathlib.Path(args.model)
    model_path = model_path if model_path.is_absolute() else (ROOT / args.model)
    if not model_path.exists():
        print(f"model not found: {model_path}")
        return 2
    # Evidence must not carry local paths (AGENTS.md redaction rule): record
    # the repo-relative path only.
    try:
        model_path_rel = model_path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        model_path_rel = "<outside-repository>"
    work_dir = ROOT / ".runtime" / "ijsdk_admission" / args.candidate
    work_dir.mkdir(parents=True, exist_ok=True)

    model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
    state = start_candidate_server(model_path, args.alias, args.backend, args.port, work_dir)
    results = {"schema_version": 1, "candidate": args.candidate, "alias": args.alias,
               "model_path": model_path_rel, "model_sha256": model_sha,
               "backend": args.backend, "started_utc": utc(),
               "gpu": {"layers_offloaded": state.get("layers_offloaded"), "layers_total": state.get("layers_total")},
               "cases": {}}
    skip = {s.strip() for s in args.skip_cases.split(",") if s.strip()}
    base_url = f"http://127.0.0.1:{args.port}"
    dev_score, scored = 0.0, 0
    try:
        for name, fn in CASES:
            if name in skip:
                results["cases"][name] = {"status": "SKIPPED"}
                continue
            try:
                detail = fn(base_url)
                detail["status"] = "PASS" if detail.get("pass") else "FAIL"
                results["cases"][name] = detail
                scored += 1
                dev_score += 1.0 if detail.get("pass") else 0.0
            except Exception as exc:  # record and continue
                results["cases"][name] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
                scored += 1
    finally:
        stop_candidate_server(state["pid"])
        results["finished_utc"] = utc()
        results["token_usage"] = dict(USAGE_TOTALS)
        results["dev_score"] = {"passed_cases": dev_score, "scored_cases": scored,
                                "rate": round(dev_score / scored, 4) if scored else None}
        out = ROOT / args.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {args.output} dev_score={dev_score}/{scored}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
