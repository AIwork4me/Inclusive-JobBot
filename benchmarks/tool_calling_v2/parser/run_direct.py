"""Run the native Windows or Linux parser probe and record diagnostic evidence."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import platform
import subprocess
import tempfile
import uuid
from pathlib import Path

from .assessment import assess, validators_for
from .fixtures import V1, build


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--probe", type=Path, required=True)
    cli.add_argument("--chat-template", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--upstream-commit", required=True)
    cli.add_argument("--patch", type=Path, action="append", default=[])
    cli.add_argument("--lexical", action="store_true")
    cli.add_argument("--require-native-pass", action="store_true")
    opts = cli.parse_args()
    if opts.output.exists():
        cli.error("Output already exists. Choose a new evidence path.")
    if len(opts.upstream_commit) != 40 or any(char not in "0123456789abcdef" for char in opts.upstream_commit):
        cli.error("Specify the exact upstream source commit")

    data = build(opts.lexical)
    original = json.loads(V1.read_text(encoding="utf-8"))
    raw_fixtures = original["fixtures"] + data["fixtures"]
    probe_input = {"tools": data["tools"], "fixtures": raw_fixtures}
    wire = json.dumps(probe_input, ensure_ascii=True, sort_keys=True).encode("ascii")
    started = stamp()
    opts.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=opts.output.resolve().parent) as scratch:
        input_path = Path(scratch) / "suite.json"
        input_path.write_bytes(wire)
        run = subprocess.run(
            [str(opts.probe.resolve()), str(opts.chat_template.resolve()), str(input_path)],
            capture_output=True, check=True, timeout=300,
        )
    rows = json.loads(run.stdout)
    if [row["id"] for row in rows] != [fixture["id"] for fixture in raw_fixtures]:
        raise ValueError("Native probe fixture order or coverage changed")

    validators = validators_for(data["tools"])
    expanded = [
        {**row, **assess(fixture, row, validators)}
        for fixture, row in zip(data["fixtures"], rows[len(original["fixtures"]):], strict=True)
    ]
    counts = {
        dimension: dict(collections.Counter(row[dimension] for row in expanded))
        for dimension in ("native", "strict_arguments", "parser_stream_parity")
    }
    evidence = {
        "run_id": "ij06-native-" + uuid.uuid4().hex,
        "evidence_type": "native C++ parser only; fixed inputs; no model execution",
        "platform": platform.system(),
        "upstream_commit": opts.upstream_commit,
        "patch_sha256": [sha(patch) for patch in opts.patch],
        "probe_sha256": sha(opts.probe),
        "probe_source_sha256": sha(Path(__file__).with_name("native_probe.cpp")),
        "assessment_source_sha256": sha(Path(__file__).with_name("assessment.py")),
        "chat_template_sha256": sha(opts.chat_template),
        "fixture_version": data["version"],
        "probe_input_sha256": hashlib.sha256(wire).hexdigest(),
        "fixture_v1_sha256": sha(V1),
        "started_utc": started,
        "finished_utc": stamp(),
        "counts": counts,
        "original_fixture_observations": rows[:len(original["fixtures"])],
        "expanded_fixture_results": expanded,
    }
    opts.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(counts))
    return int(opts.require_native_pass and any(counts[dimension].get("FAIL") for dimension in counts))


if __name__ == "__main__":
    raise SystemExit(main())
