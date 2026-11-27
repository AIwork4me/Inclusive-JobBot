"""Build the A/B/D TC-V3 milestone directly from the published portable seals."""

import argparse
from collections import Counter, defaultdict
import csv
from hashlib import sha256
from html import escape
from io import StringIO
import json

from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import ROOT, canonical

from .tc_atlas_views import paired_frontier
from .tc_capability_metrics import build, summarize_cell
from .tc_capability_replay import VERDICTS
from .tc_dashboard import ARCHIVE, STATUS, objects, percentile, proportion
from .tc_priority_report import MODELS, pairs
from .tc_v3 import HERE

OUT = HERE.parent / "milestones/tc-priority"
TRACKS = ("direct_first", "sdk_first", "sdk_streaming", "sdk_repeat")
CORE_METRICS = (
    "FIRST_TOOL_CHOICE", "REQUIRED_ACTION_COVERAGE", "EXACT_ACTION_SEQUENCE",
    "EXECUTION_PROCESS_CORRECTNESS", "OUTPUT_CONTRACT_COMPLIANCE", "TERMINATION_CORRECTNESS",
)
HYPOTHESES = {
    "A": ("Repeated proposals and termination failures", "Action Ledger and Goal/Budget Controller",
          "Measure proposals, caught duplicates and correct terminal answers separately. Include legitimate retries, "
          "entity changes, expired observations and changed authorization as negative controls."),
    "B": ("Reduced scoped completion through SDK", "Compact Result Codec",
          "Use the frozen 12-task holdout. Keep the model, tools, world, seed and evaluation contract paired."),
    "D": ("Output contract failures despite successful execution", "Structured Output Contract",
          "Compare native, constrained, normalized and retry-assisted arms. Reject ambiguous values and forbid "
          "access to private expected answers."),
}
SEALED_COMPONENTS = ("authorization", "entity_binding", "required_arguments")
FACT_METRICS = {"BUSINESS_FACT_CORRECTNESS", "QUALIFIED_BUSINESS_COMPLETION"}
TOOL_METRICS = {"RESULT_DELIVERY", "RESULT_COMPREHENSION", "entity_binding", "required_arguments"}


def metric_cell(observations):
    chosen = []
    not_applicable = 0
    for applicable, status in observations:
        if status not in STATUS:
            raise ValueError(f"invalid disposition: {status}")
        if applicable:
            chosen.append(status)
        else:
            not_applicable += 1
    result = proportion(chosen)
    return result | {"full": len(chosen) + not_applicable, "applicable": len(chosen),
                     "observed": result["PASS"] + result["FAIL"], "N/A": not_applicable}


def outcome(row, metric, oracle):
    if metric in SEALED_COMPONENTS:
        status = row["sealed_component_assessment"][metric]
    else:
        status = row["sealed_status"] if metric == "STRICT_END_TO_END_SUCCESS" else row["metrics"][metric]
    applicable = (
        (metric not in FACT_METRICS or row["business_fact_scope_eligible"])
        and (metric not in TOOL_METRICS or bool(oracle["nodes"]))
        and (metric != "authorization" or oracle["risk_scope"] != "synthetic-read-only")
    )
    return applicable, status


def resource_summary(rows):
    fields = ("input_tokens", "output_tokens", "total_tokens", "model_requests", "provider_inference_ms",
              "end_to_end_wall_ms", "sdk_boundary_wall_ms_sum")
    samples = {field: [r["telemetry"][field] for r in rows] for field in fields}
    samples["actual_tool_executions"] = [r["call_counts"]["executions"] for r in rows]
    samples["context_consumption"] = [None] * len(rows)
    return {field: {"status": ("PASS" if all(v is not None for v in values) else
                              "BLOCKED" if any(v is not None for v in values) else "NOT_RUN"),
                    "observed": sum(v is not None for v in values), "full": len(values), **percentile([v for v in values if v is not None])}
            for field, values in samples.items()}


