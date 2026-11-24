"""Decode bounded Unicode JSON and keep decimal precision."""

from __future__ import annotations

import json
from decimal import Decimal, DecimalException

from .errors import ErrorCode, GatewayError

MAX_ARGUMENT_BYTES = 16_384
MAX_DEPTH = 32


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _integer(token: str) -> int:
    if len(token) > 20:
        raise ValueError("integer out of bounds")
    value = int(token)
    if not -(2**63) <= value < 2**63:
        raise ValueError("integer out of bounds")
    return value


def _decimal(token: str) -> Decimal:
    if len(token) > 64:
        raise ValueError("decimal token out of bounds")
    value = Decimal(token)
    _, digits, exponent = value.as_tuple()
    if len(digits) > 28 or not -28 <= exponent <= 18 or value.adjusted() > 18:
        raise ValueError("decimal precision, scale or magnitude out of bounds")
    return value


def _non_finite(token: str) -> None:
    raise ValueError("non-finite JSON number")


def _check_unicode_and_depth(root: dict, limit: int) -> None:
    pending = [(root, 1)]
    while pending:
        item, depth = pending.pop()
        if isinstance(item, str):
            item.encode("utf-8", errors="strict")
        elif isinstance(item, dict):
            if depth > limit:
                raise ValueError("JSON nesting limit exceeded")
            for key, value in item.items():
                key.encode("utf-8", errors="strict")
                pending.append((value, depth + 1))
        elif isinstance(item, list):
            if depth > limit:
                raise ValueError("JSON nesting limit exceeded")
            pending.extend((value, depth + 1) for value in item)


def strict_object(
    raw: bytes | str,
    *,
    max_bytes: int = MAX_ARGUMENT_BYTES,
    max_depth: int = MAX_DEPTH,
) -> dict:
    """Read an object directly from bytes or text. Object coercion loses evidence."""
    try:
        if isinstance(raw, bytes):
            if len(raw) > max_bytes:
                raise ValueError("JSON byte limit exceeded")
            text = raw.decode("utf-8", errors="strict")
        elif isinstance(raw, str):
            if len(raw.encode("utf-8", errors="strict")) > max_bytes:
                raise ValueError("JSON byte limit exceeded")
            text = raw
        else:
            raise ValueError("expected raw JSON text or bytes")
        root = json.loads(text, object_pairs_hook=_unique_object, parse_int=_integer,
                          parse_float=_decimal, parse_constant=_non_finite)
        if not isinstance(root, dict):
            raise ValueError("JSON root must be an object")
        _check_unicode_and_depth(root, max_depth)
        return root
    except (ValueError, RecursionError, DecimalException) as failure:
        # A JSONDecodeError may retain raw content in .doc. Do not retain it in
        # a chained exception surfaced to callers or newline-delimited logs.
        if isinstance(failure, json.JSONDecodeError):
            message = "invalid JSON syntax"
        elif isinstance(failure, UnicodeError):
            message = "invalid Unicode in JSON"
        elif isinstance(failure, RecursionError):
            message = "JSON nesting limit exceeded"
        else:
            message = "invalid JSON number" if isinstance(failure, DecimalException) else str(failure)
        raise GatewayError(ErrorCode.PROTOCOL_ERROR, message) from None
