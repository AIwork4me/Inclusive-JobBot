"""Replay the five historically blocked Extension cases on a versioned SDK track."""

import argparse
import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from uuid import uuid4

from audit import write_evidence
from benchmarks.root_cause.historical_replay import gpu_server
from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT, canonical, fingerprint
from scripts.tools.verify_ij06_evidence import verify_gpu

from . import lfm3_ha_admission as ha, sdk_extension_execution as ext
from .admission import git_head
from .ha11_preflight import checked_runtime
from .ha11_sdk import TYPED, execute_sdk


PRIOR = ROOT / "evidence/IJSLM/physical-followup/sdk-extension/holdout"
CASES = {"A": ("EXT-H-LAYOUT",), "B": ("EXT-H-RESCAN", "EXT-H-LAYOUT"),
         "D": ("EXT-H-RESCAN", "EXT-H-LAYOUT")}


def archive(assets, candidate):
    public_report = json.loads((PRIOR / candidate / "report.json").read_bytes())
    folder = assets / ".runtime/ij-slm-1.0/sdk-extension-physical-v1/holdout" / candidate
    private_report = folder / "report.json"
    if digest(private_report) != public_report["private_report_sha256"]:
        raise ValueError("Historic private report differs from the published seal")
    rows = {row["case_id"]: row for row in public_report["results"]
            if row["mechanical"]["status"] == "BLOCKED"}
    if rows.keys() != set(CASES[candidate]):
        raise ValueError("Historic blocked Extension roster differs")
    for case_id in CASES[candidate]:
        row = rows[case_id]
        path = folder / row["trial_id"] / "trial.json"
        if digest(path) != row["capture_sha256"]:
            raise ValueError("Historic private Extension trace differs from its seal")
        yield row, json.loads(path.read_bytes())


@contextmanager
def replay_first_reply(event, alias):
    """Play archived provider bytes once, then return a scripted terminal reply."""
    raw = event["response"].encode()
    terminal = canonical({"id": "ha11-scripted-terminal", "model": alias, "object": "chat.completion",
                          "created": 1, "choices": [{"index": 0, "finish_reason": "stop",
                          "message": {"role": "assistant", "content": "Scripted replay ended."}}]})
    requests = []

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            requests.append(self.rfile.read(int(self.headers["Content-Length"])))
            body = raw if len(requests) == 1 else terminal
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with ThreadingHTTPServer(("127.0.0.1", 0), Provider) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            yield SimpleNamespace(base_url=f"http://127.0.0.1:{server.server_port}", trace_path=None)
        finally:
            server.shutdown()
            thread.join()


def execute(client, alias, public, graph, trial_id, target, harness):
    sandbox = ext.ExtensionSandbox(public, graph)
    tools = [{"type": "function", "function": {"name": name, **definition}}
             for name, definition in public["tools"].items()]
    result = asyncio.run(execute_sdk(
        client, alias, tools, public["tools"], sandbox.execute, public["prompt"], ext.SYSTEM,
        trial_id, target, harness, profile=TYPED,
        model_budget=ext.BUDGET["max_model_calls"], tool_budget=ext.BUDGET["max_tool_calls"],
        token_budget=ext.BUDGET["max_completion_tokens"], provider_controls=ext.PROFILE,
    ))
    return result | {"family": public["family"], "case_id": public["case_id"],
                     "track": TYPED, "calls": sandbox.calls}