def compile_milestone():
    raw_rows, replay = build()
    rows = [row for row in raw_rows if row["candidate"] in MODELS]
    if len(rows) != 4950 or any(row["physical_execution"] != "PASS" for row in rows):
        raise ValueError("priority milestone requires the original 4950 physical trials")
    oracle = {row["case_id"]: row for row in objects(HERE / "holdout-oracle.jsonl")}
    grouped = defaultdict(list)
    for row in rows:
        for stratum, value in (("all", "all"), ("family", row["family"]), ("language", row["language"]),
                               ("risk_scope", row["risk_scope"])):
            grouped[row["candidate"], row["track"], stratum, value].append(row)
    counts = Counter((row["candidate"], row["track"]) for row in rows)
    expected = { (model, track): 150 if track == "sdk_repeat" else 500 for model in MODELS for track in TRACKS }
    if counts != expected:
        raise ValueError("priority track coverage differs from the frozen design")
    matrix = []
    for (model, track, stratum, value), cohort in sorted(grouped.items()):
        for metric in (*VERDICTS, *SEALED_COMPONENTS):
            cells = metric_cell(outcome(row, metric, oracle[row["case_id"]]) for row in cohort)
            matrix.append({"model": model, "track": track, "stratum": stratum, "value": value, "metric": metric,
                           "planned": len(cohort), "executed": len(cohort), "sealed": len(cohort), **cells})
    sessions, identities = {}, defaultdict(dict)
    for run, seal in replay["sealed_manifests"].items():
        model = seal["candidate"]
        if model not in MODELS:
            continue
        path = ARCHIVE / run / "manifest.json"
        manifest = json.loads(path.read_bytes())
        identity = {k: manifest["identity"][k] for k in
                    ("model", "engine", "backend", "sdk_version", "harness_sha256", "template_sha256")}
        identity["gpu"] = manifest["launch"]["gpu"]
        identity["launch_args"] = manifest["launch"]["args"]
        identity["gpu_lease"] = {k: manifest["launch"]["gpu_lease"][k]
                                 for k in ("host_sha256", "gpu_physical_sha256")}
        identities[model][canonical(identity)] = identity
        sessions[run] = seal | {"path": path.relative_to(ROOT).as_posix(),
                                "execution_git_sha": manifest["identity"]["git_sha"]}
    models = {}
    for m in MODELS:
        selected = [row for row in rows if row["candidate"] == m]
        source = ROOT / f"evidence/IJ07/model_identity/{m}.json"
        official = json.loads(source.read_bytes())
        weight_bytes = official["runtime_asset"].get("size")
        if m == "A":
            acquisition = ROOT / "evidence/IJ0/model_identity.json"
            records = json.loads(acquisition.read_bytes())["models"]
            asset = official["runtime_asset"]
            weight_bytes, = [file["actual_size"] for record in records for file in record["files"]
                             if record["revision"] == asset["revision"] and file["path"] == asset["filename"]
                             and file["actual_sha256"] == asset["expected_sha256"] and file["status"] == "PASS"]
        per_track = {}
        for track in TRACKS:
            cohort = grouped[m, track, "all", "all"]
            runs = {r["physical_run_id"] for r in cohort}
            peaks = [sessions[run]["peak_gpu_committed_bytes"] for run in sorted(runs)]
            summary = summarize_cell(cohort)
            per_track[track] = {"resources": resource_summary(cohort), "session_peak_gpu_committed_bytes": {
                "observed_sessions": sum(p is not None for p in peaks), "sessions": len(peaks), **percentile([p for p in peaks if p is not None])},
                "event_rates": summary["rates"], "cost_per_outcome": summary["cost_per_outcome"]}
        comparisons = {}
        for metric in VERDICTS:
            matches = defaultdict(dict)
            for row in selected:
                if row["track"] in TRACKS[:3]:
                    key = (row["case_id"], row["seed"], row["risk_scope"])
                    matches[key][row["track"]] = row["metrics"][metric]
            comparisons[metric] = {f"{first}/{second}": pairs(matches, first, second)
                                   for first, second in ((TRACKS[0], TRACKS[1]), (TRACKS[1], TRACKS[2]))}
        examples = {}
        for metric in (*CORE_METRICS, "QUALIFIED_BUSINESS_COMPLETION"):
            for track in TRACKS:
                cohort = grouped[m, track, "all", "all"]
                examples[f"{track}/{metric}"] = [
                    {k: r[k] for k in ("trial_id", "case_id", "physical_run_id", "physical_manifest_sha256")}
                    for r in cohort if r["metrics"][metric] == "FAIL"
                ][:3]
        models[m] = {
            "identity_source": {"path": source.relative_to(ROOT).as_posix(), "sha256": digest(source)},
            "architecture": official["official_config_and_template"]["config_fields"]["architectures"],
            "official_parameter_count": official["hf_safetensors_parameters"], "license_id": official["license_id"],
            "weight_file_bytes": weight_bytes,
            "configurations": list(identities[m].values()), "tracks": per_track, "matched": comparisons,
            "failure_examples": examples, "pareto": paired_frontier(selected, sessions),
        }
    return {"schema_version": "1.0", "scope": "TC-V3/1.0 priority Radeon measurement", "planned": 4950,
            "executed": len(rows), "sealed": len(rows), "strict_d25": "BLOCKED",
            "definitions": replay["definitions"], "models": models, "cells": matrix}, {
        "schema_version": "1.0", "dataset_manifest_sha256": replay["dataset_manifest_sha256"],
        "mechanical_registry_sha256": replay["mechanical_registry_sha256"], "sources": replay["sources"],
        "sessions": sessions, "derived_priority_rows_sha256": sha256(
            b"".join(canonical(row) + b"\n" for row in rows)).hexdigest(),
    }


