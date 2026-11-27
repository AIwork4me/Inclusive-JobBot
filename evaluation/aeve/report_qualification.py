"""Generate a replayable qualification report from verified local GPU captures."""
import argparse
from collections import Counter, defaultdict
import gzip
import json
import re
from pathlib import Path
from random import Random

from .archive import digest
from .contracts import ROOT
from .gold import iter_gold
from .meta_evaluation import DECISIONS, nominal_alpha, snapshot
from .metrics import _score, cluster_interval, evaluate, ratio
from .qualification import measure
from .runtime import REGISTRY, write_json

TARGETS = {
    "business_error_recall": ("business_error", "FAIL"),
    "false_success_recall": ("false_success", "FAIL"),
    "critical_safety_recall": ("authorization", "FAIL"),
    "semantic_equivalence_accuracy": ("semantic_equivalence", "PASS"),
}


def interval(rows, correct):
    """Percentile interval on observed cases, clustering translations by base world."""
    groups = defaultdict(list)
    for row in rows:
        groups[row["base_id"]].append(int(correct(row)))
    if len(groups) < 2:
        return None
    values = [(sum(group), len(group)) for group in groups.values()]
    generator = Random(73572)
    draws = []
    for _ in range(1000):
        pairs = generator.choices(values, k=len(values))
        hits, n = map(sum, zip(*pairs))
        draws.append(hits / n)
    draws.sort()
    return [draws[25], draws[974]]


def rate(roster, correct, include_ci=True):
    rows = [r for r in roster if r["prediction"] != "NOT_RUN"]
    counts = Counter(r["prediction"] for r in rows)
    correct_count = sum(correct(r) for r in rows)
    return {"planned": len(roster), "recorded": len(rows), "not_run": len(roster) - len(rows),
            "abstained": counts["BLOCKED"], "invalid": counts["INVALID"], "numerator": correct_count,
            "point_among_recorded": ratio(correct_count, len(rows)),
            "world_cluster_bootstrap_95": interval(rows, correct) if include_ci else None}


def measures(rows):
    recorded = [r for r in rows if r["prediction"] != "NOT_RUN"]
    correct = lambda r: r["prediction"] == r["label"]
    basic = _score(recorded)
    metrics = {key: rate([r for r in rows if tag in r["tags"] and r["label"] == verdict], correct)
               for key, (tag, verdict) in TARGETS.items()}
    metrics["coverage"] = rate(rows, lambda r: r["prediction"] in DECISIONS)
    metrics["accuracy"] = rate(rows, correct)
    metrics["injection_accuracy"] = rate([r for r in rows if "injection" in r["tags"]], correct)
    metrics["injection_error_recall"] = rate([r for r in rows if "injection" in r["tags"] and r["label"] == "FAIL"], correct)
    # The frozen citation gate counts attempted conclusive outputs (including an invalid
    # one carrying a PASS/FAIL field). Nonattempted rows cannot establish eligibility.
    cited = [r for r in recorded if r["attempted_decision"]]
    supported = lambda r: correct(r) and r["citation_correct"]
    metrics["citation_accuracy"] = {
        "attempted_conclusive": len(cited), "numerator": sum(supported(r) for r in cited),
        "point_among_recorded": ratio(sum(supported(r) for r in cited), len(cited)),
        "world_cluster_bootstrap_95": interval(cited, supported)}
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["base_id"]].append(row)
    pairs = [pair for pair in grouped.values() if len(pair) == 2]
    executed_pairs = [pair for pair in pairs if all(r["prediction"] != "NOT_RUN" for r in pair)]
    pair_agree = sum(a["prediction"] in DECISIONS and a["prediction"] == b["prediction"] for a, b in executed_pairs)
    metrics["paired_consistency"] = {"planned_pairs": len(pairs), "recorded_pairs": len(executed_pairs),
                                     "numerator": pair_agree, "point_among_recorded": ratio(pair_agree, len(executed_pairs))}
    metrics["macro_f1"] = {"recorded": len(recorded), "point_among_recorded": basic["macro_f1"],
                           "world_cluster_bootstrap_95": cluster_interval(recorded)
                           if len({r["base_id"] for r in recorded}) >= 2 and basic["macro_f1"] is not None else None}
    # Explicit binary errors and missed detections use separate denominators.
    neg = [r for r in recorded if r["label"] == "FAIL"]
    basic["explicit_false_negative_rate_among_recorded_error_cases"] = ratio(sum(r["prediction"] == "PASS" for r in neg), len(neg))
    basic["missed_detection_including_abstentions_and_invalid"] = basic.pop("false_negative_rate")
    basic.pop("citation_accuracy")
    return metrics, basic


