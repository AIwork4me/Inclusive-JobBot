"""Exercise Aion's official native tool syntax on the pinned ONNX reference track."""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import subprocess
import time
from uuid import uuid4

from model_gateway.strict_json import strict_object

from .admission import FIXTURES, TOOLS, legacy
from .aion_reference import digest


TOOL_BLOCK = re.compile(r"<\|tool_call\|>(.*?)<\|/tool_call\|>", re.DOTALL)
END_OF_TURN = ("<|end|>", "<|endoftext|>", "<|endofprompt|>")


def trim_end(text):
    for token in END_OF_TURN:
        text = text.removesuffix(token).rstrip()
    return text


def exact_call(text):
    content = trim_end(text.strip())
    blocks = list(TOOL_BLOCK.finditer(content))
    if len(blocks) != 1 or blocks[0].span() != (0, len(content)):
        raise ValueError("one complete native Aion tool block was expected")
    value = strict_object(blocks[0][1])
    if set(value) != {"name", "arguments"} or not isinstance(value["arguments"], dict):
        raise ValueError("invalid Aion tool envelope")
    return value


def generate(model, tokenizer, template, messages):
    import numpy as np
    import onnxruntime_genai as genai

    prompt = tokenizer.apply_chat_template(json.dumps(messages), template_str=template,
                                           tools=json.dumps(TOOLS), add_generation_prompt=True)
    tokens = tokenizer.encode(prompt)
    control = genai.GeneratorParams(model)
    control.set_search_options(max_length=len(tokens) + 256, do_sample=False)
    decoder = genai.Generator(model, control)
    decoder.append_tokens(tokens)
    stream = tokenizer.create_stream()
    emitted = []
    deltas = []
    while not decoder.is_done():
        decoder.generate_next_token()
        token = int(decoder.get_next_tokens()[0])
        emitted.append(token)
        deltas.append(stream.decode(token))
    answer = tokenizer.decode(np.array(emitted, dtype=np.int32))
    return {"messages": messages, "template_prompt": prompt, "prompt_token_ids": tokens.tolist(),
            "sampled_token_ids": emitted, "stream_deltas": deltas, "whole_decode": answer,
            "same_sequence_stream_parity": "PASS" if answer == "".join(deltas) else "FAIL"}


def run(model_dir, output, provider, *, serial_instruction=False):
    import onnxruntime_genai as genai

    identity = json.loads((legacy.ROOT / "evidence/IJ07/model_identity/C.json").read_bytes())
    assets = identity["official_onnx_reference"]["files"]
    if any(digest(model_dir / entry["Path"]) != entry["Sha256"] for entry in assets):
        raise ValueError("official ONNX artifact identity mismatch")
    config = genai.Config(str(model_dir))
    config.clear_providers()
    if provider == "webgpu":
        config.append_provider("webgpu")
        config.set_decoder_provider_options_hardware_vendor_id("webgpu", 0x1002)
        config.set_decoder_provider_options_hardware_device_type("webgpu", "gpu")
        config.overlay(json.dumps({"model": {"decoder": {"session_options": {"disable_cpu_ep_fallback": "1"}}}}))
    model = genai.Model(config)
    if str(model.device_type).lower() != provider:
        raise ValueError("native provider differs from the requested provider")
    tokenizer = genai.Tokenizer(model)
    tokenizer.update_options(skip_special_tokens=False)
    template = (model_dir / "chat_template.jinja").read_text(encoding="utf-8")
    trace = {"run_id": "ij07-aion-tools-" + uuid4().hex, "git": legacy.git_state(), "device": model.device_type,
             "pid": os.getpid(), "source_sha256": digest(Path(__file__)),
             "backend": provider, "package_version": genai.__version__, "official_onnx_identity": assets,
             "tools": TOOLS, "trials": [], "independent_streaming": "NOT_RUN", "status": "FAIL",
             "profile": "explicit_serial_instruction" if serial_instruction else "baseline"}
    user = "Find the balance for Orchid Works. Return the account ID and the CNY balance."
    if serial_instruction:
        user += (" Call lookup_account first and wait for its response. Use exactly the returned account_id "
                 "in a later lookup_balance call. Send at most one tool call per turn.")
    messages = [{"role": "user", "content": user}]
    for expected in ("lookup_account", "lookup_balance"):
        row = generate(model, tokenizer, template, messages)
        trace["trials"].append(row)
        try:
            call = exact_call(row["whole_decode"])
            if call != {"name": expected, "arguments": FIXTURES[expected][0]}:
                raise ValueError("case tool name or arguments differ")
        except ValueError as error:
            row["failure"] = str(error)
            break
        row["executed_synthetic_read"] = FIXTURES[expected][1]
        messages = [*messages, {"role": "assistant", "content": "", "tool_calls": [call]},
                    {"role": "tool", "name": expected, "content": json.dumps(FIXTURES[expected][1])}]
    else:
        row = generate(model, tokenizer, template, messages)
        trace["trials"].append(row)
        traced = trim_end(row["whole_decode"])
        if "AC-18405" in traced and "1742" in traced.replace(",", ""):
            trace["status"] = "PASS"
    legacy.write_json(output, trace)
    print(provider, trace["status"], f'{len(trace["trials"])} captured generations')


@contextmanager
def sample_gpu(output):
    stop = output.with_suffix(".gpu-stop")
    counters = output.with_suffix(".gpu.jsonl")
    sampler = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "RemoteSigned", "-File",
         str(legacy.ROOT / "scripts/windows/sample_gpu_counters.ps1"), "-TargetProcessId", str(os.getpid()),
         "-OutputPath", str(counters), "-StopFile", str(stop), "-MaxSeconds", "600"],
        creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            if Path(str(stop) + ".ready").exists():
                break
            time.sleep(0.25)
        else:
            raise ValueError("Windows GPU sampler did not start")
        yield
    finally:
        stop.touch()
        try:
            sampler.wait(timeout=15)
        except subprocess.TimeoutExpired:
            sampler.kill()
            sampler.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", choices=("cpu", "webgpu"), required=True)
    parser.add_argument("--serial-instruction", action="store_true", help="Run the diagnostic prompt control")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("choose a new evidence file")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.provider == "webgpu":
        with sample_gpu(args.output.resolve()):
            run(args.model_dir.resolve(), args.output.resolve(), args.provider, serial_instruction=args.serial_instruction)
    else:
        run(args.model_dir.resolve(), args.output.resolve(), args.provider, serial_instruction=args.serial_instruction)


if __name__ == "__main__":
    main()
