"""Measure the LFM3 adapter intervention on the pinned Radeon runtime."""

import argparse
import asyncio
from contextlib import contextmanager
from functools import partial
from importlib.metadata import version
import json
import math
from pathlib import Path
import re
import subprocess
from struct import pack
import time
from urllib.error import URLError
from uuid import uuid4

from audit import write_evidence
from benchmarks.competitive_slm.admission import request, test_gpu
from benchmarks.competitive_slm.tc_v2_candidate import server_environment
from benchmarks.root_cause.generation_capture import CaptureClient
from benchmarks.root_cause.gpu_lease import physical_gpu, windows_query
from benchmarks.root_cause.windows_job import job_process
from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT, fingerprint, write_json
from scripts.tools.verify_ij06_evidence import verify_gpu

from .sdk_adapter_development import require_idle_controller

ATLAS = ROOT / "atlas/slm/v1.0/lfm3-harness-adapters"
ALIAS = "lfm3-ha"
PROMPTS = (
    "The product invoice records a quantity of seven and a unit price of",
    "In a warehouse, inventory is grouped by",
    "Return the order identifier in a JSON object with the key",
)
SEED = 7107
FLAGS = ("--ctx-size", "8192", "--parallel", "1", "--n-gpu-layers", "99",
         "--device", "Vulkan0", "--cache-ram", "0", "--ctx-checkpoints", "0", "--jinja", "--offline", "--no-webui", "--verbosity", "4")


def numeric_row(reply):
    rows = reply.get("completion_probabilities")
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("native probability reply must cover exactly one generated token")
    row = rows[0]
    result = [(entry["id"], entry["logprob"]) for entry in row["top_logprobs"]]
    if (len(result) != 32 or len({token for token, _ in result}) != 32
            or any(type(token) is not int or token < 0 or not math.isfinite(value)
                   or value > 0 for token, value in result)
            or row["id"] != result[0][0]):
        raise ValueError("expected finite, unique native top-token log probabilities")
    return result


def equivalent(left, right):
    return len(left) == len(right) and all(
        key_a == key_b and abs(value_a - value_b) <= 1e-5
        for (key_a, value_a), (key_b, value_b) in zip(left, right, strict=True)
    )


def intervention(left, right):
    original, adapted = dict(left), dict(right)
    return any(abs(original[key] - adapted[key]) >= 1e-3 for key in original.keys() & adapted.keys())


def panel(client, scale=None):
    results = []
    for prompt in PROMPTS:
        status, _, raw = client.post("/tokenize", {"content": prompt, "add_special": True})
        if status != 200:
            raise ValueError("server tokenization failed")
        tokens = json.loads(raw)["tokens"]
        if not tokens or any(type(token) is not int for token in tokens):
            raise ValueError("server returned no usable token prefix")
        body = {"prompt": tokens, "n_predict": 1, "n_probs": 32, "temperature": -1.0,
                "seed": SEED, "cache_prompt": False, "post_sampling_probs": False}
        status, _, _ = client.post("/slots/0?action=erase", {})
        if status != 200:
            raise ValueError("server refused to erase the recurrent slot")
        if scale is not None:
            body["lora"] = [{"id": 0, "scale": scale}]
        status, _, raw = client.post("/completion", body)
        if status != 200:
            raise ValueError(f"numerical completion returned HTTP {status}")
        results.append({"tokens": tokens, "values": numeric_row(json.loads(raw))})
    return results


def compare(left, right, predicate):
    return [base["tokens"] == other["tokens"] and predicate(base["values"], other["values"])
            for base, other in zip(left, right, strict=True)]


def pinned_file(assets, spec, *, sha_key="sha256", size_key="size_bytes"):
    path = (assets / spec["local_asset"]).resolve(strict=True)
    if not path.is_relative_to(assets) or path.stat().st_size != spec[size_key] or digest(path) != spec[sha_key]:
        raise ValueError("local artifact differs from the pinned identity")
    return path


def owner_capture_active():
    return bool(windows_query(
        "$ErrorActionPreference='Stop'; (Get-CimInstance Win32_Process | Where-Object { "
        "$_.ProcessId -ne $PID -and $_.CommandLine -match "
        r"'(?i)(-m\s+scripts\.tools\.ag11_owner\b|-File\s+[^\r\n]*RUN_AG11_ELEVATED\.ps1\b|"
        r"-m\s+evaluation\.aeve\b)' }).ProcessId"
    ))


