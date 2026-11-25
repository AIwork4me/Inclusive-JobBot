"""Check native sampler grammar in the archived Qwen3-8B P3 probe."""

from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from benchmarks.agentic_planning_v1.freeze import FROZEN
from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.atlas_validity.evaluation import planning_layered_scores
from scripts.tools.atlas_compare_pc_p_pilot import selected_archive
from scripts.tools.atlas_pc_p import frozen_panel
from scripts.tools.atlas_progress import document, jsonl
from scripts.tools.bundle_ij07_planning import verify


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/IJ072/benchmark_validity"
ARCHIVE = EVIDENCE / "pc-p-h-factorial-p3-005"
OUTPUT = EVIDENCE / "pc-p-h-p3-wire-probe.json"
PAIRED_OUTPUT = EVIDENCE / "pc-p-h-clean-p1-p3-005.json"


def audit(archive=ARCHIVE):
    verify(archive)
    diagnostic = document(archive / "diagnostic.json")
    if diagnostic["evidence"]["physical_execution_status"] != "PASS":
        raise ValueError("P3 probe must have verified physical capture")
    cases, captures = {}, {}
    for part in sorted(archive.glob("planning-part-*.jsonl.gz")):
        for entry in jsonl(part):
            name, raw = entry["name"], entry["raw_text"]
            if name.startswith("cases/"):
                cases[Path(name).stem] = json.loads(raw)
            elif name.startswith("attempts/"):
                journal = list(map(json.loads, raw.splitlines()))
                records = [event for event in journal if event["kind"] == "capture"]
                captures[Path(name).name.split(".", 1)[0]] = records
    if cases.keys() != captures.keys():
        raise ValueError("P3 case and capture identities differ")
    rows = []
    for key, case in sorted(cases.items()):
        events = captures[key]
        wire = events[0]["wire"]
        source = wire["source_generation"]
        requested = wire["request"]["response_format"]["json_schema"]["schema"]
        sampler = source["generation_settings"]
        grammar = sampler["grammar"]
        if (events[0]["turn"] != 0 or wire["http_status"] != 200 or sampler["grammar_lazy"]
                or "response-format-schema" not in grammar
                or any(f'\\"{field}\\"' not in grammar for field in requested["required"])
                or any("response_format" in event["wire"]["request"] for event in events[1:])):
            raise ValueError(f"P3 native sampling configuration did not match the treatment for {key}")
        content = json.loads(wire["raw_response"])["choices"][0]["message"]["content"]
        valid = Draft202012Validator(requested).is_valid(json.loads(content))
        rows.append({"case_id": case["case_id"], "grammar_sha256": sha256(grammar.encode()).hexdigest(),
                     "completion_id": source["completion_id"], "has_public_tools": bool(wire["request"].get("tools")),
                     "native_plan_shape": "PASS" if valid else "FAIL",
                     "initial_plan_executable": "PASS" if case["plan"]["executable"] else "FAIL",
                     "strict": case["status"]})
    return {"scope": "native P3 wire probe", "physical_evidence": "PASS",
            "factorial_eligibility": "BLOCKED" if diagnostic["identity"]["git"]["dirty"] else "PASS",
            "source_git": diagnostic["identity"]["git"], "run_id": diagnostic["run_id"], "trials": rows}


def paired():
    selected = set(sorted(frozen_panel()["case_ids"])[:5])
    p1_run, p1_rows = selected_archive(EVIDENCE / "pc-p-h-clean-p1-005", selected)
    p3_archive = EVIDENCE / "pc-p-h-clean-p3-005"
    p3_run, p3_rows = selected_archive(p3_archive, selected)
    left, right = p1_run["configuration"], p3_run["configuration"]
    source = left["git"]
    if (source["dirty"] or left["settings"].get("prompt_contract") != "p1"
            or left | {"settings": left["settings"] | {"prompt_contract": "p3"}} != right):
        raise ValueError("clean P1/P3 batch crossed input identities")
    schema = audit(p3_archive)
    if schema["factorial_eligibility"] != "PASS":
        raise ValueError("P3 clean batch lacks enrollment evidence")
    public = {case["case_id"]: case for case in load_jsonl(FROZEN / "datasets/holdout.jsonl")}
    graphs = {row["case_id"]: row for row in load_jsonl(FROZEN / "task_graphs/holdout.jsonl")}
    rows = []
    for case_id in sorted(selected):
        a, b = p1_rows[case_id], p3_rows[case_id]
        if a["trial"] != b["trial"]:
            raise ValueError("clean P1/P3 trial identities differ")
        rows.append({"case_id": case_id, "level": public[case_id]["level"], "language": public[case_id]["language"],
                     "p1": planning_layered_scores(public[case_id], graphs[case_id], a),
                     "p3": planning_layered_scores(public[case_id], graphs[case_id], b)})
    return {"scope": "first five paired Qwen3-8B factorial cases", "source_git": source,
            "p1_run_id": p1_run["run_id"], "p3": schema, "pairs": rows}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--paired", action="store_true")
    args = parser.parse_args()
    result = paired() if args.paired else audit()
    output = PAIRED_OUTPUT if args.paired else OUTPUT
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if output.read_bytes() != raw:
            parser.error("P3 wire probe evidence differs")
    else:
        with output.open("xb") as handle:
            handle.write(raw)
    trials = result["pairs"] if args.paired else result["trials"]
    print(f"P3 sampler grammar verified in {len(trials)} captured trials")


if __name__ == "__main__":
    main()
