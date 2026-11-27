"""Compare E0–E7 on their frozen eligible rosters and matched observations."""
import argparse
from collections import Counter
from math import isfinite
from pathlib import Path

from .archive import digest
from .evaluation_skill import ARMS
from .history import lines
from .q2_closure import wall_summary
from .runtime import write_json

DECISIVE = {"PASS", "FAIL"}
COSTS = ("llm_requests", "tokens", "gpu_inference_ms", "wall_ms")
PAIRS = (("E0", "E1"), ("E1", "E2"), ("E1", "E3"), ("E3", "E4"),
         ("E4", "E5"), ("E5", "E6"), ("E5", "E7"))


def metrics(case, row):
    verdict = row["verdict"]
    conclusive = verdict in DECISIVE
    correct = verdict == case["label"]
    false_accept = verdict == "PASS" and case["label"] == "FAIL"
    return {"correct": correct, "conclusive": conclusive, "abstentions": verdict == "BLOCKED",
            "false_accepts": false_accept, "false_rejects": verdict == "FAIL" and case["label"] == "PASS",
            "critical_false_accepts": false_accept and case["critical"],
            "sufficient_evidence": conclusive and row["evidence_sufficient"]}


def summarize(cases, rows, eligible):
    totals = Counter()
    for case_id, row in rows.items():
        totals.update(metrics(cases[case_id], row))
    cost = {}
    for field in COSTS:
        values = [row[field] for row in rows.values() if row.get(field) is not None]
        cost[field] = {"recorded": len(values), "total": sum(values)}
        if field == "wall_ms":
            cost["wall_distribution"] = wall_summary(values)
    required = len(eligible)
    return {"full_roster": len(cases), "required": required, "recorded": len(rows),
            "ineligible": len(cases) - required, "unexecuted": required - len(rows),
            "accuracy": totals["correct"] / required if required else None,
            "decision_coverage": totals["conclusive"] / required if required else None,
            "evidence_sufficiency": totals["sufficient_evidence"] / totals["conclusive"]
            if totals["conclusive"] else None,
            **{key: totals[key] for key in ("correct", "abstentions", "false_accepts", "false_rejects",
                                            "critical_false_accepts", "sufficient_evidence")},
            "cost": cost}


def paired(cases, groups, first, second, eligible):
    shared = sorted(eligible[first] & eligible[second])
    pairs = [(cases[key], groups[first][key], groups[second][key]) for key in shared
             if key in groups[first] and key in groups[second]]
    deltas = Counter()
    for case, left, right in pairs:
        before, after = metrics(case, left), metrics(case, right)
        deltas.update({field: int(after[field]) - int(before[field]) for field in before})
    result = {"required": len(shared), "recorded": len(pairs),
              "accuracy_delta": deltas["correct"] / len(pairs) if pairs else None,
              "counts_delta": dict(deltas)}
    for field in COSTS:
        values = [right[field] - left[field] for _, left, right in pairs
                  if left.get(field) is not None and right.get(field) is not None]
        result[f"{field}_delta"] = {"paired": len(values), "total": sum(values)}
    return result


def compare(roster, observations):
    cases = {}
    for case in roster:
        key = case["case_id"]
        if (not key or key in cases or case["label"] not in DECISIVE
                or any(type(case[name]) is not bool for name in ("critical", "mechanical"))):
            raise ValueError("invalid or repeated evaluation case")
        cases[key] = case
    if not cases:
        raise ValueError("empty paired evaluation roster")
    eligible = {arm: {key for key, case in cases.items() if arm != "E6" or case["mechanical"]} for arm in ARMS}
    groups = {arm: {} for arm in ARMS}
    for row in observations:
        key, arm = row["case_id"], row["arm"]
        if (arm not in ARMS or key not in eligible[arm] or key in groups[arm]
                or row["verdict"] not in DECISIVE | {"BLOCKED"}
                or type(row["evidence_sufficient"]) is not bool
                or type(row["llm_requests"]) is not int):
            raise ValueError("invalid or repeated paired observation")
        for field in COSTS:
            value = row.get(field)
            if (value is not None and (type(value) not in {int, float} or not isfinite(value) or value < 0)):
                raise ValueError("invalid measured evaluation cost")
        if (row["llm_requests"] == 0 and (row.get("tokens") not in {None, 0}
                or row.get("gpu_inference_ms") not in {None, 0})):
            raise ValueError("zero-request route has inconsistent inference costs")
        groups[arm][key] = row
    arms = {arm: summarize(cases, groups[arm], keys) for arm, keys in eligible.items()}
    return {"status": "PASS" if all(not row["unexecuted"] for row in arms.values()) else "NOT_RUN",
            "qualification": "NOT_RUN", "arms": arms,
            "comparisons": {f"{first}/{second}": paired(cases, groups, first, second, eligible)
                            for first, second in PAIRS}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roster", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(lines(args.roster), lines(args.observations))
    write_json(args.output, {**report, "roster_sha256": digest(args.roster),
                             "observations_sha256": digest(args.observations)})


if __name__ == "__main__":
    main()
