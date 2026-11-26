"""Measure blinded local Judge agreement and controlled bias on sealed evidence."""
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import gzip
import json
from math import comb
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from .archive import digest, verify
from .contracts import ROOT, sha
from .gold import FOLDER, iter_gold
from .local_judge import check
from .metrics import evaluate, ratio
from .qualification import measure
from .robustness import COLLECTION, FAMILIES, cases, request_for
from .runtime import REGISTRY, write_json

DECISIONS = {"PASS", "FAIL"}


def nominal_alpha(items):
    """Nominal Krippendorff alpha using only units with two conclusive ratings."""
    marginal = Counter()
    observed = 0.0
    usable = 0
    for votes in items:
        counts = Counter(v for v in votes if v in DECISIONS)
        size = sum(counts.values())
        if size < 2:
            continue
        usable += 1
        marginal.update(counts)
        observed += (size * size - sum(n*n for n in counts.values())) / (size - 1)
    total = sum(marginal.values())
    expected = (total * total - sum(n*n for n in marginal.values())) / (total - 1) if total > 1 else 0
    return {"units_with_overlap": usable, "conclusive_ratings_with_overlap": total,
            "marginals": dict(marginal), "nominal_alpha": 1 - observed / expected if expected else None}


def compare(rows, arm):
    """Exact conditional McNemar p uses independent source cases, one pair per case."""
    by_case = defaultdict(dict)
    for row in rows:
        by_case[row["case_id"]][row["arm"]] = row
    comparable = improved = degraded = same = both_correct = proof_correct = flipped = 0
    for variants in by_case.values():
        base, variant = variants["baseline"], variants[arm]
        if base["prediction"] not in DECISIONS or variant["prediction"] not in DECISIONS:
            continue
        comparable += 1
        left = base["prediction"] == base["expected"]
        right = variant["prediction"] == variant["expected"]
        improved += right and not left
        degraded += left and not right
        both_correct += left and right
        proof_correct += base["supported_correct"] and variant["supported_correct"]
        same += base["prediction"] == variant["prediction"]
        flipped += base["prediction"] != variant["prediction"] and left and right
    discordant = improved + degraded
    tail = sum(comb(discordant, i) for i in range(min(improved, degraded) + 1))
    return {"planned_pairs": len(by_case), "conclusive_pairs": comparable,
            "improved": improved, "degraded": degraded, "both_correct": both_correct,
            "both_correct_with_gold_citations": proof_correct,
            "verdict_preservation": ratio(same, comparable) if arm != "fact_changed" else None,
            "correctly_changed_decision": flipped if arm == "fact_changed" else None,
            "accuracy_delta_on_matched_pairs": ratio(improved - degraded, comparable),
            "mcnemar_two_sided_exact_p": min(1.0, 2 * tail / 2**discordant) if comparable else None}


@contextmanager
def snapshot(archive, previous=None):
    """Pin complete manifests before scoring. Replays ignore newly sealed sessions."""
    stamps = sorted((archive / "sessions").glob("*/manifest.json"))
    hashes = {p.parent.name: digest(p) for p in stamps}
    if previous is not None:
        if any(hashes.get(key) != value for key, value in previous.items()):
            raise ValueError("requested snapshot is missing or changed")
        hashes = previous
    with TemporaryDirectory() as temporary:
        view = Path(temporary)
        for run, expected in hashes.items():
            folder = archive / "sessions" / run
            target = view / "sessions" / run
            target.mkdir(parents=True)
            for name in ("manifest.json", "identity.json", "captures.jsonl.gz", "outcomes.json",
                         "live-gpu.jsonl.gz", "live-generation.jsonl.gz"):
                try:
                    os.link(folder / name, target / name)
                except OSError:
                    shutil.copyfile(folder / name, target / name)
            if digest(target / "manifest.json") != expected:
                raise ValueError("manifest changed while pinning snapshot")
        verify(view)
        yield view, hashes


