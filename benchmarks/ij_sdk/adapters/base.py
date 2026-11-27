"""IJ-SDK-1.0 P4: unified adapter contract (mission 7.1).

Every SDK arm implements this interface. The unified layer standardizes task
inputs, tool schemas, tool execution environment, logging, evaluation and
resource budgets. It must NOT silently supply correct plans, correct tool
names, correct tool arguments, missing identifiers, hidden task solutions,
oracle verdicts or automatic business decisions - the adapter records what
the SDK/model produced, verbatim, including failures.

Adapters must retain the original framework's meaningful orchestration
behavior (mission 7.1): never replace an SDK's execution loop with a generic
custom loop and report that the SDK passed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from benchmarks.ij_sdk.contracts.events import EventLog


@dataclass
class ToolManifest:
    """Tool schemas offered to the model/SDK (unified across arms)."""

    tools: list[dict[str, Any]]
    handler: Any                 # callable(name, args_dict) -> dict (the shared gateway)
    gateway_decides: bool = True  # the gateway, not the adapter, permits actions


@dataclass
class Budget:
    max_model_calls: int = 16
    max_tool_calls: int = 32
    max_generated_tokens: int = 8192
    max_wall_seconds: float = 180.0
    corrective_retries: int = 0   # M0: 0; M1: <=2 (frozen per profile)


@dataclass
class Task:
    task_id: str
    prompt: str
    system: str | None = None
    tools: ToolManifest | None = None
    budget: Budget = field(default_factory=Budget)
    world_id: str | None = None


@dataclass
class Usage:
    model_calls: int = 0
    tool_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    retries: int = 0
    wall_seconds: float = 0.0


class AdapterError(RuntimeError):
    pass


class AgentAdapter:
    """Common interface with mission-7.1 semantics."""

    name = "abstract"

    def __init__(self, run_id: str, events: EventLog):
        self.run_id = run_id
        self.events = events
        self._usage = Usage()

    # -- lifecycle ----------------------------------------------------------

    def initialize(self, model: str, runtime: dict[str, Any], configuration: dict[str, Any]) -> None:
        raise NotImplementedError

    def reset_session(self, world_id: str | None) -> None:
        raise NotImplementedError

    def register_tools(self, manifest: ToolManifest) -> None:
        raise NotImplementedError

    def run_task(self, task: Task) -> dict[str, Any]:
        """Execute one task. Returns {"final_answer": str, "usage": Usage,
        "status": PASS|FAIL|BLOCKED|NOT_RUN, "detail": {...}}.

        The status reflects EXECUTION completion only. Evidence validity,
        business success, safety compliance and capability qualification are
        separate fields determined by the independent evaluator.
        """
        raise NotImplementedError

    def export_trace(self) -> dict[str, Any]:
        raise NotImplementedError

    def export_usage(self) -> Usage:
        return self._usage

    def checkpoint(self) -> dict[str, Any]:
        raise NotImplementedError

    def close(self) -> None:
        pass

    # -- shared accounting helpers ------------------------------------------

    def charge_model_call(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        self._usage.model_calls += 1
        self._usage.prompt_tokens += prompt_tokens
        self._usage.completion_tokens += completion_tokens

    def charge_tool_call(self) -> None:
        self._usage.tool_calls += 1

    def charge_retry(self) -> None:
        self._usage.retries += 1