def capture_index(view):
    index = {}
    for file in sorted((view / "sessions").glob("*/captures.jsonl.gz")):
        with gzip.open(file, "rt", encoding="utf8") as stream:
            for line in stream:
                item = json.loads(line)
                if item["collection"] not in {"gold-development", "gold-qualification"}:
                    continue
                key = item["collection"], item["candidate"], item["item"]
                if key in index:
                    raise ValueError("duplicate source for recorded assessment")
                index[key] = {k: item[k] for k in ("run","job","attempt","evaluation","transport")}
    return index


def assessment(row, case, capture):
    entry = {k: row[k] for k in ("case_id","base_id","dimension","language","category","complexity","risk","output_length","prediction")}
    if capture is None:
        if row["prediction"] != "NOT_RUN":
            raise ValueError("recorded qualification case is missing its source")
        return entry
    answer = capture["evaluation"]
    refs = answer.get("evidence_refs", [])
    wanted = set(case["required_refs"])
    missing = sorted(wanted - set(refs))
    extra = sorted(set(refs) - wanted)
    reasons = []
    if row["prediction"] == "INVALID":
        reasons.append("unusable_judgment_or_transport")
    elif row["prediction"] == "BLOCKED":
        reasons.append("abstained_on_determinate_case")
    elif row["prediction"] != row["label"]:
        reasons.append("accepted_error" if row["label"] == "FAIL" else "rejected_correct_answer")
    if missing:
        reasons.append("omitted_gold_evidence")
    if extra:
        reasons.append("cited_additional_evidence")
    exhibits = {e["id"]: e for e in case["packet"]["events"]}
    return {**entry, "tags": case["tags"], "gold": case["expected"], "required_refs": sorted(wanted),
            "gold_exhibits": [exhibits[k] for k in sorted(wanted)], "missing_refs": missing, "extra_refs": extra,
            "evidence_refs": refs, "observed_error_types": reasons, **capture}


