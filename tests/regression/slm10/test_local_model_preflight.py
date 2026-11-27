from hashlib import sha256

import pytest

from benchmarks.slm10.local_model_preflight import verify_asset


def test_moe_with_two_billion_active_parameters_can_have_more_total(tmp_path):
    payload = b"software identity fixture"
    asset = tmp_path / "fixture.gguf"
    asset.write_bytes(payload)
    manifest = {
        "architecture": "MIXTURE_OF_EXPERTS", "model": "fixture",
        "parameters": {"total": 8000000000, "active": 2000000000, "effective": None},
        "parameter_source": "software fixture, no physical attribution",
        "local_asset": asset.name, "size_bytes": len(payload), "sha256": sha256(payload).hexdigest(),
    }
    result = verify_asset(tmp_path, manifest, max_active_parameters=2000000000)
    assert result["asset_status"] == "PASS"
    assert result["runtime_admission"] == "NOT_RUN" and result["frozen_trial_attribution"] == 0
    with pytest.raises(ValueError, match="exceeds"):
        verify_asset(tmp_path, manifest, max_active_parameters=1999999999)
    manifest["architecture"] = "PER_LAYER_EMBEDDINGS"
    manifest["parameters"] = {"total": 8000000000, "active": None, "effective": 2000000000}
    with pytest.raises(ValueError, match="unavailable"):
        verify_asset(tmp_path, manifest, max_active_parameters=2000000000)
    asset.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="bytes differ"):
        verify_asset(tmp_path, manifest)
