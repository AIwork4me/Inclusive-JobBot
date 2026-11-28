"""Exercise a pinned local Q8_0 candidate with a synthetic, read-only task."""

import argparse
from contextlib import contextmanager
from functools import partial
import json
from pathlib import Path
import subprocess
import time
from urllib.error import URLError
from uuid import uuid4

from benchmarks.root_cause.generation_capture import CaptureClient, CaptureError, check_gateway, protocol_reply
from benchmarks.root_cause.historical_replay import ROOT, engine_runtime, gpu_server, legacy
from scripts.tools.verify_ij06_evidence import verify_gpu


GATES = (
    "artifact_identity", "load", "cpu_reference", "gpu_execution", "ordinary_chat", "native_call",
    "result_roundtrip", "dependent_call", "stream_parity", "schema_and_invalid_choice",
)
TOOLS = [
    {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "additionalProperties": False, "required": [key],
        "properties": {key: {"type": "string"}},
    }}}
    for name, description, key in (
        ("lookup_account", "Find the internal account ID for a company name.", "company"),
        ("lookup_balance", "Return the balance in CNY for an internal account ID.", "account_id"),
    )
]
FIXTURES = {
    "lookup_account": ({"company": "Orchid Works"}, {"account_id": "AC-18405"}),
    "lookup_balance": ({"account_id": "AC-18405"}, {"currency": "CNY", "balance": 1742}),
}
MODEL_ROOTS = {"A": "models/MiniCPM5-2B-GGUF", "H": ".tools/models/Qwen3-8B-GGUF"}


@contextmanager
def cpu_server(binary, model, port, log, alias):
    proc = subprocess.Popen(
        [str(binary), "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
         "--alias", alias, "--ctx-size", "8192", "--parallel", "1", "--device", "none",
         "--n-gpu-layers", "0", "--jinja", "--offline", "--no-webui", "--log-file", str(log)],
        cwd=binary.parent, creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    client = CaptureClient(port)
    try:
        for _ in range(90):
            if proc.poll() is not None:
                raise CaptureError(f"CPU reference exited with code {proc.returncode}")
            try:
                with client.opener.open(client.base_url + "/props", timeout=3) as reply:
                    props = json.load(reply)
            except URLError:
                time.sleep(1)
                continue
            if props["model_alias"] != alias or Path(props["model_path"]).resolve() != model:
                raise CaptureError("CPU reference identity mismatch")
            owner = subprocess.check_output(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 f"(Get-NetTCPConnection -LocalPort {port} -State Listen).OwningProcess | Select-Object -Unique"],
                text=True, timeout=20,
            ).strip()
            if owner != str(proc.pid):
                raise CaptureError("CPU listener is not owned by the launched process")
            yield client, props["build_info"]
            return
        raise CaptureError("CPU reference did not become ready")
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=15)


def request(client, alias, messages, wire, *, disable_thinking, **kwargs):
    body = {"model": alias, "messages": messages, "temperature": 0, "seed": 7107, "max_tokens": 1024, **kwargs}
    if disable_thinking:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    started = time.perf_counter()
    status, media, data = client.post("/v1/chat/completions", body)
    wire.append({"request": body, "status": status, "response_type": media,
                 "response": data.decode("utf-8"), "wall_ms": round((time.perf_counter() - started) * 1000)})
    return status, data


def chat_ok(send):
    status, raw = send([
        {"role": "user", "content": "Reply with exactly this text: RAD-7107"},
    ], max_tokens=128)
    return status == 200 and json.loads(raw)["choices"][0]["message"].get("content", "").strip() == "RAD-7107"


def tool_signature(reply):
    choice = reply["choices"][0]
    return tuple((call["function"]["name"], json.loads(call["function"]["arguments"]))
                 for call in choice["message"].get("tool_calls", []))


