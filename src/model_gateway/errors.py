"""Stable error categories crossing the model boundary."""

from enum import StrEnum


class ErrorCode(StrEnum):
    MODEL_ERROR = "MODEL_ERROR"
    PARSER_ERROR = "PARSER_ERROR"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    POLICY_DENIED = "POLICY_DENIED"
    BUSINESS_VALIDATION_ERROR = "BUSINESS_VALIDATION_ERROR"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    RECOVERY_EXHAUSTED = "RECOVERY_EXHAUSTED"


class GatewayError(ValueError):
    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code


class TransientToolError(Exception):
    """A trusted simulator handler may raise this to request bounded rollback/retry."""
