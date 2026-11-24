#!/usr/bin/env python3
"""Run fixed MiniCPM5 outputs through llama-server's native parser."""

from __future__ import annotations

import argparse
import collections
import json
import sys
import urllib.request
import uuid

from run_benchmark import HERE, chat, git_state, output_lock, parse_tool_arguments, utc_now, write_json
from server_identity import ROOT, read_json, server_identity, sha256_of

FIXTURE_PATH = HERE.parent / "fixtures/minicpm5_parser_fixtures.json"


def assistant_prefix(native_output: str) -> dict:
  message = {"role": "assistant", "content": native_output}
  if native_output.startswith("<think>\n"):
    reasoning, marker, content = native_output.removeprefix("<think>\n").partition("\n</think>\n\n")
    if marker:
      message.update(reasoning_content=reasoning, content=content)
  return message


def eos_token_id(base_url: str) -> int:
  with urllib.request.urlopen(base_url + "/props", timeout=10) as response:
    eos = json.load(response)["eos_token"]
  body = json.dumps({"content": eos, "add_special": False, "parse_special": True}).encode("utf-8")
  request = urllib.request.Request(base_url + "/tokenize", data=body, headers={"Content-Type": "application/json"})
  with urllib.request.urlopen(request, timeout=10) as response:
    (token_id,) = json.load(response)["tokens"]
  return token_id


def score(fixture: dict, message: dict) -> list[str]:
  expected = fixture["expected"]
  try:
    calls = [
        {"name": call["function"]["name"], "arguments": parse_tool_arguments(call["function"]["arguments"])}
        for call in message.get("tool_calls") or []
        if call["type"] == "function" and call["id"]
    ]
  except (KeyError, TypeError, ValueError):
    return ["Malformed structured tool call"]
  failures = []
  if len(calls) != len(message.get("tool_calls") or []):
    failures.append("Malformed structured tool call")
  observed = [json.dumps(call, sort_keys=True) for call in calls]
  if fixture["expect_mode"] == "exact":
    if observed != [json.dumps(call, sort_keys=True) for call in expected["calls"]]:
      failures.append("Parsed calls differ from the fixed expectation")
  elif fixture["expect_mode"] == "no_fabrication":
    allowed = {json.dumps(call, sort_keys=True) for call in expected["allowed_calls"]}
    if any(call not in allowed for call in observed):
      failures.append("Parsed calls include an unapproved name, parameter or value")
    content = (message.get("content") or "").strip()
    if content and content not in fixture["native_output"]:
      failures.append("Returned content was absent from the fixed input")
  else:
    raise ValueError(f"Unknown expectation mode: {fixture['expect_mode']}")

  for field, needle_key in (("content", "content_contains"), ("reasoning_content", "reasoning_contains")):
    if needle_key in expected and expected[needle_key] not in (message.get(field) or ""):
      failures.append(f"{field} lacks the expected text")
  return failures


def run_fixture(base_url: str, alias: str, tools: list[dict], fixture: dict, eos: int) -> dict:
  request = {
      "model": alias,
      "messages": [
          {"role": "user", "content": "Continue the assistant response."},
          assistant_prefix(fixture["native_output"]),
      ],
      "tools": tools,
      "tool_choice": "auto",
      "parallel_tool_calls": True,
      "chat_template_kwargs": {"enable_thinking": False},
      "temperature": 0,
      "max_tokens": 1,
      "logit_bias": {str(eos): 1000},
      "logprobs": True,
      "top_logprobs": 1,
  }
  reply = chat(base_url, request)
  row = {"id": fixture["id"], "kind": fixture["kind"], "wall_ms": reply["wall_ms"]}
  if reply.get("parser_rejected"):
    # The error envelope explicitly identifies rejection by the native parser.
    # There is no successful response or token trace for rejected fixtures.
    valid = fixture["expect_mode"] == "exact"
    return {
        **row, "parser_rejected": True, "status": "FAIL" if valid else "PASS",
        "failures": ["Native parser rejected a valid fixture"] if valid else [],
    }
  if "error" in reply:
    return {**row, "status": "BLOCKED", "failures": [reply["error"]]}
  choice = reply["choices"][0]
  token_trace = [
      {key: token.get(key) for key in ("id", "bytes")}
      for token in (choice.get("logprobs") or {}).get("content", [])
  ]
  row.update(
      usage=reply.get("usage"), finish_reason=choice.get("finish_reason"),
      sampled_tokens=token_trace, message=choice["message"],
  )
  if token_trace != [{"id": eos, "bytes": []}] or (reply.get("usage") or {}).get("completion_tokens") != 1:
    return {**row, "status": "BLOCKED", "failures": ["Could not verify that the model emitted only EOS"]}
  failures = score(fixture, choice["message"])
  return {**row, "status": "FAIL" if failures else "PASS", "failures": failures}


def main() -> int:
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--base-url", default="http://127.0.0.1:8080")
  parser.add_argument("--model", default="minicpm5-2b")
  parser.add_argument("--output", default="evidence/IJ0/protocol/parser_fixtures")
  args = parser.parse_args()
  output = ROOT / args.output
  output.mkdir(parents=True, exist_ok=True)
  with output_lock(output):
    evidence = output / "fixtures.json"
    if evidence.exists():
      parser.error("Fixture evidence already exists. Choose a new output directory.")
    engine, server, session = server_identity(args.base_url, args.model)
    document = read_json(FIXTURE_PATH)
    eos = eos_token_id(args.base_url)
    run = {
        "schema_version": 1,
        "run_id": f"tc-fixtures-{uuid.uuid4().hex}",
        "started_utc": utc_now(),
        "method": "assistant continuation through the native parser with only EOS sampled",
        "evidence_type": "fixed parser fixtures",
        "engine": engine, "server": server, "session": session, "git": git_state(),
        "fixture_version": document["version"], "fixture_sha256": sha256_of(FIXTURE_PATH),
        "runner_sha256": sha256_of(HERE / "run_parser_fixtures.py"),
        "support_sha256": {name: sha256_of(HERE / name) for name in ("run_benchmark.py", "server_identity.py")},
        "sdk": {"used": False, "version": None},
        "eos_token_id": eos,
    }
    results = []
    for fixture in document["fixtures"]:
      result = run_fixture(args.base_url, args.model, document["tools"], fixture, eos)
      results.append(result)
      print(f"{result['status']} {result['id']} {result['failures']}")
    run["results"] = results
    run["counts"] = dict(collections.Counter(row["status"] for row in results))
    run["finished_utc"] = utc_now()
    write_json(evidence, run)
    print(run["counts"])
    return 0 if run["counts"] == {"PASS": len(results)} else 1


if __name__ == "__main__":
  sys.exit(main())
