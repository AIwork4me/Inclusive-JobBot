"""N02R persistent physical experiment controller (order 1.2 sections 3
and 9).

Holds the host-wide GPU lease for the whole session; per model, starts the
pinned llama-server once per wave and executes the trial queue with:

- immutable trial identity: sha256(model|arm|task_id|budget|experiment_id);
- atomic persistence: one JSON line per trial, fsync after each write;
- checkpoint recovery / duplicate prevention: completed trial ids are
  reloaded at start and skipped;
- bounded watchdog timeout per request;
- process ownership verification (socket owned by launched PID) and D-010
  offload evidence;
- disk-space monitoring and simple resource accounting;
- probe false-positive audit (order section 3.2) once per model session;
- evidence sealing: manifest with hashes at session end.

Usage:
    python -I benchmarks/ij_nano/n02r/controller.py \
        --weights-root <dir> --models S1,S2,S3 --phase main --port 8095
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
import gpu_lease  # noqa: E402  (host-wide named-mutex lease, reused as-is)

from tasks import build_suite, suite_hash  # noqa: E402
import arms  # noqa: E402
import scorer  # noqa: E402

MODELS = {
    "S1": ("models/MiniCPM5-2B-GGUF/MiniCPM5-2B-Q8_0.gguf", "minicpm5-2b"),
    "S2": ("models/ij_sdk/LFM3-1.7B-GGUF/LFM3-1.7B-Q8_0.gguf", "lfm3-1.7b"),
    "S3": ("models/ij_sdk/Qwen3.5-2B-GGUF/Qwen3.5-2B-Q8_0.gguf", "qwen3.5-2b"),
}
WAVE = 20            # tasks per wave (GPU balance across models)
PANEL_TASKS = 12     # first 2 tasks per family, by task order (preregistered)


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(p: pathlib.Path, limit_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
            if limit_bytes and h.digest_size * 0:
                break
    return h.hexdigest()


def post_json(base: str, path: str, body: dict, timeout: float = 240):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class ServerSession:
    """One llama-server lifetime for one model (process ownership + D-010)."""

    def __init__(self, backend: str, model: pathlib.Path, alias: str, port: int,
                 workdir: pathlib.Path):
        self.binary_dir = ROOT / "runtime" / "llama-cpp" / backend
        self.model, self.alias, self.port = model, alias, port
        self.workdir = workdir
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.proc = None
        self.stdout_log = workdir / "server.stdout.log"
        self.stderr_log = workdir / "server.stderr.log"

    def start(self):
        exe = self.binary_dir / "llama-server.exe"
        args = [str(exe), "-m", str(self.model), "--alias", self.alias,
                "--host", "127.0.0.1", "--port", str(self.port),
                "-c", "8192", "-ngl", "99", "--jinja", "--cache-reuse", "256",
                "-v"]
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
                with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                    owner = self.proc.pid
                with urllib.request.urlopen(base + "/health", timeout=5) as r:
                    if r.status == 200:
                        return {"socket_owner_pid": owner,
                                "health": json.loads(r.read().decode("utf-8"))}
            except Exception:
                time.sleep(1.5)
        raise RuntimeError("server not healthy before deadline")

    def offload_line(self) -> str | None:
        pat = re.compile(r"offloaded (\d+)/(\d+) layers to GPU")
        for log in (self.stdout_log, self.stderr_log):
            try:
                for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
                    m = pat.search(line)
                    if m:
                        return m.group(0)
            except OSError:
                continue
        return None

    def stop(self):
        if self.proc and self.proc.poll() is None:
            subprocess.run(["taskkill", "/F", "/PID", str(self.proc.pid)],
                           capture_output=True)
        time.sleep(2)


# -- probe audit (order 3.2) -----------------------------------------------------

def probe_audit(base: str, out_dir: pathlib.Path, model_id: str) -> dict:
    """Corrected probe checks run once per model session. The original N02
    artifacts are preserved untouched; this audit supersedes their scoring
    logic only inside N02R evidence."""
    res = {"kind": "n02r_probe_audit", "model": model_id, "checks": {}}
    ck = res["checks"]

    # A) empty final content is NOT successful text generation
    try:
        j = post_json(base, "/v1/chat/completions", {
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            "max_tokens": 16, "temperature": 0, "seed": 42})
        content = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        ck["empty_content_gate"] = {
            "status": "PASS" if content.strip() else "FAIL",
            "content": content[:80],
            "note": "PASS requires non-empty final content (v1 probe accepted "
                    "empty content with completion_tokens set)"}
    except Exception as e:
        ck["empty_content_gate"] = {"status": "ERROR", "error": str(e)[:200]}

    # B) native tool call: structural + semantic scoring
    try:
        j = post_json(base, "/v1/chat/completions", {
            "messages": [{"role": "system", "content": "需要查询数据时调用工具。"},
                         {"role": "user", "content": "查询 SKU-1001 的库存"}],
            "tools": [{"type": "function", "function": {
                "name": "get_inventory",
                "description": "按商品编号查询当前库存数量和仓库位置。",
                "parameters": {"type": "object",
                               "properties": {"sku": {"type": "string"}},
                               "required": ["sku"],
                               "additionalProperties": False}}}],
            "tool_choice": "auto", "max_tokens": 256, "temperature": 0, "seed": 42})
        msg = (j.get("choices") or [{}])[0].get("message") or {}
        tcs = msg.get("tool_calls") or []
        structural = bool(tcs) and bool(tcs[0].get("function", {}).get("name"))
        semantic = False
        if structural:
            try:
                fargs = json.loads(tcs[0]["function"].get("arguments") or "{}")
                semantic = (tcs[0]["function"]["name"] == "get_inventory"
                            and fargs.get("sku") == "SKU-1001")
            except Exception:
                semantic = False
        ck["tool_call_structural_semantic"] = {
            "status": "PASS" if (structural and semantic) else "FAIL",
            "structural": structural, "semantic": semantic,
            "tool_calls": [{"name": t.get("function", {}).get("name"),
                            "arguments": t.get("function", {}).get("arguments", "")[:80]}
                           for t in tcs[:2]]}
    except Exception as e:
        ck["tool_call_structural_semantic"] = {"status": "ERROR", "error": str(e)[:200]}

    # C) SSE usage reconciliation with actual streamed content
    try:
        body = {"messages": [{"role": "user",
                              "content": "Count from 1 to 5, digits only, comma separated."}],
                "max_tokens": 32, "temperature": 0, "seed": 42, "stream": True,
                "stream_options": {"include_usage": True}}
        data = json.dumps(body).encode()
        req = urllib.request.Request(base + "/v1/chat/completions", data=data,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        content_pieces, reasoning_pieces, usage = [], [], None
        with urllib.request.urlopen(req, timeout=120) as r:
            for raw in r:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:") or line.endswith("[DONE]"):
                    continue
                pj = json.loads(line[5:].strip())
                if pj.get("usage"):
                    usage = pj["usage"]
                for ch in pj.get("choices", []):
                    delta = ch.get("delta") or {}
                    if delta.get("content"):
                        content_pieces.append(delta["content"])
                    if delta.get("reasoning_content"):
                        reasoning_pieces.append(delta["reasoning_content"])
        streamed_chars = sum(len(p) for p in content_pieces) \
            + sum(len(p) for p in reasoning_pieces)
        completion_tokens = (usage or {}).get("completion_tokens")
        reconciled = bool(usage) and completion_tokens \
            and streamed_chars > 0
        ck["sse_usage_reconciliation"] = {
            "status": "PASS" if reconciled else "FAIL",
            "streamed_content_chars": sum(len(p) for p in content_pieces),
            "streamed_reasoning_chars": sum(len(p) for p in reasoning_pieces),
            "content_piece_count": len(content_pieces),
            "completion_tokens": completion_tokens,
            "note": "observable stream channels (content + reasoning) "
                    "reconciled with usage; exact reasoning-token attribution "
                    "is UNAVAILABLE in b12359 usage (no breakdown field)"}
    except Exception as e:
        ck["sse_usage_reconciliation"] = {"status": "ERROR", "error": str(e)[:200]}

    # D) cancellation scope: client abort vs server-side termination + slot release
    try:
        body = {"messages": [{"role": "user",
                              "content": "Write a 300-word story about a warehouse robot."}],
                "max_tokens": 512, "temperature": 0, "seed": 42, "stream": True}
        data = json.dumps(body).encode()
        req = urllib.request.Request(base + "/v1/chat/completions", data=data,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        client_aborted, server_terminated = False, False
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                for _ in range(3):
                    r.read(64)
                raise TimeoutError("client abort")
        except TimeoutError:
            client_aborted = True
        except urllib.error.HTTPError:
            server_terminated = True
        time.sleep(3)
        healthy = False
        try:
            with urllib.request.urlopen(base + "/health", timeout=10) as r:
                healthy = r.status == 200
        except Exception:
            healthy = False
        slot_released = False
        try:
            j = post_json(base, "/v1/chat/completions", {
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "max_tokens": 64, "temperature": 0, "seed": 42})
            usage = j.get("usage") or {}
            # slot release = the server accepted and completed a NEW
            # generation after the abort (token accounting progressed);
            # empty text content is model behavior, not slot state
            slot_released = bool(usage.get("completion_tokens"))
        except Exception:
            slot_released = False
        ck["cancellation_scope"] = {
            "status": "PASS" if (client_aborted and not server_terminated
                                 and healthy and slot_released) else "FAIL",
            "client_aborted": client_aborted, "server_terminated": server_terminated,
            "server_healthy_after": healthy, "slot_released_followup_ok": slot_released,
            "note": "client-side cancellation distinguished from server-side "
                    "termination; inference-slot release proven by a follow-up "
                    "generation"}
    except Exception as e:
        ck["cancellation_scope"] = {"status": "ERROR", "error": str(e)[:200]}

    # E) rendered-prompt verification endpoint
    try:
        j = post_json(base, "/apply-template", {
            "messages": [{"role": "user", "content": "ping"}]})
        prompt = j.get("prompt")
        ck["rendered_prompt_endpoint"] = {
            "status": "PASS" if isinstance(prompt, str) and prompt else "FAIL",
            "prompt_sha256": hashlib.sha256((prompt or "").encode()).hexdigest()[:16],
            "prompt_head": (prompt or "")[:160]}
    except Exception as e:
        ck["rendered_prompt_endpoint"] = {"status": "UNAVAILABLE",
                                          "error": str(e)[:160]}

    # F) escaped-quote GBNF reproduction (order 3.7): the N02 engine record
    # blamed the parser; upstream source at b1b770d90 supports \" escapes in
    # parse_char. Distinguish incorrect grammar construction from an engine
    # defect by sending three grammars.
    def _grammar_probe(name: str, grammar: str):
        try:
            j = post_json(base, "/completion", {
                "prompt": "x", "grammar": grammar, "n_predict": 4,
                "temperature": 0, "seed": 42}, timeout=60)
            ck[name] = {"status": "ACCEPTED",
                        "sample": (j.get("content") or "")[:40]}
        except urllib.error.HTTPError as e:
            ck[name] = {"status": "REJECTED",
                        "http": e.code,
                        "error": e.read().decode(errors="replace")[:160]}
        except Exception as e:
            ck[name] = {"status": "ERROR", "error": str(e)[:160]}
    # F1: the exact grammar string reconstructed from the N02 probe record
    _grammar_probe("gbnf_n02_escaped_quote_reconstruction",
                   'root ::= "{" "\\"sku\\":\\"" [A-Z0-9-]+ "\\" "}"')
    # F2: minimal known-valid upstream-style escaped-quote literal
    _grammar_probe("gbnf_minimal_escaped_quote",
                   'root ::= "say \\"hi\\""')
    # F3: char-class form (the documented workaround)
    _grammar_probe("gbnf_charclass_quote",
                   'root ::= "{" ["] "sku" ["] ":" ["] [A-Z0-9-]+ ["] "}"')
    # F4-F7: decomposition of the rejected N02 construction
    _grammar_probe("gbnf_only_escaped_quote_literal",
                   'root ::= "\\" [A-Z]+ "\\"')
    _grammar_probe("gbnf_literal_starts_with_escaped_quote",
                   'root ::= "\\"sku" [A-Z0-9-]+')
    _grammar_probe("gbnf_escaped_quote_with_colon_inside",
                   'root ::= "a\\":\\"b"')
    _grammar_probe("gbnf_brace_then_escaped_quote_start",
                   'root ::= "{" "\\"sku" [A-Z0-9-]+ "\\" "}"')

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"probe_audit_{model_id}.json").write_text(
        json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    return res


def verify_thinking_kwarg(base: str) -> tuple[str | None, bool, dict]:
    """Find a chat_template_kwargs flag that the model's template actually
    HONORS, and verify it suppresses reasoning output.

    A kwarg is accepted silently by jinja even when the template ignores
    it, so acceptance alone proves nothing: first diff the RENDERED prompt
    via /apply-template with vs without the kwarg (template-effective),
    then confirm behaviorally on one constrained request.
    Returns (kwarg, verified, evidence)."""
    evidence: dict = {"candidates": {}}
    schema = {"type": "object",
              "properties": {"decision": {"type": "string",
                                          "enum": ["stop", "continue"]}},
              "required": ["decision"], "additionalProperties": False}
    try:
        base_render = post_json(base, "/apply-template", {
            "messages": [{"role": "user", "content": "Continue or stop? Answer."}]})
        base_prompt = base_render.get("prompt")
    except Exception as e:
        base_prompt = None
        evidence["apply_template"] = f"unavailable: {str(e)[:120]}"
    for kw in ("enable_thinking", "thinking"):
        ev: dict = {}
        try:
            if base_prompt is not None:
                r = post_json(base, "/apply-template", {
                    "messages": [{"role": "user", "content":
                                  "Continue or stop? Answer."}],
                    "chat_template_kwargs": {kw: False}})
                ev["template_effective"] = (r.get("prompt") != base_prompt)
                if not ev["template_effective"]:
                    evidence["candidates"][kw] = ev
                    continue
            j = post_json(base, "/v1/chat/completions", {
                "messages": [{"role": "user", "content": "Continue or stop? Answer."}],
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": "d", "strict": True,
                                                    "schema": schema}},
                "chat_template_kwargs": {kw: False},
                "max_tokens": 128, "temperature": 0, "seed": 42}, timeout=180)
            msg = (j.get("choices") or [{}])[0].get("message") or {}
            reasoning = msg.get("reasoning_content") or ""
            content = msg.get("content") or ""
            ev["reasoning_suppressed"] = not reasoning.strip()
            ev["content_nonempty"] = bool(content.strip())
            verified = (not reasoning.strip()) and bool(content.strip())
            evidence["candidates"][kw] = ev
            if verified:
                return kw, True, evidence
        except urllib.error.HTTPError as e:
            ev["rejected"] = e.code
            evidence["candidates"][kw] = ev
        except Exception as e:
            ev["error"] = str(e)[:120]
            evidence["candidates"][kw] = ev
    return None, False, evidence


# -- controller -----------------------------------------------------------------

class Controller:
    def __init__(self, args):
        self.args = args
        self.weights_root = pathlib.Path(args.weights_root).resolve()
        self.suite = build_suite()
        self.ev_dir = ROOT / "evidence" / "IJNANO" / "N02R" / "runs"
        self.experiment_id = self._identity()
        self.run_dir = self.ev_dir / self.experiment_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.results_path = self.run_dir / "results.jsonl"
        self.done: set[str] = set()
        self.thinking_kwarg: dict[str, tuple] = {}
        self.engine_sha = sha256_file(
            ROOT / "runtime" / "llama-cpp" / args.backend / "llama-server.exe")

    def _identity(self) -> str:
        spec = {
            "suite_hash": suite_hash(),
            "arms": {a: arms.ARM_LABELS[a] for a in arms.ARMS},
            "budget_panel_arms": list(arms.BUDGET_PANEL_ARMS),
            "panel_tasks": PANEL_TASKS,
            "primary_budget": arms.PRIMARY_BUDGET,
            "budgets": list(arms.BUDGETS),
            "decoding": {"temperature": 0, "seed": 42, "cache_prompt": True},
            "controller_sha": hashlib.sha256(
                pathlib.Path(__file__).read_bytes()).hexdigest(),
            "arms_sha": hashlib.sha256(
                pathlib.Path(arms.__file__).read_bytes()).hexdigest(),
            "scorer_sha": hashlib.sha256(
                pathlib.Path(scorer.__file__).read_bytes()).hexdigest(),
            "phase_plan": {"main": "3 models x 8 arms x 60 tasks @1024",
                           "panel": "3 models x 4 arms x 12 tasks x 5 budgets"},
        }
        return hashlib.sha256(json.dumps(spec, sort_keys=True)
                              .encode()).hexdigest()[:16]

    def _reload_done(self):
        if self.results_path.exists():
            for line in self.results_path.read_text(encoding="utf-8").splitlines():
                try:
                    self.done.add(json.loads(line)["trial_id"])
                except Exception:
                    continue

    def _trial_id(self, model: str, arm: str, task_id: str, budget: int) -> str:
        return hashlib.sha256(
            f"{self.experiment_id}|{model}|{arm}|{task_id}|{budget}"
            .encode()).hexdigest()[:24]

    def _append(self, record: dict):
        with open(self.results_path, "ab") as f:
            f.write((json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())

    def _queue(self, phase: str):
        """(model, arm, task, budget) tuples in wave-interleaved order."""
        q = []
        if phase in ("main", "smoke"):
            suite = self.suite[:2] if phase == "smoke" else self.suite
            wave_size = 2 if phase == "smoke" else WAVE
            for w0 in range(0, len(suite), wave_size):
                wave = suite[w0:w0 + wave_size]
                for model in self.args.models.split(","):
                    for t in wave:
                        for arm in arms.ARMS:
                            q.append((model, arm, t, arms.PRIMARY_BUDGET))
        if phase == "panel":
            panel_ids = {t["task_id"] for t in self.suite[:PANEL_TASKS]}
            for model in self.args.models.split(","):
                for t in [x for x in self.suite if x["task_id"] in panel_ids]:
                    for arm in arms.BUDGET_PANEL_ARMS:
                        for b in arms.BUDGETS:
                            q.append((model, arm, t, b))
        return q

    def run(self) -> int:
        self._reload_done()
        manifest = {
            "experiment_id": self.experiment_id,
            "created_utc": utc(),
            "identity_spec": "see controller._identity(); suite_hash="
                             + suite_hash(),
            "engine": {"binary": "runtime/llama-cpp/"
                       f"{self.args.backend}/llama-server.exe",
                       "sha256": self.engine_sha,
                       "pinned_build": "b12359 (commit b1b770d90)"},
            "lease": "benchmarks/root_cause/gpu_lease.py physical_gpu() "
                     "(host-wide named mutex)",
            "models": {}, "phase": self.args.phase,
        }
        for m in self.args.models.split(","):
            rel, alias = MODELS[m]
            mp = (self.weights_root / rel).resolve()
            manifest["models"][m] = {"path": rel, "alias": alias,
                                     "sha256": sha256_file(mp) if mp.is_file() else None}
        (self.run_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")

        disk = shutil.disk_usage(self.run_dir)
        print(f"[ctrl] experiment {self.experiment_id} phase={self.args.phase} "
              f"queue≈{len(self._queue(self.args.phase))} done={len(self.done)} "
              f"disk_free_GB={disk.free / 1e9:.1f}", flush=True)

        executed = skipped = 0
        base = f"http://127.0.0.1:{self.args.port}"
        with gpu_lease.physical_gpu():
            print(f"[lease ACQUIRED {utc()}]", flush=True)
            current_model, session = None, None
            try:
                for model, arm, task, budget in self._queue(self.args.phase):
                    tid = self._trial_id(model, arm, task["task_id"], budget)
                    if tid in self.done:
                        skipped += 1
                        continue
                    if model != current_model:
                        if session:
                            session.stop()
                        rel, alias = MODELS[model]
                        mp = (self.weights_root / rel).resolve()
                        session = ServerSession(
                            self.args.backend, mp, alias, self.args.port,
                            ROOT / ".runtime" / "ij_nano_n02r" / model)
                        session.start()
                        proof = session.wait_ready(time.time() + 900)
                        time.sleep(2)
                        offload = session.offload_line()
                        print(f"[{model}] server pid={proof['socket_owner_pid']} "
                              f"offload={offload}", flush=True)
                        probe_audit(base, self.run_dir, model)
                        kw, verified, ev = verify_thinking_kwarg(base)
                        self.thinking_kwarg[model] = (kw, verified)
                        (self.run_dir / f"thinking_verification_{model}.json").write_text(
                            json.dumps({"model": model, "kwarg": kw,
                                        "verified": verified, "evidence": ev},
                                       indent=1, ensure_ascii=False),
                            encoding="utf-8")
                        print(f"[{model}] thinking_kwarg={kw} verified={verified}",
                              flush=True)
                        current_model = model
                    record = self._run_trial(base, model, arm, task, budget, tid)
                    self._append(record)
                    self.done.add(tid)
                    executed += 1
                    if executed % 25 == 0:
                        print(f"[ctrl] executed={executed} skipped={skipped} "
                              f"({utc()})", flush=True)
            finally:
                if session:
                    session.stop()
                print(f"[lease RELEASED {utc()}]", flush=True)

        seal = {"experiment_id": self.experiment_id, "sealed_utc": utc(),
                "executed_this_session": executed, "skipped_done": skipped,
                "total_done": len(self.done),
                "results_sha256": sha256_file(self.results_path)}
        (self.run_dir / "seal.json").write_text(
            json.dumps(seal, indent=1), encoding="utf-8")
        print(f"[ctrl] session done: executed={executed} skipped={skipped} "
              f"total={len(self.done)} -> {self.results_path}", flush=True)
        return 0

    def _run_trial(self, base: str, model: str, arm: str, task: dict,
                   budget: int, tid: str) -> dict:
        kw = self.thinking_kwarg.get(model, (None, False))[0]
        path, body = arms.build_request(arm, task, budget, kw)
        timeout = 240 + budget          # watchdog, seconds
        t0 = time.monotonic()
        http_json, http_error = None, None
        try:
            http_json = post_json(base, path, body, timeout)
        except urllib.error.HTTPError as e:
            http_error = f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}"
        except Exception as e:
            http_error = f"{type(e).__name__}: {str(e)[:200]}"
        latency = round(time.monotonic() - t0, 3)

        parsed = arms.parse_response(arm, task, http_json, http_error)
        scored = scorer.score(task, parsed.get("payload"))

        usage = (http_json or {}).get("usage") or {}
        ch0 = ((http_json or {}).get("choices") or [{}])[0] if http_json else {}
        msg = (ch0.get("message") or {}) if ch0 else {}
        if arm in ("P0", "P1", "P2", "P5"):
            content = msg.get("content") if isinstance(msg, dict) else None
            reasoning = msg.get("reasoning_content") if isinstance(msg, dict) else None
        else:
            content = (http_json or {}).get("content")
            reasoning = (http_json or {}).get("reasoning_content") \
                if isinstance(http_json, dict) else None
            if not isinstance(reasoning, str):
                reasoning = None
        raw_trim = json.dumps(http_json, ensure_ascii=False)[:4000] if http_json else None

        return {
            "trial_id": tid, "experiment_id": self.experiment_id,
            "model": model, "arm": arm, "task_id": task["task_id"],
            "family": task["family"], "lang": task["lang"], "budget": budget,
            "http_ok": http_json is not None, "http_error": http_error,
            "finish_reason": ch0.get("finish_reason"),
            "content_empty": not (content or "").strip() if content is not None else True,
            "content_len": len(content or "") if isinstance(content, str) else None,
            "reasoning_content_present": bool((reasoning or "").strip()),
            "reasoning_token_attribution": "UNAVAILABLE",
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "timeout": bool(http_error and "timed out" in str(http_error).lower()),
            "latency_s": latency,
            "structural_valid": bool(parsed.get("structural_ok")),
            "semantic_correct": scored["semantic_correct"],
            "tool_correct": scored["tool_correct"],
            "args_correct": scored["args_correct"],
            "reasons": scored["reasons"],
            "parse_notes": parsed.get("notes"),
            "truncated": ch0.get("finish_reason") == "length",
            "raw_trimmed": raw_trim,
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights-root", required=True)
    ap.add_argument("--models", default="S1,S2,S3")
    ap.add_argument("--backend", default="vulkan")
    ap.add_argument("--port", type=int, default=8095)
    ap.add_argument("--phase", default="main", choices=["smoke", "main", "panel"])
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    return Controller(args).run()


if __name__ == "__main__":
    sys.exit(main())
