"""Independent, deny-by-default tool, actor, resource and workflow permissions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Supplied by the trusted session and workflow, outside model arguments."""

    actor: str
    role: str
    session_id: str
    workflow_state: str
    operation_id: str | None = None


@dataclass(frozen=True, slots=True)
class Grant:
    actor: str
    role: str
    tool: str
    resources: frozenset[str]
    workflow_states: frozenset[str]
    write: bool = False


@dataclass(frozen=True, slots=True)
class Policy:
    grants: tuple[Grant, ...]

    def allows(self, context: ExecutionContext, tool: str, resource: str, *, write: bool) -> bool:
        return any(
            grant.actor == context.actor and grant.role == context.role and grant.tool == tool
            and grant.write == write and resource in grant.resources
            and context.workflow_state in grant.workflow_states
            for grant in self.grants
        )
