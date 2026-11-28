"""Inspect the pinned LFM3 short-convolution tensors from native Radeon slot saves."""

import argparse
from hashlib import sha256
from itertools import product
import json
from math import isfinite
from pathlib import Path
import re
from struct import iter_unpack, unpack_from
from uuid import uuid4

from audit import write_evidence
from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT, fingerprint
from scripts.tools.verify_ij06_evidence import verify_gpu

from . import ha11_cache as cache
from . import lfm3_ha_admission as ha


def read_shortconv(data, *, state_layers, block_count, width, prefix):
    """Extract the single LFM3 recurrent cell at the end of a GGSQ v4 save."""
    row_bytes = width * 4
    # The native R section is followed by one F32, zero-width S header per
    # recurrent layer. LFM3 has no PLE state. Both attention caches precede R.
    suffix_bytes = 20 + len(state_layers) * (12 + row_bytes + 12)
    if len(data) < 12 + suffix_bytes:
        raise ValueError("Truncated LFM3 slot state")
    magic, version, packed_count = unpack_from("<3I", data)
    token_offset, packed_end = 12, 12 + packed_count * 4
    if (magic, version) != (0x67677371, 4) or not prefix or packed_end > len(data) - suffix_bytes:
        raise ValueError("Invalid slot header")
    token_count = packed_count
    if packed_count and unpack_from("<i", data, 12)[0] == -1:
        if packed_count < 4:
            raise ValueError("Incomplete packed server token header")
        token_version, token_count = unpack_from("<2I", data, 16)
        token_offset = 24
        if (token_version != 1 or packed_count != token_count + 4
                or unpack_from("<I", data, packed_end - 4)[0] != 0):
            raise ValueError("Expected version-1 text-only server tokens")
    if token_count < len(prefix) or list(unpack_from(f"<{len(prefix)}i", data, token_offset)) != prefix:
        raise ValueError("Slot header or saved prompt differs from the LFM3 probe")
    end, checkpoints = checkpoint_boundary(data, packed_end + suffix_bytes)
    offset = end - suffix_bytes
    cells, position, seq_ids, transposed, layers = unpack_from("<5I", data, offset)
    if (cells, seq_ids, transposed, layers) != (1, 0, 0, block_count) or position >= token_count:
        raise ValueError("Expected one live non-transposed LFM3 recurrent cell")
    offset += 20
    rows = {}
    for layer in state_layers:
        if unpack_from("<IQ", data, offset) != (0, row_bytes):
            raise ValueError("Recurrent row width or tensor type differs from the pinned LFM3 model")
        offset += 12
        row = data[offset:offset + row_bytes]
        if any(not isfinite(value) for (value,) in iter_unpack("<f", row)):
            raise ValueError("Non-finite values in the serialized short-convolution row")
        rows[layer] = row
        offset += row_bytes
    for _ in state_layers:
        if unpack_from("<IQ", data, offset) != (0, 0):
            raise ValueError("Unexpected secondary state in the pinned LFM3 snapshot")
        offset += 12
    token_bytes = data[token_offset:token_offset + token_count * 4]
    return rows, {"token_count": token_count, "position": position, "checkpoint_count": checkpoints,
                  "token_sha256": sha256(token_bytes).hexdigest()}


def checkpoint_boundary(data, start):
    """Find the optional, complete server checkpoint appendix after the live state."""
    footer = data.find(b"SCKP", start)
    if footer == -1:
        return len(data), 0
    if len(data) - footer < 12:
        raise ValueError("Incomplete slot checkpoint header")
    version, count = unpack_from("<2I", data, footer + 4)
    if version != 1 or not 1 <= count <= 32:
        raise ValueError("Invalid slot checkpoint version or count")
    offset = footer + 12
    for _ in range(count):
        if offset + 16 > len(data):
            raise ValueError("Incomplete slot checkpoint metadata")
        tokens, first, last = unpack_from("<qii", data, offset)
        if tokens <= 0 or not 0 <= first <= last:
            raise ValueError("Invalid slot checkpoint token positions")
        offset += 16
        for index in range(3):
            if offset + 8 > len(data):
                raise ValueError("Missing slot checkpoint section")
            size, = unpack_from("<Q", data, offset)
            offset += 8 + size
            if offset > len(data) or (index == 0 and size == 0) or (index != 0 and size != 0):
                raise ValueError("Invalid target, draft or speculative checkpoint section")
    if offset != len(data):
        raise ValueError("Unexpected trailing slot state")
    return footer, count


