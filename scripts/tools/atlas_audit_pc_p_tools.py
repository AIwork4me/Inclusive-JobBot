"""Verify the tool definition intervention on the complete Qwen3-8B panel."""

from argparse import ArgumentParser
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from scripts.tools.atlas_audit_pc_p_schema import EVIDENCE
from scripts.tools.atlas_compare_pc_p_pilot import selected_archive
from scripts.tools.atlas_pc_p import frozen_panel
from scripts.tools.atlas_progress import jsonl


OUTPUT = EVIDENCE / "pc-p-h-p4-tool-definition-check.json"


def requests(archive):
    first_turn = {}
    for part in sorted(archive.glob("planning-part-*.jsonl.gz")):
        for member in jsonl(part):
            if not member["name"].startswith("attempts/"):
                continue
            trial = Path(member["name"]).name.split(".", 1)[0]
            records = map(json.loads, member["raw_text"].splitlines())
            event = next(row for row in records if row["kind"] == "capture" and row["turn"] == 0)
            wire = event["wire"]
            if trial in first_turn:
                raise ValueError("multiple first-turn captures for one P4 comparison trial")
            first_turn[trial] = wire["request"], wire["source_generation"]["prompt_token_ids"]
    return first_turn


def strip_descriptions(body):
    stripped = deepcopy(body)
    descriptions = {tool["function"]["name"]: tool["function"].pop("description")
                    for tool in stripped.get("tools", [])}
    return stripped, descriptions


def build():
    selected = set(frozen_panel()["case_ids"])
    left = EVIDENCE / "pc-p-h-clean-p1-032"
    right = EVIDENCE / "pc-p-h-clean-p4-032"
    p1, a = selected_archive(left, selected)
    p4, b = selected_archive(right, selected)
    configuration = p1["configuration"]
    if (configuration["git"]["dirty"] or configuration["settings"].get("prompt_contract") != "p1"
            or (configuration | {"settings": configuration["settings"] | {"prompt_contract": "p4"}})
            != p4["configuration"]):
        raise ValueError("P1 and P4 source identities differ beyond treatment")
    before, after = requests(left), requests(right)
    trials = []
    for key in sorted(selected):
        trial = a[key]["trial"]
        if trial != b[key]["trial"]:
            raise ValueError("P1 and P4 trial identities differ")
        identifier = trial["trial_id"]
        original, original_tokens = before[identifier]
        revised, revised_tokens = after[identifier]
        stripped, original_text = strip_descriptions(original)
        stripped_new, revised_text = strip_descriptions(revised)
        if stripped != stripped_new or original_text.keys() != revised_text.keys():
            raise ValueError(f"P4 changed a public input outside tool descriptions: {key}")
        for tool in original_text:
            field_label = "Result fields can include "
            if original_text[tool].split(field_label)[-1] != revised_text[tool].split(field_label)[-1]:
                raise ValueError(f"P4 changed the published result fields for {tool}")
        trials.append({"case_id": key, "applicable_tools": len(original_text),
                       "changed_tool_descriptions": sum(original_text[k] != revised_text[k] for k in original_text),
                       "p1_prompt_tokens": len(original_tokens), "p4_prompt_tokens": len(revised_tokens),
                       "tokens_saved": len(original_tokens) - len(revised_tokens)})
    with_tools = [row for row in trials if row["applicable_tools"]]
    histogram = Counter(row["tokens_saved"] for row in with_tools)
    return {"scope": "P1 and P4 first-turn captures on the complete 32-case Qwen3-8B panel",
            "run_ids": {"p1": p1["run_id"], "p4": p4["run_id"]},
            "source_git": configuration["git"], "matched_cases": len(trials), "with_tools": len(with_tools),
            "token_savings_distribution_with_tools": dict(sorted(histogram.items())), "trials": trials}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if OUTPUT.read_bytes() != raw:
            parser.error("P4 tool definition audit differs")
    else:
        with OUTPUT.open("xb") as stream:
            stream.write(raw)
    print(result["matched_cases"], result["with_tools"], result["token_savings_distribution_with_tools"])


if __name__ == "__main__":
    main()
