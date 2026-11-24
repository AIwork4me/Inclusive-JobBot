"""Score one tool-calling benchmark case from what actually happened.

The evaluator looks at requested tool calls, the tools the host executed and
the final answer. It never asks the model to judge itself.

Trace vocabulary used here:

* ``steps`` - one entry per model turn: the raw tool calls it requested, its
  text and its finish reason.
* ``requested`` - every tool call the model requested, in order, with the
  parsed arguments and whether the call is well-formed and declared.
* ``executed`` - names of the tools the host actually ran.
* ``denied`` - names of tools the model asked for that were not authorized.
"""

from __future__ import annotations

import re
import unicodedata

NUMERIC = re.compile(r"^[\d.,]+$")


def equal_argument(want, got) -> bool:
  if type(want) in (int, float) and type(got) in (int, float):
    return round(want, 6) == round(got, 6)
  if type(want) is not type(got):
    return False
  if isinstance(want, dict):
    return want.keys() == got.keys() and all(equal_argument(value, got[key]) for key, value in want.items())
  if isinstance(want, list):
    return len(want) == len(got) and all(equal_argument(left, right) for left, right in zip(want, got))
  if isinstance(want, str):
    return unicodedata.normalize("NFKC", want).strip() == unicodedata.normalize("NFKC", got).strip()
  return want == got


def contains(text: str, needle: str) -> bool:
  """Substring test; numeric needles must not be part of a longer number."""
  haystack = unicodedata.normalize("NFKC", text)
  pin = unicodedata.normalize("NFKC", needle)
  if NUMERIC.match(pin):
    return re.search(r"(?<![\d.])" + re.escape(pin) + r"(?![\d.])", haystack) is not None
  return pin in haystack


def compare_arguments(expected: dict, got) -> tuple[list[str], int, int]:
  """Returns (problems, correct argument count, expected argument count)."""
  problems = []
  correct = 0
  if not isinstance(got, dict):
    return ["arguments are not a JSON object"], 0, len(expected)
  for key, want in expected.items():
    if key not in got:
      problems.append(f"missing argument {key}")
    elif equal_argument(want, got[key]):
      correct += 1
    else:
      problems.append(f"argument {key}: expected {want!r}, got {got[key]!r}")
  for key in sorted(set(got) - set(expected)):
    problems.append(f"unexpected argument {key}")
  return problems, correct, len(expected)


def evaluate_case(case: dict, steps: list[dict], requested: list[dict], executed: list[str], denied: list[str], final_text: str) -> dict:
  expected = case.get("expected", {})
  failures: list[str] = []
  argument_total = 0
  argument_correct = 0

  wanted_first = expected.get("calls")
  if wanted_first is None and expected.get("first_call"):
    wanted_first = [expected["first_call"]]
  if wanted_first:
    first_step = steps[0].get("tool_calls", []) if steps else []
    if len(first_step) != len(wanted_first):
      failures.append(f"first step requested {len(first_step)} call(s), expected {len(wanted_first)}")
    argument_total = sum(len(call["arguments"]) for call in wanted_first)
    for want, got in zip(wanted_first, first_step):
      if got["name"] != want["name"]:
        failures.append(f"first call is {got['name']}, expected {want['name']}")
      else:
        problems, correct, _ = compare_arguments(want["arguments"], got["arguments"])
        failures.extend(problems)
        argument_correct += correct

  sequence = expected.get("sequence")
  if sequence and executed[: len(sequence)] != sequence:
    failures.append(f"executed {executed[: len(sequence)] or executed}, expected {sequence}")

  forbidden = expected.get("forbidden_attempts", [])
  attempted = sorted({name for name in denied if name in forbidden})
  if attempted:
    failures.append(f"forbidden tool requested: {attempted}")

  limit = expected.get("max_tool_calls", case["options"].get("max_steps", 5))
  if len(requested) > limit:
    failures.append(f"{len(requested)} tool call(s), limit is {limit}")

  invalid = [call for call in requested if not call["well_formed"]]
  if invalid:
    failures.append(f"{len(invalid)} malformed or undeclared tool call(s)")

  for step in steps:
    if step.get("error"):
      failures.append(f"request error: {step['error']}")
    if step.get("stream_matches_non_stream") is False:
      failures.append("streaming tool calls differ from non-streaming")

  if case.get("category") == "thinking_separation":
    if not any(step.get("reasoning", "").strip() for step in steps):
      failures.append("missing separate reasoning content")
    if any("<think>" in step.get("content", "") or "</think>" in step.get("content", "") for step in steps):
      failures.append("reasoning tags leaked into visible content")

  if steps and steps[-1].get("tool_calls"):
    failures.append("ended on tool calls without a final answer")
  if not final_text.strip() and not expected.get("allow_empty_answer"):
    failures.append("empty final answer")

  for group in expected.get("final_contains_any", []):
    if not any(contains(final_text, alternative) for alternative in group):
      failures.append(f"answer lacks required fact {group[0]!r}")
  for needle in expected.get("final_not_contains", []):
    if contains(final_text, needle):
      failures.append(f"answer contains forbidden content {needle!r}")

  return {
      "pass": not failures,
      "failures": failures,
      "argument_total": argument_total,
      "argument_correct": argument_correct,
      "tool_calls": len(requested),
      "malformed_calls": len(invalid),
      "forbidden_attempts": attempted,
      "unauthorized_executed": sorted({name for name in executed if name in forbidden}),
  }
