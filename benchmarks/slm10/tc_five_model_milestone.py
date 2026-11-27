"""Generate the complete five-model TC-V3 physical milestone from portable seals."""

import argparse
from io import StringIO
import csv

from evaluation.aeve.archive import check_text
from evaluation.aeve.runtime import canonical

from .tc_five_model_report import compile_report
from .tc_priority_milestone import (
    HYPOTHESES, compile_milestone, datasheet, html_report, overview, pareto_markdown,
)
from .tc_v3 import HERE

MODELS = ("A", "B", "D", "F", "G")
OUT = HERE.parent / "milestones/tc-five-model"
PROFILES = HYPOTHESES | {
    "F": ("Strict answer format fails more often than first tool selection", "Structured Output Contract",
          "Run an independent online comparison and preserve provider output, typed values, and intervention attribution."),
    "G": ("Exact terminal output fails despite substantial correct tool execution", "Result Codec and Structured Output Contract",
          "Use the matched case-level differences to select a candidate intervention, then test it on independent tasks."),
}


def report():
    matrix, evidence = compile_milestone(MODELS)
    expanded = compile_report()
    if expanded["physical_coverage_status"] != "PASS" or expanded["assessment_sha256"] != evidence["derived_priority_rows_sha256"]:
        raise ValueError("full scope and matched report disagree on the physical seal replay")
    pairs = {
        "scope": matrix["scope"], "dataset_manifest_sha256": evidence["dataset_manifest_sha256"],
        "assessment_sha256": expanded["assessment_sha256"],
        "first_attempt": {model: entry["matched"] for model, entry in matrix["models"].items()},
        "streaming_agreement_and_repeat_reliability": expanded["paired_cases"],
        "paired_definitions": {key: expanded["definitions"][key]
                               for key in ("STREAMING_CONSISTENCY", "REPEAT_RELIABILITY")},
        "strict_d25": "BLOCKED",
    }
    evidence["derived_all_rows_sha256"] = evidence.pop("derived_priority_rows_sha256")
    table = overview(matrix)
    text = (
        "# Five-model TC-V3 physical measurement\n\n"
        "All 8,250 frozen trials have replayable Radeon execution evidence. Physical coverage is PASS. "
        "Strict D25 remains BLOCKED for all 8,250 slots. Scoped completion uses cases where both paths "
        "have evaluable observations.\n\n"
        + table + "\n"
    )
    csv_rows = StringIO()
    writer = csv.DictWriter(csv_rows, fieldnames=list(matrix["cells"][0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(matrix["cells"])
    files = {
        "README.md": (text + "\n[Paired results](PAIRED_RESULTS.json) · "
                      "[Resource Pareto](QUALITY_RESOURCE_PARETO.md) · [Interactive report](report.html) · "
                      "[中文报告](ENGINEERING_REPORT_ZH.md) · [Evidence](EVIDENCE_MANIFEST.json)\n\n"
                      "Reproduce from a repository checkout with `PYTHONPATH=src` and "
                      "`python -m benchmarks.slm10.tc_five_model_milestone`.\n").encode(),
        "ENGINEERING_REPORT_ZH.md": (
            "# 五模型 TC-V3 真机闭合\n\n"
            "8,250 条冻结试次均有 Radeon 可复算封存。物理覆盖为 PASS。"
            "严格 D25 为 BLOCKED。配对完成率使用双方均可评价的同一任务。\n\n" + table + "\n"
        ).encode(),
        "CAPABILITY_MATRIX.json": canonical(matrix) + b"\n",
        "CAPABILITY_MATRIX.csv": csv_rows.getvalue().encode(),
        "PAIRED_RESULTS.json": canonical(pairs) + b"\n",
        "EVIDENCE_MANIFEST.json": canonical(evidence) + b"\n",
        "QUALITY_RESOURCE_PARETO.md": pareto_markdown(matrix).encode(),
        "report.html": html_report(matrix).replace("priority capability", "five-model capability")
        .replace("4,950 physical", "8,250 physical").encode(),
    }
    for model, entry in matrix["models"].items():
        sheet = datasheet(model, entry, matrix, hypotheses=PROFILES)
        if model == "F":
            sheet += ("\nThe publisher describes a 3.4B language model and a 0.4B vision encoder for the family. "
                      "[Publisher model card](https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF)\n")
        if model == "G":
            sheet += ("\nThe 2.3 billion figure is effective capacity. The source count includes per-layer "
                      "embeddings. [Radeon admission](../../../../../reports/SLM11_GEMMA4_RADEON_ADMISSION.md)\n")
        files[f"MODEL_{model}_DATASHEET.md"] = sheet.encode()
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    for name, raw in report().items():
        check_text(raw)
        path = OUT / name
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"{name} differs from the complete TC-V3 replay")
    print("Verified the complete 8,250-trial TC-V3 physical milestone. Strict D25 is BLOCKED.")


if __name__ == "__main__":
    main()
