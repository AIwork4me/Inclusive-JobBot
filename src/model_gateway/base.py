"""Model-neutral gateway types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Proposal:
    call_id: str
    name: str
    arguments_raw: str


@dataclass(frozen=True, slots=True)
class Completion:
    calls: tuple[Proposal, ...]
    content: str
    reasoning: str
    finish_reason: str


class ModelBackend(Protocol):
    def complete(self, request: dict) -> Completion: ...