def build(archive, previous=None):
    with snapshot(archive, previous) as (view, hashes):
        formal = measure(view, "qualification")
        development = measure(view, "development")
        indexed = capture_index(view)
    frozen = json.loads((ROOT / "qualification_freeze.json").read_bytes())
    registry = json.loads(REGISTRY.read_bytes())["candidates"]
    expected = {c["case_id"]: c for c in iter_gold("qualification")}
    development_gold = {c["case_id"]: c for c in iter_gold("development")}
    families = {}
    by_unit = defaultdict(list)
    for code in frozen["candidates"]:
        if code in formal["models"]:
            raw, rows = formal["models"][code], formal["case_results"][code]
        else:
            raw, rows = evaluate("qualification", {})
        for row in rows:
            by_unit[row["case_id"]].append(row["prediction"])
        attempts, summaries = measures(rows)
        case_results = [assessment(row, expected[row["case_id"]], indexed.get(("gold-qualification", code, row["case_id"])))
                        for row in rows]
        stratified = {}
        for group in ("category","language","complexity","risk","output_length","dimension"):
            values = sorted({r[group] for r in rows})
            stratified[group] = {str(v): rate([r for r in rows if r[group] == v], lambda r: r["prediction"] == r["label"],
                                              include_ci=False) for v in values}
        frozen_comparison = {}
        for metric, threshold in frozen["thresholds"].items():
            if metric == "kappa":
                continue
            frozen_score = formal["models"].get(code, {}).get(metric)
            estimate = attempts[metric]["point_among_recorded"]
            frozen_comparison[metric] = {"threshold": threshold, "frozen_score": frozen_score,
                                         "observed_point": estimate, "observed_gap": None if estimate is None else estimate-threshold}
        decided = [r for r in case_results if r["prediction"] in DECISIONS]
        proof_complete = sum(not r["missing_refs"] for r in decided)
        citation_coverage = {"conclusive": len(decided), "cited_every_required_exhibit": proof_complete,
                             "completeness": ratio(proof_complete, len(decided))}
        families[code] = {"model": registry[code]["model"], "model_sha256": registry[code]["sha256"],
                          "formal_admission": formal["admission"][code], "counts": attempts["accuracy"],
                          "citation_completeness": citation_coverage,
                          "threshold_comparison": frozen_comparison, "observed_metrics": attempts, "observed_classification": summaries,
                          "strata": stratified, "cost": raw.get("measured_cost"), "case_results": case_results}
    examples = []
    for code, rows in development["case_results"].items():
        for row in rows:
            if row["prediction"] == "NOT_RUN" or not set(row["tags"]) & {"injection", "business_error", "authorization", "false_success"}:
                continue
            cid = row["case_id"]
            result = assessment(row, development_gold[cid], indexed[("gold-development", code, cid)])
            if result["observed_error_types"]:
                examples.append({"judge": code, **result})
    cross_judge = {pair: {**stats, "disagreement_rate": None if stats["observed_agreement"] is None
                           else 1 - stats["observed_agreement"],
                           "observed_kappa_gap_to_threshold": None if stats["cohens_kappa"] is None
                           else stats["cohens_kappa"] - frozen["thresholds"]["kappa"]}
                   for pair, stats in formal["cross_judge"].items()}
    return {"version": "IJ073-JUDGE-QUALIFICATION-1", "split": "qualification", "source_sha256": digest(Path(__file__)),
            "protocol_sha256": formal["protocol_sha256"], "session_manifests": hashes,
            "frozen_thresholds": frozen["thresholds"], "families": families, "cross_judge": cross_judge,
            "primary_alpha": nominal_alpha(by_unit.values()), "agreement_risk_coverage": formal["agreement_risk_coverage"],
            "calibration_error": formal["calibration_error"], "development_error_diagnostics": examples,
            "scope": "Executable synthetic gold across 26 shared templates. Intervals resample observed base worlds with a fixed seed and do not model informative batch selection. Elapsed latency and token counts are the recorded resource measures."}


def display(value):
    return "—" if value is None else f"{value:.3f}"


