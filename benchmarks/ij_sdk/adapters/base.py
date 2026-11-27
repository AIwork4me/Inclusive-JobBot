"""IJ-SDK-1.1 P4A (D04 / D05 / D07): unified adapter contract.

Every SDK arm implements this interface. The unified layer standardizes task
inputs, tool schemas, tool execution, logging, evaluation and resource budgets.
It must NOT silently supply correct plans, correct tool names, correct tool
arguments, missing identifiers, hidden task solutions, oracle verdicts or
automatic business decisions - the adapter records what the SDK/model produced,
verbatim, including failures.

Adapters must retain the original framework's meaningful orchestration
behaviour: never replace an SDK's execution loop with a generic custom loop and
report that the SDK passed.

Session hygiene (D04) - each is a regression test in tests/ij_sdk/test_adapter_reset.py:

  * ``reset_session`` discards EVERYTHING per-trial: usage, call counters,
    tokens, retries, history, final answer, error state, fault counters, tool
    registrations and the business world behind the gateway.
  * Each trial runs under an epoch. If the session is reset while a trial is
    still running, that trial aborts instead of leaking into the next one.
  * Usage is handed out as a copy. A returned record never changes afterwards.

Budget (D05): the trial's BudgetController is the only accounting authority.
The adapter obtains a permit before every model call and closes it after, with
the usage the server reported - or with nothing, in which case the controller
charges the reservation.
"""

from __future__ import annotations

import copy
import dataclasses
import inspect
import json
import threading
from dataclasses import dataclass, field
from typing import Any

from benchmarks.ij_sdk.budget import Budget, BudgetController, BudgetExhausted
from benchmarks.ij_sdk.contracts.events import EventLog, STAGES


class AdapterError(RuntimeError):
    """A transport or protocol failure. Subclasses say which kind."""

    stop_reason = "adapter_error"


class TransportTimeout(AdapterError):
    stop_reason = "transport_timeout"


class TransportHttpError(AdapterError):
    stop_reason = "http_error"

    def __init__(self, code: int, body: str):
        super().__init__(f"server returned HTTP {code}: {body[:300]!r}")
        self.code = code


class TransportUnreachable(AdapterError):
    stop_reason = "server_unreachable"


class MalformedResponse(AdapterError):
    stop_reason = "malformed_response"


@dataclass
class ToolManifest:
    """Tool schemas offered to the model/SDK plus the gateway that executes them."""

    tools: list[dict]
    handler: Any                 # callable(name, args) -> dict (the shared gateway)
    gateway_decides: bool = True

    def reset(self, world_id: str | None = None, spec: dict | None = None) -> None:
        """Give the gateway a fresh business world if it manages one. A gateway that knows world
        specifications receives ``spec``; a plain handler receives only the world id."""
        reset = getattr(self.handler, "reset_session", None)
        if not callable(reset):
            return
        if "spec" in inspect.signature(reset).parameters:
            reset(world_id, spec)
        else:
            reset(world_id)


@dataclass
class Task:
    task_id: str
    prompt: str
    system: str | None = None
    tools: ToolManifest | None = None
    budget: Budget = field(default_factory=Budget)
    world_id: str | None = None
    world_spec: dict | None = None      # frozen world specification this trial runs on


@dataclass
class Usage:
    """Per-trial accounting snapshot. ``model_calls`` and ``tool_calls`` count attempts."""
    model_calls: int = 0
    model_calls_completed: int = 0
    model_calls_failed: int = 0
    model_calls_timed_out: int = 0
    tool_calls: int = 0
    tool_calls_completed: int = 0
    tool_calls_failed: int = 0
    tool_calls_timed_out: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    completion_tokens_unreported: int = 0
    retries: int = 0
    wall_seconds: float = 0.0

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> "Usage":
        return cls(model_calls=snapshot["model_calls"], model_calls_completed=snapshot["model_calls_completed"],
                   model_calls_failed=snapshot["model_calls_failed"],
                   model_calls_timed_out=snapshot["model_calls_timed_out"],
                   tool_calls=snapshot["tool_calls"], tool_calls_completed=snapshot["tool_calls_completed"],
                   tool_calls_failed=snapshot["tool_calls_failed"], tool_calls_timed_out=snapshot["tool_calls_timed_out"],
                   prompt_tokens=snapshot["prompt_tokens"], completion_tokens=snapshot["completion_tokens"],
                   completion_tokens_unreported=snapshot["completion_tokens_unreported"], retries=snapshot["retries"],
                   wall_seconds=snapshot["wall_seconds"])


