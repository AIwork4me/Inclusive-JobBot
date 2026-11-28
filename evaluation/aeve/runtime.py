"""Pinned local inference and content-addressed capture for development and AEVE."""
from contextlib import contextmanager
from hashlib import sha256
from importlib.metadata import version
import gzip
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from benchmarks.competitive_slm.tc_v2_candidate import server_environment, verify_launch, verify_runtime
from benchmarks.root_cause.historical_replay import gpu_server

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = Path(__file__).with_name("judge_registry.json")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def fingerprint(value):
    return sha256(canonical(value)).hexdigest()


def selected_judges(subject_family):
    """Never assign the subject's own family, including the dispute reviewer."""
    order = json.loads(REGISTRY.read_bytes())["routing_order"]
    models = json.loads(REGISTRY.read_bytes())["candidates"]
    return [key for key in order if models[key]["family"].casefold() != subject_family.casefold()][:3]


def write_json(path, value):
    raw = canonical(value)
    scratch = path.with_name(path.name + ".tmp-" + uuid4().hex)
    scratch.write_bytes(raw)
    scratch.replace(path)


@contextmanager
def session(candidate, asset_root, output, port, *, registry=REGISTRY):
    cfg = json.loads(registry.read_bytes())["candidates"][candidate]
    engine = (asset_root / ".tools/ij07-toolchoice-p4b-vulkan").resolve()
    model = (asset_root / cfg["asset"]).resolve(strict=True)
    identity = verify_runtime(candidate, model, engine)
    if identity["model"]["model_sha256"] != cfg["sha256"]:
        raise ValueError("registry and admitted artifact differ")
    run_id = "ij073-" + uuid4().hex
    folder = output / "sessions" / run_id
    folder.mkdir(parents=True)
    alias = "ij07-candidate-" + candidate.lower()
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    with gpu_server(engine / "llama-server.exe", model, "vulkan", server_environment(), folder, port,
                    "live", True, alias=alias) as (client, launch):
        verify_launch(launch, identity)
        metadata = {"run_id": run_id, "candidate": candidate, "git_sha": sha, "identity": identity,
                    "launch": launch, "sdk": version("google-antigravity"), "sdk_used": False}
        write_json(folder / "identity.json", metadata)
        yield run_id, client
    rows = [json.loads(line) for line in (folder / "live-gpu.jsonl").read_bytes().splitlines()]
    active = [row for row in rows if row["kind"] == "gpu_engine" and row["utilization"] > 0 and
              row["instance"].startswith(f"pid_{launch['pid']}_")]
    for filename in ("live-gpu.jsonl", "live-generation.jsonl"):
        path = folder / filename
        if path.exists():
            packed = gzip.compress(path.read_bytes(), mtime=0)
            path.with_suffix(".jsonl.gz").write_bytes(packed)
    write_json(folder / "seal.json", {"run_id": run_id, "active_pid_counter_samples": len(active),
               "gpu_evidence": "PASS" if active else "BLOCKED",
               "sha256": {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*.gz"))}})


def infer(client, body):
    client.requests.clear()
    reply = client.chat(client.base_url, body)
    capture, = client.requests
    source = capture["source_generation"]
    choices = reply.get("choices", [])
    complete = bool(choices and choices[0].get("finish_reason") == "stop")
    raw = choices[0].get("message", {}).get("content") if choices else None
    if capture["http_status"] != 200 or capture["render_status"] != 200 or source.get("truncated") is not False:
        return "BLOCKED", None, capture
    return ("PASS" if complete and isinstance(raw, str) else "FAIL"), raw, capture