def overview(doc):
    lines = ["| Model | SDK first tool | Required coverage | Exact sequence | Execution | Output | Termination | Direct completion | SDK completion |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    cells = {(c["model"], c["metric"]): c for c in doc["cells"] if c["track"] == "sdk_first" and c["stratum"] == "all"}
    for model, entry in doc["models"].items():
        pair = entry["matched"]["QUALIFIED_BUSINESS_COMPLETION"]["direct_first/sdk_first"]
        t = pair["transitions"]
        direct = t.get("PASS/PASS", 0) + t.get("PASS/FAIL", 0)
        sdk = t.get("PASS/PASS", 0) + t.get("FAIL/PASS", 0)
        rates = [f"{cells[model, metric]['PASS']}/{cells[model, metric]['full']}" for metric in
                 ("FIRST_TOOL_CHOICE", "REQUIRED_ACTION_COVERAGE", "EXACT_ACTION_SEQUENCE", "EXECUTION_PROCESS_CORRECTNESS",
                  "OUTPUT_CONTRACT_COMPLIANCE", "TERMINATION_CORRECTNESS")]
        n = pair["evaluable_pairs"]
        lines.append(f"| {model} | " + " | ".join(rates + [f"{direct}/{n}", f"{sdk}/{n}"]) + " |")
    return "\n".join(lines)


def datasheet(model, entry, doc):
    config = entry["configurations"][0]
    identity = config["model"]
    symptom, component, validation = HYPOTHESES[model]
    lines = [
        f"# {identity['official_model_id']} TC-V3 datasheet", "",
        f"{entry['architecture'][0]} has {entry['official_parameter_count']:,} parameters in the frozen upstream source.",
        f"The measured GGUF uses {identity['quantization']} and has SHA256 `{identity['model_sha256']}`.",
        f"Weight file size in bytes is {entry['weight_file_bytes'] or 'NOT_RUN in the published identity record'}.",
        f"The source license metadata is `{entry['license_id']}`. See the pinned source identity for revision details.",
        f"Measurements use {config['gpu']['architecture']} via {config['backend']}, an 8,192-token configured context, "
        f"llama.cpp {config['engine']['build']} and Antigravity SDK {config['sdk_version']}.",
        "Exact runtime and template digests are in the [capability matrix](CAPABILITY_MATRIX.json).", "",
        "## Native and SDK capability", "",
        "| Track | Metric | PASS | FAIL | BLOCKED | NOT_RUN | Applicable | Full |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cell in doc["cells"]:
        if cell["model"] == model and cell["stratum"] == "all":
            lines.append("| " + " | ".join(str(cell[k]) for k in
                         ("track", "metric", *STATUS, "applicable", "full")) + " |")
    lines += ["", "## Failure signature and compensation", "", f"Observed signature — {symptom}.",
              f"HYPOTHESIS — {component}. {validation}",
              "Trial and seal references are listed by metric in the [capability matrix](CAPABILITY_MATRIX.json).", "",
              "## Resource envelope", "",
              "| Track | Resource | Observed | P50 | P95 |",
              "| --- | --- | ---: | ---: | ---: |"]
    for track, summary in entry["tracks"].items():
        for field, cell in summary["resources"].items():
            values = [str(cell[k]) if cell[k] is not None else cell["status"] for k in ("p50", "p95")]
            lines.append(f"| {track} | {field} | {cell['observed']}/{cell['full']} | {' | '.join(values)} |")
    lines += ["", "The matrix records session-level GPU memory and the measured resource totals per verified outcome.",
              "Strict D25, production job accuracy, planning depth, autonomy and NPU performance remain unqualified."]
    return "\n".join(lines) + "\n"


def payloads(doc, evidence):
    data = StringIO()
    writer = csv.DictWriter(data, fieldnames=list(doc["cells"][0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(doc["cells"])
    table = overview(doc)
    prefix = "# Priority TC-V3 physical measurement\n\n"
    note = ("4,950 physical A/B/D executions and 4,950 verified portable trial records. The scoped completion "
            "columns use only pairs for which both paths are evaluable. Strict D25 remains BLOCKED. "
            "These are frozen synthetic tool-calling tasks. Job performance and autonomous planning require separate qualification.\n")
    results = {
        "CAPABILITY_MATRIX.json": canonical(doc) + b"\n",
        "EVIDENCE_MANIFEST.json": canonical(evidence) + b"\n",
        "CAPABILITY_MATRIX.csv": data.getvalue().encode(),
        "README.md": (prefix + note + "\n[English report](ENGINEERING_REPORT_EN.md) · "
                      "[中文总结](ENGINEERING_REPORT_ZH.md) · [Interactive report](report.html) · "
                      "[Reproduction guide](REPRODUCTION_GUIDE.md)\n").encode(),
        "ENGINEERING_REPORT_EN.md": (prefix + note + "\n" + table + "\n").encode(),
        "ENGINEERING_REPORT_ZH.md": ("# 三模型工具调用测量\n\nA、B、D 的 4,950 次冻结试次均有 Radeon 执行证据。"
                                     "限定合成任务的完成率使用两条路径均可评价的配对。严格 D25 仍为 BLOCKED。"
                                     "岗位正确率和自主规划等级需独立验证。\n\n" + table + "\n").encode(),
        "SDK_CAPABILITY_DELTA.md": ("# Paired SDK capability delta\n\n" + table + "\n\n"
                                    "The matrix includes all paired disposition transitions and simultaneous Wilson"
                                    " bounds for paired differences. SDK first and streaming are also paired.\n").encode(),
        "QUALITY_RESOURCE_PARETO.md": pareto_markdown(doc).encode(),
        "REPRODUCTION_GUIDE.md": ("# Reproduce the priority milestone\n\nFrom the repository root in a fresh clone, "
                                  "set `PYTHONPATH` to the root, `src`, and `benchmarks/tool_calling/runner` using the OS path separator.\n\n"
                                  "```sh\npython -m benchmarks.slm10.tc_priority_milestone\n```\n\n"
                                  "The replay verifies each portable seal and reconstructs the figures without loading model weights. "
                                  "Use `--write` to regenerate the deliverables. The evidence manifest lists each selected seal "
                                  "and its capture-source commit.\n").encode(),
        "report.html": html_report(doc).encode(),
    }
    for model, entry in doc["models"].items():
        results[f"MODEL_{model}_DATASHEET.md"] = datasheet(model, entry, doc).encode()
    return results


def pareto_markdown(doc):
    lines = ["# Matched quality and resource use", "",
             "Each model uses its jointly evaluable case intersection across all first-attempt paths with complete "
             "token, provider-latency and session-memory telemetry. Median provider latency excludes SDK overhead.", "",
             "| Model | Track | Matched cases | Scoped completions | Median tokens | Median provider ms | Frontier |",
             "| --- | --- | ---: | ---: | ---: | ---: | --- |"]
    for model, entry in doc["models"].items():
        result = entry["pareto"]
        for track, point in result["points"].items():
            lines.append(f"| {model} | {track} | {result['jointly_evaluable_cases']} | {point['quality']['PASS']} | "
                         f"{point['total_tokens']['p50']} | {point['provider_inference_ms']['p50']} | "
                         f"{point.get('on_frontier', 'BLOCKED')} |")
    return "\n".join(lines) + "\n"


def html_report(doc):
    columns = ("model", "track", "stratum", "value", "metric", "full", "applicable", "observed", *STATUS, "N/A")
    headings = "".join(f"<th scope='col'>{escape(k)}</th>" for k in columns)
    rows = "\n".join("<tr>" + "".join(f"<td>{escape(str(c[k]))}</td>" for k in columns) + "</tr>"
                     for c in doc["cells"])
    return (
        "<!doctype html><html lang='en'><meta charset='utf-8'><title>TC-V3 priority capability</title>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<style>body{font:16px system-ui;margin:2rem;color:#192633}table{border-collapse:collapse}"
        "th,td{padding:.45rem .7rem;text-align:left;border-bottom:1px solid #cad5df}"
        "th{background:#edf3f7;position:sticky;top:0}input{margin:.5rem;padding:.5rem}"
        ".table{overflow:auto;max-height:70vh}</style>"
        "<h1>TC-V3 priority capability</h1><p>4,950 physical Radeon trials. Strict D25 is BLOCKED.</p>"
        "<label>Filter rows <input id='filter' type='search'></label>"
        "<p id='count' aria-live='polite'></p><div class='table' tabindex='0' aria-label='Capability matrix'>"
        f"<table><thead><tr>{headings}</tr></thead><tbody>{rows}</tbody></table></div>"
        "<script>const input=document.querySelector('#filter');const rows=[...document.querySelectorAll('tbody tr')];"
        "function apply(){const terms=input.value.toLowerCase().trim().split(/\\s+/);let shown=0;"
        "for(const row of rows){row.hidden=!terms.every(t=>row.textContent.toLowerCase().includes(t));"
        "if(!row.hidden)shown++;}document.querySelector('#count').textContent=shown+' rows';}"
        "input.addEventListener('input',apply);apply();</script></html>\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    doc, evidence = compile_milestone()
    for name, content in payloads(doc, evidence).items():
        check_text(content)
        path = OUT / name
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        elif path.read_bytes() != content:
            raise ValueError(f"{name} differs from the priority seal replay")
    print(f"Verified {doc['sealed']} priority TC-V3 trials and their milestone outputs")


if __name__ == "__main__":
    main()
