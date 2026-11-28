"""Run the candidate b12359 routing controls against the pinned LFM3 assets."""

import json
from pathlib import Path
import subprocess
import time
from urllib.error import URLError
from uuid import uuid4

from audit import write_evidence
from benchmarks.root_cause.generation_capture import CaptureClient
from benchmarks.root_cause.gpu_lease import physical_gpu, windows_query
from benchmarks.root_cause.windows_job import job_process
from benchmarks.slm10 import lfm3_ha_admission as ha
from benchmarks.slm10.admission import git_head
from benchmarks.competitive_slm.tc_v2_candidate import server_environment
from evaluation.aeve.archive import digest
from evaluation.aeve.runtime import ROOT, fingerprint


def outcome(status, accepted):
    return "PASS" if accepted and status == 200 or not accepted and status == 400 else "FAIL"


assets = ROOT.parents[1]
captures = assets / ".runtime/lfm3-harness-adapters/ha11-tc-compatibility"
if len(list(captures.glob("batch-*/seal.json"))) != 200 or ha.owner_capture_active():
    raise BlockingIOError("The compatibility queue or owner trace has priority")
receipt = json.loads((ROOT / "evidence/IJSLM/lfm3-ha-1.1/native-routing-candidate-build.json").read_bytes())
engine = assets / ".scratch/ha11-native-route-build-b12359/bin"
hashes = {f.name: digest(f) for f in engine.iterdir() if f.suffix in (".exe", ".dll")}
if hashes != receipt["binary_sha256"] or any("vulkan" in name.lower() for name in hashes):
    raise ValueError("The CPU-only candidate binary identity differs")
registry = json.loads((ha.ATLAS / "MODEL_ADAPTER_REGISTRY.json").read_bytes())
base = registry["base"]
model = ha.pinned_file(assets, base["asset"] | {"local_asset": base["local_asset"]},
                       sha_key="expected_sha256", size_key="size")
adapter, = [value for name, value in registry["adapters"]["HA-O"]["artifacts"].items() if name.endswith(".gguf")]
lora = ha.pinned_file(assets, adapter)
run_id = "lfm3-ha11-native-route-cpu-" + uuid4().hex
output = assets / ".runtime/lfm3-harness-adapters" / run_id
output.mkdir(parents=True, exist_ok=False)
matrix = {"negative": -1, "out_of_range": 99, "upper_boundary": 1}
report = {"run_id": run_id, "git_sha": git_head(), "source_sha256": digest(Path(__file__)),
          "candidate_patch_sha256": receipt["candidate_patch_sha256"], "upstream_commit": receipt["upstream_commit"],
          "binary_sha256": hashes, "base": base["asset"], "adapter_sha256": adapter["sha256"],
          "backend": "CPU", "radeon_inference": "NOT_RUN", "core_trial_attribution": 0,
          "dataset_sha256": fingerprint({"prompt": "Return OK.", "ids": matrix}), "controls": {}}
port = 18760
log = output / "server.log"
command = [
    str(engine / "llama-server.exe"), "--model", str(model), "--lora", str(lora), "--alias", ha.ALIAS,
    "--host", "127.0.0.1", "--port", str(port), "--ctx-size", "1024", "--parallel", "1",
    "--device", "none", "--n-gpu-layers", "0", "--cache-ram", "0", "--ctx-checkpoints", "0",
    "--jinja", "--offline", "--no-webui", "--log-file", str(log),
]
client = CaptureClient(port)


def get(route):
    with client.opener.open(client.base_url + route, timeout=5) as reply:
        return json.load(reply)


def post(name, route, body, accepted):
    status, _, raw = client.post(route, body)
    result = outcome(status, accepted)
    if not accepted and not b"Unknown LoRA adapter ID" in raw:
        result = "FAIL"
    report["controls"][name] = {"status": result, "http_status": status}
    return result


with physical_gpu(mission_id="LFM3-HA-1.1", runtime_session=run_id, lease_owner="cpu-routing-slot-reservation"):
    with job_process(command, cwd=engine, env=server_environment(), creationflags=subprocess.CREATE_NO_WINDOW,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
        for attempt in range(120):
            if process.poll() is not None:
                raise RuntimeError("CPU candidate exited before readiness")
            try:
                props = get("/props")
                break
            except (URLError, TimeoutError):
                time.sleep(0.5)
        else:
            raise TimeoutError("CPU candidate did not become ready")
        owner = windows_query(f"(Get-NetTCPConnection -LocalPort {port} -State Listen).OwningProcess")
        if (owner != str(process.pid) or props["model_alias"] != ha.ALIAS
                or Path(props["model_path"]).resolve() != model or "b12359" not in props["build_info"]):
            raise ValueError("CPU listener or runtime identity differs")
        report["engine_build"] = props["build_info"]
        native = {"prompt": "Return OK.", "n_predict": 1, "seed": 7107, "temperature": 0.0, "cache_prompt": False}
        chat = {"model": ha.ALIAS, "messages": [{"role": "user", "content": "Return OK."}],
                "max_completion_tokens": 1, "seed": 7107, "temperature": 0.0, "cache_prompt": False}
        baseline = get("/lora-adapters")
        if len(baseline) != 1 or baseline[0]["id"] != 0 or baseline[0]["scale"] != 1.0:
            raise ValueError("CPU candidate loaded an unexpected adapter")
        matrices = {key: [{"id": ident, "scale": 1.0}] for key, ident in matrix.items()}
        matrices["mixed_known_and_unknown"] = [{"id": 0, "scale": 0.5}, {"id": 99, "scale": 1.0}]
        for key, rows in matrices.items():
            post("completion_" + key, "/completion", native | {"lora": rows}, False)
            post("chat_" + key, "/v1/chat/completions", chat | {"lora": rows}, False)
            post("global_" + key, "/lora-adapters", rows, False)
            report["controls"]["global_unchanged_" + key] = {"status": ha.verdict(get("/lora-adapters") == baseline)}
        known = [{"id": 0, "scale": 1.0}]
        post("known_completion", "/completion", native | {"lora": known}, True)
        post("known_chat", "/v1/chat/completions", chat | {"lora": known}, True)
        post("known_global_zero", "/lora-adapters", [{"id": 0, "scale": 0.0}], True)
        report["controls"]["global_applied_zero"] = {"status": ha.verdict(get("/lora-adapters")[0]["scale"] == 0.0)}
        post("known_global_restore", "/lora-adapters", known, True)
        report["controls"]["restored_default"] = {"status": ha.verdict(get("/lora-adapters") == baseline)}
        report["server_log_sha256"] = digest(log)

report["cpu_http_controls"] = ha.verdict(all(value["status"] == "PASS" for value in report["controls"].values()))
write_evidence(output / "report.json", report)
print(report["cpu_http_controls"], run_id, len(report["controls"]))