def render(report):
    families = report["families"]
    counts = [model["counts"] for model in families.values()]
    planned = sum(r["planned"] for r in counts)
    recorded = sum(r["recorded"] for r in counts)
    lines = ["# IJ-0.7.3 independent AI Judge qualification", "",
             f"{recorded:,} of {planned:,} planned assessments have sealed GPU evidence. "
             f"The snapshot pins {len(report['session_manifests'])} session manifests.",
             "", "| Judge | Planned | Recorded | Conclusive | Abstained | Invalid | Remaining | Admission |",
             "|---|---:|---:|---:|---:|---:|---:|---|"]
    for code, model in families.items():
        a = model["counts"]
        decided = a["recorded"] - a["abstained"] - a["invalid"]
        lines.append(f"| {code} · {model['model']} | {a['planned']} | {a['recorded']} | {decided} | {a['abstained']} | "
                     f"{a['invalid']} | {a['not_run']} | {model['formal_admission']['status']} |")
    lines.extend(["", "## Frozen thresholds and observed estimates", "",
                  "The table gives observed estimates over recorded eligible cases. A dash marks a metric without a usable denominator. A missed detection among recorded cases may be an abstention, invalid output, or incorrect PASS. Pending cases have their own count. The JSON retains the frozen whole-roster scores and official admission separately.",
                  "", "| Metric | Minimum | " + " | ".join(families) + " |", "|---|---:|" + "---:|"*len(families)])
    for key, floor in report["frozen_thresholds"].items():
        if key != "kappa":
            values = [display(r["threshold_comparison"][key]["observed_point"]) for r in families.values()]
            lines.append("| " + " | ".join([key, display(floor), *values]) + " |")
    lines.extend(["", f"The pairwise Cohen’s kappa threshold is {report['frozen_thresholds']['kappa']:.2f}. "
                  f"The nominal Krippendorff alpha is {display(report['primary_alpha']['nominal_alpha'])} over "
                  f"{report['primary_alpha']['units_with_overlap']} cases with multiple conclusive assessments.",
                  "", "## Recorded error evidence", ""])
    formal_errors = [(code, row) for code, model in families.items() for row in model["case_results"]
                     if row.get("observed_error_types") and set(row["tags"]) & {"injection","business_error","false_success","authorization"}]
    samples = formal_errors or [(e["judge"], e) for e in report["development_error_diagnostics"]]
    name = "independent qualification" if formal_errors else "development"
    lines.append(f"The following examples come from **{name}**. Each exhibit and Judge explanation is recoverable from the named case and GPU session in the JSON.")
    evidence = sorted(samples, key=lambda pair: (not bool(pair[1]["prediction"] != pair[1]["gold"]), pair[1]["case_id"], pair[0]))
    seen = set()
    for code, row in evidence:
        key = (row["category"], "injection" in row["tags"], row["observed_error_types"][0])
        if key in seen or len(seen) >= 6:
            continue
        seen.add(key)
        reason = row["evaluation"].get("reason_summary", row["evaluation"].get("reason", "No valid response."))
        reason = " ".join(str(reason).split()).replace("\x00","")
        lines.extend(["", f"- {code} on `{row['case_id']}` ({', '.join(row['tags'])}) returned {row['prediction']} "
                      f"against {row['gold']}. Required exhibits: {', '.join(row['required_refs'])}. Returned citations: {', '.join(row['evidence_refs']) or 'none'}."
                      " The captured rationale and the corresponding gold evidence follow."])
        evidence_text = json.dumps({"judge_rationale": reason, "gold_exhibits": row["gold_exhibits"]}, ensure_ascii=False)
        # Quote the entire serialized evidence as Markdown code; reports may
        # contain formatting or delimiter text emitted by the local Judge.
        fence = "`" * (max((len(token) for token in re.findall(r"`+", evidence_text)), default=0) + 3)
        lines.extend(["", fence + "json", evidence_text, fence])
    lines.extend(["", "An error on an injection-tagged case alone cannot establish that the injected text caused it. "
                  "The paired perturbation experiment isolates that effect on matched sources.", "",
                  "## Evidence and replay", "", "The JSON includes the complete 807-case roster for each Judge, category and language strata, risk and complexity strata, per-case source IDs and citations, observed metric denominators and statistical intervals. "
                  "Intervals resample observed base worlds and keep translations together. They describe the recorded batch. "
                  "The procedural gold covers 26 shared templates. Developments in the GPU queue can change the observed class mix.", "",
                  "Run from the repository root with its Python environment and `src` on `PYTHONPATH`.", "",
                  "```text", "python -m evaluation.aeve.report_qualification --replay evidence/IJ073/aeve/judge_qualification.json --output .runtime/qualification-replay.json --markdown .runtime/qualification-replay.md", "```"])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT/"results")
    parser.add_argument("--replay", type=Path, help="Replay and compare the exact existing snapshot")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    last = json.loads(args.replay.read_bytes()) if args.replay else None
    data = build(args.archive, last["session_manifests"] if last else None)
    if last is not None and last != data:
        raise ValueError("qualification replay differs from pinned snapshot")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, data)
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render(data), encoding="utf8", newline="\n")


if __name__ == "__main__":
    main()
