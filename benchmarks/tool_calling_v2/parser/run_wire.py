"""Run versioned fixed native outputs through a managed llama-server."""

from __future__ import annotations

import argparse
import collections
import hashlib
import http.client
import json
import subprocess
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from benchmarks.tool_calling.runner import run_benchmark as baseline
from benchmarks.tool_calling.runner.run_parser_fixtures import assistant_prefix, eos_token_id
from model_gateway.errors import GatewayError
from model_gateway.openai_protocol import decode_completion
from model_gateway.streaming import StreamAssembler

from .assessment import assess, validators_for
from .fixtures import build


def fixture_request(alias, tools, fixture, eos, stream):
    req = {
        "model": alias,
        "messages": [{"role": "user", "content": "Continue the assistant response."},
                     assistant_prefix(fixture["native_output"])],
        "tools": tools, "tool_choice": "auto", "parallel_tool_calls": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "temperature": 0, "max_tokens": 1, "logit_bias": {str(eos): 1000},
        "stream": stream, "echo": True,
    }
    if stream:
        req["stream_options"] = {"include_usage": True}
        # llama-server's documented native probability option records the
        # sampled token even when Chat Completions logprobs is unavailable.
        req["n_probs"] = 1
    else:
        req.update(logprobs=True, top_logprobs=1)
    return req


