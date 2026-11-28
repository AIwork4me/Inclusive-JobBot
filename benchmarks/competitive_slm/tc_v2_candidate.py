"""Run one frozen TC-V2 case on an exact strict-admission Vulkan candidate."""

import argparse
import http.client
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

from benchmarks.root_cause.generation_capture import CaptureClient, CaptureError, MAX_BODY
from benchmarks.root_cause.historical_replay import gpu_server, legacy
from benchmarks.tool_calling_v2.holdout import dataset, qualify, runner
from model_gateway.openai_protocol import MAX_CALLS
from scripts.tools.verify_ij06_evidence import verify_gpu

from .admission import GATES
from .statistics import digest, frozen_suite


ROOT = dataset.HERE.parents[2]
CANDIDATES = ("A", "B", "D", "E", "F", "G", "H", "J")
VULKAN_DEVICE = {"name": "AMD Radeon(TM) 8060S Graphics", "device": "Vulkan0", "architecture": "gfx1151"}
ENGINE_PROFILE = "p4b-tool-choice-validation-generation-observer-vulkan"
BUDGETS = {
    "version": "IJ07-TCV2-Controlled-1", "context_tokens": 8192, "model_turns": 7,
    "completion_tokens_per_turn": 768, "tool_calls_per_turn": 16, "tool_calls_per_case": 112,
    "wall_clock_seconds_per_case": 180, "temperature": 0, "parallel_tool_calls": True,
    "thinking": "frozen_case_requirement", "cache_prompt": False,
}
SOURCE_PATCHES = (
    "patches/ij07/llama-b12359-explicit-tool-choice.patch",
    "patches/ij07/llama-b12359-generation-observer.patch",
    "benchmarks/tool_calling_v2/parser/minicpm5-native-json-lexical.patch",
    "benchmarks/tool_calling_v2/parser/minicpm5-terminal-integrity.patch",
)
MISTRAL_EMPTY_MESSAGE_CHECK = (
    "{%- if (message['content'] is none or message['content'] == '' or "
    "message['content']|length == 0) and (message['tool_calls'] is not defined or "
    "message['tool_calls'] is none or message['tool_calls']|length == 0) %}"
)


def read_embedded_template(model):
    from gguf import GGUFReader, LlamaFileType

    reader = GGUFReader(model)
    file_type = reader.get_field("general.file_type")
    template = reader.get_field("tokenizer.chat_template")
    if file_type is None or file_type.contents() != LlamaFileType.MOSTLY_Q8_0:
        raise ValueError("GGUF is outside the pinned Q8_0 quantization")
    value = template.contents() if template is not None else None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("GGUF does not contain its default native chat template")
    if reader.get_field("tokenizer.chat_template.tool_use") is not None:
        raise ValueError("candidate has an additional tool-use template without its own admission digest")
    return value


def server_template_source(embedded):
    # Mirror b12359 common/chat.cpp's existing Ministral compatibility fix,
    # followed by its jinja lexer normalization. This is a digest check only.
    native = embedded
    if "[TOOL_CALLS]" in native:
        native = native.replace(MISTRAL_EMPTY_MESSAGE_CHECK, "{%- if false %}")
    normalized = native.replace("\r\n", "\n").replace("\r", "\n")
    return normalized[:-1] if native.endswith("\n") else normalized


def read_json(path):
    return json.loads(path.read_bytes())