def compare_states(left, right):
    differences = {}
    for layer, row in left.items():
        other = right[layer]
        identical = row == other
        pairs = zip(iter_unpack("<f", row), iter_unpack("<f", other), strict=True)
        absolute = [0.0] if identical else [abs(a - b) for (a,), (b,) in pairs]
        differences[layer] = {"byte_identical": identical, "max_abs_delta": max(absolute),
                              "mean_abs_delta": sum(absolute) / len(absolute)}
    return {"byte_identical_layers": sum(item["byte_identical"] for item in differences.values()),
            "total_layers": len(differences), "layers": differences}


def snapshot(client, folder, name, probe, layout):
    filename = name + ".ggsq"
    status, _, raw = client.post("/slots/0?action=save", {"filename": filename})
    if status != 200:
        raise ValueError(f"Slot snapshot returned HTTP {status}")
    receipt = json.loads(raw)
    data = (folder / filename).read_bytes()
    rows, state = read_shortconv(data, **layout, prefix=probe["prefix"])
    if (receipt["id_slot"] != 0 or receipt["filename"] != filename
            or receipt["n_saved"] != state["token_count"] or receipt["n_written"] < len(data)):
        raise ValueError("Native save receipt differs from the snapshot")
    return rows, state | {"snapshot_sha256": sha256(data).hexdigest(), "snapshot_size": len(data),
                          "sampled_tokens": probe["tokens"], "tokens_cached": probe["tokens_cached"],
                          "layer_sha256": {layer: sha256(row).hexdigest() for layer, row in rows.items()}}


def measure(client, folder, mode, prompt, cached, adapted, layout):
    before = 1.0 if adapted else None
    stages = [("initial", before), ("repeat", before), ("unrelated", before), ("restore", before)]
    if adapted:
        stages += [("scale_zero", 0.0), ("scale_one_restored", 1.0)]
    states, records = {}, {}
    for label, scale in stages:
        text = ("Unrelated isolated session. " + cache.DISTRACTOR) if label == "unrelated" else prompt
        probe = cache.sample(client, text, cached, scale)
        if probe["http_status"] != 200:
            raise ValueError("Native ShortConv probe did not complete")
        states[label], records[label] = snapshot(client, folder, mode + "-" + label, probe, layout)
        if label == "initial":
            states["observer_repeat"], records["observer_repeat"] = snapshot(
                client, folder, mode + "-observer-repeat", probe, layout)
    contrasts = [("initial", "observer_repeat"), ("initial", "repeat"), ("repeat", "unrelated"),
                 ("repeat", "restore")]
    if adapted:
        contrasts += [("restore", "scale_zero"), ("restore", "scale_one_restored")]
    return {"states": records, "contrasts": {first + "/" + second: compare_states(states[first], states[second])
            | {"same_saved_tokens": records[first]["token_sha256"] == records[second]["token_sha256"]}
            for first, second in contrasts}}


