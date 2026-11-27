"""Publish and replay the synthetic P0-B D/F evidence without the workstation SDK."""

import argparse
import gzip
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.gpu_handoff import HANDOFF
from evaluation.aeve.runtime import ROOT, canonical, fingerprint

from . import online_compensation as run
from . import online_compensation_score as scorer
from .multitool_v2_statistics import observer_identity
from .portable import portable
from .sdk_wave_queue import verify_gpu_artifact


OUTPUT = ROOT / "evidence/IJSLM/online-compensation"
REGISTRY = ROOT / "atlas/slm/v1.0/model_registry.json"
CAPTURE_SHA = "0597fb9d593f3db3e9885086091844580ca20d56"
FILES = ("capture.json.gz", "gpu.jsonl.gz", "score.json")


def json_file(path, data):
    raw = canonical(data) + b"\n"
    check_text(raw)
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == ".gz" else raw)


def read_file(path):
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    check_text(raw)
    return json.loads(raw)


def make_attempt(attempt, spec, candidate):
    result = portable(attempt)
    for original, event in zip(attempt["wire"], result["wire"], strict=True):
        raw_sdk_request = event.pop("request", None)
        if raw_sdk_request is not None:
            event["private_sdk_request_sha256"] = sha256(original["request"].encode()).hexdigest()
        if not event.get("provider_request_id"):
            continue
        # The exact outbound provider request is retained. The SDK seed message
        # below is a public input for replay, since the original SDK message
        # also embeds workstation paths and per-session workspace metadata.
        alias = f"ijslm-candidate-{candidate.lower()}"
        prompt = run.prompt_text(run.PUBLIC[spec["case_id"]][1], attempt["profile"])
        event["request"] = canonical({"model": alias, "messages": [{"role": "user", "content": prompt}]}).decode()
        if original.get("response_capture_complete") is True and "private_response_hex" in original:
            event["response"] = bytes.fromhex(original["private_response_hex"]).decode()
        if event.get("source_generation") is not None:
            event["private_native_source_sha256"] = fingerprint(original["source_generation"])
            event["native_prompt_token_count"] = len(original["source_generation"]["prompt_token_ids"])
    return result


def read_public(folder, candidate):
    data = read_file(folder / "capture.json.gz")
    meta, launch, trials = (data[key] for key in ("run", "launch", "trials"))
    registry = read_file(REGISTRY)["models"][candidate]["asset"]
    engine, sdk, harness = observer_identity()
    lease = launch["gpu_lease"]
    handoff = read_file(ROOT / HANDOFF)["lease"]
    if (meta["candidate"] != candidate or meta["git_sha"] != CAPTURE_SHA or meta["backend"] != "vulkan"
            or meta["sdk_version"] != sdk or meta["harness_sha256"] != harness or meta["engine_sha256"] != engine
            or meta["handoff_sha256"] != digest(ROOT / HANDOFF) or meta["model_registry_sha256"] != digest(REGISTRY)
            or meta["source_sha256"] != run.source_hashes() or meta["gpu_execution"] != "PASS"
            or launch["build"] != meta["engine_build"] or launch["template_sha256"] != meta["template"]["sha256"]
            or any(meta["model"][key] != registry[pin] for key, pin in (
                ("model_sha256", "expected_sha256"), ("runtime_repo", "repo"), ("runtime_revision", "revision")))
            or lease["lease_owner"] != "slm11-online-compensation" or lease["runtime_session"] != meta["run_id"]
            or lease["mission_id"] != "IJ-SLM-1.0"
            or any(lease[key] != handoff[key] for key in ("host_sha256", "gpu_physical_sha256"))):
        raise ValueError("portable physical capture differs from the registered identity")
    counters = gzip.decompress((folder / "gpu.jsonl.gz").read_bytes())
    check_text(counters)
    if sha256(counters).hexdigest() != meta["artifacts"][launch["counter_file"]]:
        raise ValueError("portable GPU sample bytes differ from the private run index")
    verify_gpu_artifact(folder, "gpu.jsonl.gz", launch)
    if len(trials) != len(run.schedule()) or set(meta["trial_sha256"]) != {t["trial_id"] for t in trials}:
        raise ValueError("portable capture lacks a complete matched trial index")

    used = set()
    for trial, spec in zip(trials, run.schedule(), strict=True):
        trial_id = fingerprint([meta["run_id"], spec])
        if trial["trial_id"] != trial_id or any(trial[key] != value for key, value in spec.items()):
            raise ValueError("portable trial identity differs from the registered schedule")

        def invoke(profile, n):
            attempt = trial["attempts"][n]
            scorer.verified_attempt(attempt, f"{trial_id}-{n}", spec, profile, candidate)
            for event in attempt["wire"]:
                if event.get("native_evidence", {}).get("status") != "PASS":
                    continue
                trace = event["source_generation"]
                completion = event["completion_id"]
                if (completion in used or trace["completion_id"] != completion or trace["stream"] is not True
                        or event["native_prompt_token_count"] != event["usage"]["prompt_tokens"]
                        or len(trace["sampled_token_ids"]) != event["usage"]["completion_tokens"]):
                    raise ValueError("portable native observation differs from the provider completion")
                used.add(completion)
            return attempt

        replayed = run.apply_arm(spec["arm"], invoke)
        if (len(trial["attempts"]) != len(replayed["attempts"])
                or any(trial[key] != replayed[key] for key in ("delivered", "host_normalized", "retry_reason"))):
            raise ValueError("portable intervention differs from the recorded online behavior")
    return scorer.replay(meta, trials) | {
        "private_run_sha256": data["private_run_sha256"],
        "scorer_sha256": digest(Path(scorer.__file__)),
    }


