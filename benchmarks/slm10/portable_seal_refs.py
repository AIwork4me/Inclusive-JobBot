"""Verify the byte identity of a portable TC-V3 seal and its referenced payloads."""

from hashlib import sha256
import json

from evaluation.aeve.archive import digest


def verify_seal_artifacts(path, expected_manifest_sha256):
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected_manifest_sha256:
        raise ValueError(f"Portable seal manifest digest differs for {path.parent.name}")
    seal = json.loads(raw)
    artifacts = seal["artifacts"]
    required = {"trials.jsonl.gz", "gpu.jsonl.gz"} if seal["gpu_execution"] == "PASS" else {"trials.jsonl.gz"}
    if (seal["identity"]["run_id"] != path.parent.name or not isinstance(artifacts, dict)
            or not required <= artifacts.keys() <= {"trials.jsonl.gz", "gpu.jsonl.gz"}):
        raise ValueError(f"Invalid portable seal inventory for {path.parent.name}")
    for name, expected in artifacts.items():
        artifact = path.parent / name
        if not artifact.is_file():
            raise ValueError(f"Portable seal is missing payload {name} in {path.parent.name}")
        if digest(artifact) != expected:
            raise ValueError(f"Portable seal payload digest differs for {name} in {path.parent.name}")
