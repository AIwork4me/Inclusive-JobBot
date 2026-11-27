"""Seal the full frozen Q2 report with its original captures and measured costs."""
import argparse
from collections import Counter, defaultdict
import json
from math import ceil, isfinite
from pathlib import Path

from .archive import digest
from .contracts import ROOT as AEVE
from .history import lines
from .meta_evaluation import snapshot
from .q2_development import config
from .q2_qualification import COLLECTION, measure, protocol, roster
from .report_qualification import rate
from .runtime import ROOT, fingerprint, write_json

FROZEN = ROOT / "evidence/IJ073/aeve/q2_qualification_protocol.json"


def require_coverage(expected, seen):
    if set(seen) - set(expected):
        raise ValueError("unexpected Q2 candidate")
    missing = [f"{code}: {len(seen.get(code, set()) & cases)}/{len(cases)}"
               for code, cases in sorted(expected.items()) if seen.get(code) != cases]
    if missing:
        raise ValueError("sealed Q2 roster is incomplete or differs from its freeze: " + ", ".join(missing))


def wall_summary(samples):
    values = sorted(samples)
    count, elapsed = len(values), sum(values)
    return {"requests": count,
            "p50_wall_ms": values[ceil(count * .50) - 1] if count else None,
            "p95_wall_ms": values[ceil(count * .95) - 1] if count else None,
            "total_request_wall_ms": elapsed,
            "evaluations_per_request_wall_second": 1000 * count / elapsed if elapsed else None}


def measured_cost(rows):
    summary = wall_summary([row["wall_ms"] for row in rows])
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        values = [row["usage"][field] for row in rows if type(row["usage"].get(field)) is int]
        summary[field] = {"recorded": len(values), "total": sum(values)}
    durations = []
    for row in rows:
        prompt, decode = (row["timings"].get(key) for key in ("prompt_ms", "predicted_ms"))
        if all(type(value) in {int, float} and isfinite(value) and value >= 0 for value in (prompt, decode)):
            durations.append(prompt + decode)
    summary["native_inference_ms"] = {"recorded": len(durations), "total": round(sum(durations), 3)}
    return summary


def scan(out):
    sessions, cases = [], defaultdict(set)
    for stamp in sorted((out / "sessions").glob("*/manifest.json")):
        rows = json.loads(stamp.with_name("outcomes.json").read_bytes())
        selected = [row for row in rows if row["collection"] == COLLECTION]
        if not selected:
            continue
        sessions.append(stamp)
        for row in selected:
            candidate, item = row["candidate"], row["item"]
            if item in cases[candidate]:
                raise ValueError("duplicate Q2 assessment in sealed index")
            cases[candidate].add(item)
    return sessions, cases


def details(stamps):
    sessions, responses = {}, {}
    registry = config()
    for stamp in stamps:
        identity = json.loads(stamp.with_name("identity.json").read_bytes())
        candidate, launch = identity["candidate"], identity["launch"]
        runtime = identity["identity"]
        model = runtime["model"]
        pin = registry["candidates"][candidate]
        if (model["model_sha256"] != pin["sha256"] or model["runtime_revision"] != pin["revision"]
                or model["quantization"] != registry["quantization"]
                or launch["backend"] != registry["backend"]
                or not 0 < launch["layers_offloaded"] == launch["layers_total"]
                or launch["template_sha256"] != runtime["template"]["sha256"]
                or "--ctx-size" not in launch["args"]
                or int(launch["args"][launch["args"].index("--ctx-size") + 1]) != registry["context_tokens"]):
            raise ValueError("Q2 runtime identity differs from the frozen registry")
        memory = {"dedicated_bytes": [], "shared_bytes": [], "committed_bytes": []}
        pid = f"pid_{launch['pid']}_"
        for counter in lines(stamp.with_name("live-gpu.jsonl.gz")):
            if counter["kind"] == "gpu_process_memory" and counter["instance"].startswith(pid):
                for field in memory:
                    memory[field].append(counter[field])
        manifest = json.loads(stamp.read_bytes())
        sessions[identity["run_id"]] = {
            "candidate": candidate, "manifest_sha256": digest(stamp), "sha256": manifest["sha256"],
            "identity": identity, "pid_bound_gpu_active_samples": manifest["active_pid_counter_samples"],
            "process_gpu_memory_sample_count": len(memory["dedicated_bytes"]),
            "process_gpu_memory_peaks": {field: max(values, default=None) for field, values in memory.items()},
        }
        for row in lines(stamp.with_name("captures.jsonl.gz")):
            if row["collection"] != COLLECTION:
                continue
            capture = row["capture"]
            try:
                wire = json.loads(capture["raw_response"] or "{}")
            except ValueError:
                wire = {}
            choices = wire.get("choices") or [{}]
            reason = choices[0].get("finish_reason")
            evaluation = row["evaluation"]
            responses[row["job"]] = {
                "source_generation_id": wire.get("id"), "transport": row["transport"],
                "http_status": capture["http_status"], "finish_reason": reason,
                "error": "output_limit" if reason == "length" else
                         "transport_failure" if row["transport"] != "PASS" else
                         "judgment_contract" if "verdict" not in evaluation else None,
                "citations": evaluation.get("evidence_refs"), "reason_summary": evaluation.get("reason_summary"),
                "wall_ms": capture["wall_ms"], "usage": wire.get("usage") or {},
                "timings": wire.get("timings") or {},
            }
    return sessions, responses


