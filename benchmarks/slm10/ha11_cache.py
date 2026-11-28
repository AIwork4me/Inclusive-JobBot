"""Run the LFM3 cache and checkpoint factorial under the single Radeon lease."""

import argparse
from collections import Counter
from itertools import product
import json
from pathlib import Path
import re
from uuid import uuid4

from audit import write_evidence
from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT, fingerprint
from scripts.tools.verify_ij06_evidence import verify_gpu

from . import lfm3_ha_admission as ha


FACTORS = {"default": (False, False), "cache_off": (True, False),
           "checkpoints_off": (False, True), "both_off": (True, True)}
WEIGHTS = ("Original", "HA-O", "HA-P", "HA-H")
DISTRACTOR = "A separate inventory session has products, lot numbers, and unrelated measurements. " * 24
PROMPTS = {"admission_request_cache_off": (False, ha.PROMPTS),
           "warm_long_prefix": (True, tuple(DISTRACTOR * 4 + item for item in ha.PROMPTS))}


def cache_flags(cache_off, checkpoints_off):
    base = list(ha.FLAGS)
    for remove, flag in [(not cache_off, "--cache-ram"), (not checkpoints_off, "--ctx-checkpoints")]:
        if remove:
            index = base.index(flag)
            del base[index:index + 2]
    return tuple(base)


def same_numerics(left, right):
    return (left["prefix"] == right["prefix"] and left["tokens"] == right["tokens"]
            and len(left["logprobs"]) == len(right["logprobs"])
            and all(ha.equivalent(a, b) for a, b in zip(left["logprobs"], right["logprobs"], strict=True)))


def equivalent(left, right):
    return bool(left) and len(left) == len(right) and all(map(same_numerics, left, right))


def classify_unknown(observed, zero, one):
    zero_match, one_match = equivalent(observed, zero), equivalent(observed, one)
    return {(True, False): "SCALE_ZERO", (False, True): "SCALE_ONE",
             (True, True): "INDETERMINATE", (False, False): "OTHER"}[zero_match, one_match]


def read_native_scores(reply):
    probabilities = reply["completion_probabilities"]
    tokens = [entry["id"] for entry in probabilities]
    if not tokens or tokens != reply["tokens"] or any(type(token) is not int or token < 0 for token in tokens):
        raise ValueError("Native token sequence is missing or inconsistent")
    # The sampling chain can choose a token other than the top pre-sampling token.
    scores = []
    for entry in probabilities:
        top = entry["top_logprobs"]
        if not top:
            raise ValueError("Native log-probability ranking is missing")
        scores.append(ha.numeric_row({"completion_probabilities": [entry | {"id": top[0]["id"]}]}))
    return tokens, scores


def sample(client, prompt, cached, scale=None, adapter_id=0):
    status, _, raw = client.post("/tokenize", {"content": prompt, "add_special": True})
    if status != 200:
        raise ValueError("Pinned tokenizer did not complete")
    prefix = json.loads(raw)["tokens"]
    if not prefix or any(type(token) is not int for token in prefix):
        raise ValueError("Invalid pinned token prefix")
    body = {"prompt": prefix, "n_predict": 4, "n_probs": 32, "temperature": -1.0,
            "seed": ha.SEED, "cache_prompt": cached, "post_sampling_probs": False, "return_tokens": True}
    if scale is not None:
        body["lora"] = [{"id": adapter_id, "scale": scale}]
    status, _, raw = client.post("/completion", body)
    if status != 200:
        return {"http_status": status, "response_sha256": fingerprint(raw.hex())}
    reply = json.loads(raw)
    tokens, logprobs = read_native_scores(reply)
    return {"http_status": status, "prefix": prefix, "tokens": tokens,
            "logprobs": logprobs,
            "timings": reply["timings"], "tokens_cached": reply["tokens_cached"]}


