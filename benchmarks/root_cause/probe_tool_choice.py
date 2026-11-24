"""Compare HTTP rejection and neighboring valid tool choices before and after the fix."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from benchmarks.competitive_slm.admission import TOOLS, cpu_server
from benchmarks.root_cause.generation_capture import protocol_reply
from benchmarks.root_cause.historical_replay import ALIAS, ROOT, legacy


VECTORS = (
    ("omitted", {}),
    ("null", {"tool_choice": None}),
    ("auto", {"tool_choice": "auto"}),
    ("none", {"tool_choice": "none"}),
    ("required", {"tool_choice": "required"}),
    ("invalid-string", {"tool_choice": "undefined_lookup"}),
    ("invalid-number", {"tool_choice": 44}),
    ("invalid-object", {"tool_choice": {"type": "function", "function": {"name": "undefined_lookup"}}}),
)


def probe(binary, port, output, label):
    model = (ROOT / "models/MiniCPM5-2B-GGUF/MiniCPM5-2B-Q8_0.gguf").resolve()
    result = {"exe_sha256": legacy.sha256_of(binary), "runtime_dll_sha256": {
        file.name: legacy.sha256_of(file) for file in sorted(binary.parent.glob("*.dll"))
    }, "model_sha256": legacy.sha256_of(model), "cases": {}}
    with cpu_server(binary, model, port, output / f"{label}.log", ALIAS) as (client, build):
        result["build"] = build
        for label, choice in VECTORS:
            for stream in (False, True):
                body = {
                    "model": ALIAS, "messages": [
                        {"role": "user", "content": "Use lookup_account for Orchid Works."},
                    ],
                    "tools": TOOLS, "temperature": 0, "seed": 7107, "max_tokens": 64,
                    "chat_template_kwargs": {"enable_thinking": False}, "stream": stream,
                    **choice,
                }
                status, _, raw = client.post("/v1/chat/completions", body)
                row = {"request": body, "status": status, "response": raw.decode("utf-8")}
                if status == 200:
                    reply = protocol_reply(raw, stream)
                    message = reply["choices"][0]["message"]
                    row["semantic_wire"] = {
                        "finish_reason": reply["choices"][0]["finish_reason"],
                        "content": message.get("content") or "",
                        "calls": [call["function"] for call in message.get("tool_calls", [])],
                    }
                result["cases"][f"{label}-{'sse' if stream else 'json'}"] = row
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--patched", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", default=8096, type=int, choices=range(1024, 65536), metavar="PORT")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    start = legacy.utc_now()
    original = probe(args.original.resolve(), args.port, output, "original")
    patched = probe(args.patched.resolve(), args.port, output, "patched")
    outcomes = {}
    for key, first in original["cases"].items():
        second = patched["cases"][key]
        if key.startswith(("invalid-number", "invalid-object")):
            ok = first["status"] == 200 and second["status"] == 400
        elif key.startswith("invalid-string"):
            ok = first["status"] == second["status"] == 400
        else:
            ok = first["status"] == second["status"] == 200 and first["semantic_wire"] == second["semantic_wire"]
        outcomes[key] = "PASS" if ok else "FAIL"
    legacy.write_json(output / "evidence.json", {
        "run_id": "ij07-tool-choice-" + uuid4().hex, "git": legacy.git_state(), "backend": "cpu",
        "started_utc": start, "finished_utc": legacy.utc_now(), "original": original, "patched": patched,
        "outcomes": outcomes,
    })
    print(outcomes)
    return int("FAIL" in outcomes.values())


if __name__ == "__main__":
    raise SystemExit(main())
