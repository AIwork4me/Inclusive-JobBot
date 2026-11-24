"""Compare decoder profiles on unchanged MULTITOOL-V1 Radeon responses."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from benchmarks.root_cause.generation_capture import check_gateway
from benchmarks.multitool_v1.dataset import canonical, load_freeze
from model_gateway.openai_protocol import MAX_CALLS, MAX_NONSTREAM_CALLS


def probe(source):
    trials = []
    freeze = load_freeze()
    with gzip.open(source, "rt", encoding="utf-8") as file:
        for line, wire in enumerate(file, 1):
            checkpoint = json.loads(wire)
            row = checkpoint["row"]
            for turn, request in enumerate(row["requests"]):
                if request["gateway_protocol"].get("error") != "invalid tool call batch":
                    continue
                raw = request["raw_response"].encode()
                native = json.loads(raw)["choices"][0]["message"]["tool_calls"]
                samples = bytes.fromhex(request["source_generation"]["pre_parser_bytes_hex"])
                nodes = freeze.active[row["case_id"]].oracle["nodes"]
                parallel_match = None
                if turn == 0 and all(not node["depends_on"] for node in nodes):
                    expected = Counter((node["tool"], canonical(node["arguments"])) for node in nodes)
                    observed = Counter((call["function"]["name"], canonical(json.loads(call["function"]["arguments"])))
                                       for call in native)
                    parallel_match = observed == expected
                trials.append({
                    "case_id": row["case_id"], "case_verdict": row["status"], "turn": turn,
                    "checkpoint_line": line, "checkpoint_sha256": checkpoint["sha256"],
                    "native_call_count": len(native), "pre_parser_complete_function_tags": samples.count(b"</function>"),
                    "exact_independent_plan_tool_and_argument_match": parallel_match,
                    "wire_sha256": hashlib.sha256(raw).hexdigest(),
                    "source_sha256": hashlib.sha256(samples).hexdigest(),
                    "default": check_gateway(raw, False),
                    "multitool_profile": check_gateway(raw, False, max_nonstream_calls=MAX_NONSTREAM_CALLS),
                })
    if not trials or any(row["default"]["status"] != "FAIL" for row in trials):
        raise ValueError("expected failures did not reproduce on archived bytes")
    return {
        "scope": "wire-only replay of physical model responses, no model execution or business effects",
        "default_limit": MAX_CALLS, "multitool_profile_limit": MAX_NONSTREAM_CALLS,
        "source_archive_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "trials": trials,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = probe(args.source)
    args.output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode())
    passed = sum(row["multitool_profile"]["status"] == "PASS" for row in result["trials"])
    print(f"{passed}/{len(result['trials'])} replayed batches accepted by bounded profile")


if __name__ == "__main__":
    main()