def run(assets, output, port):
    from gguf import GGUFReader

    from .admission import git_head
    from .ha11_preflight import checked_runtime

    registry, pin, model, binary, _ = checked_runtime(assets)
    gguf = GGUFReader(model)
    if gguf.get_field("general.architecture").contents() != "lfm3":
        raise ValueError("Expected the pinned LFM3 architecture")
    state_layers = sorted(int(match[1]) for tensor in gguf.tensors
                          if (match := re.fullmatch(r"blk\.(\d+)\.shortconv\.conv\.weight", tensor.name)))
    width = gguf.get_field("lfm3.embedding_length").contents() * (gguf.get_field("lfm3.shortconv.l_cache").contents() - 1)
    layout = {"state_layers": state_layers, "block_count": gguf.get_field("lfm3.block_count").contents(), "width": width}
    if len(state_layers) != 13 or len(set(state_layers)) != 13 or width != 12288 or layout["block_count"] != 24:
        raise ValueError("ShortConv layer inventory differs from the pinned LFM3 model")
    handoff = require_handoff(ROOT)
    output.mkdir(parents=True, exist_ok=False)
    run_id = "lfm3-ha11-shortconv-" + uuid4().hex
    report = {"run_id": run_id, "git_sha": git_head(), "runtime": pin, "backend": "vulkan",
              "base": registry["base"]["asset"], "layout": layout, "seed": ha.SEED,
              "handoff_sha256": digest(ROOT / HANDOFF),
              "dataset_sha256": fingerprint({"prompts": cache.PROMPTS, "prompt_index": 0,
                                             "unrelated": "Unrelated isolated session. " + cache.DISTRACTOR}),
              "core_trial_attribution": 0, "status": "BLOCKED", "cells": {}}
    for factor, weight in product(cache.FACTORS, cache.WEIGHTS):
        name = factor + "-" + weight
        folder = output / name
        folder.mkdir()
        spec = None
        if weight != "Original":
            spec, = [item for path, item in registry["adapters"][weight]["artifacts"].items() if path.endswith(".gguf")]
        lora = ha.pinned_file(assets, spec) if spec else None
        flags = (*cache.cache_flags(*cache.FACTORS[factor]), "--slots", "--slot-save-path", str(folder))
        with ha.server(binary, model, lora, port, folder, pin, run_id + "-" + name, handoff,
                       launch_flags=flags, sampler_seconds=900) as (client, launch):
            modes = {mode: measure(client, folder, mode, prompts[0], cached, lora is not None, layout)
                     for mode, (cached, prompts) in cache.PROMPTS.items()}
        if spec:
            for mode, result in modes.items():
                base = report["cells"][factor + "-Original"]["modes"][mode]["states"]["initial"]
                zero = result["states"]["scale_zero"]
                result["scale_zero_vs_original"] = {
                    "same_saved_tokens": base["token_sha256"] == zero["token_sha256"],
                    "byte_identical_layers": sum(base["layer_sha256"][layer] == zero["layer_sha256"][layer]
                                                 for layer in state_layers),
                    "total_layers": len(state_layers),
                }
        launch_file, counters = folder / "launch.json", folder / "gpu.jsonl"
        write_evidence(launch_file, launch)
        physical = verify_gpu({"gpu_launch": launch_file, "gpu_counters": counters}, "vulkan")
        report["cells"][name] = {"gpu_execution": ha.verdict(physical), "weight": weight, "factor": factor,
                                 "adapter_sha256": spec["sha256"] if spec else None, "modes": modes,
                                 "launch_sha256": digest(launch_file), "gpu_counters_sha256": digest(counters),
                                 "server_log_sha256": digest(folder / "server.log")}
        write_evidence(output / "report.json", report)
        print(name, ha.verdict(physical), flush=True)
    observers = [mode["contrasts"]["initial/observer_repeat"] for cell in report["cells"].values()
                 for mode in cell["modes"].values()]
    report["status"] = ("BLOCKED" if any(cell["gpu_execution"] != "PASS" for cell in report["cells"].values())
                        else ha.verdict(all(row["same_saved_tokens"] and row["byte_identical_layers"] == row["total_layers"]
                                            for row in observers)))
    write_evidence(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18757)
    args = parser.parse_args()
    report = run(args.assets.resolve(strict=True), args.output.resolve(), args.port)
    print(report["status"], len(report["cells"]))


if __name__ == "__main__":
    main()