def export_candidate(source, output, candidate):
    private = source / candidate
    metadata, captures, reserved = scorer.read_capture(private)
    private_result = scorer.replay(metadata, captures, reserved)
    if private_result["physical"] != "PASS":
        raise ValueError("cannot publish the complete experiment until all private captures are verified")
    destination = output / candidate
    destination.mkdir(parents=True)
    launch = json.loads((private / "launch.json").read_bytes())
    raw_counters = (private / launch["counter_file"]).read_bytes()
    check_text(raw_counters)
    (destination / "gpu.jsonl.gz").write_bytes(gzip.compress(raw_counters, mtime=0))
    launch.pop("args")
    trials = [
        trial | {"attempts": [make_attempt(a, trial, candidate) for a in trial["attempts"]]}
        for trial in captures
    ]
    run_sha = digest(private / "run.json")
    json_file(destination / "capture.json.gz", {
        "run": metadata, "launch": launch, "trials": trials, "private_run_sha256": run_sha,
    })
    public_result = read_public(destination, candidate)
    if any(public_result[key] != value for key, value in private_result.items()):
        raise ValueError("publication projection changes the physical experiment score")
    json_file(destination / "score.json", public_result)


def export(source, output):
    for candidate in run.CANDIDATES:
        export_candidate(source, output, candidate)
    json_file(output / "manifest.json", inventory(output))


def inventory(output):
    return {"version": run.VERSION, "scope": "synthetic terminal output through the real local SDK and Radeon",
            "physical_trials": 192, "formal_trial_attribution": 0, "capture_git_sha": CAPTURE_SHA,
            "files": {f"{candidate}/{name}": digest(output / candidate / name)
                      for candidate in run.CANDIDATES for name in FILES}}


def verify(output=OUTPUT):
    manifest = read_file(output / "manifest.json")
    if manifest != inventory(output):
        raise ValueError("portable evidence manifest differs from the archive")
    results = {}
    for candidate in run.CANDIDATES:
        folder = output / candidate
        results[candidate] = read_public(folder, candidate)
        if results[candidate] != read_file(folder / "score.json") or results[candidate]["physical"] != "PASS":
            raise ValueError("portable physical score differs from the replayed evidence")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish-from", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.publish_from:
        with TemporaryDirectory(prefix=".online-compensation-", dir=args.output.parent) as temp:
            staged = Path(temp) / "evidence"
            export(args.publish_from, staged)
            verify(staged)
            staged.rename(args.output)
    verify(args.output)
    print("Verified 192 matched Radeon SDK output trials with zero core attribution.")


if __name__ == "__main__":
    main()
