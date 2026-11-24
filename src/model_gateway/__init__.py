"""Strict model proposal decoding and validated business execution."""

from .authorization import ExecutionContext, Grant, Policy
from .base import Completion, ModelBackend, Proposal
from .errors import ErrorCode, GatewayError
from .execution_policy import Gateway
from .openai_protocol import decode_completion
from .streaming import StreamAssembler
from .tool_validation import ToolSpec

__all__ = [
    "Completion", "ErrorCode", "ExecutionContext", "Gateway", "GatewayError",
    "Grant", "ModelBackend", "Policy", "Proposal", "StreamAssembler", "ToolSpec",
    "decode_completion",
]
