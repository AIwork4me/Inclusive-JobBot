"""Verify local model assets for supplemental capability evaluation."""

import argparse
import json
from pathlib import Path
import re

from evaluation.aeve.archive import digest
from evaluation.aeve.runtime import ROOT

REGISTRY = ROOT / "atlas/slm/v1.0/model_registry.json"
PINS = ROOT / "atlas/slm/v1.0/local-model-preflight.json"
SHA256 = re.compile(r"[0-9a-f]{64}")
ROUTING = {"DENSE", "PER_LAYER_EMBEDDINGS", "MIXTURE_OF_EXPERTS"}


def verify_asset(root, entry, *, max_active_parameters=None):
    counts = entry["parameters"]
    kinds = ("total", "effective", "active")
    if set(counts) != set(kinds) or entry["architecture"] not in ROUTING:
        raise ValueError("explicit architectural and parameter-count semantics are required")
    if type(counts["total"]) is not int or counts["total"] <= 0:
        raise ValueError("positive total parameter count required")
    for kind in ("effective", "active"):
        amount = counts[kind]
        if amount is not None and (type(amount) is not int or not 0 < amount <= counts["total"]):
            raise ValueError(f"invalid {kind} parameter count")
    if entry["architecture"] == "MIXTURE_OF_EXPERTS" and counts["active"] is None:
        raise ValueError("mixture-of-experts entries require a separately evidenced active parameter count")
    if max_active_parameters is not None:
        if type(max_active_parameters) is not int or max_active_parameters <= 0:
            raise ValueError("positive active-parameter cap required")
        if counts["active"] is None or counts["active"] > max_active_parameters:
            raise ValueError("evidenced active parameter count is unavailable or exceeds the requested cap")
    if not isinstance(entry["parameter_source"], str) or not entry["parameter_source"].strip():
        raise ValueError("parameter provenance is required")
    expected = entry["sha256"]
    if not isinstance(expected, str) or not SHA256.fullmatch(expected) or type(entry["size_bytes"]) is not int:
        raise ValueError("exact asset SHA256 and bytes are required")
    base = Path(root).resolve(strict=True)
    raw = Path(entry["local_asset"])
    asset = (base / raw).resolve(strict=True)
    if raw.is_absolute() or not asset.is_relative_to(base) or asset.suffix.lower() != ".gguf" or not asset.is_file():
        raise ValueError("a repository-local GGUF file is required")
    if asset.stat().st_size != entry["size_bytes"] or digest(asset) != expected:
        raise ValueError("local GGUF bytes differ from the registered asset")
    return {"asset_status": "PASS", "model": entry["model"], "sha256": expected,
            "size_bytes": entry["size_bytes"], "parameters": counts,
            "runtime_admission": "NOT_RUN", "frozen_trial_attribution": 0}


def gemma():
    pin = json.loads(PINS.read_bytes())["G"]
    registry = json.loads(REGISTRY.read_bytes())["models"]["G"]
    identity = registry["asset"]
    source = ROOT / registry["reference_model_identity"]
    if digest(source) != registry["reference_model_identity_sha256"]:
        raise ValueError("Gemma source identity differs from the frozen registry")
    if (pin["sha256"] != identity["expected_sha256"] or pin["size_bytes"] != identity["size"]
            or pin["local_asset"] != registry["local_asset"] or pin["model"] != registry["model"]
            or pin["parameters"]["total"] != json.loads(source.read_bytes())["hf_safetensors_parameters"]):
        raise ValueError("Gemma local preparation differs from the frozen inputs")
    return pin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--gemma", action="store_true")
    source.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--max-active-parameters", type=int)
    args = parser.parse_args()
    entry = gemma() if args.gemma else json.loads(args.candidate_manifest.read_bytes())
    print(json.dumps(verify_asset(args.assets, entry, max_active_parameters=args.max_active_parameters), sort_keys=True))


if __name__ == "__main__":
    main()