def control_rows(view):
    panel = {case["item"]: case for case in cases()}
    registry = json.loads(REGISTRY.read_bytes())["candidates"]
    index = {}
    for path in sorted((view / "sessions").glob("*/captures.jsonl.gz")):
        ident = json.loads((path.parent / "identity.json").read_bytes())
        with gzip.open(path, "rt", encoding="utf8") as stream:
            for line in stream:
                row = json.loads(line)
                if row["collection"] != COLLECTION:
                    continue
                key = candidate, item = row["candidate"], row["item"]
                role, spec = request_for(panel[item], candidate)
                if (key in index or row["spec"] != spec or row["role"] != role or
                        row["dimension"] != spec["packet"]["dimension"] or ident["candidate"] != candidate or
                        ident["identity"]["model"]["model_sha256"] != registry[candidate]["sha256"]):
                    raise ValueError("paired source or physical identity differs")
                answer = row["evaluation"]
                prediction = "INVALID"
                if row["transport"] == "PASS":
                    try:
                        raw = json.loads(row["capture"]["raw_response"])["choices"][0]["message"]["content"]
                        verified = check(spec["packet"], raw)
                    except (IndexError, ValueError, TypeError, KeyError, AttributeError):
                        verified = None
                    if verified is not None and verified != answer:
                        raise ValueError("control verdict differs from raw response")
                    if verified is not None:
                        prediction = verified["verdict"]
                if prediction == "INVALID" and isinstance(answer, dict) and "verdict" in answer:
                    raise ValueError("archived control verdict lacks a valid transport or raw response")
                refs = answer.get("evidence_refs", []) if isinstance(answer, dict) else []
                index[key] = {"prediction": prediction, "cited_ids": refs, "job": row["job"],
                              "run": row["run"], "attempt": row["attempt"], "transport": row["transport"]}
    rows = []
    for candidate in FAMILIES:
        for item, case in panel.items():
            _, spec = request_for(case, candidate)
            observation = index.get((candidate, item), {"prediction": "NOT_RUN", "cited_ids": []})
            expected = case["expected"]
            proof = case["required_refs"]
            supported = observation["prediction"] == expected and set(proof) == set(observation["cited_ids"])
            rows.append({"candidate": candidate, "case_id": case["case_id"], "arm": case["arm"], "item": item,
                         "expected": expected, "required_refs": proof, "packet_sha256": sha(spec["packet"]),
                         "wire_body_sha256": sha(spec["body"]), **observation, "supported_correct": supported})
    return rows


def family_comparison(left, right):
    """Compare families only on shared case IDs and count their evidence-backed successes."""
    x = {r["case_id"]: r for r in left if r["prediction"] in DECISIONS}
    y = {r["case_id"]: r for r in right if r["prediction"] in DECISIONS}
    shared = sorted(x.keys() & y.keys())
    counts = Counter()
    by_label = Counter()
    for identifier in shared:
        a, b = x[identifier], y[identifier]
        if a["label"] != b["label"]:
            raise ValueError("cross-family source gold differs")
        by_label[a["label"]] += 1
        counts["left_correct"] += a["prediction"] == a["label"]
        counts["right_correct"] += b["prediction"] == b["label"]
        counts["left_supported_correct"] += a["prediction"] == a["label"] and a["citation_correct"]
        counts["right_supported_correct"] += b["prediction"] == b["label"] and b["citation_correct"]
    return {"conclusive_paired": len(shared), "gold_labels": dict(by_label), **counts,
            "paired_accuracy_delta_left_minus_right": ratio(counts["left_correct"] - counts["right_correct"], len(shared))}


def build(archive, split="development", previous=None):
    with snapshot(archive, previous) as (view, hashes):
        primary = measure(view, split)
        controls = control_rows(view)
    controls_by_family = defaultdict(list)
    for row in controls:
        controls_by_family[row["candidate"]].append(row)
    arms = sorted({r["arm"] for r in controls} - {"baseline"})
    comparisons = {k: {arm: compare(rows, arm) for arm in arms} for k, rows in controls_by_family.items()}
    ratings = defaultdict(list)
    family_stats = {}
    strata = {}
    family_rows = {}
    n = sum(1 for _ in iter_gold(split))
    for code in FAMILIES:
        if code in primary["models"]:
            model, relevant = primary["models"][code], primary["case_results"][code]
        else:
            model, relevant = evaluate(split, {})
        family_rows[code] = relevant
        strata[code] = {
            group: {key: {metric: values[metric] for metric in (
                "n", "executed", "predictions", "coverage", "selective_accuracy", "abstention_rate_among_executed")}
                    for key, values in categories.items()}
            for group, categories in model["strata"].items()
        }
        for row in relevant:
            ratings[row["case_id"]].append(row["prediction"])
        family_stats[code] = {"planned": n, "executed": model.get("executed", 0),
                              "conclusive": sum(r["prediction"] in DECISIONS for r in relevant),
                              "correct": sum(r["prediction"] == r["label"] for r in relevant),
                              "supported_correct": sum(r["prediction"] == r["label"] and r["citation_correct"] for r in relevant),
                              "abstained": sum(r["prediction"] == "BLOCKED" for r in relevant),
                              "invalid": sum(r["prediction"] == "INVALID" for r in relevant)}
    family_pairs = {a + "/" + b: family_comparison(family_rows[a], family_rows[b])
                    for a in FAMILIES for b in FAMILIES if a < b}
    source_digests = {p.name: digest(p) for p in
                      (Path(__file__), Path(__file__).with_name("robustness.py"), FOLDER / "manifest.json")}
    return {"version": "IJ073-AEVE-META-1", "source_sha256": source_digests, "primary_strata": strata, "matched_families": family_pairs, "split": split, "qualification_freeze": primary["protocol_sha256"],
            "session_manifests": hashes, "primary": family_stats, "primary_nominal_agreement": nominal_alpha(ratings.values()),
            "primary_pairwise_agreement": primary["cross_judge"], "control_collection": COLLECTION,
            "planned_controls": len(controls), "executed_controls": sum(r["prediction"] != "NOT_RUN" for r in controls),
            "paired_controls": comparisons, "control_case_results": controls,
            "interpretation": {"source_worlds": 4, "dimension": "D05", "source": "synthetic business balance",
                "language": "Within-source translation comparisons control for the label-language correlation in these four baselines.",
                "claimed_family": "Synthetic attribution labels measure sensitivity to a claimed source. Actual own-family preference needs blinded model-authored examples.",
                "uncertainty": "Each treatment compares at most four source cases. Exact McNemar p-values are descriptive, with no multiplicity adjustment.",
                "scope": "Primary coverage and agreement describe this archive snapshot. Admission uses the frozen qualification procedure."}}


