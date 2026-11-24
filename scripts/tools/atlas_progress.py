"""Rebuild the Atlas dashboard from frozen trial evidence and documented gate states."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUSES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")


def document(path):
    return json.loads(path.read_bytes())


def jsonl(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        yield from map(json.loads, stream)


def count_trials(rows, planned):
    by_id = {}
    for key, status in rows:
        if key in by_id or status not in STATUSES:
            raise ValueError(f"Duplicate trial or invalid status: {key}, {status}")
        by_id[key] = status
    if len(by_id) > planned:
        raise ValueError("Trial records exceed planned denominator")
    counts = Counter(by_id.values())
    counts["NOT_RUN"] += planned - len(by_id)
    executed = planned - counts["NOT_RUN"]
    return {
        "planned": planned,
        "executed": executed,
        "valid_evidence": counts["PASS"] + counts["FAIL"],
        "outcomes": {status: counts[status] for status in STATUSES},
        "coverage": executed / planned if planned else None,
        "strict_pass_rate": counts["PASS"] / planned if planned else None,
    }


def historical(root):
    result = {}

    def add(name, rows, planned, key, source, **metrics):
        result[name] = {
            **count_trials(((key(row), row["status"]) for row in rows), planned),
            "source": source.relative_to(root.parent).as_posix(),
            **metrics,
        }

    replay = root / "historical_replay/full"
    requests = 0
    all_rows = []
    for arm in ("R0-V", "R0-R", "R1-V", "R1-R"):
        folder = replay / arm
        evidence = {
            row["completion_id"]
            for file in folder.glob("*-generation.jsonl.gz")
            for row in jsonl(file)
        }
        trials = list(jsonl(folder / "results.jsonl.gz"))
        captures = [c["source_generation"]["completion_id"] for row in trials for c in row["capture"]]
        if set(captures) != evidence or len(captures) != len(evidence):
            raise ValueError(f"Source capture mismatch: {arm}")
        requests += len(captures)
        all_rows.extend({**r["rescored_v2"], "trial": (arm, r["id"])} for r in trials)
    add("historical-replay", all_rows, 2000, lambda r: r["trial"], replay,
        unique_cases=len({r["trial"][1] for r in all_rows}), model_requests=requests)

    for backend in ("vulkan", "rocm"):
        file = root / f"tc_v2/holdout/{backend}/terminal.jsonl.gz"
        groups = defaultdict(list)
        for entry in jsonl(file):
            row = entry["row"]
            phase = row["key"].split("--", 1)[0]
            groups["repeat" if phase.startswith("repeat-") else phase].append(row)
        for phase, planned in (("first", 500), ("stream", 500), ("repeat", 150), ("fixture", 146)):
            rows = groups[phase]
            add(f"tc-v2-{backend}-{phase}", rows, planned, lambda r: r["key"], file,
                unit="fixed_fixture" if phase == "fixture" else "model_trial",
                model_requests=sum(len(r.get("requests", [])) for r in rows))
        rows = [r for r in groups["first"] if r["category"] == "sequential_multi_tool"]
        add(f"tc-v2-{backend}-sequential", rows, 100, lambda r: r["key"], file,
            subset_of=f"tc-v2-{backend}-first")

    for panel, planned in (("primary", 600), ("repeat", 300)):
        file = root / f"multitool/{panel}-vulkan-full/terminal.jsonl.gz"
        rows = [entry["row"] for entry in jsonl(file)]
        outcomes = defaultdict(list)
        for row in rows:
            outcomes[row["case_id"]].append(row["status"])
        add(f"multitool-{panel}", rows, planned, lambda r: (r["case_id"], r["seed"]), file,
            unique_cases=len(outcomes), model_requests=sum(r["model_calls"] for r in rows))
        if panel == "repeat":
            if any(len(items) != 3 for items in outcomes.values()) or len(outcomes) != 100:
                raise ValueError("Incomplete multitool reliability panel")
            result[f"multitool-{panel}"].update(
                repeat_cases_passing_any=sum("PASS" in items for items in outcomes.values()),
                repeat_cases_passing_all=sum(set(items) == {"PASS"} for items in outcomes.values()),
            )

    for panel, planned in (("primary", 800), ("repeat", 480)):
        folder = root / f"planning/{panel}-vulkan-full"
        rows = []
        requests = Counter()
        for file in sorted(folder.glob("planning-part-*.jsonl.gz")):
            for entry in jsonl(file):
                name = entry["name"]
                if name.startswith("cases/"):
                    rows.append(json.loads(entry["raw_text"]))
                elif name.startswith("attempts/"):
                    track = Path(name).name.split("-")[3]
                    requests[track] += sum(json.loads(line)["kind"] == "request"
                                           for line in entry["raw_text"].splitlines())
        for track in ("A", "P"):
            selected = [r for r in rows if r["track"] == track]
            add(f"planning-{panel}-{track}", selected, planned, lambda r: r["trial"]["trial_id"], folder,
                unique_cases=len({r["case_id"] for r in selected}), journaled_requests=requests[track])
        if panel == "repeat":
            add("planning-repeat-combined", rows, planned * 2, lambda r: r["trial"]["trial_id"], folder,
                aggregate_of=["planning-repeat-A", "planning-repeat-P"])

    for name, folder in (("primary", "primary"), ("correction", "receipt-correction/corrected/primary")):
        file = root / f"job_ablation/F/{folder}/records.jsonl.gz"
        rows = [json.loads(entry["raw_json"]) for entry in jsonl(file)]
        add(f"job-f-{name}", rows, 600, lambda r: r["case_id"], file,
            unit="diagnostic_replay" if name == "correction" else "deterministic_business_trial",
            completed_business_tasks=sum(r["completed"] for r in rows),
            model_requests=sum(r["model_calls"] for r in rows))

    file = root / "competitive_slm/tc-v2-B-first-checkpoint/trials.jsonl.gz"
    add("competitive-b-first-checkpoint", jsonl(file), 1150, lambda r: r["key"], file, unique_cases=500)
    for candidate in ("B", "D", "F", "G"):
        file = root.parent / f"IJ071/legacy_competitive/{candidate}/trials.jsonl.gz"
        if file.exists():
            add(f"competitive-{candidate.lower()}-legacy-full", jsonl(file), 1150, lambda r: r["key"],
                file, unique_cases=500)

    for backend in ("vulkan", "rocm"):
        file = root / f"antigravity/{backend}/report.json"
        sdk = document(file)
        add(f"ag06-{backend}", sdk["repetitions"], 3, lambda r: r["trial"], file,
            model_requests=sum(len(r["wire"]) for r in sdk["repetitions"]))
        result[f"ag11-{backend}"] = {
            **count_trials([("AG-11", sdk["AG-11"]["status"])], 1),
            "source": file.relative_to(root.parent).as_posix(), "reason": sdk["AG-11"]["reason"],
            "unit": "gate_assessment",
        }
    return result


def dashboard(progress):
    def value(row, key):
        return row.get(key) if row.get(key) is not None else "—"

    lines = ["# Atlas Progress Dashboard", "", "Generated by `python scripts/tools/atlas_progress.py`.", "",
             "## IJ-0.7.1 workstreams", "",
             "| Phase | Gate | Planned | Executed | Valid | PASS | FAIL | BLOCKED | NOT_RUN | Investigated | Confirmed | Fixed and regressed | Independently qualified |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for phase, row in progress["workstreams"].items():
        cells = [phase, row["status"], *(value(row, k) for k in ("planned", "executed", "valid_evidence")),
                 *(value(row["outcomes"], s) for s in STATUSES),
                 *(value(row, k) for k in ("investigated", "confirmed", "fixed_and_regressed", "independently_qualified"))]
        lines.append("| " + " | ".join(map(str, cells)) + " |")
    gates = progress["gate_status_counts"]
    lines.extend(["", f"Formal gates passed {gates['PASS']}/{len(progress['gates'])}. "
                  "A1 counts refer to software fixture execution. Dashes indicate an unavailable or inapplicable denominator. "
                  "The historical rows below retain individual denominators and can overlap.", "",
                  "## IJ-0.7 historical evidence", "",
                  "| Run | Planned | Executed | Valid | PASS | FAIL | BLOCKED | NOT_RUN | Coverage | Strict result rate |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for name, row in progress["historical"].items():
        source = "evidence/" + row["source"]
        cells = [f"[{name}](../{source})", row["planned"], row["executed"], row["valid_evidence"],
                 *(row["outcomes"][s] for s in STATUSES), f"{row['coverage']:.1%}", f"{row['strict_pass_rate']:.1%}"]
        lines.append("| " + " | ".join(map(str, cells)) + " |")
    return "\n".join(lines) + "\n"


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    status = document(ROOT / "atlas/workstreams.json")
    workstreams = {}
    for name, row in status.items():
        counts = count_trials([], row["planned"]) if row.get("planned") is not None else {}
        workstreams[name] = {**counts, **row, "outcomes": row.get("outcomes", counts.get("outcomes", {}))}
    controls_path = ROOT / "evidence/IJ071/controls-reconciled.json.gz"
    with gzip.open(controls_path, "rt", encoding="utf-8") as stream:
        controls = json.load(stream)
    control_trials = [((cohort, row["case_id"]), row["status"])
                      for cohort, result in controls["cohorts"].items() for row in result["trials"]]
    workstreams["A1"].update(count_trials(control_trials, workstreams["A1"]["planned"]))
    workstreams["A0"].update(count_trials([("baseline-audit", workstreams["A0"]["status"])], 1))
    gates = document(ROOT / "atlas/gates.json")
    if any(row["status"] not in STATUSES for row in gates.values()):
        raise ValueError("Invalid formal gate status")
    gate_counts = Counter(row["status"] for row in gates.values())
    progress = {"schema_version": 1, "workstreams": workstreams, "gates": gates,
                "gate_status_counts": {s: gate_counts[s] for s in STATUSES},
                "verdicts": document(ROOT / "atlas/verdicts.json"),
                "historical": historical(ROOT / "evidence/IJ07")}
    outputs = {
        "atlas/progress.json": json.dumps(progress, indent=2, ensure_ascii=False) + "\n",
        "reports/ATLAS_PROGRESS_DASHBOARD.md": dashboard(progress),
    }
    for name, contents in outputs.items():
        target = ROOT / name
        if args.check:
            if target.read_text(encoding="utf-8") != contents:
                parser.exit(1, f"Stale generated file: {name}\n")
        else:
            target.write_text(contents, encoding="utf-8", newline="\n")
    print(f"Atlas progress {'verified' if args.check else 'generated'}: {len(progress['historical'])} archive views")


if __name__ == "__main__":
    main()