def verify_runtime(candidate, model, engine_dir, *, root=ROOT, require_prior_admission=True):
    """Hash local files and compare official, packaged and admitted identities."""
    if candidate not in CANDIDATES:
        raise ValueError("candidate is outside the GGUF Vulkan track")
    config_path = root / "configs/ij07/model_candidates.yaml"
    config = read_json(config_path)  # The checked-in YAML uses the JSON subset.
    declared = config["shared_runtime"]
    commit = declared["engine_commit"]
    if (config["schema_version"] != 1 or declared["backend"] != "vulkan" or declared["quantization"] != "Q8_0"
            or declared["context_tokens"] != BUDGETS["context_tokens"] or re.fullmatch("[a-f0-9]{40}", commit) is None):
        raise ValueError("shared runtime declaration differs from the controlled profile")
    if candidate == "J":
        identity_path = root / "atlas/benchmarks/pc_s_qwen3_14b.json"
        pin = read_json(identity_path)
        report_path = root / "evidence/IJ072/model_identity/admission/J/report.json"
        expected = pin["expected_sha256"]
        identity = {
            "official_model_id": pin["model"],
            "official_config_and_template": {"publisher_card": "https://huggingface.co/Qwen/Qwen3-14B-GGUF"},
            "runtime_asset": {"repo": pin["artifact_repository"], "revision": pin["revision"],
                              "filename": pin["filename"], "size": pin["expected_bytes"],
                              "expected_sha256": expected, "observed_sha256": expected, "status": "PASS"},
        }
    else:
        identity_path = root / config["candidate_identity"][candidate]
        identity = read_json(identity_path)
        report_path = root / "evidence/IJ07/model_identity/admission_strict" / candidate / "report.json"
    asset = identity["runtime_asset"]
    model_sha = asset["expected_sha256"]
    if (asset["status"] != "PASS" or asset.get("observed_sha256") != model_sha
            or re.fullmatch("[a-f0-9]{64}", model_sha) is None or not asset["repo"]
            or re.fullmatch("[a-f0-9]{40}", asset["revision"]) is None):
        raise ValueError("candidate model asset is unverified")
    report = read_json(report_path)
    if (report.get("candidate") != candidate or report.get("model_id") != identity["official_model_id"]
            or report.get("asset") != asset or report.get("requested_disable_thinking") is not True):
        raise ValueError("prior Vulkan assessment does not match the candidate identity")
    if require_prior_admission and (report.get("status") != "PASS"
            or any(report.get("gates", {}).get(gate) != "PASS" for gate in GATES)):
        raise ValueError("strict Vulkan admission did not pass for this candidate and identity")
    gpu = report["gpu"]
    if (gpu["backend"] != "vulkan" or gpu["gpu"] != VULKAN_DEVICE or gpu["build"] != f"b12359-{commit}"
            or not 0 < gpu["layers_offloaded"] == gpu["layers_total"]):
        raise ValueError("strict admission lacks the pinned full GPU offload")
    binary = engine_dir / "llama-server.exe"
    hashes = {
        "exe_sha256": legacy.sha256_of(binary),
        "dll_sha256": {file.name: legacy.sha256_of(file) for file in sorted(engine_dir.glob("*.dll"))},
    }
    if hashes != report["gpu_engine"] or "ggml-vulkan.dll" not in hashes["dll_sha256"]:
        raise ValueError("Vulkan engine EXE or DLL set differs from strict admission")
    if (model.name != asset["filename"] or not model.name.endswith("-Q8_0.gguf")
            or (asset.get("size") is not None and model.stat().st_size != asset["size"])):
        raise ValueError("model filename or size differs from the pinned artifact")
    if legacy.sha256_of(model) != model_sha:
        raise ValueError("model digest differs from the pinned artifact")
    embedded_template = read_embedded_template(model)
    template_sha = dataset.sha(server_template_source(embedded_template).encode("utf-8"))
    if template_sha != gpu["template_sha256"]:
        raise ValueError("embedded GGUF template differs from the strict admission template")
    return {
        "candidate": candidate, "track": "controlled", "backend": "vulkan", "gpu": VULKAN_DEVICE,
        "model": {"official_model_id": identity["official_model_id"], "runtime_repo": asset["repo"],
                  "runtime_revision": asset["revision"], "filename": asset["filename"], "model_sha256": model_sha,
                  "quantization": declared["quantization"], "upstream_config": identity["official_config_and_template"]},
        "engine": {"profile": ENGINE_PROFILE, "build": gpu["build"], "layers": gpu["layers_total"], **hashes},
        "template": {"selection": "gguf_embedded", "sha256": template_sha,
                     "embedded_sha256": dataset.sha(embedded_template.encode("utf-8"))},
        "provenance": {"candidate_config_sha256": legacy.sha256_of(config_path),
                       "model_passport_sha256": legacy.sha256_of(identity_path),
                       "strict_admission_sha256": legacy.sha256_of(report_path), "admission_run_id": report["run_id"]},
        "budgets": dict(BUDGETS), "source_observer_requested": True,
    }


