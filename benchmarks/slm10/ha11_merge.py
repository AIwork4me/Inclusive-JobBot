"""Build and verify F16-merged and quantized LoRA artifacts on the CPU."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from audit import write_evidence
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import canonical, write_json

from .admission import git_head
from .lfm3_ha_admission import ATLAS, pinned_file


BASE = {
    "repo": "LiquidAI/LFM3-1.7B-GGUF",
    "revision": "cd0c74c575b5c416f3011b5b4c298077f26ca8c2",
    "publisher_file": "LFM3-1.7B-F16.gguf",
    "local_asset": ".tools/models/lfm3-harness-adapters/high-precision/LFM3-1.7B-F16.publisher.gguf",
    "size_bytes": 3466626336,
    "sha256": "b7ab8b69a85e4dfbf62cdfd0e02d7d051ed09f2c5b84c701771dddb073b85970",
}
ENGINE_SHA = "b1b770d90d94cad9e9ea5b993bdbc383a522fb28"
FORMATS = ("Q8_0", "Q4_K_M")


def tensor_hash(tensor):
    return sha256(memoryview(tensor.data).cast("B")).hexdigest()


def index(file):
    from gguf import GGUFReader

    reader = GGUFReader(file)
    tensors = {t.name: t for t in reader.tensors}
    if len(tensors) != len(reader.tensors):
        raise ValueError("Duplicate GGUF tensors")
    return reader, tensors


def signature(tensors):
    return {name: tuple(int(dim) for dim in tensor.shape) for name, tensor in tensors.items()}


def run_tool(bin_dir, tool, args, log):
    with log.open("wb") as output:
        subprocess.run([str(bin_dir / tool), *map(str, args)], cwd=bin_dir, stdin=subprocess.DEVNULL,
                       stdout=output, stderr=subprocess.STDOUT, timeout=1200, check=True)


def identity(path):
    return {"filename": path.name, "size_bytes": path.stat().st_size, "sha256": digest(path)}


def run(assets, bin_dir, output):
    base = pinned_file(assets, BASE)
    registry = json.loads((ATLAS / "MODEL_ADAPTER_REGISTRY.json").read_bytes())
    output.mkdir(parents=True, exist_ok=False)
    _, base_tensors = index(base)
    base_signature = signature(base_tensors)
    base_hashes = {name: tensor_hash(tensor) for name, tensor in base_tensors.items()}
    report = {
        "run_id": "ha11-merge-" + uuid4().hex, "git_sha": git_head(), "evidence_class": "CPU artifact packaging",
        "engine_source_commit": ENGINE_SHA, "core_trial_attribution": 0,
        "tool_binary_sha256": {file.name: digest(file) for file in bin_dir.iterdir()
                               if file.suffix.lower() in {".dll", ".exe"}},
        "base": {key: value for key, value in BASE.items() if key != "local_asset"},
        "base_tensor_count": len(base_signature), "arms": {}, "radeon_inference": "NOT_RUN", "DX-M2": "NOT_RUN",
    }
    for arm in ("HA-O", "HA-P", "HA-H"):
        spec, = (info for key, info in registry["adapters"][arm]["artifacts"].items() if key.endswith(".gguf"))
        adapter = pinned_file(assets, spec)
        adapter_names = set(index(adapter)[1])
        targets = {name.removesuffix(".lora_a") for name in adapter_names if name.endswith(".lora_a")}
        if (not targets or {name + factor for name in targets for factor in (".lora_a", ".lora_b")} != adapter_names
                or not targets <= base_signature.keys()):
            raise ValueError("Adapter targets do not match the high-precision base")
        merged = output / f"{arm}-merged-F16.gguf"
        export_log = output / f"{arm}-merge.log"
        run_tool(bin_dir, "llama-export-lora.exe", ["-m", base, "--lora", adapter, "-t", 4, "-o", merged],
                 export_log)
        _, merged_tensors = index(merged)
        if signature(merged_tensors) != base_signature:
            raise ValueError("Merged tensor shapes differ from the base")
        changed = {name for name, tensor in merged_tensors.items() if tensor_hash(tensor) != base_hashes[name]}
        if not changed or not changed <= targets:
            raise ValueError("Merged tensors changed outside the expected LoRA targets")
        row = {"adapter": identity(adapter), "scale": 1.0, "target_tensors": len(targets),
               "changed_target_tensors": len(changed), "merged": identity(merged), "quantized": {},
               "merge_log_sha256": digest(export_log)}
        report["arms"][arm] = row
        write_evidence(output / "report.json", report)
        for quant in FORMATS:
            artifact = output / f"{arm}-merged-{quant}.gguf"
            log = output / f"{arm}-{quant}.log"
            run_tool(bin_dir, "llama-quantize.exe", [merged, artifact, quant, 4], log)
            _, tensors = index(artifact)
            if signature(tensors) != base_signature:
                raise ValueError("Quantized artifact shape inventory differs from the base")
            row["quantized"][quant] = identity(artifact) | {
                "log_sha256": digest(log), "tensor_types": sorted({tensor.tensor_type.name for tensor in tensors.values()})
            }
            write_evidence(output / "report.json", report)
        print(arm, "CPU packaging PASS", len(changed), len(targets), flush=True)
    return report


def verify(assets, bin_dir, output):
    import numpy as np

    source = output / "report.json"
    report = json.loads(source.read_bytes())
    base = pinned_file(assets, BASE)
    _, base_tensors = index(base)
    registry = json.loads((ATLAS / "MODEL_ADAPTER_REGISTRY.json").read_bytes())
    if (set(report["arms"]) != {"HA-O", "HA-P", "HA-H"}
            or report["base"]["sha256"] != BASE["sha256"]
            or any(digest(bin_dir / name) != sha for name, sha in report["tool_binary_sha256"].items())):
        raise ValueError("CPU artifact lane identities differ")
    for arm, row in report["arms"].items():
        spec, = (info for key, info in registry["adapters"][arm]["artifacts"].items() if key.endswith(".gguf"))
        adapter = pinned_file(assets, spec)
        adapter_reader, factors = index(adapter)
        alpha = float(adapter_reader.get_field("adapter.lora.alpha").contents())
        merged_path = output / row["merged"]["filename"]
        _, merged = index(merged_path)
        if (identity(adapter) != row["adapter"] or identity(merged_path) != row["merged"]
                or digest(output / f"{arm}-merge.log") != row["merge_log_sha256"]
                or set(row["quantized"]) != set(FORMATS)):
            raise ValueError("Merged or adapter artifact seal differs")
        for quant, entry in row["quantized"].items():
            file = output / entry["filename"]
            if any(entry[key] != value for key, value in identity(file).items()):
                raise ValueError("Quantized artifact seal differs")
            if digest(output / f"{arm}-{quant}.log") != entry["log_sha256"]:
                raise ValueError("Quantization evidence differs")

        checked = exact = within = 0
        for name, tensor in factors.items():
            if not name.endswith(".lora_a"):
                continue
            target = name.removesuffix(".lora_a")
            a, b = tensor.data, factors[target + ".lora_b"].data
            original, actual = base_tensors[target].data, merged[target].data
            rows = [0, b.shape[0] // 2, b.shape[0] - 1]
            cols = [0, a.shape[1] // 2, a.shape[1] - 1]
            expected = (original[np.ix_(rows, cols)].astype(np.float32) +
                        b[rows, :].astype(np.float32) @ a[:, cols].astype(np.float32)
                        * (alpha / a.shape[0] if alpha else 1.0)).astype(actual.dtype)
            got = actual[np.ix_(rows, cols)]
            checked += got.size
            exact += int(np.count_nonzero(got == expected))
            lower = np.nextafter(expected, np.full_like(expected, -np.inf))
            upper = np.nextafter(expected, np.full_like(expected, np.inf))
            within += int(np.count_nonzero((got >= lower) & (got <= upper)))
        row["independent_tensor_sample"] = {"checked_values": checked, "exact": exact,
                                            "within_one_ulp": within,
                                            "status": "PASS" if checked == within and checked else "FAIL"}
    return report | {"private_report_sha256": digest(source), "artifact_replay": "PASS"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--binaries", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--publish", type=Path, help="Replay a completed CPU artifact directory")
    args = parser.parse_args()
    inputs = (args.assets.resolve(strict=True), args.binaries.resolve(strict=True), args.output.resolve())
    if args.publish:
        result = verify(*inputs)
        check_text(canonical(result))
        write_json(args.publish, result)
    else:
        result = run(*inputs)
    print(result["run_id"])


if __name__ == "__main__":
    main()
