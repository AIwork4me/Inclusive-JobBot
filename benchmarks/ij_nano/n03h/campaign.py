"""IJ-NANO-48H persistent campaign controller (order section 13).

Extends the N03 runner family — no second incompatible runner. The
controller owns: admission evidence, authorization (per block, recheck
per dispatch), balanced-block execution with model rotation, continuous
canaries + persistent circuit breaker, dispatch limits, crash-safe
exact resume, dual-path evaluation, sealing and analysis.

Classification discipline is inherited from the pinned EAE dualpath:
software/integrity buckets never enter model statistics; canary
controls are never benchmark trials.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time

from benchmarks.ij_nano.n03.authorization import (
    RunRequest, validate_against)
from benchmarks.ij_nano.n03h import eae as eae_mod
from benchmarks.ij_nano.n03h.transport import (
    ChatTransport, renderer_digest)

ROOT = eae_mod.ROOT
RUNS = ROOT / "runs" / "n03h"
WEIGHTS = {
    "MiniCPM5-2B":
        "models/MiniCPM5-2B-GGUF/MiniCPM5-2B-Q8_0.gguf",
    "LFM3-1.7B":
        "models/ij_sdk/LFM3-1.7B-GGUF/LFM3-1.7B-Q8_0.gguf",
    "Qwen3.5-2B":
        "models/ij_sdk/Qwen3.5-2B-GGUF/Qwen3.5-2B-Q8_0.gguf",
}
MODEL_SLOTS = ["MiniCPM5-2B", "LFM3-1.7B", "Qwen3.5-2B"]
BLOCK_CASES = 20          # balanced matched block (order section 13.3)
MAX_TRANSPORT_RETRIES = 2
CONSECUTIVE_TRANSPORT_BREAK = 3

SOFTWARE_CLASSES = {"PARSER_SOFTWARE_ERROR", "EVALUATOR_SOFTWARE_ERROR",
                    "NOT_EVALUABLE", "DUPLICATE_TRIAL", "MISSING_EVIDENCE",
                    "TRANSPORT_FAILURE"}
MODEL_CLASSES = {"CORRECT", "INCORRECT", "INVALID_OUTPUT", "EMPTY_OUTPUT"}


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Campaign:
    def __init__(self, scope: str, workdir: pathlib.Path | None = None,
                 weights_root: pathlib.Path | None = None,
                 port_base: int = 8230):
        self.scope = scope
        sc = eae_mod.SCOPES[scope]
        self.experiment_id = sc["experiment_id"]
        self.workdir = workdir or (RUNS / self.experiment_id)
        self.weights_root = pathlib.Path(weights_root) if weights_root \
            else (ROOT.parent / "IJSDK")
        self.port_base = port_base
        self.workdir.mkdir(parents=True, exist_ok=True)
        (self.workdir / "server").mkdir(exist_ok=True)
        self._eae = None

        roster = json.loads(
            sc["roster_file"].read_text(encoding="utf-8"))
        self.roster_slots = roster["slots"]
        self.dispatch_budget = len(self.roster_slots)
        self.state = self._load_state()
        # containment state is always live (restart-safe breaker), even
        # before any authorization exists. A workdir without a breaker
        # file is a CLEAN SLATE (order §15); an existing file is
        # reloaded (never silently discarded).
        _Breaker = eae_mod.import_pin_module(
            "eval_assurance.breaker").CircuitBreaker
        self.breaker = _Breaker(self.workdir / "cb.json")
        if (self.workdir / "cb.json").is_file():
            self.breaker.reload()

    @property
    def eae(self):
        """Lazy trusted-EAE bootstrap: admission/plan/status need no
        authorization; run/seal/verify trigger the fail-closed path."""
        if self._eae is None:
            self._eae = eae_mod.bootstrap(self.scope)
            from benchmarks.ij_nano.n03h.session_b import make_session
            self.session = make_session(self._eae["legs"], self.workdir)
            self.session.load()          # exact dual-path resume
            self.canary = self._eae["modules"]["canary"].CanaryScheduler(
                self._eae["witnesses"], breaker=self.breaker,
                expectations=self._eae["expectations"],
                cases_by_id=self._eae["cases_by_id"])
            legs = self._eae.get("canary_legs")
            if legs:
                self.canary.production_parser = legs["production_parser"]
                self.canary.production_evaluator =                     legs["production_evaluator"]
        return self._eae

    # -- persistent controller state --------------------------------------
    def _state_path(self) -> pathlib.Path:
        return self.workdir / "campaign_state.json"

    def _load_state(self) -> dict:
        p = self._state_path()
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
        return {"scope": self.scope,
                "experiment_id": self.experiment_id,
                "physical_attempts": 0,
                "completed_trial_ids": [],
                "quarantine_transport": 0,
                "consecutive_transport_failures": 0,
                "blocks_done": 0,
                "created_utc": utc(),
                "paused": False}

    def save(self) -> None:
        p = self._state_path()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(p)
        self.session.save()

    # -- roster -> balanced blocks (order 13.3) ----------------------------
    def execution_plan(self) -> list[dict]:
        """Balanced matched blocks: case-blocks of BLOCK_CASES in roster
        case order, models rotated WITHIN each block (never one arm
        finished while matched arms are empty)."""
        case_order: list[str] = []
        for s in self.roster_slots:
            if s["case_id"] not in case_order:
                case_order.append(s["case_id"])
        blocks = []
        for i in range(0, len(case_order), BLOCK_CASES):
            chunk = case_order[i:i + BLOCK_CASES]
            blocks.append(
                {"block": len(blocks),
                 "trials": [{"case_id": c, "model": m, "protocol": "chat"}
                            for c in chunk for m in MODEL_SLOTS]})
        return blocks

    # -- admission ----------------------------------------------------------
    @staticmethod
    def _gpu_identity_robust() -> dict:
        """gpu_identity with locale-tolerant decoding (the N02R helper's
        text=True reader can crash on non-UTF8 console output)."""
        import subprocess
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_VideoController | Where-Object "
                 "{$_.Name -like '*AMD Radeon*'} | Select-Object -First 1 "
                 "| ConvertTo-Json"],
                capture_output=True, timeout=30)
            j = json.loads(r.stdout.decode("utf-8", "replace"))
            return {"name": j.get("Name"), "driver": j.get("DriverVersion"),
                    "pnp_device_id": j.get("PNPDeviceID")}
        except Exception as e:                    # noqa: BLE001
            return {"error": f"UNAVAILABLE: {str(e)[:120]}"}

    def admission(self) -> dict:
        gpu = self._gpu_identity_robust()
        engine_dir = ROOT / "runtime" / "llama-cpp" / "vulkan"
        weights = {}
        for model, rel in WEIGHTS.items():
            p = (self.weights_root / rel).resolve()
            weights[model] = {
                "path": rel,
                "size": p.stat().st_size if p.is_file() else None,
                "sha256": eae_mod.sha256_file(p) if p.is_file() else None}
        adm = {
            "schema": "ijnano.n03h.admission.v1",
            "experiment_id": self.experiment_id,
            "gpu": gpu,
            "engine": {
                "exe_sha256": eae_mod.sha256_file(
                    engine_dir / "llama-server.exe"),
                "ggml_vulkan_dll_sha256": eae_mod.sha256_file(
                    engine_dir / "ggml-vulkan.dll"),
            },
            "weights": weights,
            "chat_renderer_sha256": renderer_digest(),
            "eae_pin": eae_mod.verify_pin(),
            "verified_utc": utc(),
        }
        (self.workdir / "admission.json").write_text(
            json.dumps(adm, indent=1, ensure_ascii=False), encoding="utf-8")
        return adm

    # -- physical admission probe (order section 3.1; NO trials) ----------
    def admission_probe(self) -> dict:
        """Start each model server briefly under the GPU lease, capture
        health/netstat ownership/offload/template fingerprint/metrics
        availability, then stop. This is runtime admission evidence —
        no benchmark trial is dispatched and no model output is
        recorded as evidence."""
        probe = {"schema": "ijnano.n03h.admission_probe.v1",
                 "experiment_id": self.experiment_id,
                 "probed_utc": utc(), "models": {}}
        for model in MODEL_SLOTS:
            weights = (self.weights_root / WEIGHTS[model]).resolve()
            if not weights.is_file():
                probe["models"][model] = {"status": "WEIGHTS_MISSING"}
                continue
            port = self.port_base + MODEL_SLOTS.index(model)
            tr = ChatTransport(model, weights, port,
                               self.workdir / "server" / model)
            try:
                info = tr.start()
                probe["models"][model] = {
                    "status": "OK",
                    "health": info["health"],
                    "offload": info.get("offload"),
                    "template_fingerprint": info["template_fingerprint"],
                }
            except Exception as e:                  # noqa: BLE001
                probe["models"][model] = {"status": "FAILED",
                                          "error": str(e)[:400]}
                try:
                    tr.stop()
                except Exception:                   # noqa: BLE001
                    pass
                continue
            try:
                import urllib.request
                with urllib.request.urlopen(tr.base + "/metrics",
                                            timeout=10) as r:
                    probe["models"][model]["metrics_endpoint"] = \
                        "OK" if r.status == 200 else f"HTTP {r.status}"
            except Exception as e:                  # noqa: BLE001
                probe["models"][model]["metrics_endpoint"] = \
                    f"NOT_CAPTURED ({str(e)[:80]})"
            tr.stop()
        (self.workdir / "admission_probe.json").write_text(
            json.dumps(probe, indent=1, ensure_ascii=False),
            encoding="utf-8")
        return probe

    # -- authorization ------------------------------------------------------
    def request(self) -> RunRequest:
        ident = self.eae["identity"]
        return RunRequest(
            experiment_id=ident["experiment_id"],
            dataset_digest=ident["dataset_digest"],
            roster_digest=ident["roster_digest"],
            primitives=frozenset(ident["primitives"]),
            protocols=frozenset(ident["protocols"]),
            models=frozenset(ident["models"]),
            eae_revision=ident["eae_revision"],
            auth_level=ident["auth_level"])

    def authorize_block(self) -> dict:
        auth = self.eae["gate"].authorize_physical(self.request())
        validate_against(auth, self.request())
        return {"authorization_checksum": auth.checksum,
                "auth_level": auth.auth_level,
                "experiment_binding": auth.experiment_id,
                "granted_utc": utc()}

    # -- core loop ------------------------------------------------------------
    def run(self, max_blocks: int | None = None) -> dict:
        self.eae                      # fail-closed bootstrap FIRST
        plan = self.execution_plan()
        # preflight canaries (fail-closed)
        results = self.canary.preflight()
        self._require_healthy(results, "preflight")
        blocks_run = 0
        transports: dict[str, ChatTransport] = {}
        try:
            for block in plan:
                if self.state.get("paused"):
                    break
                if max_blocks is not None and blocks_run >= max_blocks:
                    break
                if all(self._trial_key(t) in
                       self.state["completed_trial_ids"]
                       for t in block["trials"]):
                    self.state["blocks_done"] = max(
                        self.state["blocks_done"], block["block"] + 1)
                    continue                  # exact resume
                self._run_block(block, transports)
                blocks_run += 1
                self.state["blocks_done"] = max(
                    self.state["blocks_done"], block["block"] + 1)
                self._sample_server_health(transports)
                self.save()
        finally:
            for tr in transports.values():
                tr.stop()
        return self.analyze()

    def _trial_key(self, t: dict) -> str:
        return f"{t['case_id']}|{t['model']}|{t['protocol']}"

    def _run_block(self, block: dict,
                   transports: dict[str, ChatTransport]) -> None:
        block_auth = self.authorize_block()
        results_path = self.workdir / "results.jsonl"
        try:
            for t in block["trials"]:
                tid = self._trial_key(t)
                if tid in self.state["completed_trial_ids"]:
                    continue
                # dispatch limit (physical attempts, conservative)
                if self.state["physical_attempts"] >= self.dispatch_budget:
                    self.state["paused"] = True
                    self.state["pause_reason"] = "dispatch budget exhausted"
                    break
                self.breaker.may_dispatch(tid)
                # revocation recheck before EVERY physical dispatch
                auth = self.eae["gate"].authorize_physical(self.request())
                self.eae["provider"].recheck(auth)
                model = t["model"]
                if model not in transports:
                    transports[model] = self._start_transport(model)
                case = self.eae["cases_by_id"][t["case_id"]]
                expectation = self.eae["expectations"].get(t["case_id"])
                content, telemetry, ok = self._submit_with_retry(
                    transports[model], case)
                self.state["physical_attempts"] += 1
                self.breaker.register_dispatch(tid)
                if not ok:
                    self.state["quarantine_transport"] += 1
                    self.state["consecutive_transport_failures"] += 1
                    self.session.quarantine.append(
                        {"trial_id": tid, "reason": "TRANSPORT_FAILURE"})
                    self._append_result(results_path, {
                        "trial_id": tid, "model": model,
                        "case_id": t["case_id"],
                        "classification": "TRANSPORT_FAILURE",
                        "telemetry": telemetry, "block": block["block"],
                        "authorization": block_auth[
                            "authorization_checksum"]})
                    self.breaker.complete_dispatch(tid)
                    if self.state["consecutive_transport_failures"] >= \
                            CONSECUTIVE_TRANSPORT_BREAK:
                        self.breaker.open(
                            reason="consecutive transport failures",
                            affected_scope=self.experiment_id)
                        raise RuntimeError(
                            "circuit breaker opened: transport failures")
                    continue
                self.state["consecutive_transport_failures"] = 0
                result = self.session.run_trial(
                    case, expectation, content,
                    model=model, protocol=t["protocol"])
                self.breaker.complete_dispatch(tid)
                self.state["completed_trial_ids"].append(tid)
                self._append_result(results_path, {
                    "trial_id": tid, "model": model,
                    "case_id": t["case_id"], "protocol": t["protocol"],
                    "primitive": case.get("primitive"),
                    "family": case.get("family"),
                    "language": case.get("language"),
                    "classification": result.classification,
                    "production": result.production_verdict,
                    "reference": result.reference_verdict,
                    "typed_match": result.typed_match,
                    "telemetry": telemetry,
                    "block": block["block"],
                    "authorization": block_auth[
                        "authorization_checksum"]})
                canaries = self.canary.on_trial(tid)
                if canaries is not None:
                    self._require_healthy(canaries, f"post-{tid}")
        finally:
            pass                        # transports outlive the block
        self.save()

    def _sample_server_health(self, transports: dict) -> None:
        """Best-effort server-health telemetry between blocks (order
        §12.3/§16): llama-server /metrics when the endpoint answers;
        unavailable telemetry is recorded NOT_CAPTURED, never zero."""
        row = {"sampled_utc": utc(), "servers": {}}
        for model, tr in transports.items():
            if not tr.started:
                continue
            try:
                import urllib.request
                with urllib.request.urlopen(tr.base + "/metrics",
                                            timeout=10) as r:
                    text = r.read().decode("utf-8", "replace")
                keep = {}
                for line in text.splitlines():
                    if line.startswith(("#", "llamacpp:prompt")):
                        continue
                    if line.startswith("llamacpp:"):
                        keep[line.split("{")[0]] = line.rsplit(" ", 1)[-1]
                row["servers"][model] = keep
            except Exception as e:               # noqa: BLE001
                row["servers"][model] = {"metrics": "NOT_CAPTURED",
                                         "error": str(e)[:120]}
        if row["servers"]:
            with open(self.workdir / "server_health.jsonl", "a",
                      encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _start_transport(self, model: str) -> ChatTransport:
        weights = (self.weights_root / WEIGHTS[model]).resolve()
        port = self.port_base + MODEL_SLOTS.index(model)
        tr = ChatTransport(model, weights, port,
                           self.workdir / "server" / model)
        info = tr.start()
        (self.workdir / "server" / model / "session.json").write_text(
            json.dumps({"started_utc": utc(), **info}, indent=1,
                       ensure_ascii=False), encoding="utf-8")
        offload = (info.get("offload") or "")
        if "/24GB" not in str(info) and "offloaded" not in offload:
            raise RuntimeError(f"no GPU offload evidence for {model}: "
                               f"{offload!r}")
        return tr

    def _submit_with_retry(self, transport: ChatTransport, case: dict):
        telemetry = {}
        last_err = None
        for attempt in range(1 + MAX_TRANSPORT_RETRIES):
            try:
                content, telemetry = transport.submit(case)
                telemetry["transport_attempts"] = attempt + 1
                return content, telemetry, True
            except Exception as e:                # noqa: BLE001
                last_err = str(e)[:300]
                time.sleep(5)
        telemetry["transport_error"] = last_err
        telemetry["transport_attempts"] = 1 + MAX_TRANSPORT_RETRIES
        return "", telemetry, False

    def _require_healthy(self, results, where: str) -> None:
        failed = [r for r in results if not r.passed]
        if failed:
            self.breaker.open(
                reason=f"canary failure at {where}",
                affected_scope=self.experiment_id)
            raise RuntimeError(
                f"canary failure at {where}: "
                f"{[(f.family, f.positive_checks, f.negative_checks) for f in failed]}")

    def _append_result(self, path: pathlib.Path, row: dict) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # -- analysis / sealing ---------------------------------------------------
    def analyze(self) -> dict:
        counts: dict[str, int] = {}
        by_model: dict[str, dict[str, int]] = {}
        by_primitive: dict[str, dict[str, int]] = {}
        rows = []
        p = self.workdir / "results.jsonl"
        if p.is_file():
            rows = [json.loads(l) for l in
                    p.read_text(encoding="utf-8").splitlines() if l.strip()]
        for r in rows:
            c = r["classification"]
            counts[c] = counts.get(c, 0) + 1
            by_model.setdefault(r["model"], {})
            by_model[r["model"]][c] = by_model[r["model"]].get(c, 0) + 1
            prim = r.get("primitive") or "?"
            by_primitive.setdefault(prim, {})
            by_primitive[prim][c] = by_primitive[prim].get(c, 0) + 1
        model_eval = sum(counts.get(c, 0) for c in MODEL_CLASSES)
        software = sum(counts.get(c, 0) for c in SOFTWARE_CLASSES)
        planned = len(self.roster_slots)
        session = getattr(self, "session", None)
        return {
            "experiment_id": self.experiment_id,
            "scope": self.scope,
            "planned_slots": planned,
            "physical_attempts": self.state["physical_attempts"],
            "dispatch_budget": self.dispatch_budget,
            "recorded_trials": len(rows),
            "counts": counts,
            "by_model": by_model,
            "by_primitive": by_primitive,
            "model_evaluable_outcomes": model_eval,
            "software_or_unresolvable": software,
            "quarantined": len(self.session.quarantine) if session
            else self.state.get("quarantine_transport", 0),
            "canary_controls": len(session.canary_controls) if session
            else None,
            "breaker_open": bool(self.breaker.is_open),
            "analyzed_utc": utc(),
        }

    def seal(self) -> dict:
        if bool(self.breaker.is_open):
            return {"sealed": False,
                    "reason": "breaker open; evidence preserved unsealed"}
        canaries = self.canary.before_seal()
        self._require_healthy(canaries, "before_seal")
        problems = self.verify()
        digest = eae_mod.sha256_file(self.workdir / "results.jsonl") \
            if (self.workdir / "results.jsonl").is_file() else ""
        seal = {
            "schema": "ijnano.n03h.seal.v1",
            "experiment_id": self.experiment_id,
            "results_sha256": digest,
            "trials": len(self.state["completed_trial_ids"]),
            "physical_attempts": self.state["physical_attempts"],
            "integrity_problems": problems,
            "sealed_utc": utc(),
        }
        (self.workdir / "seal.json").write_text(
            json.dumps(seal, indent=1, ensure_ascii=False),
            encoding="utf-8")
        return seal

    def verify(self) -> list[str]:
        """Independent offline replay of every recorded trial through the
        preserved dual-path artifacts (no transport), plus the dual-path
        artifact re-hash (tamper/absence detection)."""
        problems = self.session.verify()
        p = self.workdir / "results.jsonl"
        if not p.is_file():
            return problems
        rows = [json.loads(l) for l in
                p.read_text(encoding="utf-8").splitlines() if l.strip()]
        for r in rows:
            if r["classification"] == "TRANSPORT_FAILURE":
                continue
            tid = r["trial_id"]
            if tid not in self.session.trials:
                problems.append(f"{tid}: not in dual-path store")
                continue
            case = self.eae["cases_by_id"].get(r["case_id"])
            expectation = self.eae["expectations"].get(r["case_id"])
            protocol = r.get("protocol") or r["trial_id"].rsplit("|", 1)[1]
            rep = self.session.replay(case, expectation, r["model"],
                                      protocol)
            if not rep["matches_recorded"]:
                problems.append(f"{tid}: replay mismatch "
                                f"{rep['replay_classification']} != "
                                f"{rep['recorded_classification']}")
        return problems


def main() -> int:
    ap = argparse.ArgumentParser("n03h campaign controller")
    ap.add_argument("command",
                    choices=["plan", "status", "admission",
                             "admission-probe", "run",
                             "analyze", "seal", "verify", "pause"])
    ap.add_argument("--scope", default="AUTH-1",
                    choices=["AUTH-1", "AUTH-2", "AUTH-2B"])
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--weights-root", default=None)
    ap.add_argument("--max-blocks", type=int, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    camp = Campaign(args.scope,
                    pathlib.Path(args.workdir) if args.workdir else None,
                    pathlib.Path(args.weights_root)
                    if args.weights_root else None)
    if args.command == "plan":
        out = {"blocks": [
            {"block": b["block"], "trials": len(b["trials"])}
            for b in camp.execution_plan()]}
    elif args.command == "status":
        out = {"state": camp.state,
               "analysis": camp.analyze()}
    elif args.command == "admission":
        out = camp.admission()
    elif args.command == "admission-probe":
        from benchmarks.root_cause.gpu_lease import physical_gpu
        with physical_gpu():        # host-wide GPU lease (N00R)
            out = {"admission": camp.admission(),
                   "probe": camp.admission_probe()}
    elif args.command == "run":
        from benchmarks.root_cause.gpu_lease import physical_gpu
        with physical_gpu():            # host-wide GPU lease (N00R)
            camp.admission()
            out = camp.run(args.max_blocks)
            out["seal"] = camp.seal()
    elif args.command == "analyze":
        out = camp.analyze()
    elif args.command == "verify":
        out = {"problems": camp.verify()}
    elif args.command == "pause":
        camp.state["paused"] = True
        camp.state["pause_reason"] = "operator pause"
        camp.save()
        out = {"paused": True}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