def post(base_url, data):
    request = urllib.request.Request(
        base_url + "/v1/chat/completions",
        data=json.dumps(data, ensure_ascii=True).encode("ascii"),
        method="POST", headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read(512 * 1024 + 1)
    except urllib.error.HTTPError as error:
        return error.code, error.read(512 * 1024 + 1)


def split_sse(raw):
    """Return complete event data fields while refusing a malformed framing."""
    if not raw.endswith((b"\n\n", b"\r\n\r\n")):
        raise ValueError("SSE terminated mid-event")
    events = []
    for frame in raw.replace(b"\r\n", b"\n").split(b"\n\n"):
        if frame:
            parts = frame.splitlines()
            if len(parts) != 1 or not parts[0].startswith(b"data:"):
                raise ValueError("unexpected SSE frame")
            events.append(parts[0].removeprefix(b"data:").removeprefix(b" "))
    return events


def raw_stream(events):
    """Observe arguments without coercing their nested JSON."""
    calls = collections.defaultdict(lambda: {"function": {"name": "", "arguments": ""}})
    message = {"role": "assistant", "content": "", "reasoning_content": ""}
    logprobs = []
    finish_reason = usage = None
    for event in events:
        if event == b"[DONE]":
            continue
        chunk = json.loads(event)
        if chunk.get("error"):
            return {"error": chunk["error"]}
        usage = chunk.get("usage") or usage
        for choice in chunk.get("choices") or []:
            finish_reason = choice.get("finish_reason") or finish_reason
            delta = choice.get("delta") or {}
            for key in ("content", "reasoning_content"):
                message[key] += delta.get(key) or ""
            logprobs.extend((choice.get("logprobs") or {}).get("content") or [])
            for part in delta.get("tool_calls") or []:
                observed = calls[part["index"]]
                for key in ("id", "type"):
                    if part.get(key) is not None:
                        observed[key] = part[key]
                for key in ("name", "arguments"):
                    observed["function"][key] += (part.get("function") or {}).get(key) or ""
    message["tool_calls"] = [calls[index] for index in sorted(calls)]
    return {"choices": [{"message": message, "finish_reason": finish_reason,
                         "logprobs": {"content": logprobs}}], "usage": usage}


def eos_only(reply, eos):
    return (
        (reply.get("usage") or {}).get("completion_tokens") == 1
        and [(item.get("id"), item.get("bytes")) for item in
             (reply["choices"][0].get("logprobs") or {}).get("content", [])] == [(eos, [])]
    )


def inspect_response(status, raw, stream, eos):
    label = "stream" if stream else "complete"
    observation = {"http_status": status, "raw_response": raw.decode("utf-8")}
    if status == 200:
        events = split_sse(raw) if stream else None
        reply = raw_stream(events) if stream else json.loads(raw)
    else:
        events = None
        reply = json.loads(raw)
    error = reply.get("error")
    if isinstance(error, dict) and error.get("message") == (
            "The model produced output that does not match the expected peg-native format"):
        observation.update(parser_rejected=True, wire="PASS")
        return observation
    if error or status != 200:
        observation.update(blocked=f"{label}: response is neither completion nor native parser rejection", wire="BLOCKED")
        return observation
    observation["message"] = reply["choices"][0]["message"]
    observation["eos_only"] = eos_only(reply, eos)
    try:
        if stream:
            assembler = StreamAssembler()
            for event in events:
                assembler.feed(event)
            assembler.finish()
        else:
            decode_completion(raw)
    except GatewayError as error:
        observation.update(wire="FAIL", wire_error=str(error))
    else:
        observation["wire"] = "PASS"
    return observation


def trial(base_url, alias, tools, fixture, eos, validators):
    result = {"id": fixture["id"]}
    try:
        for stream, name in ((False, "complete"), (True, "stream")):
            req = fixture_request(alias, tools, fixture, eos, stream)
            result[name] = inspect_response(*post(base_url, req), stream, eos)
    except (ValueError, KeyError, OSError, http.client.HTTPException) as error:
        result["status"] = "BLOCKED"
        result["failure"] = str(error)
        return result
    full, streamed = result["complete"], result["stream"]
    if any(item.get("blocked") or not (item.get("parser_rejected") or item.get("eos_only"))
           for item in (full, streamed)):
        result["status"] = "BLOCKED"
        result["failure"] = "Could not verify the fixed-input EOS or native rejection"
        return result
    row = {"parser_rejected": full.get("parser_rejected"), "message": full.get("message"),
           "stream_rejected": streamed.get("parser_rejected"), "stream_message": streamed.get("message")}
    result.update(assess(fixture, row, validators))
    result["wire"] = "PASS" if all(item["wire"] == "PASS" for item in (full, streamed)) else "FAIL"
    result["execution_safety"] = "NOT_RUN"
    result["status"] = "FAIL" if "FAIL" in (
        result["native"], result["wire"], result["strict_arguments"], result["parser_stream_parity"]
    ) else "PASS"
    return result


def candidate_identity(base_url, alias, binary, patches, pid, launch_path=None):
    """Verify a separately built candidate without altering the baseline."""
    address = urlsplit(base_url)
    if address.scheme != "http" or address.hostname != "127.0.0.1" or base_url != f"http://127.0.0.1:{address.port}":
        raise ValueError("Candidate endpoint must be an explicit IPv4 loopback URL")
    if pid <= 0:
        raise ValueError("Candidate PID must be positive")
    binary = binary.resolve(strict=True)
    command = (
        f"$owners = @(Get-NetTCPConnection -LocalPort {address.port} -State Listen -ErrorAction Stop"
        " | Select-Object -ExpandProperty OwningProcess -Unique); "
        "$owners; "
        f"(Get-Process -Id {pid} -ErrorAction Stop).Path"
    )
    listener = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command], check=True,
        capture_output=True, text=True, timeout=30,
    ).stdout.strip().splitlines()
    if len(listener) != 2 or listener[0] != str(pid) or Path(listener[1]) != binary:
        raise ValueError("Endpoint does not belong to the supplied candidate process")
    device_listing = subprocess.run([str(binary), "--list-devices"], capture_output=True, text=True,
                                    check=True, timeout=30).stdout.strip()
    backend = "cpu"
    gpu = None
    compiled_backend = "CPU-only static"
    launch = None
    if launch_path:
        launch = baseline.read_json(launch_path)
        backend = launch["backend"]
        device = {"vulkan": "Vulkan0", "rocm": "ROCm0"}.get(backend)
        if (
            not device or launch["pid"] != pid or launch["owns_port"] is not True
            or launch["status"] != "PASS" or launch["base_url"] != base_url
            or not launch["layers_offloaded"]
            or f"{device}: AMD Radeon(TM) 8060S Graphics" not in device_listing
            or f"using device {device} (AMD Radeon(TM) 8060S Graphics)" not in launch["gpu_line"]
        ):
            raise ValueError("Candidate GPU identity, offload or launch record differs")
        compiled_backend = "Dynamic b12359 GPU plugin with patched candidate core"
        gpu = {"device": device, "name": "AMD Radeon(TM) 8060S Graphics", "architecture": "gfx1151"}
    elif " ".join(device_listing.split()) not in ("Available devices:", "Available devices: (none)"):
        raise ValueError("GPU candidates require explicit verified launch evidence")
    with urllib.request.urlopen(base_url + "/props", timeout=10) as response:
        props = json.load(response)
    expected = baseline.read_json(baseline.ROOT / "configs/llama_cpp/engine.json")
    model_path = Path(props["model_path"])
    manifest = baseline.read_json(baseline.ROOT / "models/model_manifest.json")
    model_candidates = [
        (source, item) for source in manifest["models"] for item in source["files"]
        if baseline.ROOT / source["local_dir"] / item["path"] == model_path
    ]
    if len(model_candidates) != 1 or props["model_alias"] != alias:
        raise ValueError("Candidate model does not match the pinned manifest and alias")
    source, item = model_candidates[0]
    model_sha = baseline.sha256_of(model_path)
    if props["build_info"] != f"{expected['build_tag']}-{expected['build_commit']}" or model_sha != item["sha256"]:
        raise ValueError("Candidate upstream commit or ModelScope model digest differs")
    runtime_hashes = {path.name: baseline.sha256_of(path) for path in sorted(binary.parent.glob("*.dll"))} if gpu else {}
    if gpu:
        plugin = {"vulkan": "ggml-vulkan.dll", "rocm": "ggml-hip.dll"}[backend]
        official_plugin = baseline.ROOT / "runtime/llama-cpp" / backend / plugin
        if runtime_hashes.get(plugin) != baseline.sha256_of(official_plugin):
            raise ValueError("Candidate GPU plugin differs from the pinned release installation")
    return (
        {"configuration": "P4-local-terminal-integrity", "upstream_commit": expected["build_commit"],
         "exe_sha256": baseline.sha256_of(binary), "patch_sha256": [baseline.sha256_of(patch) for patch in patches],
         "compiled_backend": compiled_backend, "runtime_dll_sha256": runtime_hashes},
        {"backend": backend, "gpu": gpu, "model_alias": alias, "model_sha256": model_sha,
         "layers_offloaded": launch["layers_offloaded"] if launch else 0,
         "modelscope_id": source["model_id"], "modelscope_revision": source["revision"],
         "chat_template_sha256": hashlib.sha256(props["chat_template"].encode("utf-8")).hexdigest()},
        {"pid": pid, **({"started_utc": launch["started_utc"]} if launch else {})},
    )


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--base-url", default="http://127.0.0.1:8080")
    cli.add_argument("--alias", default="minicpm5-2b")
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--resume", action="store_true")
    cli.add_argument("--candidate-server", type=Path)
    cli.add_argument("--candidate-patch", type=Path, action="append", default=[])
    cli.add_argument("--candidate-pid", type=int)
    cli.add_argument("--candidate-launch", type=Path)
    cli.add_argument("--lexical", action="store_true")
    args = cli.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = build(args.lexical)
    candidate = (args.candidate_server, args.candidate_patch, args.candidate_pid)
    if any(candidate) or args.candidate_launch:
        if not all(candidate):
            cli.error("Candidate testing requires the explicit binary, patch and PID")
        engine, server, session = candidate_identity(args.base_url, args.alias, *candidate, args.candidate_launch)
    else:
        engine, server, session = baseline.server_identity(args.base_url, args.alias)
    fixtures_sha256 = hashlib.sha256(json.dumps(data, ensure_ascii=True, sort_keys=True).encode("ascii")).hexdigest()
    eos = eos_token_id(args.base_url)
    metadata = {
        "fixture_version": data["version"], "fixture_sha256": fixtures_sha256,
        "engine": engine, "server": server, "git": baseline.git_state(),
        "runner_sha256": baseline.sha256_of(Path(__file__)),
        "eos_token_id": eos, "evidence_type": "fixed-output native and wire fixtures; no business execution",
    }
    run_path = args.output / "run.json"
    rows_path = args.output / "results.jsonl"
    with baseline.output_lock(args.output):
        if run_path.exists():
            if not args.resume:
                cli.error("Output exists. Pass --resume or choose a new directory.")
            run = baseline.read_json(run_path)
            if any(run[key] != value for key, value in metadata.items()):
                cli.error("Resume identity changed")
        else:
            if rows_path.exists():
                cli.error("Results exist without metadata")
            run = {**metadata, "run_id": "ij06-wire-" + uuid.uuid4().hex, "started_utc": baseline.utc_now(),
                   "sessions": []}
        rows = {}
        if rows_path.exists():
            for line in rows_path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                if row["id"] in rows or row["run_id"] != run["run_id"]:
                    cli.error("Invalid checkpoint")
                rows[row["id"]] = row
        if set(rows) - {fixture["id"] for fixture in data["fixtures"]}:
            cli.error("Checkpoint contains unknown fixture IDs")
        if session not in run["sessions"]:
            run["sessions"].append(session)
        baseline.write_json(run_path, run)
        validators = validators_for(data["tools"])
        with rows_path.open("a", encoding="utf-8", newline="\n") as log:
            for fixture in data["fixtures"]:
                if fixture["id"] in rows:
                    continue
                row = trial(args.base_url, args.alias, data["tools"], fixture, eos, validators)
                row["run_id"] = run["run_id"]
                if row["status"] == "BLOCKED":
                    baseline.write_json(args.output / "blocked.json", row)
                    print(row["id"], row["status"], row.get("failure"))
                    return 2
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
                log.flush()
                rows[row["id"]] = row
        summary = {"run_id": run["run_id"], "finished_utc": baseline.utc_now()}
        for dimension in ("status", "native", "wire", "strict_arguments", "parser_stream_parity", "execution_safety"):
            summary[dimension] = dict(collections.Counter(row[dimension] for row in rows.values()))
        baseline.write_json(args.output / "summary.json", summary)
        print(json.dumps(summary))
        return 1 if summary["status"].get("FAIL") else 0


if __name__ == "__main__":
    raise SystemExit(main())
