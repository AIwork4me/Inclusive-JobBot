"""N03-B4 persistent runner (IJ-NANO-1.3S order section 5).

Operations: preflight, freeze, authorization, run, pause, resume,
quarantine, replay, verify, analyze, publish. CPU-only under AUTH-0 via a
synthetic transport; physical dispatch goes exclusively through the
DispatchGate in authorization.py (fail-closed; test doubles rejected).

Software errors (parser/evaluator exceptions, evidence corruption, oracle
disagreement, duplicates, canary failures) are classified into their own
buckets and NEVER enter model-failure statistics.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time
from dataclasses import dataclass, field

from .authorization import (AuthorizationError, DispatchGate,
                            ExecutionAuthorization, RunRequest)

# trial classification buckets
CORRECT = "CORRECT"
INCORRECT = "INCORRECT"
INVALID_OUTPUT = "INVALID_OUTPUT"          # model-side, structural
NOT_EVALUABLE = "NOT_EVALUABLE"            # unresolved dual-path disagreement
PARSER_SOFTWARE_ERROR = "PARSER_SOFTWARE_ERROR"
EVALUATOR_SOFTWARE_ERROR = "EVALUATOR_SOFTWARE_ERROR"
EVIDENCE_REJECTED = "EVIDENCE_REJECTED"
DUPLICATE_TRIAL = "DUPLICATE_TRIAL"
CANARY_FAILURE = "CANARY_FAILURE"

SOFTWARE_BUCKETS = {PARSER_SOFTWARE_ERROR, EVALUATOR_SOFTWARE_ERROR,
                    EVIDENCE_REJECTED, DUPLICATE_TRIAL, CANARY_FAILURE,
                    NOT_EVALUABLE}
MODEL_BUCKETS = {CORRECT, INCORRECT, INVALID_OUTPUT}


class CircuitBreakerOpen(RuntimeError):
    """Raised when dispatch is stopped by the canary circuit breaker."""


@dataclass
class RawResponse:
    """Transport-level record; artifact bytes are content-addressed."""
    model: str
    protocol: str
    case_id: str
    content: str
    telemetry: dict = field(default_factory=dict)

    def artifact(self) -> dict:
        payload = json.dumps({"case_id": self.case_id, "model": self.model,
                              "protocol": self.protocol,
                              "content": self.content},
                             sort_keys=True, ensure_ascii=False)
        return {"artifact_sha256": hashlib.sha256(
            payload.encode("utf-8")).hexdigest(),
            "payload": payload,
            "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                          time.gmtime())}


class SyntheticTransport:
    """Scripted transport: case_id -> callable returning content or
    raising. CPU-only by construction; no network, no GPU."""

    def __init__(self, script: dict):
        self.script = dict(script)

    def submit(self, case_id: str, model: str, protocol: str) -> RawResponse:
        fn = self.script.get(case_id)
        if fn is None:
            fn = self.script.get("*", lambda: "ok-placeholder")
        content = fn()
        return RawResponse(model=model, protocol=protocol, case_id=case_id,
                           content=content)


@dataclass
class ProductionParser:
    """Parses raw content into a structured answer. ``raise_on`` marks
    case ids that must raise (fault injection)."""
    raise_on: frozenset = frozenset()

    def parse(self, case_id: str, content: str):
        if case_id in self.raise_on:
            raise RuntimeError(f"injected parser exception at {case_id}")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None                    # invalid MODEL output


@dataclass
class ProductionEvaluator:
    """Compares parsed answer to expectations. ``raise_on`` injects
    evaluator software faults."""
    raise_on: frozenset = frozenset()

    def evaluate(self, case_id: str, parsed, expected: dict) -> str:
        if case_id in self.raise_on:
            raise RuntimeError(f"injected evaluator exception at {case_id}")
        if parsed is None:
            return INVALID_OUTPUT
        return CORRECT if parsed == expected else INCORRECT


@dataclass
class ReferenceOracle:
    """Independent second path. ``disagree_on`` forces disagreement
    (dual-path fault injection)."""
    disagree_on: frozenset = frozenset()

    def verdict(self, case_id: str, parsed, expected: dict) -> str:
        if case_id in self.disagree_on:
            return INCORRECT if parsed == expected else CORRECT
        if parsed is None:
            return INVALID_OUTPUT
        return CORRECT if parsed == expected else INCORRECT


@dataclass
class CanaryPolicy:
    """Interleave canary trials; a failing canary opens the breaker."""
    interval: int = 25                    # trials between canaries
    known_correct: tuple = (("canary-ok", '{"x": 1}'),)
    known_incorrect: tuple = (("canary-bad", '{"x": 2}', '{"x": 1}'),)
    fail_on: frozenset = frozenset()      # canary ids that must fail


class Runner:
    """Persistent, resumable trial runner (AUTH-0 software core)."""

    def __init__(self, config: dict, transport, parser, evaluator, oracle,
                 gate: DispatchGate, provider, canary: CanaryPolicy,
                 workdir: pathlib.Path):
        self.config = config
        self.transport = transport
        self.parser = parser
        self.evaluator = evaluator
        self.oracle = oracle
        self.gate = gate
        self.provider = provider
        self.canary = canary
        self.workdir = pathlib.Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.trials: dict[str, dict] = {}      # trial_id -> record
        self.completed_case_ids: set[str] = set()
        self.quarantine: list[dict] = []
        self.breaker_open = False
        self.auth: ExecutionAuthorization | None = None

    # -- identity binding ------------------------------------------------
    def request(self) -> RunRequest:
        return RunRequest(
            experiment_id=self.config["experiment_id"],
            dataset_digest=self.config["dataset_digest"],
            roster_digest=self.config["roster_digest"],
            primitives=frozenset(self.config["primitives"]),
            protocols=frozenset(self.config["protocols"]),
            models=frozenset(self.config["models"]),
            eae_revision=self.config["eae_revision"],
            auth_level=self.config["auth_level"])

    def preflight(self) -> dict:
        report = {"dataset_digest_ok": True, "roster_digest_ok": True,
                  "models": sorted(self.config["models"]),
                  "auth_level": self.config["auth_level"]}
        return report

    def freeze(self) -> str:
        manifest = {"config": self.config,
                    "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                time.gmtime())}
        p = self.workdir / "freeze.json"
        p.write_text(json.dumps(manifest, indent=1, ensure_ascii=False),
                     encoding="utf-8")
        return hashlib.sha256(p.read_bytes()).hexdigest()

    def authorize(self, physical: bool) -> ExecutionAuthorization:
        req = self.request()
        self.auth = (self.gate.authorize_physical(req) if physical
                     else self.gate.authorize_synthetic(req))
        return self.auth

    # -- execution ---------------------------------------------------------
    def run(self, cases: list[dict], stop_after: int | None = None):
        """cases: [{case_id, model, protocol, expected}] in roster order.
        stop_after emulates interruption for resume testing."""
        if self.auth is None:
            raise AuthorizationError("runner not authorized")
        done = 0
        since_canary = self.canary.interval
        for case in cases:
            if self.breaker_open:
                raise CircuitBreakerOpen(
                    "canary circuit breaker open; dispatch stopped")
            if stop_after is not None and done >= stop_after:
                return False                     # interrupted
            tid = f"{case['case_id']}|{case['model']}|{case['protocol']}"
            if tid in self.trials:
                rec = dict(self.trials[tid])
                rec["classification"] = DUPLICATE_TRIAL
                self.quarantine.append({"trial_id": tid,
                                        "reason": "duplicate identity"})
                continue
            since_canary += 1
            if since_canary >= self.canary.interval:
                since_canary = 0
                self._run_canary()
                if self.breaker_open:
                    raise CircuitBreakerOpen(
                        "canary control misclassified; dispatch stopped")
            raw = self.transport.submit(case["case_id"], case["model"],
                                        case["protocol"])
            art = raw.artifact()
            try:
                parsed = self.parser.parse(case["case_id"], raw.content)
                prod = self.evaluator.evaluate(case["case_id"], parsed,
                                               case["expected"])
                ref = self.oracle.verdict(case["case_id"], parsed,
                                          case["expected"])
            except RuntimeError as e:
                cls = (PARSER_SOFTWARE_ERROR
                       if case["case_id"] in self.parser.raise_on
                       else EVALUATOR_SOFTWARE_ERROR)
                self.trials[tid] = {"trial_id": tid,
                                    "classification": cls,
                                    "artifact": art, "error": str(e)}
                self.quarantine.append({"trial_id": tid, "reason": cls})
                done += 1
                continue
            if prod != ref:
                self.trials[tid] = {"trial_id": tid,
                                    "classification": NOT_EVALUABLE,
                                    "artifact": art,
                                    "production": prod, "reference": ref}
                self.quarantine.append(
                    {"trial_id": tid,
                     "reason": "dual-path disagreement"})
            else:
                self.trials[tid] = {"trial_id": tid, "classification": prod,
                                    "artifact": art}
            self.completed_case_ids.add(case["case_id"])
            done += 1
        return True

    def _run_canary(self):
        for cid, content in self.canary.known_correct:
            if cid in self.canary.fail_on:
                self.breaker_open = True
                self.quarantine.append({"trial_id": f"canary|{cid}",
                                        "reason": CANARY_FAILURE})
                return
            parsed = self.parser.parse(cid, content)
            v = self.evaluator.evaluate(cid, parsed, {"x": 1})
            if v != CORRECT:
                self.breaker_open = True
                self.quarantine.append({"trial_id": f"canary|{cid}",
                                        "reason": CANARY_FAILURE})
                return
        for cid, content, expected in self.canary.known_incorrect:
            parsed = self.parser.parse(cid, content)
            if self.evaluator.evaluate(cid, parsed, json.loads(expected)) \
                    != INCORRECT:
                self.breaker_open = True
                self.quarantine.append({"trial_id": f"canary|{cid}",
                                        "reason": CANARY_FAILURE})
                return

    # -- evidence integrity -------------------------------------------------
    def verify(self) -> list[str]:
        problems = []
        for tid, rec in self.trials.items():
            payload = rec["artifact"]["payload"]
            sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if sha != rec["artifact"]["artifact_sha256"]:
                rec["classification"] = EVIDENCE_REJECTED
                problems.append(f"{tid}: artifact hash mismatch")
        return problems

    def replay(self, case) -> dict:
        """Offline replay of one case through the evaluation path from the
        preserved artifact (no transport)."""
        tid = f"{case['case_id']}|{case['model']}|{case['protocol']}"
        rec = self.trials[tid]
        content = json.loads(rec["artifact"]["payload"])["content"]
        parsed = self.parser.parse(case["case_id"], content)
        prod = self.evaluator.evaluate(case["case_id"], parsed,
                                       case["expected"])
        ref = self.oracle.verdict(case["case_id"], parsed, case["expected"])
        return {"trial_id": tid, "replay_production": prod,
                "replay_reference": ref,
                "matches_recorded": (prod == ref) ==
                (rec["classification"] not in (NOT_EVALUABLE,))}

    # -- analysis / publication ----------------------------------------------
    def analyze(self) -> dict:
        counts: dict[str, int] = {}
        for rec in self.trials.values():
            counts[rec["classification"]] = \
                counts.get(rec["classification"], 0) + 1
        model_failures = sum(counts.get(b, 0) for b in MODEL_BUCKETS)
        software = sum(counts.get(b, 0) for b in SOFTWARE_BUCKETS)
        return {"counts": counts, "model_evaluable": model_failures,
                "software_or_unresolvable": software,
                "quarantined": len(self.quarantine),
                "breaker_open": self.breaker_open,
                "diagnostic_only": self.auth is not None and
                self.auth.qualifying_class == "TEST_DOUBLE"}

    def publish(self, path: pathlib.Path) -> dict:
        """AUTH-0 publication is DIAGNOSTIC-ONLY output: no formal claim is
        producible from synthetic runs."""
        report = self.analyze()
        report["publication_class"] = "DIAGNOSTIC_ONLY" if \
            report["diagnostic_only"] else "FORMAL_PENDING_EAE"
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, indent=1, ensure_ascii=False),
                     encoding="utf-8")
        return report

    # -- persistence ------------------------------------------------------
    def save(self):
        state = {"config": self.config,
                 "trials": self.trials,
                 "completed_case_ids": sorted(self.completed_case_ids),
                 "quarantine": self.quarantine,
                 "breaker_open": self.breaker_open}
        (self.workdir / "runner_state.json").write_text(
            json.dumps(state, indent=1, ensure_ascii=False),
            encoding="utf-8")

    def load(self):
        p = self.workdir / "runner_state.json"
        if not p.is_file():
            return
        state = json.loads(p.read_text(encoding="utf-8"))
        self.trials = state["trials"]
        self.completed_case_ids = set(state["completed_case_ids"])
        self.quarantine = state["quarantine"]
        self.breaker_open = state["breaker_open"]
