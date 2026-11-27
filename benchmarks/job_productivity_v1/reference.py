"""Run the same document-review development cases on the Qwen3-8B candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import ProxyHandler, build_opener
import uuid

from .development import CASES, ROOT, execute, sha256_of, utc_now, write_evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--launch", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a fresh candidate evidence path")
    config = json.loads((ROOT / "configs/qwen3_8b_reference.json").read_text(encoding="utf-8"))
    launch = json.loads(args.launch.read_text(encoding="utf-8-sig"))
    if launch["backend"] != "vulkan" or launch["layers_offloaded"] <= 0:
        parser.error("Expected the separately launched Qwen3 Vulkan candidate")
    args.base_url = f"http://127.0.0.1:{config['port']}"
    args.model = config["alias"]
    with build_opener(ProxyHandler({})).open(args.base_url + "/props", timeout=10) as reply:
        props = json.load(reply)
    model_path = ROOT / ".tools/models/Qwen3-8B-GGUF" / config["filename"]
    if (
        props.get("model_alias") != args.model or Path(props["model_path"]) != model_path
        or not props["chat_template_caps"]["supports_tool_calls"]
        or props.get("build_info") != "b12359-b1b770d90"
    ):
        parser.error("Live candidate build, model or capabilities differ")
    run_id = "qwen3-8b-job-dev-" + uuid.uuid4().hex
    evidence = {
        "run_id": run_id, "started_utc": utc_now(), "config": config, "launch": launch,
        "chat_template_sha256": hashlib.sha256(props["chat_template"].encode("utf-8")).hexdigest(),
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): sha256_of(path)
            for path in (Path(__file__), Path(__file__).with_name("development.py"))
        },
        "classification": "REFERENCE_MODEL_DEVELOPMENT_REHEARSAL",
        "results": [],
    }
    for case in CASES:
        result = execute(case, "D", args, run_id)
        result["arm"] = "E"
        evidence["results"].append(result)
        print(f'vulkan E {case["id"]} {result["status"]}', flush=True)
        write_evidence(args.output, evidence)
    evidence["finished_utc"] = utc_now()
    write_evidence(args.output, evidence)
    return int(any(row["status"] != "PASS" for row in evidence["results"]))


if __name__ == "__main__":
    sys.exit(main())
