"""Register and resume sealed LFM3-HA development and TC-V3 compatibility panels."""

import argparse
from collections import Counter
from itertools import permutations
import json
from pathlib import Path
from time import perf_counter

from audit import write_evidence
from evaluation.aeve.archive import digest
from evaluation.aeve.controller import gpu_lock
from evaluation.aeve.runtime import ROOT, fingerprint, write_json

from .lfm3_ha_admission import ATLAS
from .tc_v3 import FIRST_SEED, HERE, roster, verify_freeze


WEIGHTS = ("Original", "HA-O", "HA-P", "HA-H")
DIRECT, ORIGINAL, CORRECTED = "DIRECT", "ORIGINAL_SDK", "SDK_MATCHED_CONTEXT_PhaseAware"
TRANSFER = "LFM3-HA-TRANSFER-DEV/1.1"
COMPATIBILITY = "LFM3-HA-TCV3-COMPAT/1.1"
PROVIDER_CONTRACT = "shared-budget-cache-sampling/1.0"
PREFLIGHT = ROOT / "evidence/IJSLM/lfm3-ha-1.1/action-phase-retest.json"


def load_inputs(suite):
    if suite == "transfer":
        matrix = ATLAS / "CROSS_HARNESS_TRANSFER_MATRIX.json"
        manifest = json.loads(matrix.read_bytes())
        folder, split, hashes = ATLAS, "development", manifest["files"]
    else:
        verify_freeze()
        matrix = HERE / "manifest.json"
        folder, split, hashes = HERE, "holdout", json.loads(matrix.read_bytes())["sha256"]
    inputs = []
    for key in ("public", "worlds", "oracle"):
        name = f"{split}-{key}.jsonl"
        path = folder / name
        if digest(path) != hashes[name]:
            raise ValueError("Frozen panel input differs")
        inputs.append([json.loads(row) for row in path.read_bytes().splitlines()])
    cases = {a["case_id"]: (a, b, c) for a, b, c in zip(*inputs, strict=True)
             if a["case_id"] == b["case_id"] == c["case_id"]}
    if len(cases) != (60 if suite == "transfer" else 500):
        raise ValueError("Frozen panel cases are missing or duplicated")
    return cases, digest(matrix)