@contextmanager
def server(binary, model, lora, port, folder, pin, run_id, handoff, *, expected_error=None):
    require_idle_controller()
    if owner_capture_active():
        raise BlockingIOError("the owner capture or another controller is active")
    flags = list(FLAGS)
    if lora is not None:
        flags.extend(["--lora", str(lora)])
    boot_path, samples, stop = (folder / name for name in ("server.log", "gpu.jsonl", "sample-stop"))
    cmd = [str(binary), "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
           "--alias", ALIAS, "--log-file", str(boot_path), *flags]
    with physical_gpu(mission_id="LFM3-HA-1.0", runtime_session=run_id, lease_owner="lora-admission") as lease:
        if any(lease[key] != handoff["lease"][key] for key in ("host_sha256", "gpu_physical_sha256")):
            raise ValueError("Radeon differs from the frozen handoff")
        with job_process(cmd, cwd=binary.parent, env=server_environment(),
                         creationflags=subprocess.CREATE_NO_WINDOW,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
            client = CaptureClient(port)
            for _ in range(90):
                if process.poll() is not None:
                    if expected_error is None:
                        raise ValueError("pinned llama-server exited before readiness")
                    boot = boot_path.read_text(encoding="utf-8", errors="replace")
                    rejected = process.returncode != 0 and expected_error in boot and "listening on" not in boot
                    yield None, {"status": verdict(rejected), "log_sha256": digest(boot_path)}
                    return
                try:
                    with client.opener.open(client.base_url + "/props", timeout=2) as reply:
                        props = json.load(reply)
                except (URLError, TimeoutError):
                    time.sleep(1)
                    continue
                break
            else:
                raise TimeoutError("pinned llama-server did not become ready")
            if expected_error is not None:
                yield None, {"status": "FAIL", "log_sha256": digest(boot_path)}
                return
            owner = windows_query(f"(Get-NetTCPConnection -LocalPort {port} -State Listen).OwningProcess")
            boot = boot_path.read_text(encoding="utf-8", errors="replace")
            layers = re.findall(r"offloaded ([1-9]\d*)/(\d+) layers to GPU", boot)
            if (owner != str(process.pid) or props["model_alias"] != ALIAS
                    or Path(props["model_path"]).resolve() != model or props["build_info"] != pin["engine_build"]
                    or not props["chat_template_caps"]["supports_tool_calls"]
                    or "AMD Radeon(TM) 8060S Graphics" not in boot
                    or not layers or layers[-1][0] != layers[-1][1]):
                raise ValueError("listener, model, native parser or Radeon identity differs")
            with client.opener.open(client.base_url + "/lora-adapters", timeout=5) as reply:
                loaded = json.load(reply)
            valid = (len(loaded) == 1 and loaded[0]["id"] == 0 and loaded[0]["scale"] == 1.0
                     and Path(loaded[0]["path"]).resolve() == lora) if lora is not None else loaded == []
            if not valid:
                raise ValueError("server adapter identity or default scale differs")
            allocations = [{"device": device, "mib": float(size)} for device, size in
                           re.findall(r"(\S+) LoRA buffer size =\s*([\d.]+) MiB", boot)]
            with job_process(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "RemoteSigned", "-File",
                 str(ROOT / "scripts/windows/sample_gpu_counters.ps1"), "-TargetProcessId", str(process.pid),
                 "-OutputPath", str(samples), "-StopFile", str(stop), "-MaxSeconds", "90"],
                creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ) as sampler:
                try:
                    for _ in range(60):
                        if sampler.poll() is not None:
                            raise ValueError("GPU sampler exited before readiness")
                        if stop.with_suffix(".ready").is_file():
                            break
                        time.sleep(0.25)
                    else:
                        raise TimeoutError("GPU sampler did not start")
                    yield client, {"backend": "vulkan", "pid": process.pid, "owns_port": True,
                                   "layers_offloaded": int(layers[-1][0]), "engine_build": props["build_info"],
                                   "adapter_allocations": allocations, "lease": lease, "status": "PASS"}
                finally:
                    stop.touch()
                    sampler.wait(timeout=15)


