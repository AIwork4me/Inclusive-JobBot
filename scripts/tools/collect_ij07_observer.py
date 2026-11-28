"""Validate and copy a clean observer control from local to publishable evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from benchmarks.root_cause.generation_capture import protocol_reply
from scripts.tools.verify_ij06_evidence import verify_gpu


ARMS = ("R0-V", "R0-R", "R1-V", "R1-R", "R0-V-off")


def semantic_wire(item):
    reply = protocol_reply(item["raw_response"].encode("utf-8"), item["request"]["stream"])
    choice = reply["choices"][0]
    message = choice["message"]
    return (
        choice["finish_reason"], message.get("content") or "", message.get("reasoning_content") or "",
        [tool["function"] for tool in message.get("tool_calls", []) or []],
    )


def copy_arm(source, dest):
    summary = json.loads((source / "summary.json").read_bytes())
    run = json.loads((source / "run.json").read_bytes())
    if run["configuration"]["git"]["dirty"] is not False or len(run["sessions"]) != 1:
        raise ValueError("observer comparison requires one clean launch")
    launch = run["sessions"][0]
    raw = (source / "results.jsonl").read_bytes()
    if hashlib.sha256(raw).hexdigest() != summary["result_sha256"]:
        raise ValueError("observer result digest mismatch")
    dest.mkdir()
    for file in ("run.json", "summary.json", "results.jsonl", launch["counter_file"], launch["trace_file"]):
        if file:
            shutil.copyfile(source / file, dest / file)
    launch_path = dest / "launch.json"
    launch_path.write_bytes((json.dumps({**launch, "status": "PASS"}, indent=2) + "\n").encode())
    if not verify_gpu({"gpu_launch": launch_path, "gpu_counters": dest / launch["counter_file"]}, launch["backend"]):
        raise ValueError("observer launch lacks physical Radeon activity")
    return run["configuration"], [json.loads(line) for line in raw.splitlines()]


def compare(on, off):
    config_on, rows_on = on
    config_off, rows_off = off
    if ({**config_on, "observe": False} != config_off or config_on["observe"] is not True):
        raise ValueError("control changed an input besides the observer switch")
    pairs = []
    for row_on, row_off in zip(rows_on, rows_off, strict=True):
        if row_on["id"] != row_off["id"]:
            raise ValueError("control case identities differ")
        for step, (one, two) in enumerate(zip(row_on["capture"], row_off["capture"], strict=True), 1):
            wire_equal = semantic_wire(one) == semantic_wire(two)
            stream = one["request"]["stream"]
            row = {"case_id": row_on["id"], "request_index": step, "stream": stream, "wire_equal": wire_equal}
            if not stream:
                source = one["source_generation"]
                disabled = json.loads(two["raw_response"])["__verbose"]
                row["exact_tokens_and_bytes"] = (
                    source["sampled_token_ids"] == disabled["tokens"]
                    and source["pre_parser_bytes_hex"] == disabled["content"].encode().hex()
                )
            pairs.append(row)
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    arms = {arm: copy_arm(args.source / arm, args.output / arm) for arm in ARMS}
    pairs = compare(arms["R0-V"], arms["R0-V-off"])
    passed = all(row["wire_equal"] and row.get("exact_tokens_and_bytes", True) for row in pairs)
    summary = {
        "status": "PASS" if passed else "FAIL", "pairs": pairs,
        "exact_nonstream_pairs": sum(row.get("exact_tokens_and_bytes", False) for row in pairs),
        "native_stream_token_control": "NOT_RUN",
        "capture_enabled_requests": {
            name: sum(len(row["capture"]) for row in arm[1]) for name, arm in arms.items() if name != "R0-V-off"
        },
    }
    (args.output / "comparison.json").write_bytes((json.dumps(summary, indent=2) + "\n").encode())
    print(summary["status"], len(pairs), "wire comparisons")
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())