def test_gpu(send, report):
    gates = report["gates"]

    def mark(name, passed):
        gates[name] = "PASS" if passed else "FAIL"

    mark("ordinary_chat", chat_ok(send))
    messages = [{"role": "user", "content": "Find the balance for Orchid Works. Report the account ID and the CNY balance."}]
    kwargs = {"tools": TOOLS, "tool_choice": "auto", "parallel_tool_calls": False}
    first_calls = ()
    executed = []
    for turn in range(3):
        gate = ("native_call", "dependent_call", "result_roundtrip")[turn]
        status, data = send(messages, **kwargs)
        if status != 200 or check_gateway(data, False)["status"] != "PASS":
            mark(gate, False)
            break
        reply = protocol_reply(data, False)
        assistant = reply["choices"][0]["message"]
        signature = tool_signature(reply)
        if turn == 0:
            first_calls = signature
        if not signature:
            content = assistant.get("content") or ""
            mark(gate, turn == 2 and "AC-18405" in content and "1742" in content.replace(",", ""))
            break
        target = ("lookup_account", "lookup_balance")[turn] if turn < 2 else None
        tool = signature[0][0]
        valid = target is not None and len(signature) == 1 and tool == target and signature[0][1] == FIXTURES[tool][0]
        mark(gate, valid)
        if not valid:
            break
        executed.append(tool)
        # The simulator returns data only for the model's validated proposal.
        messages = [*messages, assistant, {"role": "tool", "tool_call_id": assistant["tool_calls"][0]["id"],
                                           "content": json.dumps(FIXTURES[tool][1])}]
    report["executed_read_only_tools"] = executed

    status, raw = send(messages[:1], **kwargs, stream=True, stream_options={"include_usage": True})
    mark("stream_parity", bool(first_calls) and status == 200 and check_gateway(raw, True)["status"] == "PASS"
         and tool_signature(protocol_reply(raw, True)) == first_calls)

    schema = {"type": "object", "properties": {"status": {"const": "ready"}},
              "required": ["status"], "additionalProperties": False}
    status, raw = send([{"role": "user", "content": "Return a status object with status ready."}],
                       response_format={"type": "json_schema", "json_schema": {
                           "name": "readiness", "strict": True, "schema": schema,
                       }})
    parsed = None
    if status == 200:
        try:
            parsed = json.loads(json.loads(raw)["choices"][0]["message"].get("content") or "")
        except ValueError:
            pass
    invalid, _ = send(messages[:1], tools=TOOLS,
                      tool_choice={"type": "function", "function": {"name": "undefined_lookup"}})
    report["schema_probe"] = {"schema_exact": parsed == {"status": "ready"}, "invalid_choice_http_status": invalid}
    mark("schema_and_invalid_choice", parsed == {"status": "ready"} and 400 <= invalid < 500)