class _Trial:
    """Everything that belongs to one trial. Replaced wholesale by reset_session."""

    def __init__(self, world_id: str | None, budget: Budget):
        self.world_id = world_id
        self.budget = BudgetController(budget)
        self.history: list[dict[str, Any]] = []
        self.final_answer: str | None = None
        self.finish_reason: str | None = None
        self.truncated = False
        self.error: AdapterError | None = None
        self.faults: dict[str, int] = {}
        self.events_by_stage: dict[str, int] = {}
        self.tool_results: list[dict[str, Any]] = []

    def note_fault(self, kind: str) -> None:
        self.faults[kind] = self.faults.get(kind, 0) + 1

    def note_stage(self, stage: str) -> None:
        self.events_by_stage[stage] = self.events_by_stage.get(stage, 0) + 1


class AgentAdapter:
    """Common interface: lifecycle, session hygiene, budget, evidence emission."""

    name = "abstract"

    def __init__(self, run_id: str, events: EventLog):
        self.run_id = run_id
        self.events = events
        self._epoch = 0
        self._manifest: ToolManifest | None = None
        self._manifest_used = False                     # the registered manifest served a trial already
        self._trial: _Trial | None = None
        self._trial_id: str = ""
        self._task_event_id: str | None = None
        self._leaks: list[dict[str, Any]] = []           # cross-trial leaks that were caught
        self.error_detail_level = "detail"               # "code" (M0) or "detail" (M1)

    # -- lifecycle ----------------------------------------------------------
    def initialize(self, model: str, runtime: dict[str, Any], configuration: dict[str, Any]) -> None:
        raise NotImplementedError

    def reset_session(self, world_id: str | None = None, *, spec: dict | None = None) -> None:
        """Complete per-trial reset between tasks. Nothing of the previous trial survives:
        usage, counters, tokens, retries, history, final answer, error state, fault counters,
        tool registrations and the business world behind the gateway."""
        self._begin_trial(world_id, spec)
        self._manifest = None                            # task-specific tool registrations are gone

    def _begin_trial(self, world_id: str | None, spec: dict | None) -> None:
        """Start a new epoch. Any trial still running under the old epoch must abort."""
        self._epoch += 1
        if self._manifest is not None:                   # fresh business world behind the gateway
            self._manifest.reset(world_id, spec)
        self._trial = None                               # usage, counters, tokens, retries, history, answer, errors
        self._trial_id = ""
        self._task_event_id = None

    def register_tools(self, manifest: ToolManifest) -> None:
        """Register the tools of the trial that runs next (``Task.tools`` does this too)."""
        self._manifest = manifest
        self._manifest_used = False

    # -- the template every arm runs through --------------------------------
    def run_task(self, task: Task) -> dict[str, Any]:
        """Execute one task and return

            {"trial_id", "status": PASS|FAIL|BLOCKED, "final_answer", "usage": Usage,
             "detail", "budget", "action_log", "submitted_facts", "initial_state",
             "final_state", "final_state_hash", "leaks"}

        The status reflects EXECUTION completion only. Evidence validity, business
        success, safety compliance and capability qualification are separate and
        are decided by the independent evaluator.

        Tools come from ``task.tools`` or from a ``register_tools`` call made for this trial.
        A manifest that already served a trial is never reused: tools do not outlive their trial.
        """
        if task.tools is not None:
            self.register_tools(task.tools)
        elif self._manifest_used:
            self._manifest = None
        self._begin_trial(task.world_id, task.world_spec)
        epoch = self._epoch
        trial = self._trial = _Trial(task.world_id, task.budget)
        self._trial_id = task.task_id
        gateway = self._manifest.handler if self._manifest is not None else None
        if gateway is not None and hasattr(gateway, "bind_budget"):
            gateway.bind_budget(trial.budget)
        if gateway is not None and hasattr(gateway, "bind_events"):
            gateway.bind_events(self._gateway_sink, self.run_id, task.task_id)
        initial: dict | None = None
        status, detail = "NOT_RUN", {}
        try:
            self._task_event_id = self.emit("task_input", {
                "prompt": task.prompt, "system": task.system, "world_id": task.world_id,
                "budget": dataclasses.asdict(trial.budget.budget), "adapter": self.name,
                "error_detail_level": self.error_detail_level}, parent_id=None)
            world = getattr(gateway, "world", None)
            if world is not None:
                initial = copy.deepcopy(world.snapshot())
                self.emit("business_state", {"phase": "initial", "snapshot": initial, "digest": world.digest()},
                          parent_id=self._task_event_id)
            self._declare_arm_stages()
            status, detail = self._execute(task, epoch)
        except BudgetExhausted as exhausted:
            status, detail = "FAIL", {"stop_reason": f"budget:{exhausted.reason}", "budget": exhausted.snapshot}
        except AdapterError as exc:
            trial.error = exc
            status, detail = "FAIL", {"stop_reason": exc.stop_reason, "error": str(exc)[:500]}
        except Exception as exc:                           # a crash is a recorded failure, never a silent pass
            status, detail = "FAIL", {"stop_reason": "adapter_crash", "error": f"{type(exc).__name__}: {exc}"[:500]}
        if epoch != self._epoch:                           # the session was reset under a running trial
            self._leaks.append({"trial_id": task.task_id, "kind": "session_reset_during_trial"})
            return {"trial_id": task.task_id, "status": "BLOCKED", "final_answer": None, "usage": Usage(),
                    "detail": {"stop_reason": "session_reset_during_trial"},
                    "evidence": {"status": "INVALID", "problems": ["session was reset while the trial was running"]},
                    "leaks": list(self._leaks)}
        snapshot = trial.budget.finalize()
        world = getattr(gateway, "world", None)
        final_state = copy.deepcopy(world.snapshot()) if world is not None else None
        result = {
            "trial_id": task.task_id,
            "status": status,
            "final_answer": trial.final_answer,
            "usage": Usage.from_snapshot(snapshot),      # a copy: it never changes afterwards
            "detail": {**detail, "truncated": trial.truncated, "finish_reason": trial.finish_reason,
                       "faults": dict(trial.faults), "events_by_stage": dict(trial.events_by_stage)},
            "budget": snapshot,
            "action_log": copy.deepcopy(getattr(gateway, "audit", None) or []),
            "submitted_facts": copy.deepcopy(getattr(gateway, "submitted_results", None) or []),
            "initial_state": initial,
            "final_state": final_state,
            "final_state_hash": world.digest() if world is not None else None,
            "tool_results": copy.deepcopy(trial.tool_results),
            "leaks": list(self._leaks),
        }
        # the trial is closed: its event route is shut and its tools will not serve another trial
        self._manifest_used = True
        self._trial_id = ""
        return result

    def _execute(self, task: Task, epoch: int) -> tuple[str, dict[str, Any]]:
        raise NotImplementedError

    def _declare_arm_stages(self) -> None:
        """Each arm states which stages it cannot observe (``declare_not_captured``).
        Overridden per arm; the default claims nothing."""

    # -- helpers every arm shares -------------------------------------------
    @property
    def trial(self) -> _Trial:
        if self._trial is None:
            raise AdapterError("no trial is running")
        return self._trial

    @property
    def budget(self) -> BudgetController:
        return self.trial.budget

    def current(self, epoch: int) -> bool:
        """False once the session has been reset - the running trial must then abort."""
        return epoch == self._epoch

    def emit(self, stage: str, payload: dict[str, Any], *, parent_id: str | None = None,
             call_id: str | None = None) -> str | None:
        """Write one evidence row and return its event id."""
        self.trial.note_stage(stage)
        self.events.emit(self.run_id, self._trial_id, stage, payload, parent_id=parent_id, call_id=call_id)
        return self.events.last_event_id

    def declare_not_captured(self, stage: str, reason: str, *, parent_id: str | None = None,
                             call_id: str | None = None) -> str | None:
        """State explicitly that a stage could not be observed, and why."""
        self.trial.note_stage(stage)
        self.events.not_captured(self.run_id, self._trial_id, stage, reason, parent_id=parent_id, call_id=call_id)
        return self.events.last_event_id

    def _gateway_sink(self, stage: str, payload: dict[str, Any], *, parent_id: str | None, call_id: str | None,
                      run_id: str | None, trial_id: str | None) -> None:
        """Receive the gateway's own evidence rows. An event for another trial is a leak."""
        if self._trial is None or trial_id != self._trial_id:
            self._leaks.append({"trial_id": trial_id, "kind": "gateway_event_for_other_trial", "stage": stage})
            return
        if stage == "tool_gateway" and payload.get("fault_inapplicable"):
            self.trial.note_fault(str(payload["fault_inapplicable"]))
        if stage == "tool_result" and payload.get("fault"):
            self.trial.note_fault(str(payload["fault"]))
        self.emit(stage, payload, parent_id=parent_id, call_id=call_id)

    GATEWAY_KEYWORDS = ("idempotency_key", "call_id", "parent_event_id", "deadline_seconds")

    @staticmethod
    def _accepts_gateway_keywords(handler) -> bool:
        """True for a gateway (it takes the correlation and deadline keyword arguments), False
        for a plain callable(name, args)."""
        try:
            return set(AgentAdapter.GATEWAY_KEYWORDS) <= set(inspect.signature(handler).parameters)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _call_plain(handler, name: str, args: Any, timeout_seconds: float, call_id: str | None) -> dict[str, Any]:
        """Run a plain handler under the tool deadline. Such a handler manages its own state, so
        the adapter can bound its wait but cannot roll back what it did."""
        box: dict[str, Any] = {}

        def target() -> None:
            try:
                box["envelope"] = handler(name, args)
            except Exception as exc:
                box["error"] = exc

        worker = threading.Thread(target=target, name="ij-tool-plain", daemon=True)
        worker.start()
        worker.join(max(0.0, timeout_seconds))
        envelope: dict[str, Any] = {"name": name, "call_id": call_id, "decision": "allow", "result": None,
                                    "error": None, "detail": None}
        if worker.is_alive():
            return {**envelope, "error": "tool_timeout", "detail": "tool exceeded its deadline"}
        if "error" in box:
            return {**envelope, "error": "handler_error", "detail": f"{type(box['error']).__name__}: {box['error']}"[:300]}
        returned = box.get("envelope")
        if not isinstance(returned, dict):
            return {**envelope, "error": "handler_error", "detail": "handler returned no result envelope"}
        return {**envelope, **returned}

    def dispatch_tool(self, name: str, args: Any, *, tool_call_id: str | None, parent_event_id: str | None,
                      idempotency_key: str | None = None) -> tuple[str, dict[str, Any]]:
        """Send one model-proposed tool call through the gateway and return the model-visible
        content plus the envelope. The gateway decides; the adapter only relays.

        The adapter holds the tool-call permit: it counts the attempt before anything runs and
        hands the remaining tool time to the handler, so a call is counted once and can never
        outlive its deadline."""
        if self._manifest is None or self._manifest.handler is None:
            raise AdapterError("no tool handler registered")
        handler = self._manifest.handler
        permit = self.budget.begin_tool_call()            # counted here, by the one authority
        try:
            if self._accepts_gateway_keywords(handler):
                envelope = handler(name, args, idempotency_key=idempotency_key, call_id=tool_call_id,
                                   parent_event_id=parent_event_id, deadline_seconds=permit.timeout_seconds)
            else:
                envelope = self._call_plain(handler, name, args, permit.timeout_seconds, tool_call_id)
        except (AdapterError, BudgetExhausted):
            self.budget.end_tool_call(permit, error="aborted")
            raise
        except Exception as exc:                          # never let a handler crash the loop silently
            self.budget.end_tool_call(permit, error="handler_exception")
            envelope = {"name": name, "call_id": tool_call_id, "decision": "allow", "result": None,
                        "error": "handler_error", "detail": f"{type(exc).__name__}: {exc}"[:300]}
        else:
            self.budget.end_tool_call(permit, timed_out=envelope.get("error") == "tool_timeout",
                                      error=envelope.get("error"))
        self.trial.tool_results.append(copy.deepcopy(envelope))
        if envelope.get("error") is not None:
            content = {"error": envelope["error"]}
            if self.error_detail_level == "detail" and envelope.get("detail"):
                content["detail"] = envelope["detail"]
        else:
            content = {"result": envelope.get("result")}
        return json.dumps(content, ensure_ascii=False), envelope

    # -- introspection ------------------------------------------------------
    def export_trace(self) -> dict[str, Any]:
        trial = self._trial
        return {"adapter": self.name, "history": copy.deepcopy(trial.history) if trial else [],
                "final_answer": trial.final_answer if trial else None}

    def export_usage(self) -> Usage:
        """A copy of the current trial's usage (zeros when no trial has run)."""
        if self._trial is None:
            return Usage()
        return Usage.from_snapshot(self._trial.budget.snapshot())

    def checkpoint(self) -> dict[str, Any]:
        return {"epoch": self._epoch, "trial_id": self._trial_id, "usage": dataclasses.asdict(self.export_usage()),
                "final_answer": self._trial.final_answer if self._trial else None}

    def close(self) -> None:
        pass