def render(report):
    lines = ["# AEVE Judge agreement and controlled bias", "",
             f"Primary split `{report['split']}`. {len(report['session_manifests'])} GPU session manifests are pinned in the companion JSON.", "",
             "| Judge | Planned | Recorded | Conclusive | Correct | Correct with gold citations | Abstained | Invalid |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for code, stats in report["primary"].items():
        cells = [stats[k] for k in ("planned", "executed", "conclusive", "correct", "supported_correct", "abstained", "invalid")]
        lines.append("| " + " | ".join(map(str, [FAMILIES[code], *cells])) + " |")
    alpha = report["primary_nominal_agreement"]
    coefficient = alpha["nominal_alpha"]
    formatted = "undefined" if coefficient is None else f"{coefficient:.3f}"
    lines.extend(["", f"Nominal Krippendorff agreement is {formatted} across {alpha['units_with_overlap']} cases with overlapping decisions.",
                  "", "| Judge pair | Same-source conclusive pairs | First correct | Second correct |",
                  "|---|---:|---:|---:|"])
    for pair, values in sorted(report["matched_families"].items()):
        first, second = pair.split("/")
        lines.append(f"| {FAMILIES[first]} / {FAMILIES[second]} | {values['conclusive_paired']} | "
                     f"{values.get('left_correct', 0)} | {values.get('right_correct', 0)} |")
    lines.extend(["", "The following groups describe the primary cases recorded so far. Counts on different cases can reflect case selection.",
                  "", "| Judge | Group | Planned | Recorded | Conclusive | Accuracy among conclusive |",
                  "|---|---|---:|---:|---:|---:|"])
    for code in FAMILIES:
        for dimension in ("language", "injection"):
            for label, vals in sorted(report["primary_strata"][code][dimension].items()):
                count = sum(vals["predictions"].get(k, 0) for k in DECISIONS)
                accuracy = vals["selective_accuracy"]
                display = f"{accuracy:.1%}" if accuracy is not None else "—"
                lines.append(f"| {FAMILIES[code]} | {dimension}={label} | {vals['n']} | {vals['executed']} | {count} | {display} |")
    lines.extend(["", f"Paired controls have {report['executed_controls']}/{report['planned_controls']} captured responses."])
    if report["executed_controls"]:
        lines.extend(["", "| Judge | Treatment | Conclusive pairs / planned | Improved | Degraded | Both correct with gold citations |",
                      "|---|---|---:|---:|---:|---:|"])
        for code, arms in report["paired_controls"].items():
            for arm, result in arms.items():
                lines.append(f"| {FAMILIES[code]} | {arm} | {result['conclusive_pairs']} / {result['planned_pairs']} | "
                             f"{result['improved']} | {result['degraded']} | {result['both_correct_with_gold_citations']} |")
    lines.extend(["", *[report["interpretation"][k] for k in ("language","claimed_family","uncertainty","scope")]])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT / "results")
    parser.add_argument("--split", choices=["development","calibration","qualification"], default="development")
    parser.add_argument("--replay", type=Path, help="Pin the same session manifests as an earlier JSON report")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    previous = json.loads(args.replay.read_bytes()) if args.replay else None
    if previous and previous["split"] != args.split:
        raise ValueError("replay split differs")
    report = build(args.archive, args.split, previous["session_manifests"] if previous else None)
    if previous is not None and report != previous:
        raise ValueError("replayed report differs from pinned results or procedure")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, report)
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render(report), encoding="utf8", newline="\n")


if __name__ == "__main__":
    main()