def cell(client, adapted, factor):
    output = {}
    for mode, (cached, prompts) in PROMPTS.items():
        stages = [("initial", None), ("repeat", None)] if not adapted else [
            ("scale0", 0.0), ("scale1", 1.0), ("scale1_repeat", 1.0), ("restore0", 0.0),
        ]
        probes = {key: [] for key, _ in stages}
        for prompt in prompts:
            for key, scale in stages:
                probes[key].append(sample(client, prompt, cached, scale))
        before = probes["scale1_repeat" if adapted else "repeat"]
        sample(client, "Unrelated isolated session. " + DISTRACTOR, cached)
        after = probes["after_other_input"] = [sample(client, prompt, cached, 1.0 if adapted else None)
                                                for prompt in prompts]
        repeated = (probes["scale1"], probes["scale1_repeat"]) if adapted else (probes["initial"], probes["repeat"])
        checks = {"same_prefix_repeat": ha.verdict(equivalent(*repeated)),
                  "other_input_isolation": ha.verdict(equivalent(before, after))}
        if adapted:
            checks["scale0_restoration"] = ha.verdict(equivalent(probes["scale0"], probes["restore0"]))
            if factor == "both_off" and not cached:
                unknown = probes["unknown_id"] = [sample(client, prompt, False, 1.0, adapter_id=99)
                                                 for prompt in prompts]
                checks["native_unknown_id_rejected"] = ha.verdict(all(400 <= r["http_status"] < 500 for r in unknown))
                if all(r["http_status"] == 200 for r in unknown):
                    checks["native_unknown_id_effect"] = classify_unknown(unknown, probes["restore0"], probes["scale1"])
        output[mode] = {"checks": checks, "probes": probes}
    return output


def memory_and_state(folder):
    counters = [json.loads(line) for line in (folder / "gpu.jsonl").read_bytes().splitlines()]
    keys = {"gpu_process_memory": "committed_bytes", "process": "private_bytes"}
    memory = {field: max((row[field] for row in counters if row.get("kind") == kind), default=None)
              for kind, field in keys.items()}
    log = (folder / "server.log").read_text(encoding="utf-8", errors="replace")
    markers = Counter()
    for line in log.splitlines():
        for key, pattern in {
            "checkpoint_creation": r"creat(?:ed|ing) (?:context )?checkpoint",
            "checkpoint_restore": r"restor(?:ed|ing) (?:context )?checkpoint",
            "cache_load": r"(?:loading|loaded) (?:prompt )?cache",
        }.items():
            markers[key] += bool(re.search(pattern, line, flags=re.IGNORECASE))
    return {"peak_memory_bytes": memory, "context_state_log_events": dict(markers),
            "shortconv_tensor_state": "NOT_RUN"}


def run(assets, output, port):
    from .admission import git_head
    from .ha11_preflight import checked_runtime

    registry, pin, model, binary, _ = checked_runtime(assets)
    handoff = require_handoff(ROOT)
    output.mkdir(parents=True, exist_ok=False)
    run_id = "lfm3-ha11-cache-" + uuid4().hex
    report = {"run_id": run_id, "git_sha": git_head(), "runtime": pin, "backend": "vulkan",
              "base": registry["base"]["asset"], "seed": ha.SEED, "dataset_sha256": fingerprint(PROMPTS),
              "handoff_sha256": digest(ROOT / HANDOFF), "factors": FACTORS, "cells": {},
              "core_trial_attribution": 0}
    for factor, weight in product(FACTORS, WEIGHTS):
        name = factor + "-" + weight
        folder = output / name
        folder.mkdir()
        spec = None
        if weight != "Original":
            spec, = [item for path, item in registry["adapters"][weight]["artifacts"].items() if path.endswith(".gguf")]
        lora = ha.pinned_file(assets, spec) if spec else None
        flags = cache_flags(*FACTORS[factor])
        with ha.server(binary, model, lora, port, folder, pin, run_id + "-" + name, handoff,
                       launch_flags=flags, sampler_seconds=1800) as (client, launch):
            profiles = cell(client, lora is not None, factor)
        launch_file = folder / "launch.json"
        write_evidence(launch_file, launch)
        counters = folder / "gpu.jsonl"
        gpu_status = "PASS" if verify_gpu({"gpu_launch": launch_file, "gpu_counters": counters}, "vulkan") else "BLOCKED"
        if weight != "Original":
            base = report["cells"][factor + "-Original"]["profiles"]
            for mode, data in profiles.items():
                data["checks"]["scale0_original_equivalence"] = ha.verdict(equivalent(
                    data["probes"]["scale0"], base[mode]["probes"]["initial"]))
        report["cells"][name] = {"weight": weight, "factor": factor, "flags": flags,
                                 "adapter_sha256": spec["sha256"] if spec else None,
                                 "gpu_counters_sha256": digest(counters), "launch_sha256": digest(launch_file),
                                 "server_log_sha256": digest(folder / "server.log"), "gpu_execution": gpu_status,
                                 "profiles": profiles, **memory_and_state(folder)}
        write_evidence(output / "report.json", report)
        print(name, gpu_status, {mode: data["checks"] for mode, data in profiles.items()}, flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18757)
    args = parser.parse_args()
    report = run(args.assets.resolve(strict=True), args.output.resolve(), args.port)
    print(report["run_id"], len(report["cells"]))


if __name__ == "__main__":
    main()
