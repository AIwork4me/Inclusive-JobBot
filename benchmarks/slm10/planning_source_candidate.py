"""Build and replay the role-separated Planning V2 source candidate."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.aeve.runtime import ROOT, canonical

from . import planning_public_authoring, planning_source_controls
from .planning_roster import ATLAS, SOURCE_VERSION, SUITE, freeze, output_files


OUTPUT = ATLAS / "planning-v2-source-candidate"


def json_line(value):
    return canonical(value) + b"\n"


def author_proof(module, role, inputs, outputs):
    source = Path(module.__file__).resolve()
    return json_line({
        "role": role,
        "authoring": "separate AI authoring assignment within the same project",
        "inputs": inputs,
        "outputs": outputs,
        "source": source.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(source.read_bytes()).hexdigest(),
    })


def build_bundle():
    cases = list(planning_public_authoring.public_cases())
    bundle = {
        "holdout-public.jsonl": b"".join(map(json_line, cases)),
        "holdout-controls.jsonl": b"".join(
            json_line(planning_source_controls.build_control(case)) for case in cases
        ),
    }
    proofs = {
        "public_authoring": ("public-authoring.json", author_proof(
            planning_public_authoring, "codex-planning-public",
            ["mission requirements", "public Planning V2 contract"],
            ["task", "public fields", "tool schemas", "limits"],
        )),
        "world_and_witness_authoring": ("world-witness-authoring.json", author_proof(
            planning_source_controls, planning_source_controls.AUTHOR_ROLE,
            ["public task", "public contract"],
            ["synthetic worlds", "witnesses", "terminal facts", "host events", "negative controls"],
        )),
    }
    bundle["manifest.json"] = json_line({
        "version": SOURCE_VERSION, "mission": "IJ-SLM-1.0", "suite": SUITE,
        "partition": "sealed_holdout", "origin": "independent_synthetic_authoring",
        "artifacts": {name: sha256(payload).hexdigest() for name, payload in bundle.items()},
        "authoring_sources": {
            role: {"path": name, "sha256": sha256(payload).hexdigest()}
            for role, (name, payload) in proofs.items()
        },
    })
    bundle.update({name: payload for name, payload in proofs.values()})
    return bundle


def verify_candidate(source, source_manifest_sha256):
    result = freeze(source, source_manifest_sha256)
    report = json.loads(result["manifest.json"])
    return {
        "version": "IJ-SLM-AGENTIC-PLAN-V2-SOURCE-CANDIDATE/0.1",
        "source_manifest_sha256": source_manifest_sha256,
        "software_world_replay": "PASS",
        "world_replay_by_level": report["world_replay_by_level"],
        "verifier_sources": report["sources"],
        "software_roster_sha256": report["roster_sha256"],
        "software_roster_slots": report["allocation"]["suite_totals"][SUITE],
        "release_review": "NOT_RUN",
        "formal_freeze": "NOT_RUN",
        "formal_dispatch": "BLOCKED",
        "formal_trials_recorded": 0,
    }


def candidate():
    bundle = build_bundle()
    pin = sha256(bundle["manifest.json"]).hexdigest()
    with TemporaryDirectory(prefix="ijslm-planning-source-") as temp:
        source = Path(temp)
        output_files(source, bundle, False)
        certificate = verify_candidate(source, pin)
    return bundle, certificate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    bundle, certificate = candidate()
    output_files(args.output, bundle | {"candidate-verification.json": json_line(certificate)}, not args.write)
    print(json.dumps({"source_cases": sum(row["cases"] for row in certificate["world_replay_by_level"].values()),
                      **{key: certificate[key] for key in ("source_manifest_sha256", "software_world_replay",
                                                           "release_review", "formal_freeze", "formal_dispatch")}}))


if __name__ == "__main__":
    main()
