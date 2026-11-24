"""Deterministic execution of versioned workflow dependency graphs."""

from collections.abc import Callable
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from typing import Any


@dataclass(frozen=True)
class Step:
    name: str
    depends_on: tuple[str, ...]
    operation: str


class Workflow:
    def __init__(self, steps: tuple[Step, ...]):
        by_name = {step.name: step for step in steps}
        if not steps or len(by_name) != len(steps):
            raise ValueError("Workflow steps must have distinct names")
        if any(set(step.depends_on) - by_name.keys() for step in steps):
            raise ValueError("Workflow references an unknown dependency")
        try:
            order = tuple(TopologicalSorter({step.name: step.depends_on for step in steps}).static_order())
        except CycleError as exc:
            raise ValueError("Workflow contains a dependency cycle") from exc
        self.steps = tuple(by_name[name] for name in order)

    def execute(self, inputs: dict, operations: dict[str, Callable[..., Any]]) -> dict:
        missing = {step.operation for step in self.steps} - operations.keys()
        if missing:
            raise ValueError(f"Missing workflow operations {sorted(missing)}")
        results = {}
        for step in self.steps:
            parents = {name: results[name] for name in step.depends_on}
            results[step.name] = operations[step.operation](inputs, parents)
        return results