def admit(candidate, output, port, engine_directory, disable_thinking, *, model=None, cpu_binary=None):
    if candidate == "J":
        pin = json.loads((ROOT / "atlas/benchmarks/pc_s_qwen3_14b.json").read_bytes())
        if model is None or cpu_binary is None or not model.is_file() or not cpu_binary.is_file():
            raise ValueError("the larger reference needs an explicit verified GGUF and CPU executable")
        if model.name != pin["filename"] or model.stat().st_size != pin["expected_bytes"]:
            raise ValueError("the larger reference GGUF differs from its pinned filename or size")
        info = {"official_model_id": pin["model"], "runtime_asset": {
            "repo": pin["artifact_repository"], "revision": pin["revision"], "filename": pin["filename"],
            "expected_sha256": pin["expected_sha256"], "size": pin["expected_bytes"],
        }}
        model = model.resolve()
    else:
        if model is not None or cpu_binary is not None:
            raise ValueError("path overrides are reserved for the larger reference")
        info = json.loads((ROOT / f"evidence/IJ07/model_identity/{candidate}.json").read_bytes())
        asset = info["runtime_asset"]
        directory = MODEL_ROOTS.get(candidate, ".runtime/ij07-candidates/" + asset["repo"].replace("/", "__"))
        model = (ROOT / directory / asset["filename"]).resolve()
        cpu_binary = ROOT / "runtime/llama-cpp/cpu/llama-server.exe"
    asset = info["runtime_asset"]
    output.mkdir(parents=True, exist_ok=False)
    alias = "ij07-candidate-" + candidate.lower()
    report = {
        "run_id": "ij07-admission-" + uuid4().hex, "candidate": candidate, "git": legacy.git_state(),
        "started_utc": legacy.utc_now(), "model_id": info["official_model_id"], "asset": asset,
        "gates": dict.fromkeys(GATES, "NOT_RUN"), "wire": [], "requested_disable_thinking": disable_thinking,
    }
    def send_for(client):
        return partial(request, client, alias, wire=report["wire"], disable_thinking=disable_thinking)

    try:
        model_hash = legacy.sha256_of(model)
        report["gates"]["artifact_identity"] = "PASS" if model_hash == asset["expected_sha256"] else "FAIL"
        if candidate == "J":
            asset.update(observed_sha256=model_hash, status=report["gates"]["artifact_identity"])
        if report["gates"]["artifact_identity"] != "PASS":
            raise CaptureError("model hash mismatch")
        with cpu_server(cpu_binary, model, port, output / "cpu.log", alias) as (client, build):
            report["gates"]["load"] = "PASS"
            report["cpu"] = {"engine_sha256": legacy.sha256_of(cpu_binary), "build": build}
            report["gates"]["cpu_reference"] = "PASS" if chat_ok(send_for(client)) else "FAIL"
        backend = "vulkan"
        binary, engine, env = engine_runtime(engine_directory, backend)
        report["gpu_engine"] = engine
        with gpu_server(binary, model, backend, env, output, port, "vulkan", False, alias=alias) as (client, launch):
            report["gpu"] = launch
            test_gpu(send_for(client), report)
    except (CaptureError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        # The raw process logs remain private. Public snapshots use an error type and stage.
        report["execution_interrupted"] = type(exc).__name__
        report["local_error"] = str(exc)
    if "gpu" in report:
        launch = output / "launch.json"
        legacy.write_json(launch, {**report["gpu"], "status": "PASS"})
        report["gates"]["gpu_execution"] = "PASS" if verify_gpu(
            {"gpu_launch": launch, "gpu_counters": output / report["gpu"]["counter_file"]}, "vulkan"
        ) else "FAIL"
    report["finished_utc"] = legacy.utc_now()
    report["status"] = ("FAIL" if "FAIL" in report["gates"].values() else
                        "PASS" if set(report["gates"].values()) == {"PASS"} else "BLOCKED")
    legacy.write_json(output / "report.json", report)
    print(f"{candidate} {report['status']} {report['gates']}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices="ABDEFGHJ", required=True)
    parser.add_argument("--model", type=Path, help="explicit pinned GGUF for candidate J")
    parser.add_argument("--cpu-bin", type=Path, help="explicit CPU reference executable for candidate J")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--engine-dir", default=ROOT / "runtime/llama-cpp/vulkan", type=Path)
    parser.add_argument("--disable-thinking", action="store_true")
    parser.add_argument("--port", default=8095, type=int, choices=range(1024, 65536), metavar="PORT")
    args = parser.parse_args()
    if args.candidate == "J" and not (args.model and args.cpu_bin):
        parser.error("candidate J requires --model and --cpu-bin")
    if args.candidate != "J" and (args.model or args.cpu_bin):
        parser.error("path overrides require candidate J")
    admit(args.candidate, args.output.resolve(), args.port, args.engine_dir.resolve(), args.disable_thinking,
          model=args.model, cpu_binary=args.cpu_bin.resolve() if args.cpu_bin else None)


if __name__ == "__main__":
    main()
