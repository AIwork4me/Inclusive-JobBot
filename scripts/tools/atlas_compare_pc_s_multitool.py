"""Compare the complete Qwen3 PC-S MULTITOOL panel by matched trial."""

from argparse import ArgumentParser
from collections import Counter
from hashlib import sha256
import gzip
import json
from pathlib import Path

from benchmarks.job_productivity_v1.statistics import exact_mcnemar, wilson_interval
from benchmarks.multitool_v1.run import digest
from benchmarks.tool_calling_v2.oracle import decode_object, equal
from scripts.tools.atlas_reference_panel import create
from scripts.tools.atlas_progress import document


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJ072/benchmark_validity"
OUTPUT = EVIDENCE / "pc-s-multitool-qwen-pair.json"
STREAM_OUTPUT = EVIDENCE / "pc-s-j-multitool-streaming-pairs.json"


def load(archive, candidate):
    run, coverage = (document(archive / name) for name in ("run.json", "coverage.json"))
    raw = gzip.decompress((archive / "terminal.jsonl.gz").read_bytes())
    config = run["configuration"]
    if (sha256(raw).hexdigest() != coverage["terminal_uncompressed_sha256"]
            or digest(config) != run["fingerprint"] or coverage["run_id"] != run["run_id"]
            or config["candidate"] != candidate or config["git"]["dirty"]
            or coverage["run_end_summary"]["physical_evidence_status"] != "PASS"
            or not coverage["coverage_complete"]):
        raise ValueError("comparison requires a complete physical source archive")
    rows = {}
    for line in raw.splitlines():
        row = json.loads(line)["row"]
        if row["key"] in rows or row["status"] not in {"PASS", "FAIL"}:
            raise ValueError("comparison requires exactly one assessable record per trial")
        rows[row["key"]] = row
    roster = {item["key"] for item in config["roster"]}
    if rows.keys() != roster:
        raise ValueError("matched source rows differ from the original roster")
    return run, rows


def summarize(pairs):
    joint = Counter((row["8B"], row["14B"]) for row in pairs)
    h, j = sum(row["8B"] == "PASS" for row in pairs), sum(row["14B"] == "PASS" for row in pairs)
    return {"pairs": len(pairs), "8B_pass": h, "14B_pass": j,
            "both_pass": joint["PASS", "PASS"], "only_8B": joint["PASS", "FAIL"],
            "only_14B": joint["FAIL", "PASS"], "both_fail": joint["FAIL", "FAIL"],
            "8B_wilson95": wilson_interval(h, len(pairs)), "14B_wilson95": wilson_interval(j, len(pairs)),
            "mcnemar_exact_two_sided_descriptive": exact_mcnemar(joint["PASS", "FAIL"], joint["FAIL", "PASS"])}


def build():
    h_run, h_trials = load(EVIDENCE / "pc-s-multi", "H")
    j_run, j_trials = load(EVIDENCE / "pc-s-j-multi-full", "J")
    left, right = h_run["configuration"], j_run["configuration"]
    if any(left[name] != right[name] for name in ("freeze_sha256", "roster", "limits", "backend", "scope", "panel")):
        raise ValueError("strong references do not share the frozen task protocol")
    pairs = []
    for key in sorted(h_trials):
        lower, upper = h_trials[key], j_trials[key]
        identity = ("case_id", "seed", "category", "depth_bin")
        if any(lower[name] != upper[name] for name in identity):
            raise ValueError(f"mismatched trial in model contrast: {key}")
        pairs.append({**{name: lower[name] for name in identity}, "8B": lower["status"], "14B": upper["status"]})
    by_stratum = {}
    for field in ("category", "depth_bin"):
        by_stratum[field] = {name: summarize([row for row in pairs if row[field] == name])
                             for name in sorted({row[field] for row in pairs})}
    return {"scope": "complete frozen PC-S MULTITOOL model contrast",
            "interpretation": "Matched tasks and budget. Model and runtime source identities can differ.",
            "dataset_sha256": left["freeze_sha256"], "run_ids": {"8B": h_run["run_id"], "14B": j_run["run_id"]},
            "source_commits": {"8B": left["git"]["commit"], "14B": right["git"]["commit"]},
            "overall": summarize(pairs), "strata": by_stratum, "trials": pairs}


def payload(value):
    if isinstance(value, str):
        try:
            return decode_object(value)
        except ValueError:
            return value
    return value


def action_signature(row):
    return [{"tool": call["name"], "arguments": payload(call["arguments_raw"]), "result": call["result"]}
            for call in row["calls"]]


def stream_pairs():
    plain, original = load(EVIDENCE / "pc-s-j-multi-full", "J")
    stream, streamed = load(EVIDENCE / "pc-s-j-multi-stream", "J")
    left, right = plain["configuration"], stream["configuration"]
    strata = create()["multitool_v1"]["selection_by_stratum"]
    selected = {group[0] for group in strata.values()}
    if (left["stream"] or not right["stream"]
            or (left | {"stream": True, "roster": right["roster"]}) != right
            or {row["case_id"] for row in streamed.values()} != selected or not streamed.keys() <= original.keys()):
        raise ValueError("stream pair changed a bound input beyond transport and roster")
    rows = []
    for key, b in sorted(streamed.items()):
        a = original[key]
        responses = []
        for row, expected_stream, content_type in ((a, False, "application/json"), (b, True, "text/event-stream")):
            requests = row["requests"]
            responses.append(bool(requests) and all(
                wire["request"]["stream"] is expected_stream and wire["content_type"] == content_type
                and wire["http_status"] == 200 and wire["gateway_protocol"]["status"] == "PASS"
                for wire in requests))
        outcomes = {"same_strict_outcome": a["status"] == b["status"],
                    "same_actions": equal(action_signature(a), action_signature(b)),
                    "same_final": equal(payload(a["final"]), payload(b["final"])),
                    "verified_transport": all(responses)}
        maximum = {mode: max(Counter(call["turn"] for call in row["calls"]).values(), default=0)
                   for mode, row in (("nonstream", a), ("stream", b))}
        rows.append({"case_id": a["case_id"], "seed": a["seed"], "depth_bin": a["depth_bin"],
                     "nonstream_strict": a["status"], "stream_strict": b["status"],
                     "max_calls_in_a_turn": maximum,
                     **outcomes, "parity": "PASS" if all(outcomes.values()) else "FAIL"})
    return {"scope": "Qwen3-14B physical MULTITOOL streaming and non-streaming matched pairs",
            "nonstream_run_id": plain["run_id"], "stream_run_id": stream["run_id"],
            "source_commit": left["git"]["commit"], "action_budget": left["limits"]["max_proposals"],
            "counts": dict(Counter(row["parity"] for row in rows)), "trials": rows}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--stream-pairs", action="store_true")
    args = parser.parse_args()
    report = stream_pairs() if args.stream_pairs else build()
    output = STREAM_OUTPUT if args.stream_pairs else OUTPUT
    data = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if output.read_bytes() != data:
            parser.error("matched MULTITOOL evidence differs")
    else:
        with output.open("xb") as target:
            target.write(data)
    print(report["counts"] if args.stream_pairs else report["overall"])


if __name__ == "__main__":
    main()
