"""IJ-SDK-1.0 P4: arm B0 - raw llama.cpp reference loop.

The minimal autonomous loop over the pinned llama-server Chat Completions
API. It measures the model/runtime baseline without any SDK: the harness
itself provides nothing beyond transport, the shared gateway, budgets and
logging. No task-specific hints, no retries (M0), no hidden planner.

The loop shape follows the engine-native protocol verified in P1 (OpenAI
tool_calls round trip, greedy sampling by default, thinking disabled).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from benchmarks.ij_sdk.adapters.base import AdapterError, AgentAdapter, Budget, Task, ToolManifest
from benchmarks.ij_sdk.contracts.events import NOT_CAPTURED

DEFAULT_BASE_URL = "http://127.0.0.1:8080"


class B0RawAdapter(AgentAdapter):
    name = "b0-raw-llamacpp"

    def __init__(self, run_id: str, events):
        super().__init__(run_id, events)
        self._base_url = DEFAULT_BASE_URL
        self._model = "minicpm5-2b"
        self._manifest: ToolManifest | None = None
        self._history: list[dict[str, Any]] = []
        self._final: str = ""
        self._sampling: dict[str, Any] = {}

    # -- lifecycle ----------------------------------------------------------

    def initialize(self, model: str, runtime: dict[str, Any], configuration: dict[str, Any]) -> None:
        self._model = model
        self._base_url = runtime.get("base_url", DEFAULT_BASE_URL)
        self._sampling = configuration.get("sampling", {"temperature": 0.0, "top_p": 1.0})
        self._thinking = bool(configuration.get("enable_thinking", False))

    def reset_session(self, world_id: str | None) -> None:
        self._history = []
        self._final = ""

    def register_tools(self, manifest: ToolManifest) -> None:
        self._manifest = manifest

    # -- execution ----------------------------------------------------------

    def _chat(self, messages: list[dict[str, Any]], max_tokens: int) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": self._thinking},
            **self._sampling,
        }
        if self._manifest is not None:
            body["tools"] = self._manifest.tools
            body["tool_choice"] = "auto"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self._base_url + "/v1/chat/completions", data=data,
                                     headers={"Content-Type": "application/json"}, method="POST")
        trial = self._trial_id or ""
        self.events.emit(self.run_id, trial, "server_request", {"body": body})
        try:
            with urllib.request.urlopen(req, timeout=self._budget.max_wall_seconds) as reply:
                response = json.load(reply)
        except urllib.error.HTTPError as exc:
            raise AdapterError(f"server returned HTTP {exc.code}: {exc.read()[:400]!r}") from None
        self.events.emit(self.run_id, trial, "model_generation", {"body": response})
        usage = response.get("usage") or {}
        self.charge_model_call(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        self.events.emit(self.run_id, trial, "usage", {"usage": usage, "model_calls": self._usage.model_calls})
        return response

    def run_task(self, task: Task) -> dict[str, Any]:
        import time as _t
        started = _t.time()
        self._trial_id = task.task_id
        self._budget = task.budget
        self.events.emit(self.run_id, task.task_id, "task_input",
                         {"prompt": task.prompt, "world_id": task.world_id, "budget": vars(task.budget)})
        messages: list[dict[str, Any]] = []
        if task.system:
            messages.append({"role": "system", "content": task.system})
        messages.append({"role": "user", "content": task.prompt})
        self._history = messages

        status = "PASS"
        detail: dict[str, Any] = {}
        try:
            while True:
                if self._usage.model_calls >= task.budget.max_model_calls:
                    status = "FAIL"
                    detail["reason"] = "model_call_budget_exhausted"
                    break
                response = self._chat(self._history, 1024)
                choice = response["choices"][0]
                message = choice.get("message") or {}
                calls = message.get("tool_calls") or []
                if not calls:
                    self._final = message.get("content") or ""
                    self.events.emit(self.run_id, task.task_id, "final_answer", {"final_answer": self._final,
                                                                                 "finish_reason": choice.get("finish_reason")})
                    break
                self.events.emit(self.run_id, task.task_id, "parser_output", {"tool_calls": calls})
                self._history.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
                for call in calls:
                    if self._usage.tool_calls >= task.budget.max_tool_calls:
                        status = "FAIL"
                        detail["reason"] = "tool_call_budget_exhausted"
                        break
                    fn = call.get("function", {})
                    name = fn.get("name")
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = None
                    self.charge_tool_call()
                    self.events.emit(self.run_id, task.task_id, "tool_gateway",
                                     {"name": name, "arguments": args})
                    if self._manifest is None or args is None:
                        result = {"error": "invalid_tool_call", "detail": "unparseable arguments"}
                    else:
                        try:
                            result = self._manifest.handler(name, args)
                        except Exception as exc:  # gateway/handler failure is a recorded result, never silent
                            result = {"error": "handler_error", "detail": f"{type(exc).__name__}: {exc}"}
                    self.events.emit(self.run_id, task.task_id, "tool_result", {"name": name, "result": result})
                    self._history.append({"role": "tool", "tool_call_id": call.get("id"),
                                          "content": json.dumps(result, ensure_ascii=False)})
                if status == "FAIL":
                    break
        except AdapterError as exc:
            status = "FAIL"
            detail["reason"] = str(exc)
        self._usage.wall_seconds = _t.time() - started
        return {"final_answer": self._final, "usage": self._usage, "status": status, "detail": detail}

    def export_trace(self) -> dict[str, Any]:
        return {"adapter": self.name, "history": self._history, "final_answer": self._final}

    def checkpoint(self) -> dict[str, Any]:
        return {"usage": vars(self._usage), "final_answer": self._final}