def build_plan(suite, cases, input_sha):
    scope = TRANSFER if suite == "transfer" else COMPATIBILITY
    assignments = {}
    if suite == "transfer":
        inputs = list(cases.values())
        for i, (public, _, _) in enumerate(inputs):
            options = ((DIRECT, "direct_first", FIRST_SEED), (ORIGINAL, "sdk_streaming", FIRST_SEED),
                       (CORRECTED, "sdk_streaming", FIRST_SEED))
            order = tuple(permutations(options))[((i % 15) % 3) * 2 + (i // 15) % 2]
            assignments[public["case_id"]] = order
        chunk_size = 15
    else:
        for entry in roster([case[0] for case in cases.values()]):
            if entry["candidate"] == "B":
                track = entry["track"]
                assignments.setdefault(entry["case_id"], []).append(
                    (DIRECT if track == "direct_first" else CORRECTED, track, entry["seed"]))
        chunk_size = 10

    ids = list(assignments)
    weight_order = ((0, 1, 3, 2), (1, 2, 0, 3), (2, 3, 1, 0), (3, 0, 2, 1))
    batches = []
    for start in range(0, len(ids), chunk_size):
        period = start // chunk_size
        for position in weight_order[period % len(weight_order)]:
            weight = WEIGHTS[position]
            batch = []
            for case_index, case_id in enumerate(ids[start:start + chunk_size]):
                entries = assignments[case_id]
                rotation = case_index % len(entries) if suite == "tc-extension" else 0
                for profile, track, seed in entries[rotation:] + entries[:rotation]:
                    attribution = "supplemental" if suite != "transfer" or profile == CORRECTED else "frozen-480"
                    slot = {"case_id": case_id, "weight": weight, "profile": profile, "track": track,
                            "seed": seed, "attribution": attribution}
                    slot["slot_id"] = fingerprint([scope, slot])
                    batch.append(slot)
            batches.append(batch)
    rows = [row for batch in batches for row in batch]
    if len(rows) != len({row["slot_id"] for row in rows}) or len(rows) != (720 if suite == "transfer" else 6600):
        raise ValueError("Capability roster differs from its allocation")
    return batches, {"scope": scope, "suite": suite, "input_manifest_sha256": input_sha,
                     "planned": len(rows), "core_attribution": 0, "roster_sha256": fingerprint(batches),
                     "provider_contract": PROVIDER_CONTRACT}


def plan(suite):
    return build_plan(suite, *load_inputs(suite))


def enforce_admission(suite, extension_admission):
    gate = json.loads(PREFLIGHT.read_bytes())
    if (gate["replay"] != "PASS" or gate["gpu_execution"] != "PASS" or len(gate["results"]) != 40
            or gate["direct_executor_scope"] != "PASS" or gate["corrected_sdk_executor_scope"] != "PASS"):
        raise ValueError("The matched physical transport preflight is required")
    if suite == "tc-extension":
        if extension_admission is None:
            raise BlockingIOError("TC compatibility dispatch requires physical qualification of first and repeat transport")
        from .ha11_compatibility_admission import verify

        readiness = verify(extension_admission)
        if readiness["scope"] != COMPATIBILITY or any(readiness["transport"][track] != "PASS"
                                                      for track in ("sdk_first", "sdk_repeat")):
            raise ValueError("Physical compatibility transport admission is incomplete")


def verify_batch(folder, batch, freeze):
    from scripts.tools.verify_ij06_evidence import verify_gpu

    seal = json.loads((folder / "seal.json").read_bytes())
    if (seal.get("provider_contract") != PROVIDER_CONTRACT
            or seal["roster_sha256"] != freeze["roster_sha256"] or seal["batch_sha256"] != fingerprint(batch)
            or seal["gpu_execution"] != "PASS" or [row["slot_id"] for row in seal["results"]]
            != [row["slot_id"] for row in batch]
            or any(digest(folder / name) != expected for name, expected in seal["artifacts"].items())
            or not verify_gpu({"gpu_launch": folder / "launch.json", "gpu_counters": folder / "gpu.jsonl"}, "vulkan")):
        raise ValueError("Sealed panel batch differs from the frozen roster or physical observations")
    for row in seal["results"]:
        if digest(folder / (row["slot_id"] + ".json")) != row["capture_sha256"]:
            raise ValueError("Sealed panel trial differs from the retained trace")
    return seal


def require_effective_controls(trial, slot):
    from .tc_v3 import CONFIG

    common = {"stream": slot["track"] == "sdk_streaming", "seed": slot["seed"],
              "temperature": CONFIG["temperature"], "max_completion_tokens": CONFIG["max_completion_tokens"],
              "cache_prompt": CONFIG["cache_prompt"], "parallel_tool_calls": True,
              "chat_template_kwargs": {"enable_thinking": CONFIG["thinking"]}}
    for turn in trial["wire"]:
        if "provider_request" in turn:
            body = json.loads(turn["provider_request"])
            if any(body.get(field) != expected for field, expected in common.items()):
                raise ValueError("Effective capability request differs from the shared provider contract")


def execute_batch(folder, batch, freeze, cases, assets, port, checked, handoff, head):
    from evaluation.aeve.gpu_handoff import HANDOFF
    from scripts.tools.verify_ij06_evidence import verify_gpu
    from . import lfm3_ha_admission as ha
    from .ha11_preflight import FLAGS, FixedChatClient, trial
    from .tc_capability_replay import assess

    registry, pin, model, binary, harness = checked
    weight = batch[0]["weight"]
    spec = None
    if weight != "Original":
        spec, = [item for key, item in registry["adapters"][weight]["artifacts"].items() if key.endswith(".gguf")]
    adapter = ha.pinned_file(assets, spec) if spec else None
    run_id = "ha11-" + fingerprint([head, freeze["roster_sha256"], folder.name])[:32]
    folder.mkdir()
    write_json(folder / "reservation.json", {"run_id": run_id, "batch_sha256": fingerprint(batch),
                                             "roster_sha256": freeze["roster_sha256"], "git_sha": head})
    trace = folder / "native.jsonl"
    rows = []
    try:
        with ha.server(binary, model, adapter, port, folder, pin, run_id, handoff, launch_flags=FLAGS,
                       trace_path=trace, sampler_seconds=5400) as (_, launch):
            client = FixedChatClient(port, trace, max_nonstream_calls=12)
            for slot in batch:
                public, world, oracle = cases[slot["case_id"]]
                ident = fingerprint([run_id, slot["slot_id"]])
                target = folder / (slot["slot_id"] + ".json")
                started = perf_counter()
                result = trial(client, public, world, slot["profile"], ident, folder / ident, harness,
                               seed=slot["seed"], track=slot["track"])
                require_effective_controls(result, slot)
                result["elapsed_wall_ms"] = round((perf_counter() - started) * 1000, 3)
                assessment = assess(result, oracle, "BLOCKED")
                write_evidence(target, result)
                rows.append(slot | {"trial_id": ident, "capture_sha256": digest(target), "assessment": assessment,
                                    "requests": len(result["wire"]),
                                    "native_requests": sum(e.get("native_evidence", {}).get("status") == "PASS"
                                                           for e in result["wire"]),
                                    "callback_bindings": dict(Counter(c["status"] for c in result.get("callbacks", []))),
                                    "failure_type": (result["failure"] or {}).get("type")})
                write_evidence(folder / "progress.json", {"results": rows})
    except (RuntimeError, OSError, ValueError) as failure:
        write_evidence(folder / "interruption.json", {"status": "BLOCKED", "type": type(failure).__name__,
                                                     "reason": str(failure), "captured": len(rows)})
        raise
    write_evidence(folder / "launch.json", launch)
    if not verify_gpu({"gpu_launch": folder / "launch.json", "gpu_counters": folder / "gpu.jsonl"}, "vulkan"):
        raise BlockingIOError("Captured panel batch needs GPU evidence reconciliation")
    artifacts = {name: digest(folder / name) for name in ("launch.json", "gpu.jsonl", "native.jsonl", "server.log")}
    seal = {"run_id": run_id, "git_sha": head, "runtime": pin, "base": registry["base"]["asset"],
            "adapter": spec, "weights": weight, "backend": "vulkan", "launch_flags": FLAGS,
            "handoff_sha256": digest(ROOT / HANDOFF), "roster_sha256": freeze["roster_sha256"],
            "dataset_manifest_sha256": freeze["input_manifest_sha256"], "batch_sha256": fingerprint(batch),
            "provider_contract": PROVIDER_CONTRACT, "gpu_execution": "PASS", "artifacts": artifacts, "results": rows}
    write_evidence(folder / "seal.json", seal)
    return verify_batch(folder, batch, freeze)


def run(suite, assets, output, port, extension_admission):
    from evaluation.aeve.gpu_handoff import require_handoff
    from .admission import git_head
    from .ha11_preflight import checked_runtime

    enforce_admission(suite, extension_admission)
    head, handoff = git_head(), require_handoff(ROOT)
    checked = checked_runtime(assets)
    cases, input_sha = load_inputs(suite)
    batches, freeze = build_plan(suite, cases, input_sha)
    output.mkdir(parents=True, exist_ok=True)
    with gpu_lock(output, "panel.lock"):
        contract = output / "freeze.json"
        registered = freeze | {"git_sha": head}
        if contract.exists() and json.loads(contract.read_bytes()) != registered:
            raise ValueError("Resume from the original panel source and roster identities")
        write_json(contract, registered)
        count = 0
        for number, batch in enumerate(batches):
            folder = output / f"batch-{number:03d}"
            if folder.exists():
                if not (folder / "seal.json").is_file():
                    raise BlockingIOError(f"Unsealed reservation requires reconciliation in batch {number}")
                sealed = verify_batch(folder, batch, freeze)
            else:
                sealed = execute_batch(folder, batch, freeze, cases, assets, port, checked, handoff, head)
            count += len(sealed["results"])
            print(f"{suite} {count}/{freeze['planned']} sealed", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=("transfer", "tc-extension"))
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--port", type=int, default=18757)
    parser.add_argument("--extension-admission", type=Path)
    args = parser.parse_args()
    if args.assets is None and args.output is None:
        print(json.dumps(plan(args.suite)[1], indent=2))
    elif args.assets is not None and args.output is not None:
        run(args.suite, args.assets.resolve(strict=True), args.output.resolve(), args.port, args.extension_admission)
    else:
        parser.error("Physical execution requires both --assets and --output")


if __name__ == "__main__":
    main()