def memory_peaks(sessions):
    return {field: max((value for session in sessions
                        if (value := session["process_gpu_memory_peaks"][field]) is not None),
                       default=None)
            for field in ("dedicated_bytes", "shared_bytes", "committed_bytes")}


def build(archive, manifest_hashes=None):
    plan = json.loads(FROZEN.read_bytes())
    with snapshot(archive, manifest_hashes) as (view, hashes):
        stamps, seen = scan(view)
        expected = {code: set(roster()) for code in plan["arms"]}
        require_coverage(expected, seen)
        if protocol(view) != plan:
            raise ValueError("Q2 report cannot replay the published freeze")
        report = measure(view, plan)
        sessions, responses = details(stamps)
        if len(responses) != sum(map(len, expected.values())):
            raise ValueError("sealed Q2 capture count differs from its index")
    for code, model in report["models"].items():
        rows = model["cases"]
        for row in rows:
            row.update(responses[row["job"]])
        model["cost"] = measured_cost(rows)
        model["error_counts"] = dict(Counter(row["error"] for row in rows if row["error"]))
        model["strata"] = {
            name: {key: rate([row for row in rows if row[name] == key],
                             lambda row: row["label"] == row["prediction"])
                   for key in sorted({row[name] for row in rows})}
            for name in ("language", "dimension")
        }
        model["runtime_sessions"] = sorted(run for run, session in sessions.items() if session["candidate"] == code)
        model["cost"]["gpu_memory_peaks_bytes"] = memory_peaks(
            [sessions[run] for run in model["runtime_sessions"]])
    total = measured_cost([row for model in report["models"].values() for row in model["cases"]])
    total["gpu_memory_peaks_bytes"] = memory_peaks(list(sessions.values()))
    total["electricity_and_currency_cost"] = {"status": "NOT_RUN", "reason": "energy and tariff not captured"}
    verdict = "PASS" if sum(row["status"] == "PASS" for row in report["models"].values()) >= 2 else "FAIL"
    return {"version": "IJ073-Q2-CLOSURE-3", "judge_qualification": verdict,
            "measured_operating_cost": total, "protocol_sha256": fingerprint(plan),
            "source_sha256": digest(Path(__file__)), "dataset_sha256": plan["dataset_sha256"],
            "session_manifests": hashes, "recorded": len(responses), "sessions": sessions, **report}


def markdown(report):
    gates = report["protocol"]["thresholds"]
    parts = ["# IJ-0.7.3 full Q2 Judge qualification", "",
             f"All {report['recorded']:,} frozen Radeon assessments have sealed source evidence.", "",
             f"**Formal Q2 Judge qualification: {report['judge_qualification']}.**", "",
             "| Judge | Admission | Unmet individual gates | P50 ms | P95 ms | Input tokens | Output tokens | Peak committed GPU bytes | Inference ms |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for code, model in report["models"].items():
        cost = model["cost"]
        unmet = ", ".join(model["unmet"]) or "None"
        parts.append(f"| {code} | {model['status']} | {unmet} | {cost['p50_wall_ms']} | "
                     f"{cost['p95_wall_ms']} | {cost['prompt_tokens']['total']:,} | "
                     f"{cost['completion_tokens']['total']:,} | "
                     f"{cost['gpu_memory_peaks_bytes']['committed_bytes'] or '—'} | "
                     f"{cost['native_inference_ms']['total']:,.0f} |")
    parts.extend(["", "Admission uses the frozen individual and cross-family gates.", "",
                  "| Metric | Floor | " + " | ".join(report["models"]) + " |",
                  "|---|---:" + "|---:" * len(report["models"]) + "|"])
    for metric, floor in gates.items():
        if metric == "kappa":
            continue
        values = [model["metrics"][metric]["point_among_recorded"] for model in report["models"].values()]
        values = ["—" if value is None else f"{value:.4f}" for value in values]
        parts.append(f"| {metric} | {floor:g} | " + " | ".join(values) + " |")
    parts.extend(["", f"Paired Cohen’s κ floor is {gates['kappa']:g}. The companion JSON records agreement, "
                  "world-cluster intervals, error categories, run identity, token usage and GPU counters. "
                  "Request wall time excludes server startup and model switching. Native inference time is "
                  "the engine's measured prefill plus decode time on the qualified GPU-offloaded runtime. "
                  "Electricity and currency cost were not measured.", ""])
    return "\n".join(parts)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, default=AEVE / "results")
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--markdown", type=Path)
    cli.add_argument("--replay", type=Path)
    args = cli.parse_args()
    original = json.loads(args.replay.read_bytes()) if args.replay else None
    report = build(args.archive, original["session_manifests"] if original else None)
    if original is not None and original != report:
        raise ValueError("sealed Q2 closure does not replay")
    write_json(args.output, report)
    if args.markdown:
        args.markdown.write_text(markdown(report), encoding="utf8")
    print(f"{report['recorded']} frozen Q2 assessments verified")


if __name__ == "__main__":
    main()
