"""Summarize real tool attempts and transactional outcomes from the audit trail."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ExecutionMetrics:
    proposals: int
    tool_attempts: int
    retries: int
    first_pass_failures: int
    business_commits: int
    replays: int
    cumulative_latency_ms: Decimal

    @classmethod
    def from_audit(cls, events: Iterable[Mapping]) -> "ExecutionMetrics":
        proposals = attempts = retries = first_pass_failures = commits = replays = 0
        latency = Decimal(0)
        for event in events:
            proposals += 1
            count = event["attempts"]
            attempts += count
            retries += max(count - 1, 0)
            first_pass_failures += count > 1 or event["error_code"] is not None
            commits += event["status"] == "COMMITTED"
            replays += event["status"] == "REPLAYED"
            latency += Decimal(str(event["elapsed_ms"]))
        return cls(proposals, attempts, retries, first_pass_failures, commits, replays, latency)
