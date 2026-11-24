"""Calculate three-seed reliability from the complete physical MULTITOOL panel."""

import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path

from benchmarks.competitive_slm.statistics import repeat_summary
from benchmarks.multitool_v1.dataset import canonical, load_freeze


def analyze(source):
    coverage = json.loads((source / "coverage.json").read_bytes())
    if (not coverage["coverage_complete"] or coverage["terminal"] != 300
            or coverage["run_end_summary"]["panel"] != "repeat"):
        raise ValueError("require all 300 frozen repeat trials")
    freeze = load_freeze()
    seeds = freeze.panel["seeds"]
    ids = freeze.panel["case_ids"]
    terminal = (source / "terminal.jsonl.gz").read_bytes()
    raw = gzip.decompress(terminal)
    if hashlib.sha256(raw).hexdigest() != coverage["terminal_uncompressed_sha256"]:
        raise ValueError("MULTITOOL repeat archive digest differs")
    rows, groups = {}, defaultdict(list)
    expected = {(case_id, "repeat", index) for case_id in ids for index in range(1, 4)}
    for line in raw.splitlines():
        row = json.loads(line)["row"]
        key = (row["case_id"], "repeat", seeds.index(row["seed"]) + 1)
        if key not in expected or key in rows or row["status"] not in {"PASS", "FAIL"}:
            raise ValueError("unexpected repeat identity or adjudication state")
        rows[key] = {"status": row["status"],
                     "failure_class": row["findings"][0]["code"] if row["findings"] else None}
    if rows.keys() != expected:
        raise ValueError("incomplete or duplicate selected repeat observations")
    for case_id in ids:
        case = freeze.active[case_id].oracle
        for field in ("category", "depth_bin", "language"):
            groups[f"{field}/{case[field]}"].append(case_id)
    return {
        "run_id": coverage["run_id"], "source_archive_sha256": hashlib.sha256(terminal).hexdigest(),
        "scope": "original Vulkan profile, fixed repeat panel; failure class uses the first recorded finding",
        "all": repeat_summary(rows, ids, seeds),
        "strata": {key: repeat_summary(rows, members, seeds) for key, members in sorted(groups.items())},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = canonical(analyze(args.source))
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != expected:
            parser.exit(1, "FAIL: MULTITOOL reliability report differs\n")
        print("PASS: exact MULTITOOL three-seed analysis")
    else:
        args.output.write_bytes(expected)


if __name__ == "__main__":
    main()
