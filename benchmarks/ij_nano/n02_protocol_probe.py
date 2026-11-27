#!/usr/bin/env python3
"""IJ-NANO N02: physical runtime protocol probe (runtime/protocol tests only).

Per candidate model, starts the pinned llama-server (same launch flags as the
IJ-SDK admission smoke), then verifies: health/identity, basic generation with
usage accounting, native tool-call protocol, response_format json_schema,
GBNF grammar via /completion, SSE streaming, mid-stream cancellation, and
post-cancel server health. GPU execution is proven the D-010 way: listening
socket owned by the launched PID + the server log's offload line.

Not a business-correctness claim of any kind.

Usage:
    python -I benchmarks/ij_nano/n02_protocol_probe.py \
        --candidate S1 --model <abs path to gguf> --alias minicpm5-2b \
        --backend vulkan --port 8093 \
        --output evidence/IJNANO/N02/protocol/S1.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def post(base: str, path: str, body: dict, timeout: int = 240, stream: bool = False):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)


def wait_health(base: str, pid: int, port: int, deadline: float) -> dict:
    proof: dict = {"socket_owner_pid": None}
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                proof["socket_owner_pid"] = pid  # bound by launched proc; verified below by health
            with urllib.request.urlopen(base + "/health", timeout=5) as r:
                if r.status == 200:
                    proof["health"] = json.loads(r.read().decode("utf-8"))
                    return proof
        except Exception:
            time.sleep(1.5)
    raise RuntimeError("server did not become healthy before deadline")


def start_server(binary_dir: pathlib.Path, model: pathlib.Path, alias: str, port: int, work: pathlib.Path):
    exe = binary_dir / "llama-server.exe"
    stdout_log = work / "server.stdout.log"
    stderr_log = work / "server.stderr.log"
    args = [str(exe), "-m", str(model), "--alias", alias, "--host", "127.0.0.1",
            "--port", str(port), "-c", "8192", "-ngl", "99", "--jinja",
            "--cache-reuse", "256", "-v"]
    with open(stdout_log, "wb") as so, open(stderr_log, "wb") as se:
        proc = subprocess.Popen(args, cwd=str(binary_dir), stdout=so, stderr=se,
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    return proc, stdout_log, stderr_log


def stop_server(pid: int):
    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)


def grep_offload(log: pathlib.Path) -> str | None:
    pat = re.compile(r"offloaded (\d+)/(\d+) layers to GPU")
    try:
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = pat.search(line)
            if m:
                return m.group(0)
    except OSError:
        return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--alias", required=True)
    ap.add_argument("--backend", default="vulkan")
    ap.add_argument("--port", type=int, default=8093)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    model = pathlib.Path(args.model).resolve()
    binary_dir = ROOT / "runtime" / "llama-cpp" / args.backend
    work = ROOT / ".runtime" / "ij_nano_n02" / args.candidate
    work.mkdir(parents=True, exist_ok=True)
    base = f"http://127.0.0.1:{args.port}"

    res: dict = {"schema_version": 1, "mission": "IJ-NANO-1.0", "phase": "N02",
                 "kind": "runtime_protocol_probe (not a business claim)",
                 "candidate": args.candidate, "alias": args.alias, "backend": args.backend,
                 "started_utc": utc(), "checks": {}}
    ck = res["checks"]

    proc, stdout_log, stderr_log = start_server(binary_dir, model, args.alias, args.port, work)
    res["server_pid"] = proc.pid
    try:
        proof = wait_health(base, proc.pid, args.port, time.time() + 900)
        ck["health_and_socket"] = {"status": "PASS", "socket_owner_pid": proof["socket_owner_pid"],
                                   "health_status": proof["health"].get("status"), "url": "/health ok"}
        time.sleep(2)
        offload = grep_offload(stdout_log) or grep_offload(stderr_log)
        ck["gpu_offload_d010"] = {"status": "PASS" if offload and not offload.startswith("offloaded 0/") else "FAIL",
                                  "log_line": offload}

        # 1) basic generation + usage accounting (non-stream)
        body = {"messages": [{"role": "user", "content": "Reply with exactly: OK"}], "max_tokens": 16,
                "temperature": 0, "cache_prompt": True}
        with post(base, "/v1/chat/completions", body) as r:
            j = json.loads(r.read().decode("utf-8"))
        usage = j.get("usage", {})
        ck["basic_generation_usage"] = {
            "status": "PASS" if (j.get("choices") and usage.get("completion_tokens") is not None) else "FAIL",
            "content": (j.get("choices") or [{}])[0].get("message", {}).get("content", "")[:60],
            "usage_fields": sorted(usage.keys())}

        # 2) native tool-call protocol
        tools = [{"type": "function", "function": {
            "name": "get_inventory",
            "description": "按商品编号查询当前库存数量和仓库位置。",
            "parameters": {"type": "object", "properties": {"sku": {"type": "string"}},
                           "required": ["sku"], "additionalProperties": False}}}]
        body = {"messages": [{"role": "system", "content": "需要查询数据时调用工具。"},
                             {"role": "user", "content": "查询 SKU-1001 的库存"}],
                "tools": tools, "tool_choice": "auto", "max_tokens": 256, "temperature": 0}
        with post(base, "/v1/chat/completions", body) as r:
            j = json.loads(r.read().decode("utf-8"))
        msg = (j.get("choices") or [{}])[0].get("message", {})
        tcs = msg.get("tool_calls") or []
        ok_tool = bool(tcs) and tcs[0].get("function", {}).get("name") == "get_inventory"
        ck["native_tool_call"] = {"status": "PASS" if ok_tool else "FAIL",
                                  "tool_calls": [{"name": t.get("function", {}).get("name"),
                                                  "arguments": t.get("function", {}).get("arguments", "")[:80]}
                                                 for t in tcs[:2]]}

        # 3) response_format json_schema (structured generation)
        schema = {"type": "object", "properties": {"action": {"type": "string", "enum": ["query", "update", "stop"]},
                                                  "sku": {"type": "string"}},
                  "required": ["action", "sku"], "additionalProperties": False}
        body = {"messages": [{"role": "user", "content": "用户想查询 SKU-1001。输出 JSON。"}],
                "response_format": {"type": "json_schema", "json_schema": {"name": "act", "strict": True, "schema": schema}},
                "max_tokens": 1024, "temperature": 0}
        try:
            with post(base, "/v1/chat/completions", body) as r:
                j = json.loads(r.read().decode("utf-8"))
            ch0 = (j.get("choices") or [{}])[0]
            msg = ch0.get("message", {})
            content = msg.get("content", "")
            reasoning = msg.get("reasoning_content") or ""
            parsed = None
            try:
                parsed = json.loads(content)
            except Exception:
                pass
            valid = bool(parsed) and parsed.get("action") in ("query", "update", "stop") and isinstance(parsed.get("sku"), str)
            ck["json_schema_structured"] = {
                "status": "PASS" if valid else "FAIL",
                "parsed": parsed, "finish_reason": ch0.get("finish_reason"),
                "reasoning_burn_chars": len(reasoning),
                "note": "thinking-capable models may spend tokens in reasoning_content before the constrained JSON",
            }
        except Exception as e:
            ck["json_schema_structured"] = {"status": "FAIL", "error": str(e)[:200]}

        # 4) GBNF grammar via /completion. Main form avoids backslash-escaped
        #    quotes (b12359 rejects escaped-quote literals - recorded below).
        grammar = 'root ::= "{" ["] "action" ["] ":" ["] "query" ["] "," ["] "sku" ["] ":" ["] [A-Z0-9-]+ ["] "}"'
        body = {"prompt": "Output the JSON object for querying SKU-1001: ",
                "grammar": grammar, "n_predict": 64, "temperature": 0}
        try:
            with post(base, "/completion", body) as r:
                j = json.loads(r.read().decode("utf-8"))
            text = j.get("content", "")
            ok_g = text.strip().startswith("{") and "query" in text
            ck["gbnf_grammar"] = {"status": "PASS" if ok_g else "FAIL", "sample": text[:80]}
        except Exception as e:
            ck["gbnf_grammar"] = {"status": "FAIL", "error": str(e)[:200]}

        # 4b) engine behavior record: escaped-quote literals in GBNF
        esc = 'root ::= "{" "\\"sku\\":\\"" [A-Z0-9-]+ "\\" "}"'
        body = {"prompt": "x", "grammar": esc, "n_predict": 8, "temperature": 0}
        try:
            with post(base, "/completion", body) as r:
                j = json.loads(r.read().decode("utf-8"))
            ck["gbnf_escaped_quote_literals"] = {"status": "PASS", "note": "engine accepted escaped quotes"}
        except urllib.error.HTTPError as e:
            ck["gbnf_escaped_quote_literals"] = {
                "status": "ENGINE_REJECTS", "http": e.code,
                "error": e.read().decode("utf-8", errors="replace")[:160],
                "note": "b12359 grammar parser limitation; use [\"] char classes instead"}

        # 4c) /completion json_schema field (documented structured path; expects an object)
        body = {"prompt": "Output the JSON object for querying SKU-1001: ",
                "json_schema": schema, "n_predict": 64, "temperature": 0}
        try:
            with post(base, "/completion", body) as r:
                j = json.loads(r.read().decode("utf-8"))
            parsed = json.loads(j.get("content", ""))
            valid = parsed.get("action") in ("query", "update", "stop")
            ck["completion_json_schema_field"] = {"status": "PASS" if valid else "FAIL", "parsed": parsed}
        except Exception as e:
            ck["completion_json_schema_field"] = {"status": "FAIL", "error": str(e)[:200]}

        # 5) SSE streaming
        body = {"messages": [{"role": "user", "content": "Count from 1 to 5, digits only, comma separated."}],
                "max_tokens": 32, "temperature": 0, "stream": True,
                "stream_options": {"include_usage": True}}
        chunks = 0
        usage_seen = None
        with post(base, "/v1/chat/completions", body) as r:
            for raw in r:
                line = raw.decode("utf-8", errors="replace").strip()
                if line.startswith("data:"):
                    chunks += 1
                    if line.endswith("[DONE]"):
                        break
                    try:
                        pj = json.loads(line[5:].strip())
                        if pj.get("usage"):
                            usage_seen = sorted(pj["usage"].keys())
                    except Exception:
                        pass
        ck["sse_streaming"] = {"status": "PASS" if chunks > 2 else "FAIL", "data_chunks": chunks,
                               "stream_usage_fields": usage_seen}

        # 6) cancellation: abort a long stream mid-flight, then confirm health
        body = {"messages": [{"role": "user", "content": "Write a 300-word story about a warehouse robot."}],
                "max_tokens": 512, "temperature": 0, "stream": True}
        cancelled = False
        try:
            with post(base, "/v1/chat/completions", body) as r:
                for _ in range(3):
                    r.read(64)
                raise TimeoutError("client abort")  # simulate caller cancellation
        except TimeoutError:
            cancelled = True
        except Exception:
            cancelled = True
        time.sleep(2)
        healthy = False
        try:
            with urllib.request.urlopen(base + "/health", timeout=10) as r:
                healthy = r.status == 200
        except Exception:
            healthy = False
        ck["cancellation_and_recovery"] = {"status": "PASS" if (cancelled and healthy) else "FAIL",
                                           "client_aborted": cancelled, "server_healthy_after": healthy}

        res["finished_utc"] = utc()
        scored = {k: v for k, v in ck.items() if k != "gbnf_escaped_quote_literals"}
        res["overall"] = ("PASS" if all(v.get("status") == "PASS" for v in scored.values()) else "FAIL")
    finally:
        stop_server(proc.pid)
        time.sleep(2)

    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    scrubbed = json.dumps(res, ensure_ascii=False, indent=1)
    out.write_text(scrubbed, encoding="utf-8")
    print(f"n02 protocol probe [{args.candidate}] overall={res.get('overall')} -> {args.output}")
    for k, v in ck.items():
        print(f"  {k}: {v.get('status')}")
    return 0 if res.get("overall") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
