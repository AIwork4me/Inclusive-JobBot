"""Run the frozen V1 benchmark with llama.cpp generation capture on Radeon."""

import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import subprocess
import time
from uuid import uuid4

from benchmarks.tool_calling.runner import run_benchmark as legacy
from benchmarks.tool_calling_v2 import rescore

from model_gateway.openai_protocol import MAX_CALLS
from .generation_capture import CaptureClient, CaptureError
from .gpu_lease import physical_gpu


ROOT = legacy.ROOT
ARMS = {"R0-V": "vulkan", "R0-R": "rocm", "R1-V": "vulkan", "R1-R": "rocm"}
DEVICES = {"vulkan": "Vulkan0", "rocm": "ROCm0"}
PLUGINS = {"vulkan": "ggml-vulkan.dll", "rocm": "ggml-hip.dll"}
ALIAS = "minicpm5-2b"


def stable_digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()


def engine_runtime(directory, backend):
    plugin = PLUGINS[backend]
    installed = ROOT / "runtime/llama-cpp" / backend / plugin
    binary = directory / "llama-server.exe"
    hashes = {file.name: legacy.sha256_of(file) for file in sorted(directory.glob("*.dll"))}
    if hashes.get(plugin) != legacy.sha256_of(installed):
        raise CaptureError("observer must use the pinned binary-identical GPU plugin")
    if set(PLUGINS.values()).intersection(hashes) != {plugin}:
        raise CaptureError("observer must expose exactly the selected GPU backend")
    env = dict(os.environ)
    env.pop("LLAMA_IJ07_TRACE_PATH", None)
    if backend == "rocm":
        packages = ROOT / "runtime/llama-cpp/rocm-libs/Lib/site-packages"
        libraries = [next(packages.rglob(name), None) for name in ("hipblas.dll", "amdhip64_7.dll")]
        if any(path is None for path in libraries):
            raise CaptureError("pinned ROCm wheel libraries are missing")
        hashes.update({file.name: legacy.sha256_of(file) for file in libraries if file.name not in hashes})
        env["PATH"] = os.pathsep.join([*(str(path.parent) for path in libraries), env["PATH"]])
    return binary, {"exe_sha256": legacy.sha256_of(binary), "dll_sha256": hashes}, env


@contextmanager
def gpu_server(binary, model, backend, env, output, port, tag, observe, alias=ALIAS,
               build_prefix="b12359-b1b770d90", *, max_nonstream_calls=MAX_CALLS):
    with physical_gpu(), _leased_server(binary, model, backend, env, output, port, tag, observe, alias,
                                        build_prefix, max_nonstream_calls=max_nonstream_calls) as live:
        yield live