def run(assets, port):
    from google.antigravity import bin as sdk_bin

    from benchmarks.ij06_sdk.qualify import CASE_SPECS, execute_case
    from .admission import git_head
    from .native_diagnostics import OBSERVER_ENGINE

    registry = json.loads((ATLAS / "MODEL_ADAPTER_REGISTRY.json").read_bytes())
    startup = json.loads((ATLAS / "EVIDENCE_MANIFEST.json").read_bytes())
    pin = startup["runtime"]
    handoff = require_handoff(ROOT)
    model_spec = registry["base"]
    model = pinned_file(assets, model_spec["asset"] | {"local_asset": model_spec["local_asset"]},
                        sha_key="expected_sha256", size_key="size")
    harness = Path(sdk_bin.__file__).with_name("localharness.exe")
    engine = assets / OBSERVER_ENGINE
    hashes = {f.name: digest(f) for f in engine.iterdir() if f.suffix in {".exe", ".dll"}}
    if hashes != pin["binary_sha256"] or version("google-antigravity") != pin["sdk"] or digest(
            harness) != pin["harness_pin_sha256"]:
        raise ValueError("runtime or SDK package differs from the startup pin")
    run_id = "lfm3-ha-" + uuid4().hex
    root = assets / ".runtime/lfm3-harness-adapters" / run_id
    root.mkdir(parents=True, exist_ok=False)
    report = {"run_id": run_id, "git_sha": git_head(), "engine": pin, "base": model_spec["asset"],
              "handoff_sha256": digest(ROOT / HANDOFF), "core_trial_attribution": 0,
              "launch_flags": FLAGS,
              "registry_sha256": digest(ATLAS / "MODEL_ADAPTER_REGISTRY.json"), "seed": SEED,
              "dataset_sha256": fingerprint([PROMPTS, CASE_SPECS["AG-03"]]), "arms": {}}
    base = None
    negatives = root / "negative"
    negatives.mkdir()
    malformed = negatives / "invalid-shape.gguf"
    malformed.write_bytes(invalid_shape_gguf())
    report["negative_fixture_sha256"] = digest(malformed)
    for tag, adapter, expected in (
        ("missing", negatives / "missing.gguf", "failed to open"),
        ("shape", malformed, "has incorrect shape"),
    ):
        folder = negatives / tag
        folder.mkdir()
        with server(engine / "llama-server.exe", model, adapter, port, folder, pin, run_id + "-" + tag, handoff,
                    expected_error=expected) as (_, result):
            report.setdefault("load_controls", {})[tag] = result
    wrong_base = json.loads((ATLAS.parent / "model_registry.json").read_bytes())["models"]["A"]
    other = (assets / wrong_base["local_asset"]).resolve(strict=True)
    if not other.is_relative_to(assets) or digest(other) != wrong_base["asset"]["expected_sha256"]:
        raise ValueError("wrong-model control asset differs from its registry")
    report["wrong_base_sha256"] = wrong_base["asset"]["expected_sha256"]
    write_json(root / "report.json", report)
    for arm in ("Original", "HA-O", "HA-P", "HA-H"):
        folder = root / arm
        folder.mkdir()
        lora = None
        results = report["arms"][arm] = {"status": "NOT_RUN", "negative_controls": "NOT_RUN"}
        try:
            if arm != "Original":
                spec, = (s for name, s in registry["adapters"][arm]["artifacts"].items() if name.endswith(".gguf"))
                lora = pinned_file(assets, spec)
                results["adapter"] = spec
                negative_folder = negatives / arm
                negative_folder.mkdir()
                with server(engine / "llama-server.exe", other, lora, port, negative_folder, pin,
                            run_id + "-wrong-base-" + arm, handoff,
                            expected_error="model arch and LoRA arch mismatch") as (_, result):
                    results["wrong_base_control"] = result
            with server(engine / "llama-server.exe", model, lora, port, folder, pin, run_id + "-" + arm,
                        handoff) as (client, launch):
                results["launch"] = launch
                if arm == "Original":
                    base = results["baseline"] = panel(client)
                    results["baseline_repeatability"] = verdict(all(compare(base, panel(client), equivalent)))
                else:
                    zero, one, again, after = panel(client, 0), panel(client, 1), panel(client, 1), panel(client, 0)
                    results["native_numeric"] = {"zero": zero, "one": one, "one_repeat": again, "zero_after": after}
                    if base is not None:
                        results["zero_equivalence"] = verdict(all(compare(base, zero, equivalent)))
                        results["weight_intervention"] = verdict(any(compare(base, one, intervention)))
                        results["post_intervention_isolation"] = verdict(all(compare(base, after, equivalent)))
                        results["one_repeatability"] = verdict(all(compare(one, again, equivalent)))
                    allocations = launch["adapter_allocations"]
                    results["native_invalid_id_http_status"], _, _ = client.post(
                        "/completion", {"prompt": one[0]["tokens"], "n_predict": 1, "cache_prompt": False,
                                        "lora": [{"id": 99, "scale": 1.0}]})
                    results["adapter_device_placement"] = verdict(bool(allocations) and all(
                        entry["device"] == "Vulkan0" and entry["mib"] > 0 for entry in allocations))
                wire = []
                direct = {"gates": {}}
                test_gpu(partial(request, client, ALIAS, wire=wire, disable_thinking=True), direct)
                write_json(folder / "direct.json", {"wire": wire, **direct})
                results["direct"] = direct["gates"]
                sdk = asyncio.run(execute_case(client.base_url, ALIAS, folder / "sdk", harness, "AG-03"))
                write_evidence(folder / "sdk.json", sdk)
                results["sdk_callbacks"] = sdk["status"]
            launch_path = folder / "launch.json"
            write_json(launch_path, launch)
            results["gpu_execution"] = verdict(verify_gpu(
                {"gpu_launch": launch_path, "gpu_counters": folder / "gpu.jsonl"}, "vulkan"))
            common = [results["gpu_execution"], results["sdk_callbacks"], *results["direct"].values()]
            if arm == "Original":
                results["status"] = verdict(all(value == "PASS" for value in
                                                [*common, results["baseline_repeatability"]]))
            elif base is not None:
                checks = [results[key] for key in ("zero_equivalence", "weight_intervention",
                          "post_intervention_isolation", "one_repeatability", "adapter_device_placement")]
                checks.extend(entry["status"] for entry in report["load_controls"].values())
                checks.extend((results["wrong_base_control"]["status"],
                               verdict(400 <= results["native_invalid_id_http_status"] < 500)))
                results["status"] = ("FAIL" if "FAIL" in [*common, *checks] else "BLOCKED")

        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            results["status"] = "BLOCKED"
            results["interruption"] = type(exc).__name__
            print(arm, type(exc).__name__, str(exc), flush=True)
        finally:
            write_json(root / "report.json", report)
    pinned_file(assets, model_spec["asset"] | {"local_asset": model_spec["local_asset"]},
                sha_key="expected_sha256", size_key="size")
    report["base_reverified_after_run"] = "PASS"
    write_json(root / "report.json", report)
    print(run_id, {arm: row["status"] for arm, row in report["arms"].items()})
    return 2 if any(row["status"] != "PASS" for row in report["arms"].values()) else 0


def invalid_shape_gguf():
    # Two deliberately incompatible zero F16 factors. No model data is copied.
    def string(value):
        data = value.encode("ascii")
        return pack("<Q", len(data)) + data

    meta = b"".join(string(key) + pack("<I", 8) + string(value) for key, value in (
        ("general.architecture", "lfm3"), ("general.type", "adapter"), ("adapter.type", "lora"),
    ))
    meta += string("adapter.lora.alpha") + pack("<If", 6, 64.0)
    tensors = b"".join(string("blk.0.shortconv.in_proj.weight.lora_" + side) +
                       pack("<IQQIQ", 2, 1, 1, 1, offset) for side, offset in (("a", 0), ("b", 32)))
    header = pack("<4sIQQ", b"GGUF", 3, 2, 4) + meta + tensors
    return header + bytes((-len(header)) % 32 + 64)


def verdict(passed):
    return "PASS" if passed else "FAIL"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18757)
    args = parser.parse_args()
    return run(args.assets.resolve(strict=True), args.port)


if __name__ == "__main__":
    raise SystemExit(main())