def select_case(split, case_id, stream, repeat_index):
    rows, manifest = dataset.load(split)
    case = next((row for row in rows if row["id"] == case_id), None)
    if case is None:
        raise ValueError("case is outside the selected frozen split")
    if repeat_index is None:
        seed = manifest["first_pass_seed"]
    else:
        if (split != "holdout" or stream or case_id not in manifest["repeat"]["cases"]
                or type(repeat_index) is not int or repeat_index not in (1, 2, 3)):
            raise ValueError("case and seed must belong to the frozen non-streaming repeat panel")
        seed = manifest["repeat"]["seeds"][repeat_index - 1]
    return case, {
        "case_id": case_id, "split": split, "stream": stream, "seed": seed, "repeat_index": repeat_index,
        "phase": "repeat" if repeat_index is not None else "stream" if stream else "first", "attempt": 1,
        "dataset_sha256": manifest["split"][split]["sha256"], "pairing_sha256": digest(case),
        "manifest_sha256": legacy.sha256_of(dataset.HERE / "manifest.json"),
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise CaptureError("redirect rejected for the local candidate endpoint")


class BudgetedCapture(CaptureClient):
    """Use native rendering and observe the full source trace under the shared limits."""

    def __init__(self, port, trace_path, alias):
        super().__init__(port, trace_path)
        if self.trace_path is None:
            raise CaptureError("competitive candidate requires the source generation observer")
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.alias = alias
        self.begin_trial()

    def begin_trial(self):
        self.requests.clear()
        self.deadline = time.monotonic() + BUDGETS["wall_clock_seconds_per_case"]
        self.rendered = None
        self.budget_error = None

    def _remaining(self):
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            self.budget_error = "wall-clock budget exceeded"
            raise CaptureError(self.budget_error)
        return seconds

    def _send(self, path, body):
        request = Request(self.base_url + path, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                          headers={"Content-Type": "application/json"})
        try:
            response = self.opener.open(request, timeout=self._remaining())
        except HTTPError as error:
            response = error
        with response:
            data = response.read(MAX_BODY + 1)
            self._remaining()
            if len(data) > MAX_BODY:
                raise CaptureError("HTTP body exceeded the shared capture limit")
            return response.code, response.headers.get_content_type(), data

    def post(self, path, body):
        status, content_type, data = self._send(path, body)
        if path == "/apply-template":
            self.rendered = None
            if status != 200:
                raise CaptureError("native chat-template rendering failed")
            rendered = json.loads(data)["prompt"]
            if not isinstance(rendered, str):
                raise CaptureError("native renderer did not provide a text prompt")
            tokenizer_status, _, tokenized = self._send(
                "/tokenize", {"content": rendered, "add_special": False, "parse_special": True},
            )
            tokens = json.loads(tokenized).get("tokens") if tokenizer_status == 200 else None
            if not isinstance(tokens, list) or any(type(token) is not int for token in tokens):
                raise CaptureError("could not verify full rendered prompt context")
            # Reserve one additional token for a possible special start token.
            if len(tokens) + BUDGETS["completion_tokens_per_turn"] + 1 > BUDGETS["context_tokens"]:
                self.budget_error = "rendered prompt exceeds the shared context budget"
                raise CaptureError(self.budget_error)
            self.rendered = {"prompt_tokens_before_special": len(tokens), "prompt_characters": len(rendered),
                             "messages": len(body["messages"])}
        return status, content_type, data

    def chat(self, base_url, body):
        if (len(self.requests) >= BUDGETS["model_turns"]
                or body["max_tokens"] != BUDGETS["completion_tokens_per_turn"]
                or body["temperature"] != BUDGETS["temperature"]
                or body["parallel_tool_calls"] is not BUDGETS["parallel_tool_calls"]
                or body["cache_prompt"] is not BUDGETS["cache_prompt"]):
            self.budget_error = "request differs from the shared controlled budget"
            raise CaptureError(self.budget_error)
        try:
            response = super().chat(base_url, {**body, "model": self.alias})
        except (ValueError, KeyError) as failure:
            raise CaptureError(str(failure)) from failure
        record = self.requests[-1]
        record["context_budget"] = self.rendered
        source = record["source_generation"]
        if source.get("status") == "BLOCKED":
            raise CaptureError("missing correlated generation trace before tool execution")
        input_tokens = len(source["prompt_token_ids"])
        output_tokens = len(source["sampled_token_ids"])
        record["context_budget"].update(actual_prompt_tokens=input_tokens, actual_output_tokens=output_tokens)
        if ("truncated" in source and source["truncated"] is not False
                or input_tokens + output_tokens > BUDGETS["context_tokens"]
                or output_tokens > BUDGETS["completion_tokens_per_turn"]):
            self.budget_error = "source trace shows context truncation or budget overrun"
            raise CaptureError(self.budget_error)
        self._remaining()
        return response


def check_shared_limits():
    if (runner.MAX_TURNS != BUDGETS["model_turns"]
            or runner.MAX_TOKENS != BUDGETS["completion_tokens_per_turn"]
            or MAX_CALLS != BUDGETS["tool_calls_per_turn"]
            or runner.MAX_TURNS * MAX_CALLS != BUDGETS["tool_calls_per_case"]):
        raise ValueError("shared TC-V2 runner and candidate budget version differ")


def build_configuration(runtime, dataset_sha256, manifest_sha256, *, extra_files=()):
    files = [Path(__file__), *extra_files, *dataset.HERE.glob("*.py"), *(ROOT / "benchmarks/tool_calling_v2").glob("*.py"),
             *(ROOT / "src/business_tools").glob("*.py"), *(ROOT / "src/model_gateway").glob("*.py"),
             ROOT / "benchmarks/root_cause/generation_capture.py", ROOT / "benchmarks/root_cause/historical_replay.py",
             ROOT / "benchmarks/tool_calling_v2/parser/run_wire.py", ROOT / "scripts/tools/verify_ij06_evidence.py",
             ROOT / "scripts/windows/sample_gpu_counters.ps1", ROOT / "scripts/windows/common.ps1"]
    configuration = {
        **runtime, "git": legacy.git_state(), "sdk_installed": version("google-antigravity"), "sdk_used": False,
        "code_sha256": {file.relative_to(ROOT).as_posix(): legacy.sha256_of(file) for file in sorted(files)},
        "patch_sha256": {name: legacy.sha256_of(ROOT / name) for name in SOURCE_PATCHES},
        "dataset_sha256": dataset_sha256, "dataset_manifest_sha256": manifest_sha256,
    }
    configuration["controls_sha256"] = digest({
        "dataset_sha256": dataset_sha256, "dataset_manifest_sha256": manifest_sha256,
        "budgets": configuration["budgets"], "code_sha256": configuration["code_sha256"],
    })
    return configuration


def server_environment():
    return {key: value for key, value in os.environ.items() if
            not key.upper().startswith(("LLAMA_ARG_", "GGML_BACKEND_PATH", "LLAMA_IJ07_TRACE_PATH"))}


def verify_launch(launch, runtime, *, require_trace=True):
    if (launch["backend"] != "vulkan" or launch["owns_port"] is not True
            or launch["gpu"] != runtime["gpu"] or launch["build"] != runtime["engine"]["build"]
            or launch["template_sha256"] != runtime["template"]["sha256"]
            or launch["layers_offloaded"] != runtime["engine"]["layers"]
            or launch["layers_offloaded"] != launch["layers_total"]
            or launch["args"][launch["args"].index("--ctx-size") + 1] != str(BUDGETS["context_tokens"])
            or bool(launch["trace_file"]) is not require_trace):
        raise CaptureError("live Vulkan configuration differs from the pinned identity")


def run_one(args, runtime, model, engine_dir):
    check_shared_limits()
    case, trial = select_case(args.split, args.case, args.stream, args.repeat_index)
    if case["split"] == "holdout":
        profile = frozen_suite("TC-V2")
        if not any(row["case_id"] == trial["case_id"] and row["pairing_sha256"] == trial["pairing_sha256"]
                   for row in profile["cases"]):
            raise ValueError("frozen TC-V2 statistics roster differs from the selected case")
    configuration = build_configuration(runtime, trial["dataset_sha256"], trial["manifest_sha256"])
    arm_configuration_sha256 = digest(configuration)
    run_configuration = {"arm_configuration_sha256": arm_configuration_sha256, "trial": trial, "port": args.port}
    run_id = "ij07-competitive-tcv2-" + uuid4().hex
    metadata = {
        "run_id": run_id, "evidence_class": "local_model",
        "scope": "single competitive TC-V2 trajectory", "purpose": "diagnostic", "configuration": configuration,
        "configuration_sha256": arm_configuration_sha256, "run_configuration": run_configuration,
        "run_configuration_sha256": digest(run_configuration), "started_utc": legacy.utc_now(), "status": "NOT_RUN",
        "gpu_execution_status": "NOT_RUN", "source_capture_status": "NOT_RUN",
    }
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    legacy.write_json(output / "run.json", metadata)
    database = output / "case.sqlite"
    alias = "ij07-candidate-" + runtime["candidate"].lower()
    result = launch = None
    try:
        with gpu_server(engine_dir / "llama-server.exe", model, "vulkan", server_environment(), output, args.port,
                        "vulkan", True, alias=alias) as (client, launch):
            verify_launch(launch, runtime)
            wire = BudgetedCapture(args.port, client.trace_path, alias)
            result = runner.run_trajectory(case, wire, database, stream=trial["stream"], seed=trial["seed"])
            result["budget_error"] = wire.budget_error
    except (CaptureError, OSError, KeyError, subprocess.SubprocessError, http.client.HTTPException) as failure:
        metadata["interruption"] = type(failure).__name__
        metadata["interruption_detail"] = str(failure)

    if launch is not None and result is not None:
        launch_path = output / "launch.json"
        legacy.write_json(launch_path, {**launch, "status": "PASS"})
        counters = output / launch["counter_file"]
        try:
            gpu_observed = verify_gpu({"gpu_launch": launch_path, "gpu_counters": counters}, "vulkan")
        except (OSError, ValueError, KeyError):
            gpu_observed = False
        metadata["gpu_execution_status"] = "PASS" if gpu_observed else "BLOCKED"
        if gpu_observed:
            metadata["gpu_artifacts_sha256"] = {"launch": legacy.sha256_of(launch_path),
                                                 "counters": legacy.sha256_of(counters),
                                                 "boot": legacy.sha256_of(output / "vulkan-server.log")}
        trace = output / launch["trace_file"]
        observed_source = trace.is_file() and bool(result["requests"]) and all(
            capture["source_generation"].get("status") != "BLOCKED" for capture in result["requests"]
        )
        metadata["source_capture_status"] = "PASS" if observed_source else "BLOCKED"
        if observed_source:
            metadata["generation_trace_sha256"] = legacy.sha256_of(trace)
        result.update(
            **trial, run_id=run_id, configuration_sha256=arm_configuration_sha256,
            run_configuration_sha256=metadata["run_configuration_sha256"],
            gpu_execution_status=metadata["gpu_execution_status"],
            source_capture_status=metadata["source_capture_status"],
            database_sha256=legacy.sha256_of(database), trajectory_status=result["status"],
            native_proposal_count_scope=("requires independent native trace audit" if result["native_parser_rejected"]
                                         else "observed wire proposals"),
        )
        if not (gpu_observed and observed_source) or "interruption" in metadata:
            result["status"] = "BLOCKED"
        qualify.write_checkpoint(output / "result.json", result)
        metadata["result_sha256"] = legacy.sha256_of(output / "result.json")
    metadata["status"] = result["status"] if result is not None else "BLOCKED"
    metadata["finished_utc"] = legacy.utc_now()
    legacy.write_json(output / "run.json", metadata)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=CANDIDATES, required=True)
    parser.add_argument("--model", type=Path, required=True, help="explicit path to the candidate's pinned Q8_0 GGUF")
    parser.add_argument("--engine-dir", type=Path, required=True, help="explicit strict-admission Vulkan directory")
    parser.add_argument("--verify-runtime", action="store_true", help="verify file identities without starting a server")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--split", choices=dataset.FILES, default="holdout")
    parser.add_argument("--case")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--repeat-index", type=int, choices=(1, 2, 3))
    parser.add_argument("--port", type=int, choices=range(1024, 65536), default=8102, metavar="PORT")
    args = parser.parse_args()
    if args.verify_runtime and any((args.output, args.case, args.stream, args.repeat_index)):
        parser.error("--verify-runtime is a read-only identity check")
    if not args.verify_runtime and not (args.case and args.output):
        parser.error("inference requires exactly one --case and a fresh --output directory")
    try:
        model, engine = args.model.resolve(strict=True), args.engine_dir.resolve(strict=True)
        check_shared_limits()
        runtime = verify_runtime(args.candidate, model, engine)
        if args.verify_runtime:
            print(json.dumps({"identity_check": "PASS", "inference": "NOT_RUN", **runtime}, indent=2))
            return 0
        metadata = run_one(args, runtime, model, engine)
    except (ValueError, OSError, KeyError, ImportError, subprocess.SubprocessError) as failure:
        parser.exit(2, f"BLOCKED: {failure}\n")
    print(f"{args.candidate} {args.case}: {metadata['status']}")
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[metadata["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
