"""Backend capability claims used to gate experiment configurations."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    tool_calls: bool
    streaming: bool
    reasoning_separation: bool
    native_cancellation: bool
