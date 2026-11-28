"""Reproduce or verify the frozen AGENTIC-PLAN-V1 artifacts."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

from .author import author
from .contract import FINAL_PROMPT, POLICY, THRESHOLDS_PCT, TOOLS, TRACK_PROMPTS

FROZEN = Path(__file__).resolve().parent
SUITE = "AGENTIC-PLAN-V1"
PANEL_SALT = "IJ07-AGENTIC-PLAN-V1-repeat-panel-v1"
PANEL_SEEDS = [41909, 81563, 170003]
SOURCES = ("author.py", "contract.py", "freeze.py", "oracle.py", "sandbox.py", "../tool_calling_v2/oracle.py")


def repeat_panel(public, private):
    variants = {graph["case_id"]: graph["variant"] for graph in private}
    strata = defaultdict(lambda: defaultdict(list))
    for case in public:
        strata[case["level"]][variants[case["case_id"]], case["language"]].append(case)
    selected = []
    for level in sorted(strata):
        buckets = strata[level]
        for bucket in buckets.values():
            bucket.sort(key=lambda case: sha256(f"{PANEL_SALT}/{case['case_id']}".encode()).digest())
        iterated = [case for index in range(max(map(len, buckets.values()))) for key in sorted(buckets)
                    for case in buckets[key][index:index + 1]]
        selected.extend({key: case[key] for key in ("case_id", "level", "language")} for case in iterated[:20])
    return {"suite": SUITE, "panel_id": PANEL_SALT, "seeds": PANEL_SEEDS, "tracks": ["A", "P"], "cases": selected}


def build():
    authored = [author(level, index) for level in range(8) for index in range(100)]
    public = [case for case, _ in authored]
    private = [graph for _, graph in authored]
    return public, private, repeat_panel(public, private)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def artifacts():
    public, private, panel = build()
    protocol = {"suite": SUITE, "policy": POLICY, "tracks": TRACK_PROMPTS, "final": FINAL_PROMPT,
                "thresholds_pct": THRESHOLDS_PCT,
                "tools": {name: {"description": spec[0], "arguments": spec[1], "result_fields": spec[2]}
                          for name, spec in TOOLS.items()}}
    rows = {
        "datasets/holdout.jsonl": b"".join(map(encode, public)),
        "datasets/repeat_panel.json": encode(panel),
        "datasets/protocol.json": encode(protocol),
        "task_graphs/holdout.jsonl": b"".join(map(encode, private)),
    }
    manifest = {"suite": SUITE, "schema_version": 1, "evidence_class": "synthetic_dataset_freeze",
                "case_count": len(public), "repeat_case_count": len(panel["cases"]),
                "level_counts": dict(Counter(case["level"] for case in public)),
                "domain_counts": dict(Counter(case["domain"] for case in public)),
                "language_counts": dict(Counter(case["language"] for case in public)),
                "artifact_sha256": {name: sha256(data).hexdigest() for name, data in rows.items()},
                "implementation_sha256_normalized_lf": {
                    name: sha256((FROZEN / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                    for name in SOURCES},
                "live_model_status": "NOT_RUN"}
    rows["datasets/manifest.json"] = encode(manifest)
    return rows, manifest


def verify(directory):
    rows, manifest = artifacts()
    for name, data in rows.items():
        path = directory / name
        if not path.is_file() or path.read_bytes() != data:
            raise ValueError(f"frozen artifact missing or changed: {name}")
    return manifest


def freeze(directory):
    rows, _ = artifacts()
    for name, data in rows.items():
        path = directory / name
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"refusing to overwrite differing frozen artifact: {name}")
    for name, data in rows.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(data)
    return verify(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "verify"))
    parser.add_argument("--directory", type=Path, default=FROZEN)
    args = parser.parse_args()
    method = freeze if args.mode == "freeze" else verify
    print(json.dumps(method(args.directory), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
