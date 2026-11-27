"""Report priority TC-V3 capability coverage and exactly matched comparisons."""

import argparse
from collections import Counter, defaultdict
import gzip
from hashlib import sha256
from itertools import combinations
import json
from math import sqrt
from statistics import NormalDist

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import ROOT, canonical

from .tc_atlas_views import ROWS, SOURCE, TRACKS
from .tc_capability_replay import VERDICTS
from .tc_dashboard import STATUS, objects, proportion
from .tc_v3 import HERE

MODELS = ("A", "B", "D")
OUTPUT = HERE.parent / "tc-priority-capability.json"
REPORT = ROOT / "reports/SLM10_PRIORITY_TC_V3_CAPABILITIES.md"


def summarize(verdicts):
    verdicts = list(verdicts)
    values = proportion(verdicts)
    return values | {"planned": len(verdicts), "evaluable": values["PASS"] + values["FAIL"]}


def _wilson(count, total, z):
    p = count / total
    adjust = 1 + z * z / total
    center = (p + z * z / (2 * total)) / adjust
    width = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / adjust
    return max(0, center - width), min(1, center + width)


def pairs(grouped, first, second):
    transitions = Counter((cell[first], cell[second]) for cell in grouped.values() if {first, second} <= cell.keys())
    evaluable = sum(transitions[a, b] for a in STATUS[:2] for b in STATUS[:2])
    gains, losses = transitions["FAIL", "PASS"], transitions["PASS", "FAIL"]
    interval = None
    if evaluable:
        # Simultaneous Wilson bounds on both mutually exclusive discordant categories.
        z = NormalDist().inv_cdf(.9875)
        lower_gain, upper_gain = _wilson(gains, evaluable, z)
        lower_loss, upper_loss = _wilson(losses, evaluable, z)
        interval = [lower_gain - upper_loss, upper_gain - lower_loss]
    return {"planned_pairs": sum(transitions.values()), "evaluable_pairs": evaluable,
            "transitions": {f"{a}/{b}": n for (a, b), n in sorted(transitions.items())},
            "second_only": gains, "first_only": losses,
            "sdk_minus_reference": (gains - losses) / evaluable if evaluable else None, "difference_95": interval}


def _metric(row, name):
    if row is None:
        return "NOT_RUN"
    verdict = row["sealed_status"] if name == "STRICT_END_TO_END_SUCCESS" else row["metrics"][name]
    if verdict not in STATUS:
        raise ValueError("capability row lies outside the four frozen dispositions")
    return verdict


def report():
    matrix = json.loads(SOURCE.read_bytes())
    raw = gzip.decompress(ROWS.read_bytes())
    if sha256(raw).hexdigest() != matrix["derived_rows_sha256"]:
        raise ValueError("assessment bytes differ from the portable seal replay")
    roster = {row["trial_id"]: row for row in objects(HERE / "roster.jsonl")}
    scopes = {row["case_id"]: row["risk_scope"] for row in objects(HERE / "holdout-oracle.jsonl")}
    rows = {}
    for line in raw.splitlines():
        row = json.loads(line)
        trial = row["trial_id"]
        spec = roster.get(trial)
        if (trial in rows or spec is None or any(row[key] != spec[key] for key in ("candidate", "case_id", "seed", "track"))
                or row["risk_scope"] != scopes[spec["case_id"]]):
            raise ValueError("patched or duplicate assessment cohort")
        rows[trial] = row
    if len(rows) != matrix["totals"]["sealed"]:
        raise ValueError("assessment count differs from the portable seal replay")
    result = {}
    for model in MODELS:
        chosen = [spec for spec in roster.values() if spec["candidate"] == model]
        by_scope = {"all": chosen}
        for scope in sorted({scopes[spec["case_id"]] for spec in chosen}):
            by_scope[scope] = [spec for spec in chosen if scopes[spec["case_id"]] == scope]
        cells = {}
        for scope, specs in by_scope.items():
            tracks = (*TRACKS, "sdk_repeat")
            cells[scope] = {"by_track": {track: {metric: summarize(
                _metric(rows.get(spec["trial_id"]), metric) for spec in specs if spec["track"] == track
            ) for metric in VERDICTS} for track in tracks}, "matched": {}}
            for metric in VERDICTS:
                grouped = defaultdict(dict)
                for spec in specs:
                    if spec["track"] in TRACKS:
                        key = spec["case_id"], spec["seed"], scopes[spec["case_id"]]
                        if spec["track"] in grouped[key]:
                            raise ValueError("duplicate matched first-attempt slot")
                        grouped[key][spec["track"]] = _metric(rows.get(spec["trial_id"]), metric)
                cells[scope]["matched"][metric] = {
                    f"{first}/{second}": pairs(grouped, first, second) for first, second in combinations(TRACKS, 2)
                }
        counts = matrix["models"][model]
        result[model] = {"coverage": counts, "scopes": cells}
    return {
        "version": "IJ-SLM-TC-V3-PRIORITY-CAPABILITY/1.0",
        "from_seal_assessment_sha256": matrix["derived_rows_sha256"], "matrix_sha256": digest(SOURCE),
        "dataset_manifest_sha256": matrix["dataset_manifest_sha256"],
        "priority_planned": sum(result[model]["coverage"]["planned"] for model in MODELS),
        "priority_executed": sum(result[model]["coverage"]["executed"] for model in MODELS),
        "strict_verdict_source": "Original sealed status, separate from scoped reassessments.",
        "pair_key": ["candidate", "case_id", "seed", "risk_scope"],
        "intervals": "95% Wilson for PASS/FAIL rates. Paired difference uses simultaneous Wilson bounds on discordant "
                     "fractions; all transitions and unresolved slots remain in the full denominator.",
        "models": result,
    }


def _range(bounds):
    return f"{bounds[0]:.1%} to {bounds[1]:.1%}" if bounds else "Unavailable"


def markdown(document):
    total = document["priority_planned"]
    executed = document["priority_executed"]
    lines = ["# Priority TC-V3 capability report", "",
             f"Verified Radeon execution covers **{executed:,} of {total:,}** frozen A/B/D slots.", "",
             "Wilson intervals use PASS and FAIL. The full denominator includes BLOCKED and NOT_RUN.",
             "The machine-readable report contains the exact case, seed and scope joins, the four-way transition counts, "
             "and the intervals for paired differences. The strict column uses the original sealed verdict.",
             "[Machine-readable paired report](../atlas/slm/v1.0/tc-priority-capability.json)", ""]
    for model, value in document["models"].items():
        lines += [f"## Candidate {model}", "",
                  "| Capability | Track | Planned | PASS | FAIL | BLOCKED | NOT_RUN | 95% CI |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |"]
        for track, metrics in value["scopes"]["all"]["by_track"].items():
            for metric, result in metrics.items():
                fields = " | ".join(str(result[key]) for key in ("planned", *STATUS))
                lines.append(f"| {metric} | {track} | {fields} | {_range(result['wilson_95'])} |")
        lines.append("")
    return "\n".join(lines).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = report()
    for path, raw in {OUTPUT: canonical(result) + b"\n", REPORT: markdown(result)}.items():
        check_text(raw)
        if args.write:
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"{path.name} differs from the portable seal replay")
    print(json.dumps({key: result[key] for key in ("priority_planned", "priority_executed")}))


if __name__ == "__main__":
    main()