def run(assets, output, port, *, scripted):
    _, pin, _, binary, harness = checked_runtime(assets)
    partitions, _ = ext._frozen_partitions()
    cases = {public["case_id"]: (public, graph) for public, graph in partitions["holdout"]}
    handoff = None if scripted else require_handoff(ROOT)
    output.mkdir(parents=True, exist_ok=False)
    run_id = "lfm3-ha11-extension-" + uuid4().hex
    report = {
        "run_id": run_id, "git_sha": git_head(), "runtime": pin, "track": TYPED,
        "dataset_sha256": digest(ext.sdk_extension.FOLDER / "manifest.json"),
        "handoff_sha256": None if scripted else digest(ROOT / HANDOFF), "models": {}, "results": [],
        "evidence_class": "real SDK and archived scripted provider" if scripted else "real Radeon Extension replay",
        "core_trial_attribution": 0,
    }

    def capture(candidate, client, row, historic, folder):
        public, graph = cases[row["case_id"]]
        trial_id = fingerprint([run_id, candidate, public["case_id"]])
        alias = f"ijslm-candidate-{candidate.lower()}"
        trial = execute(client, alias, public, graph, trial_id, folder / trial_id, harness)
        capture_file = folder / f"{trial_id}.json"
        write_evidence(capture_file, trial)
        first = historic["wire"][0]
        bindings = [callback["binding"] for callback in trial["callbacks"] if callback["status"] == "PASS"]
        result = {"candidate": candidate, "case_id": public["case_id"], "trial_id": trial_id,
                  "historic_capture_sha256": row["capture_sha256"],
                  "historic_first_response_sha256": first["response_sha256"],
                  "capture_sha256": digest(capture_file), "requests": len(trial["wire"]),
                  "callbacks": len(trial["callbacks"]), "bound": len(bindings),
                  "conversions": [b["integer_conversions"] for b in bindings],
                  "executions": len(trial["calls"]), "failure_type": (trial["failure"] or {}).get("type"),
                  "score": {"status": "NOT_RUN"} if scripted else ext.score(graph, trial)}
        report["results"].append(result)
        write_evidence(output / "report.json", report)
        print(candidate, public["case_id"], result["bound"], result["executions"],
              result["score"]["status"], flush=True)

    for candidate in CASES:
        historic_rows = list(archive(assets, candidate))
        folder = output / candidate
        folder.mkdir()
        alias = f"ijslm-candidate-{candidate.lower()}"
        if scripted:
            for row, historic in historic_rows:
                with replay_first_reply(historic["wire"][0], alias) as client:
                    capture(candidate, client, row, historic, folder)
            continue

        ha.require_idle_controller()
        if ha.owner_capture_active():
            raise BlockingIOError("AG-11 or another controller holds the owner window")
        registry = json.loads((ROOT / "atlas/slm/v1.0/model_registry.json").read_bytes())
        record = registry["models"][candidate]
        model = (assets / record["local_asset"]).resolve(strict=True)
        if not model.is_relative_to(assets):
            raise ValueError("Extension model path leaves the pinned asset root")
        runtime = ext.verify_runtime(candidate, model, assets / ".tools/ij07-toolchoice-p4b-vulkan",
                                     require_prior_admission=False)
        if runtime["model"]["model_sha256"] != record["asset"]["expected_sha256"]:
            raise ValueError("Extension model differs from the frozen registry")
        with gpu_server(binary, model, "vulkan", ext.server_environment(), folder, port, "vulkan", True,
                        alias=alias, mission_id="LFM3-HA-1.1", lease_owner="typed-extension",
                        runtime_session=run_id + "-" + candidate) as (client, launch):
            ext.verify_launch(launch, runtime)
            if any(launch["gpu_lease"][k] != handoff["lease"][k]
                   for k in ("host_sha256", "gpu_physical_sha256")):
                raise ValueError("Extension GPU differs from the frozen handoff")
            for row, historic in historic_rows:
                capture(candidate, client, row, historic, folder)
        launch_path = folder / "launch.json"
        write_evidence(launch_path, launch | {"status": "PASS"})
        counters = folder / launch["counter_file"]
        report["models"][candidate] = {"model": runtime["model"], "trace_sha256": digest(folder / launch["trace_file"]),
                                       "gpu_counters_sha256": digest(counters),
                                       "gpu_execution": "PASS" if verify_gpu(
                                           {"gpu_launch": launch_path, "gpu_counters": counters}, "vulkan") else "BLOCKED"}
        write_evidence(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18754)
    parser.add_argument("--scripted", action="store_true")
    args = parser.parse_args()
    result = run(args.assets.resolve(strict=True), args.output.resolve(), args.port, scripted=args.scripted)
    print(result["run_id"], len(result["results"]))


if __name__ == "__main__":
    main()
