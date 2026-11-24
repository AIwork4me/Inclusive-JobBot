"""Probe the official Aion INT4 ONNX graph with explicit CPU or WebGPU selection."""

import argparse
import hashlib
from importlib.metadata import distribution, version
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from benchmarks.tool_calling.runner.run_benchmark import ROOT, git_state, utc_now, write_json


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(model_dir, out, backend):
    import onnxruntime as ort
    import onnxruntime_genai as genai

    record = json.loads((ROOT / "evidence/IJ07/model_identity/C.json").read_bytes())
    assets = record["official_onnx_reference"]["files"]
    for asset in assets:
        if digest(model_dir / asset["Path"]) != asset["Sha256"]:
            raise ValueError(f"official ONNX digest mismatch for {asset['Path']}")
    dlls = {}
    for name in ("onnxruntime-webgpu", "onnxruntime-genai"):
        package = distribution(name)
        for file in package.files:
            if file.suffix in (".dll", ".pyd"):
                dlls[file.as_posix()] = digest(package.locate_file(file))

    result = {
        "run_id": "ij07-aion-" + uuid4().hex, "git": git_state(), "model_id": record["official_model_id"],
        "backend": backend, "pid": os.getpid(), "started_utc": utc_now(), "assets": assets, "native_libraries": dlls,
        "versions": {"onnxruntime-webgpu": version("onnxruntime-webgpu"),
                     "onnxruntime-genai": version("onnxruntime-genai")},
        "available_providers": ort.get_available_providers(), "ordinary_chat": "NOT_RUN",
    }
    sampler = None
    stop = out / "gpu-stop"
    try:
        config = genai.Config(str(model_dir))
        config.clear_providers()
        if backend == "webgpu":
            config.append_provider("webgpu")
            config.overlay(json.dumps({"model": {"decoder": {"session_options": {"disable_cpu_ep_fallback": True}}}}))
            result["cpu_fallback_disabled"] = True
            sampler = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "RemoteSigned", "-File",
                 str(ROOT / "scripts/windows/sample_gpu_counters.ps1"), "-TargetProcessId", str(os.getpid()),
                 "-OutputPath", str(out / "gpu.jsonl"), "-StopFile", str(stop), "-MaxSeconds", "600"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            for _ in range(60):
                if stop.with_suffix(".ready").exists():
                    break
                time.sleep(0.25)
            else:
                raise ValueError("Windows GPU sampler did not start")
        model = genai.Model(config)
        result["reported_device_type"] = model.device_type
        if str(model.device_type).lower() != backend:
            raise ValueError("native runtime reported a device other than the requested provider")
        tokenizer = genai.Tokenizer(model)
        prompt = [{"role": "user", "content": "Reply with exactly this text: RAD-7107"}]
        rendered = tokenizer.apply_chat_template(
            json.dumps(prompt), template_str=(model_dir / "chat_template.jinja").read_text(encoding="utf-8"),
            add_generation_prompt=True,
        )
        tokens = tokenizer.encode(rendered)
        params = genai.GeneratorParams(model)
        params.set_search_options(max_length=len(tokens) + 64, do_sample=False)
        generator = genai.Generator(model, params)
        generator.append_tokens(tokens)
        stream = tokenizer.create_stream()
        sampled, chunks = [], []
        started = time.perf_counter()
        while not generator.is_done():
            generator.generate_next_token()
            token = int(generator.get_next_tokens()[0])
            sampled.append(token)
            chunks.append(stream.decode(token))
        answer = "".join(chunks)
        result.update(
            prompt=prompt, rendered_prompt=rendered, prompt_token_ids=tokens.tolist(), sampled_token_ids=sampled,
            answer=answer, generation_ms=round((time.perf_counter() - started) * 1000),
            ordinary_chat="PASS" if answer.strip() == "RAD-7107" else "FAIL",
        )
    except (OSError, RuntimeError, ValueError) as error:
        result["runtime_failure"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if sampler is not None and sampler.poll() is None:
            stop.touch()
            try:
                sampler.wait(timeout=15)
            except subprocess.TimeoutExpired:
                sampler.kill()
                sampler.wait()
    result["finished_utc"] = utc_now()
    result["status"] = "BLOCKED" if "runtime_failure" in result else result["ordinary_chat"]
    write_json(out / "report.json", result)
    print(result["status"], result.get("reported_device_type"), result.get("runtime_failure"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--backend", required=True, choices=("cpu", "webgpu"))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    run(args.model_dir.resolve(), output, args.backend)


if __name__ == "__main__":
    main()
