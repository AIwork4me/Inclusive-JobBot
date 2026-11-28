"""IJ-SDK-1.1 P4A: arm B0 - raw llama.cpp reference loop.

The minimal autonomous loop over the pinned llama-server Chat Completions API.
It measures the model/runtime baseline without any SDK: the harness itself
provides nothing beyond transport, the shared gateway, the budget and evidence
logging. No task-specific hints, no hidden planner, and no retry the budget
does not grant.

What B0 can and cannot observe - declared in the evidence, never implied (D07):

    captured        server_request          the exact JSON body sent
                    server_response_raw     digest and size of the response bytes
                    server_response_decoded the parsed response
                    parser_output           the tool calls as the server reported them
    not captured    sdk_request, sdk_model_adapter   (there is no SDK)
                    chat_template                   (rendered inside the server)
                    model_generation                (Chat Completions returns text, not token ids)

Every model call takes a permit first and closes it afterwards. A call that
times out, returns an HTTP error or returns garbage is charged its reservation
and ends the trial with a recorded stop reason - it never escapes as an
uncaught exception and never looks free.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import urllib.error
import urllib.request
from typing import Any

from benchmarks.ij_sdk.adapters.base import (AdapterError, AgentAdapter, BudgetExhausted, MalformedResponse,
                                             Task, TransportHttpError, TransportTimeout, TransportUnreachable)
from benchmarks.ij_sdk.contracts.events import NOT_CAPTURED

DEFAULT_BASE_URL = "http://127.0.0.1:8080"


class B0RawAdapter(AgentAdapter):
    name = "b0-raw-llamacpp"

    def __init__(self, run_id: str, events):
        super().__init__(run_id, events)
        self._base_url = DEFAULT_BASE_URL
        self._model = "minicpm5-2b"
        self._sampling: dict[str, Any] = {}
        self._thinking = False
        self.request_max_tokens: int | None = None     # None: the budget's per-request cap

    # -- lifecycle ----------------------------------------------------------
    def initialize(self, model: str, runtime: dict[str, Any], configuration: dict[str, Any]) -> None:
        self._model = model
        self._base_url = runtime.get("base_url", DEFAULT_BASE_URL)
        self._sampling = configuration.get("sampling", {"temperature": 0.0, "top_p": 1.0})
        self._thinking = bool(configuration.get("enable_thinking", False))
        self.error_detail_level = configuration.get("error_detail_level", "detail")
        self.request_max_tokens = configuration.get("request_max_tokens")

    def _declare_arm_stages(self) -> None:
        self.declare_not_captured("sdk_request", "no SDK: the runner talks to the adapter directly",
                                  parent_id=self._task_event_id)
        self.declare_not_captured("sdk_model_adapter", "no SDK model client in this arm",
                                  parent_id=self._task_event_id)

    # -- execution ----------------------------------------------------------
    def _execute(self, task: Task, epoch: int) -> tuple[str, dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if task.system:
            messages.append({"role": "system", "content": task.system})
        messages.append({"role": "user", "content": task.prompt})
        self.trial.history = messages
        parent = self._task_event_id
        prompt_lower_bound = 0
        while True:
            if not self.current(epoch):
                return "BLOCKED", {"stop_reason": "session_reset_during_trial"}
            try:
                permit = self.budget.begin_model_call(self.request_max_tokens, prompt_lower_bound)
            except BudgetExhausted as exhausted:
                return "FAIL", {"stop_reason": f"budget:{exhausted.reason}", "budget": exhausted.snapshot}

            body = self._request_body(messages, permit.max_tokens)
            request_id = self.emit("server_request", {
                "attempt": permit.call_index, "max_tokens": permit.max_tokens,
                "remaining": permit.remaining_at_issue, "timeout_seconds": round(permit.timeout_seconds, 6),
                "transport": "chat_completions", "stream": False, "body": body}, parent_id=parent)
            self.declare_not_captured("chat_template", "rendered inside the server; not returned by Chat Completions",
                                      parent_id=request_id)
            try:
                raw = self._post(body, permit.timeout_seconds)
            except AdapterError as exc:
                self.budget.end_model_call(permit, timed_out=isinstance(exc, TransportTimeout), error=exc.stop_reason)
                self.emit("server_response_decoded", {"status": "error", "error": exc.stop_reason,
                                                      "detail": str(exc)[:300], "server_usage": None,
                                                      "charged_tokens": permit.max_tokens}, parent_id=request_id)
                raise

            response, problem = self._decode(raw)
            if problem is not None:
                self.budget.end_model_call(permit, error="malformed_response")
                self.emit("server_response_decoded", {"status": "error", "error": "malformed_response",
                                                      "detail": problem, "raw_sha256": hashlib.sha256(raw).hexdigest(),
                                                      "charged_tokens": permit.max_tokens}, parent_id=request_id)
                raise MalformedResponse(problem)
            usage = response.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens") if isinstance(usage.get("prompt_tokens"), int) else None
            completion_tokens = usage.get("completion_tokens") if isinstance(usage.get("completion_tokens"), int) else None
            finish_reason = response["choices"][0].get("finish_reason")
            self.budget.end_model_call(permit, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                                       finish_reason=finish_reason)
            if prompt_tokens is not None:
                prompt_lower_bound = prompt_tokens       # the context only grows: a lower bound for the next call
            self.emit("server_response_raw", {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                                              "transport": "non-streaming"}, parent_id=request_id)
            response_id = self.emit("server_response_decoded", {"status": "ok", "body": response}, parent_id=request_id)
            self.declare_not_captured("model_generation", "Chat Completions returns decoded text, not token ids",
                                      parent_id=response_id)
            self.emit("usage", {"server_usage": usage, "trial": self.budget.snapshot()}, parent_id=response_id)

            message = response["choices"][0]["message"]
            calls = message.get("tool_calls") or []
            if not calls:
                content = message.get("content")
                if not isinstance(content, str):
                    raise MalformedResponse("final message has no string content")
                self.trial.final_answer = content
                self.trial.finish_reason = finish_reason
                self.trial.truncated = finish_reason == "length"
                final_id = self.emit("final_answer", {"final_answer": content, "finish_reason": finish_reason,
                                                      "truncated": self.trial.truncated, "status": "PASS"},
                                     parent_id=response_id)
                return "PASS", {"stop_reason": "final_answer", "truncated": self.trial.truncated,
                                "final_event_id": final_id}

            parser_id = self.emit("parser_output", {
                "tool_calls": [{"id": call.get("id"), "name": (call.get("function") or {}).get("name"),
                                "arguments": (call.get("function") or {}).get("arguments")} for call in calls],
                "source": "llama-server chat.completions tool_calls"}, parent_id=response_id)
            self.trial.history.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
            for call in calls:
                if not self.current(epoch):
                    return "BLOCKED", {"stop_reason": "session_reset_during_trial"}
                function = call.get("function") or {}
                name, call_id = function.get("name"), call.get("id")
                args = self._parse_arguments(function.get("arguments"))
                if args is None:
                    # unparseable arguments: error feedback is a corrective retry the budget must grant
                    if not self.budget.charge_retry("malformed_tool_arguments"):
                        return "FAIL", {"stop_reason": "budget:retries_exhausted",
                                        "reason": "malformed tool-call arguments and no corrective retry left",
                                        "tool": name, "tool_call_id": call_id}
                    content = json.dumps({"error": "invalid_arguments",
                                          "detail": "arguments are not a valid JSON object"}, ensure_ascii=False)
                else:
                    content, _envelope = self.dispatch_tool(name, args, tool_call_id=call_id, parent_event_id=parser_id,
                                                            idempotency_key=f"{self._trial_id}:{call_id}")
                self.trial.history.append({"role": "tool", "tool_call_id": call_id, "content": content})
            parent = self.events.last_event_id

    @staticmethod
    def _parse_arguments(raw: Any) -> dict | None:
        if raw is None or raw == "":
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _decode(raw: bytes) -> tuple[dict | None, str | None]:
        try:
            response = json.loads(raw)
        except ValueError:
            return None, "response body is not JSON"
        if not isinstance(response, dict) or not isinstance(response.get("choices"), list) or not response["choices"]:
            return None, "response has no choices"
        choice = response["choices"][0]
        if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
            return None, "first choice has no message"
        return response, None

    def _request_body(self, messages: list[dict[str, Any]], max_tokens: int) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,                    # the REMAINING budget, never a fixed number
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": self._thinking},
            **self._sampling,
        }
        if self._manifest is not None:
            body["tools"] = self._manifest.tools
            body["tool_choice"] = "auto"
        return body

    def _post(self, body: dict[str, Any], timeout_seconds: float) -> bytes:
        """One request. Every failure is classified; nothing escapes as a raw exception."""
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(self._base_url + "/v1/chat/completions", data=data,
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=max(0.001, timeout_seconds)) as reply:
                return reply.read()
        except urllib.error.HTTPError as exc:
            raise TransportHttpError(exc.code, exc.read().decode("utf-8", "replace")) from None
        except TimeoutError:
            raise TransportTimeout(f"server did not answer within the remaining {timeout_seconds:.3f}s") from None
        except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
            raise TransportUnreachable(f"{type(exc).__name__}: {exc}"[:300]) from None

    # -- introspection ------------------------------------------------------
    def export_trace(self) -> dict[str, Any]:
        trace = super().export_trace()
        trace["stages_not_captured"] = ["sdk_request", "sdk_model_adapter", "chat_template", "model_generation"]
        trace["not_captured_marker"] = NOT_CAPTURED
        return trace

    def checkpoint(self) -> dict[str, Any]:
        state = super().checkpoint()
        state["final_answer"] = self._trial.final_answer if self._trial else None
        return state
