"""Recount IJ073 baseline rows in the published archives. Run from repository root."""
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path("evidence/IJ072")
VALIDITY = ROOT / "benchmark_validity"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def opened(path):
    return (gzip.open if path.suffix == ".gz" else open)(path, "rt", encoding="utf8")


def read(path):
    with opened(path) as stream:
        return json.load(stream)


def records(path):
    with opened(path) as stream:
        for line in stream:
            yield json.loads(line)


def tally(rows, key):
    return dict(sorted(Counter(row[key] for row in rows).items()))


def recount():
    sources = {}

    def source(path):
        sources[path.as_posix()] = digest(path)
        return path

    witnesses = {}
    for name in ("tc-holdout-witness.json", "multitool-witness.json.gz", "job-witness.json.gz",
                 "planning-intent-controls.json", "planning-read-controls.json", "planning-advanced-controls.json",
                 "planning-plan-controls.json.gz"):
        rows = read(source(VALIDITY / name))["trials"]
        if len({r["case_id"] for r in rows}) != len(rows):
            raise ValueError(f"duplicate cases in {name}")
        witnesses[name] = tally(rows, "oracle_status" if "intent" in name else "status")
    plans = rows
    mutations = read(source(VALIDITY / "planning-precondition-controls.json"))["trials"]
    groups = read(source(VALIDITY / "planning-public-ambiguity.json"))["groups"]
    packet = read(source(VALIDITY / "a1-blind-review-packet.json"))
    factors = read(source(Path("atlas/benchmarks/pc_p_factorial.json")))["arm_factors"]
    panel = read(source(VALIDITY / "pc-p-factorial-full-four-models.json"))["models"]
    treatments = [(arm, score) for model in panel.values() for case in model["cases"]
                  for arm, score in case["arms"].items()]
    schema = [score for arm, score in treatments if "schema" in factors[arm]]
    quote = read(source(ROOT / "root_causes/rc02-quote-diagnostic.json"))["candidates"]
    job = read(source(ROOT / "purpose_built/legacy-job-ab-checkpoint.json"))["arms"]
    controls = {}
    for version in ("baseline", "corrected"):
        path = Path("evidence/IJ07/job_ablation/F/receipt-correction") / version / "primary/records.jsonl.gz"
        trials = [json.loads(item["raw_json"]) for item in records(source(path)) if item["name"].startswith("cases/")]
        controls[version] = tally(trials, "status")

    strong = {}
    for label, prefix, multi in (("8B", "pc-s-", "multi"), ("14B", "pc-s-j-", "multi-full")):
        strong[label] = {}
        tc = [json.loads(row["utf8"])["row"] for row in records(source(VALIDITY / (prefix+"tc/raw.jsonl.gz")))
              if row["name"].startswith("trajectories/")]
        strong[label]["TC"] = tally(tc, "trajectory_status")
        strong[label]["MULTITOOL"] = tally((r["row"] for r in records(source(
            VALIDITY / (prefix+multi) / "terminal.jsonl.gz"))), "status")
        cases = [json.loads(row["raw_text"]) for part in sorted((VALIDITY / (prefix+"planning-full")).glob("*.jsonl.gz"))
                 for row in records(source(part)) if row["name"].startswith("cases/")]
        for track in ("P", "A"):
            strong[label][track] = tally((r for r in cases if r["track"] == track), "status")

    return {"reviewed_sha": "0ba158cf95cd802ca9f9091d6abc893dce543644", "inputs": sources,
            "witnesses": witnesses, "plan_errors": dict(Counter(e for r in plans for e in r["plan_errors"])),
            "plan_levels": {level: tally((r for r in plans if r["level"] == level), "status")
                            for level in sorted({r["level"] for r in plans})},
            "missed_mutations": tally((r for r in mutations if r["status"] == "FAIL"), "mutation"),
            "ambiguous_groups": len(groups), "ambiguous_cases": sum(len(g["cases"]) for g in groups),
            "blind_review": [packet["human_review"], len(packet["items"])], "references": strong,
            "prompt_strict": tally((s for _, s in treatments), "strict_end_to_end"),
            "prompt_business": tally((s for _, s in treatments), "business_outcome"),
            "schema_protocol": tally(schema, "initial_plan_protocol"), "schema_business": tally(schema, "business_outcome"),
            "quote": {k: {"strict": tally(v["trials"], "strict"),
                          "facts_correct": sum(r["correct_requested_facts_in_final_object"] for r in v["trials"])}
                      for k, v in quote.items()},
            "job_sealed": {k: tally(v["sealed_checkpoints"].values(), "status") for k, v in job.items()},
            "job_business_from_checkpoint_summary": {k: v["summary"]["completed_business_tasks"] for k, v in job.items()},
            "job_f": controls}


if __name__ == "__main__":
    print(json.dumps(recount(), indent=2, sort_keys=True))
