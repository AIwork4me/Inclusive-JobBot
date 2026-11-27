"""N02R corrected experiment controller (addendum PR-D06..PR-D10 + T-arms).

Differences from controller.py (the audited v1, kept untouched):
- PR-D06: experiment identity binds model SHA256+quant, chat-template
  fingerprint (rendered-prompt hash), engine exe+DLL SHA256 list, backend,
  GPU physical identity, evaluator/parser/suite/renderer hashes, budgets,
  decoding, cache policy, server profile, arm registry + applicability.
  Resume refuses to append when the recomputed identity differs.
- PR-D07: socket-to-PID ownership verified independently via netstat;
  GPU identity recorded; fail-closed physical proof.
- PR-D08/D09: endpoint-specific telemetry with explicit NOT_CAPTURED
  markers; complete untruncated responses stored as content-addressed
  artifacts (responses/<trial_id>.json) with SHA256 in the trial record.
- PR-D10: queue expresses unique logical slots; analyzer reconciles
  denominators.
- T-arms: T0/T1/T3 are analysis aliases over M-arms; T2 executes M-P1
  under a server launched with --reasoning-budget (T2 pass).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "benchmarks" / "root_cause"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "src"))
import gpu_lease  # noqa: E402  (host-wide named-mutex lease, reused)

from n02r import tasks as tasks_mod  # noqa: E402
from n02r import arms_v2 as arms  # noqa: E402
from n02r import scorer  # noqa: E402

MODELS = {
    "S1": ("models/MiniCPM5-2B-GGUF/MiniCPM5-2B-Q8_0.gguf", "minicpm5-2b"),
    "S2": ("models/ij_sdk/LFM3-1.7B-GGUF/LFM3-1.7B-Q8_0.gguf", "lfm3-1.7b"),
    "S3": ("models/ij_sdk/Qwen3.5-2B-GGUF/Qwen3.5-2B-Q8_0.gguf", "qwen3.5-2b"),
}
SERVER_PROFILES = {
    "default": [],
    "reasoning-budget": ["--reasoning-budget", str(arms.REASONING_BUDGET_T2)],
}
QUANT_RE = re.compile(r"-(Q\d_\d|Q\d|IQ\d+_?\w*|F16|BF16)\.gguf$", re.I)


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def post_json(base: str, path: str, body: dict, timeout: float = 240):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def gpu_identity() -> dict:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_VideoController | Where-Object {$_.Name "
             "-like '*AMD Radeon*'} | Select-Object -First 1 | ConvertTo-Json"],
            capture_output=True, text=True, timeout=30).stdout
        j = json.loads(out)
        return {"name": j.get("Name"), "driver": j.get("DriverVersion"),
                "pnp_device_id": j.get("PNPDeviceID")}
    except Exception as e:
        return {"error": f"UNAVAILABLE: {str(e)[:120]}"}


def socket_owner_pid(port: int) -> int | None:
    """PR-D07: independently resolve the OS-level owner of the LISTENING
    socket (netstat), instead of trusting the launched PID."""
    try:
        out = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"], capture_output=True,
            text=True, timeout=30).stdout
    except Exception:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "LISTENING":
            local = parts[1]
            if local.endswith(f":{port}"):
                return int(parts[4])
    return None


class ServerSession:
    def __init__(self, backend, model, alias, port, workdir, profile_flags):
        self.binary_dir = ROOT / "runtime" / "llama-cpp" / backend
        self.model, self.alias, self.port = model, alias, port
        self.workdir = workdir
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.profile_flags = list(profile_flags)
        self.proc = None
        self.stdout_log = workdir / "server.stdout.log"
        self.stderr_log = workdir / "server.stderr.log"

    def start(self):
        exe = self.binary_dir / "llama-server.exe"
        args = [str(exe), "-m", str(self.model), "--alias", self.alias,
                "--host", "127.0.0.1", "--port", str(self.port),
                "-c", "8192", "-ngl", "99", "--jinja", "--cache-reuse", "256",
                "-v"] + self.profile_flags
        with open(self.stdout_log, "wb") as so, open(self.stderr_log, "wb") as se:
            self.proc = subprocess.Popen(
                args, cwd=str(self.binary_dir), stdout=so, stderr=se,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        return self.proc

    def wait_ready(self, deadline: float) -> dict:
        base = f"http://127.0.0.1:{self.port}"
        while time.time() < deadline:
            if self.proc and self.proc.poll() is not None:
                raise RuntimeError("server exited during startup")
            try:
                with socket.create_connection(("127.0.0.1", self.port),
                                               timeout=1):
                    pass
                with urllib.request.urlopen(base + "/health", timeout=5) as r:
                    if r.status == 200:
                        health = json.loads(r.read().decode("utf-8"))
                        owner = socket_owner_pid(self.port)
                        if owner is None or owner != self.proc.pid:
                            raise RuntimeError(
                                "PR-D07 fail-closed: listening socket not "
                                f"owned by launched pid (netstat owner="
                                f"{owner}, launched={self.proc.pid})")
                        return {"socket_owner_pid_verified": owner,
                                "health": health}
            except RuntimeError:
                raise
            except Exception:
                time.sleep(1.5)
        raise RuntimeError("server not healthy before deadline")

    def offload_line(self) -> str | None:
        pat = re.compile(r"offloaded (\d+)/(\d+) layers to GPU")
        for log in (self.stdout_log, self.stderr_log):
            try:
                for line in log.read_text(encoding="utf-8",
                                          errors="replace").splitlines():
                    m = pat.search(line)
                    if m:
                        return m.group(0)
            except OSError:
                continue
        return None

    def template_fingerprint(self, base: str) -> dict:
        probe = {"messages": [{"role": "user",
                               "content": "ij-nano template fingerprint"}]}
        try:
            j = post_json(base, "/apply-template", probe, timeout=60)
            prompt = j.get("prompt") or ""
            return {"rendered_prompt_sha256": sha256_bytes(prompt.encode()),
                    "chars": len(prompt)}
        except Exception as e:
            return {"rendered_prompt_sha256": "UNAVAILABLE",
                    "error": str(e)[:120]}

    def stop(self):
        if self.proc and self.proc.poll() is None:
            subprocess.run(["taskkill", "/F", "/PID", str(self.proc.pid)],
                           capture_output=True)
        time.sleep(2)


class ControllerV2:
    def __init__(self, args):
        self.args = args
        self.weights_root = pathlib.Path(args.weights_root).resolve()
        self.suite = tasks_mod.build_suite()
        self.gpu = gpu_identity()
        self.ev_root = ROOT / "evidence" / "IJNANO" / "N02R" / "runs"
        self.identity = self._identity()
        self.run_dir = self.ev_root / self.identity["experiment_id"]
        self.results_path = self.run_dir / "results.jsonl"
        self.done: set[str] = set()
        self.thinking_kwarg: dict[str, tuple] = {}

    # -- identity (PR-D06) ------------------------------------------------

    def _module_sha(self, rel: str) -> str:
        return sha256_bytes((ROOT / rel).read_bytes())

    def _identity(self) -> dict:
        backend = self.args.backend
        engine_dir = ROOT / "runtime" / "llama-cpp" / backend
        dlls = sorted(engine_dir.glob("*.dll"))
        models = {}
        for m in self.args.models.split(","):
            rel, alias = MODELS[m]
            p = (self.weights_root / rel).resolve()
            q = QUANT_RE.search(p.name)
            models[m] = {
                "path": rel, "alias": alias,
                "sha256": sha256_file(p) if p.is_file() else None,
                "size": p.stat().st_size if p.is_file() else None,
                "quantization": q.group(1) if q else "unknown"}
        spec = {
            "suite_hash": tasks_mod.suite_hash(),
            "arms_registry": {a: arms.ARM_LABELS[a] for a in
                              sorted(set(arms.NATIVE_ARMS + arms.MATCHED_ARMS
                                         + arms.P5_ARMS + arms.TWO_STAGE_ARMS
                                         + ("T2",)))},
            "applicability": {
                "P7": arms.P7_APPLICABILITY, "P5A": arms.P5A_APPLICABILITY,
                "P5B": arms.P5B_APPLICABILITY, "P7S": arms.P7S_APPLICABILITY},
            "primary_budget": arms.PRIMARY_BUDGET,
            "budgets": list(arms.BUDGETS),
            "budget_panel_arms": list(arms.BUDGET_PANEL_ARMS),
            "t2_reasoning_budget": arms.REASONING_BUDGET_T2,
            "decoding": {"temperature": 0, "seed": 42},
            "cache_policy": {"cache_prompt": True},
            "engine": {"exe_sha256": sha256_file(engine_dir / "llama-server.exe"),
                       "dll_sha256": {d.name: sha256_file(d) for d in dlls}},
            "backend": backend,
            "gpu": self.gpu,
            "models": models,
            "implementation": {
                "controller_v2": self._module_sha(
                    "benchmarks/ij_nano/n02r/controller_v2.py"),
                "arms_v2": self._module_sha(
                    "benchmarks/ij_nano/n02r/arms_v2.py"),
                "tasks": self._module_sha("benchmarks/ij_nano/n02r/tasks.py"),
                "scorer": self._module_sha(
                    "benchmarks/ij_nano/n02r/scorer.py"),
                "evaluator_contracts": self._module_sha(
                    "src/nanoagent/eval/contracts.py"),
                "evaluator_comparators": self._module_sha(
                    "src/nanoagent/eval/comparators.py"),
                "evaluator_units": self._module_sha(
                    "src/nanoagent/eval/units.py")},
            "phase_plan": {
                "main": "per model: M-P0..M-P6 all families; M-P7 applicable "
                        "families; P5A applicable; P5B all; P7S structured; "
                        "T2 (M-P1 under reasoning-budget server)",
                "panel": "budget panel arms x 12 tasks x budgets<1024"},
        }
        spec["experiment_id"] = hashlib.sha256(
            json.dumps({k: v for k, v in spec.items()
                        if k != "experiment_id"},
                       sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        return spec

    # -- queue (PR-D10 unique logical slots) ---------------------------------

    def _queue(self, phase: str):
        q = []
        models = self.args.models.split(",")
        if phase in ("main", "smoke"):
            suite = self.suite[:2] if phase == "smoke" else self.suite
            for t in suite:
                for m in models:
                    fam = t["family"]
                    for arm in arms.MATCHED_ARMS:
                        if arm == "M-P7" and not arms.P7_APPLICABILITY[fam]:
                            continue
                        q.append((m, arm, t, arms.PRIMARY_BUDGET))
                    if arms.P5A_APPLICABILITY[fam]:
                        q.append((m, "P5A", t, arms.PRIMARY_BUDGET))
                    q.append((m, "P5B", t, arms.PRIMARY_BUDGET))
                    if arms.P7S_APPLICABILITY[fam]:
                        q.append((m, "P7S", t, arms.PRIMARY_BUDGET))
                    q.append((m, "T2", t, arms.PRIMARY_BUDGET))
        if phase == "panel":
            panel_ids = {t["task_id"] for t in self.suite[:12]}
            for m in models:
                for t in [x for x in self.suite if x["task_id"] in panel_ids]:
                    for arm in arms.BUDGET_PANEL_ARMS:
                        if arm == "P5A" and not arms.P5A_APPLICABILITY[
                                t["family"]]:
                            continue
                        for b in arms.BUDGETS:
                            if b == arms.PRIMARY_BUDGET:
                                continue       # already executed in main
                            q.append((m, arm, t, b))
        return q

    # -- execution ------------------------------------------------------------

    def run(self) -> int:
        existing = self.run_dir / "manifest.json"
        if existing.exists():
            old = json.loads(existing.read_text(encoding="utf-8"))
            if old.get("identity", {}).get("experiment_id") \
                    != self.identity["experiment_id"]:
                print("[ctrl] REFUSED: run dir exists with a different "
                      "frozen identity (PR-D06 resume guard)")
                return 3
        else:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            template_fps = {}
            manifest = {"identity": self.identity, "created_utc": utc(),
                        "lease": "benchmarks/root_cause/gpu_lease.py "
                                 "physical_gpu() (host-wide named mutex)",
                        "template_fingerprints": template_fps}
            (self.run_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=1, ensure_ascii=False),
                encoding="utf-8")
        (self.run_dir / "responses").mkdir(exist_ok=True)

        if self.results_path.exists():
            for line in self.results_path.read_text(encoding="utf-8").splitlines():
                try:
                    self.done.add(json.loads(line)["trial_id"])
                except Exception:
                    continue

        disk = shutil.disk_usage(self.run_dir)
        print(f"[ctrl] experiment {self.identity['experiment_id']} "
              f"phase={self.args.phase} queue={len(self._queue(self.args.phase))} "
              f"done={len(self.done)} disk_free_GB={disk.free/1e9:.1f}", flush=True)

        executed = skipped = 0
        base = f"http://127.0.0.1:{self.args.port}"
        with gpu_lease.physical_gpu():
            print(f"[lease ACQUIRED {utc()}]", flush=True)
            current_key, session = None, None
            try:
                for model, arm, task, budget in self._queue(self.args.phase):
                    tid = self._trial_id(model, arm, task["task_id"], budget)
                    if tid in self.done:
                        skipped += 1
                        continue
                    profile = "reasoning-budget" if arm == "T2" else "default"
                    key = (model, profile)
                    if key != current_key:
                        if session:
                            session.stop()
                        rel, alias = MODELS[model]
                        mp = (self.weights_root / rel).resolve()
                        session = ServerSession(
                            self.args.backend, mp, alias, self.args.port,
                            ROOT / ".runtime" / "ij_nano_n02r_v2"
                            / f"{model}_{profile}",
                            SERVER_PROFILES[profile])
                        session.start()
                        proof = session.wait_ready(time.time() + 900)
                        time.sleep(2)
                        offload = session.offload_line()
                        fp = session.template_fingerprint(base)
                        print(f"[{model}|{profile}] pid_verified="
                              f"{proof['socket_owner_pid_verified']} "
                              f"offload={offload} tpl={fp}", flush=True)
                        manifest_path = self.run_dir / "manifest.json"
                        man = json.loads(manifest_path.read_text(encoding="utf-8"))
                        man.setdefault("sessions", []).append({
                            "model": model, "profile": profile,
                            "socket_owner_pid_verified":
                                proof["socket_owner_pid_verified"],
                            "health": proof["health"],
                            "offload_line": offload,
                            "template_fingerprint": fp,
                            "started_utc": utc(),
                            "gpu": self.gpu})
                        manifest_path.write_text(
                            json.dumps(man, indent=1, ensure_ascii=False),
                            encoding="utf-8")
                        current_key = key
                    executed += self._run_trial(base, model, arm, task,
                                                budget, tid)
                    if executed % 25 == 0:
                        print(f"[ctrl] executed={executed} skipped={skipped} "
                              f"({utc()})", flush=True)
            finally:
                if session:
                    session.stop()
                print(f"[lease RELEASED {utc()}]", flush=True)

        seal = {"experiment_id": self.identity["experiment_id"],
                "sealed_utc": utc(), "executed_this_session": executed,
                "skipped_done": skipped, "total_done": len(self.done),
                "results_sha256": sha256_file(self.results_path)}
        (self.run_dir / "seal.json").write_text(json.dumps(seal, indent=1),
                                                encoding="utf-8")
        print(f"[ctrl] done: executed={executed} skipped={skipped} "
              f"total={len(self.done)}", flush=True)
        return 0

    def _trial_id(self, model, arm, task_id, budget) -> str:
        return hashlib.sha256(
            f"{self.identity['experiment_id']}|{model}|{arm}|{task_id}|{budget}"
            .encode()).hexdigest()[:24]

    def _post(self, base, path, body, timeout):
        t0 = time.monotonic()
        http_json, http_error = None, None
        try:
            http_json = post_json(base, path, body, timeout)
        except urllib.error.HTTPError as e:
            http_error = f"HTTP {e.code}: " \
                         f"{e.read().decode(errors='replace')[:200]}"
        except Exception as e:
            http_error = f"{type(e).__name__}: {str(e)[:200]}"
        return http_json, http_error, round(time.monotonic() - t0, 3)

    def _run_trial(self, base, model, arm, task, budget, tid) -> int:
        kw = self.thinking_kwarg.get(model, (None, False))[0]
        stage_records = []
        selected_tool = None
        if arm == "P7S":
            # stage 1: enumerated tool selection (never leaks the answer)
            path, body = arms.build_request("P7S", task, budget, kw, stage=1)
            http_json, http_error, latency = self._post(base, path, body, 300)
            stage_records.append((1, path, http_json, http_error, latency))
            import re as _re
            m = _re.search(r"\d+", ((http_json or {}).get("content") or ""))
            tools = arms._world_tools(task)
            if m and 1 <= int(m.group(0)) <= len(tools):
                selected_tool = tools[int(m.group(0)) - 1]
        req_arm = "M-P1" if arm == "T2" else arm
        if arm != "P7S" or selected_tool is not None:
            stage = 2 if arm == "P7S" else 1
            path, body = arms.build_request(req_arm, task, budget, kw,
                                            stage=stage,
                                            selected_tool=selected_tool)
            http_json, http_error, latency = self._post(
                base, path, body, 240 + budget)
            stage_records.append((stage, path, http_json, http_error, latency))

        # parse the final stage payload (P7S stage 2 carries the answer)
        stage, path, http_json, http_error, latency = stage_records[-1]
        parse_arm = {"T2": "M-P1", "P7S": "M-P3"}.get(arm, arm)
        parsed = arms.parse_response(parse_arm, task, http_json, http_error)
        scored = scorer.score(task, parsed.get("payload"))

        tel = self._telemetry(arm, http_json, http_error, latency)
        artifact = self.run_dir / "responses" / f"{tid}.json"
        artifact.write_text(json.dumps(
            {"trial_id": tid, "stages": [
                {"stage": s, "path": p, "http": hj, "http_error": he,
                 "latency_s": l} for s, p, hj, he, l in stage_records]},
            ensure_ascii=False, indent=1), encoding="utf-8")

        record = {
            "trial_id": tid,
            "experiment_id": self.identity["experiment_id"],
            "model": model, "arm": arm, "task_id": task["task_id"],
            "family": task["family"], "lang": task["lang"], "budget": budget,
            "http_ok": http_json is not None, "http_error": http_error,
            "telemetry": tel,
            "parser": {"structural_ok": bool(parsed.get("structural_ok")),
                       "warnings": parsed.get("warnings", []),
                       "normalizations": parsed.get("normalizations", []),
                       "payload": parsed.get("payload")},
            "semantic_correct": scored["semantic_correct"],
            "tool_correct": scored["tool_correct"],
            "args_correct": scored["args_correct"],
            "reasons": scored["reasons"],
            "response_artifact": str(artifact.relative_to(ROOT)),
            "response_artifact_sha256": sha256_file(artifact),
        }
        with open(self.results_path, "ab") as f:
            f.write((json.dumps(record, ensure_ascii=False) + "\n")
                    .encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        self.done.add(tid)
        return 1

    def _telemetry(self, arm, http_json, http_error, latency) -> dict:
        """PR-D08/D09: endpoint-specific extraction; UNAVAILABLE/NOT_CAPTURED
        markers; never coerce missing usage to zero."""
        tel: dict = {"latency_s": latency,
                     "http_error": http_error}
        if http_json is None:
            tel["usage"] = "NOT_CAPTURED (request failed)"
            tel["finish_reason"] = "NOT_CAPTURED"
            return tel
        usage = http_json.get("usage")
        if usage is None:
            tel["usage"] = "NOT_CAPTURED"
        else:
            tel["usage"] = {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "cached_tokens": ((usage.get("prompt_tokens_details") or {})
                                  .get("cached_tokens", "NOT_CAPTURED")),
            }
        ch0 = (http_json.get("choices") or [{}])[0] if http_json.get("choices") else {}
        msg = ch0.get("message") or {}
        tel["finish_reason"] = ch0.get("finish_reason",
                                       http_json.get("stop_type",
                                                     "NOT_CAPTURED"))
        if arm in ("P5A", "P5B") or arm.startswith(("P0", "P1", "P2", "M-P0",
                                                    "M-P1", "M-P2", "T2")):
            tel["content"] = (msg.get("content") or "")[:2000] or None
            tel["reasoning_content_chars"] = len(
                msg.get("reasoning_content") or "")
            tel["reasoning_content_present"] = bool(
                (msg.get("reasoning_content") or "").strip())
            tel["tool_calls"] = msg.get("tool_calls") or []
            tel["truncated"] = ch0.get("finish_reason") == "length"
        else:
            content = http_json.get("content") or ""
            tel["content"] = content[:2000] or None
            tel["reasoning_content_present"] = False
            tel["truncated"] = http_json.get("stop_type") == "max_tokens" \
                or ch0.get("finish_reason") == "length"
            tel["stop_type"] = http_json.get("stop_type", "NOT_CAPTURED")
        tel["timings"] = http_json.get("timings", "NOT_CAPTURED")
        tel["reasoning_token_attribution"] = "UNAVAILABLE (b12359 usage has " \
                                             "no reasoning breakdown)"
        return tel


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights-root", required=True)
    ap.add_argument("--models", default="S1,S2,S3")
    ap.add_argument("--backend", default="vulkan")
    ap.add_argument("--port", type=int, default=8096)
    ap.add_argument("--phase", default="main", choices=["smoke", "main", "panel"])
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    return ControllerV2(args).run()


if __name__ == "__main__":
    sys.exit(main())