@contextmanager
def _leased_server(binary, model, backend, env, output, port, tag, observe, alias,
                   build_prefix, *, max_nonstream_calls):
    log = output / f"{tag}-server.log"
    trace = output / f"{tag}-generation.jsonl"
    samples = output / f"{tag}-gpu.jsonl"
    stop = output / f"{tag}-gpu-stop"
    env = env.copy()
    if observe:
        env["LLAMA_IJ07_TRACE_PATH"] = str(trace)
    flags = ["--ctx-size", "8192", "--parallel", "1", "--n-gpu-layers", "99",
             "--device", DEVICES[backend], "--jinja", "--offline", "--no-webui", "--verbosity", "4"]
    server = subprocess.Popen(
        [str(binary), "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
         "--alias", alias, "--log-file", str(log), *flags],
        env=env, cwd=binary.parent, creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    sampler = None
    client = CaptureClient(port, trace if observe else None, max_nonstream_calls=max_nonstream_calls)
    try:
        for _ in range(90):
            if server.poll() is not None:
                raise CaptureError(f"llama-server exited with code {server.returncode}")
            if log.is_file():
                boot = log.read_text(encoding="utf-8", errors="replace")
                layers = re.findall(r"offloaded ([1-9]\d*)/(\d+) layers to GPU", boot)
                if layers and "listening on" in boot:
                    break
            time.sleep(1)
        else:
            raise CaptureError("GPU server did not report readiness")
        owner = subprocess.check_output(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             f"(Get-NetTCPConnection -LocalPort {port} -State Listen).OwningProcess | Select-Object -Unique"],
            text=True, timeout=20,
        ).strip()
        if owner != str(server.pid):
            raise CaptureError("loopback listener does not match the launched process")
        with client.opener.open(client.base_url + "/props", timeout=10) as reply:
            props = json.load(reply)
        if (not props["build_info"].startswith(build_prefix)
                or props["model_alias"] != alias or Path(props["model_path"]).resolve() != model
                or not props["chat_template_caps"]["supports_tool_calls"]):
            raise CaptureError("live server identity or tool-call support differs")
        gpu = re.search(r"using device " + DEVICES[backend] + r" \((.+?)\) \(", boot)
        if gpu is None or gpu[1] != "AMD Radeon(TM) 8060S Graphics":
            raise CaptureError("expected physical Radeon 8060S offload")
        sampler = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "RemoteSigned", "-File",
             str(ROOT / "scripts/windows/sample_gpu_counters.ps1"), "-TargetProcessId", str(server.pid),
             "-OutputPath", str(samples), "-StopFile", str(stop), "-MaxSeconds", "7200"],
            creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(60):
            if stop.with_suffix(".ready").exists():
                break
            if sampler.poll() is not None:
                raise CaptureError("Windows GPU sampler exited before readiness")
            time.sleep(0.25)
        else:
            raise CaptureError("Windows GPU sampler did not report readiness")
        yield client, {
            "pid": server.pid, "owns_port": True, "launched_utc": legacy.utc_now(),
            "backend": backend, "gpu": {"name": gpu[1], "device": DEVICES[backend], "architecture": "gfx1151"},
            "layers_offloaded": int(layers[-1][0]), "layers_total": int(layers[-1][1]),
            "build": props["build_info"], "args": flags,
            "template_sha256": hashlib.sha256(props["chat_template"].encode("utf-8")).hexdigest(),
            "counter_file": samples.name, "trace_file": trace.name if observe else None,
        }
    finally:
        if sampler is not None and sampler.poll() is None:
            stop.touch()
            try:
                sampler.wait(timeout=15)
            except subprocess.TimeoutExpired:
                sampler.kill()
                sampler.wait()
        if server.poll() is None:
            server.terminate()
            server.wait(timeout=15)


def run_case(case, client):
    # Supply the recording transport for the frozen synchronous V1 loop.
    # The original runner, evaluator, tools and dataset remain byte-identical.
    client.requests.clear()
    original = legacy.chat
    legacy.chat = client.chat
    try:
        result = legacy.run_case(case, client.base_url, ALIAS)
    finally:
        legacy.chat = original
    return {**result, "capture": list(client.requests)}


