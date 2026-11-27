import json

import pytest

from benchmarks.slm10.portable_seal_refs import verify_seal_artifacts
from evaluation.aeve.archive import digest


def test_manifest_reference_requires_every_byte_of_every_payload(tmp_path):
    trial = tmp_path / "trials.jsonl.gz"
    gpu = tmp_path / "gpu.jsonl.gz"
    trial.write_bytes(b"software trial fixture")
    gpu.write_bytes(b"software GPU fixture")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({
        "identity": {"run_id": tmp_path.name},
        "gpu_execution": "PASS",
        "artifacts": {item.name: digest(item) for item in (trial, gpu)},
    }), encoding="utf-8")
    pin = digest(path)
    verify_seal_artifacts(path, pin)
    trial.write_bytes(b"changed")
    with pytest.raises(ValueError, match="payload digest"):
        verify_seal_artifacts(path, pin)
    trial.unlink()
    with pytest.raises(ValueError, match="missing payload"):
        verify_seal_artifacts(path, pin)