def replay(args):
    dataset = legacy.DATASET_DIR / legacy.DATASETS["test"]
    dataset_sha = legacy.sha256_of(dataset)
    manifest = rescore.read_json(dataset.parent / "dataset.manifest.json")
    if not any(f["path"] == dataset.name and f["sha256"] == dataset_sha for f in manifest["files"]):
        raise CaptureError("historical set digest differs from its freeze")
    cases = rescore.json_lines(dataset)
    if len(cases) != 500 or len({case["id"] for case in cases}) != 500:
        raise CaptureError("historical roster must contain 500 unique cases")
    if args.case:
        cases = [case for case in cases if case["id"] in args.case]
        if {case["id"] for case in cases} != set(args.case):
            raise CaptureError("requested cases are outside the frozen historical dataset")
    backend = ARMS[args.arm]
    model = (ROOT / "models/MiniCPM5-2B-GGUF/MiniCPM5-2B-Q8_0.gguf").resolve()
    model_sha = legacy.sha256_of(model)
    model_source = next(source for source in rescore.read_json(ROOT / "models/model_manifest.json")["models"]
                        if source["model_id"] == "OpenBMB/MiniCPM5-2B-GGUF")
    if not any(item["path"] == model.name and item["sha256"] == model_sha for item in model_source["files"]):
        raise CaptureError("model file digest differs from its pinned ModelScope identity")
    binary, engine, env = engine_runtime(args.engine_dir.resolve(), backend)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with legacy.output_lock(output):
        configuration = {
            "arm": args.arm, "backend": backend, "engine": engine, "dataset_sha256": dataset_sha,
            "model_sha256": model_sha, "modelscope_revision": model_source["revision"],
            "case_ids": [case["id"] for case in cases], "sdk_installed": version("google-antigravity"),
            "sdk_used": False, "git": legacy.git_state(),
            "code_sha256": {file.name: legacy.sha256_of(file) for file in (
                Path(__file__), Path(__file__).with_name("generation_capture.py"),
                Path(legacy.__file__), ROOT / "patches/ij07/llama-b12359-generation-observer.patch",
            )}, "port": args.port, "observe": not args.observer_disabled,
        }
        run_path, results = output / "run.json", output / "results.jsonl"
        fingerprint = stable_digest(configuration)
        if run_path.exists():
            run = rescore.read_json(run_path)
            if (not args.resume or run["fingerprint"] != fingerprint
                    or stable_digest(run["configuration"]) != fingerprint):
                raise CaptureError("resume requires the exact original run identity")
        elif results.exists():
            raise CaptureError("result records exist without run identity")
        else:
            run = {"run_id": "ij07-historical-" + uuid4().hex, "started_utc": legacy.utc_now(),
                   "fingerprint": fingerprint, "configuration": configuration, "sessions": []}
        done = legacy.read_checkpoint(results, configuration["case_ids"], recover_tail=True, run=run)
        for row in done.values():
            payload = {name: value for name, value in row.items() if name != "artifact_sha256"}
            if stable_digest(payload) != row["artifact_sha256"]:
                raise CaptureError(f"checkpoint digest mismatch for {row['id']}")
        if len(done) < len(cases):
            tag = uuid4().hex
            with gpu_server(binary, model, backend, env, output, args.port, tag, configuration["observe"]) as (client, launch):
                if run["sessions"] and any(
                    launch[key] != run["sessions"][0][key]
                    for key in ("backend", "gpu", "layers_offloaded", "build", "args", "template_sha256")
                ):
                    raise CaptureError("live server identity changed across resume")
                run["sessions"].append(launch)
                legacy.write_json(run_path, run)
                with results.open("a", encoding="utf-8", newline="\n") as handle:
                    start = len(done)
                    end = start + args.batch_size if args.batch_size else len(cases)
                    for case in cases[start:end]:
                        row = run_case(case, client)
                        row.update(run_id=run["run_id"], server_session=len(run["sessions"]))
                        row["rescored_v2"] = rescore.rescore(case, row)
                        row["artifact_sha256"] = stable_digest(row)
                        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                        done[case["id"]] = row
                        print(f"{args.arm} {len(done)}/{len(cases)} {case['id']} {row['status']}", flush=True)
        legacy.write_json(output / "summary.json", {
            "run_id": run["run_id"], "cases": len(done), "planned_cases": len(cases),
            "result_sha256": legacy.sha256_of(results), "updated_utc": legacy.utc_now(),
            "v1": dict(Counter(r["status"] for r in done.values())),
            "v2": rescore.summarize([r["rescored_v2"] for r in done.values()]),
            "source_capture": dict(Counter(
                request["source_generation"].get("status", "PASS")
                for row in done.values() for request in row["capture"]
            )),
            "scope": "historical diagnostic; V1 synthetic receipts; persisted state and SDK gates not exercised",
        })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8094, choices=range(1024, 65536), metavar="PORT")
    parser.add_argument("--case", action="append", help="select an explicit diagnostic case, repeatable")
    parser.add_argument("--batch-size", type=int, help="pause after this many additional cases")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--observer-disabled", action="store_true", help="capture-off control")
    args = parser.parse_args()
    if args.batch_size is not None and args.batch_size < 1:
        parser.error("--batch-size must be positive")
    try:
        replay(args)
    except (CaptureError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, f"BLOCKED: {error}\n")


if __name__ == "__main__":
    main()
