"""Independent business and answer expectations for Evaluator V2."""

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import re
import unicodedata
from typing import Any


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict:
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON key")
        obj[key] = value
    return obj


def _finite_decimal(raw: str) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation as error:
        raise ValueError("invalid decimal") from error
    if not value.is_finite() or abs(value.adjusted()) > 308:
        raise ValueError("number outside diagnostic range")
    return value


def decode_object(raw: str) -> dict:
    """Read a historical argument string without rounding decimals or losing duplicate keys."""
    if not isinstance(raw, str) or len(raw) > 65536:
        raise ValueError("invalid or oversized argument text")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_pairs, parse_float=_finite_decimal,
                           parse_constant=_finite_decimal)
        json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
    except (UnicodeError, RecursionError) as error:
        raise ValueError("invalid Unicode or excessively nested JSON") from error
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


@dataclass(frozen=True)
class Unordered:
    values: tuple


def equal(want, got) -> bool:
    if isinstance(want, Unordered):
        if not isinstance(got, list) or len(want.values) != len(got):
            return False
        unmatched = got.copy()
        for item in want.values:
            for index, actual in enumerate(unmatched):
                if equal(item, actual):
                    unmatched.pop(index)
                    break
            else:
                return False
        return True
    numeric = (float, Decimal, int)
    if type(want) in numeric and type(got) in numeric:
        return Decimal(str(want)) == Decimal(str(got))
    if type(want) is not type(got):
        return False
    if isinstance(want, dict):
        return want.keys() == got.keys() and all(equal(value, got[key]) for key, value in want.items())
    if isinstance(want, list):
        return len(want) == len(got) and all(equal(a, b) for a, b in zip(want, got))
    return want == got


def _contains(text: str, needle: str) -> bool:
    text = unicodedata.normalize("NFKC", text)
    needle = unicodedata.normalize("NFKC", needle)
    if re.fullmatch(r"[-+]?[0-9]+(?:\.[0-9]+)?", needle):
        tokens = re.findall(
            r"(?<![-A-Za-z0-9.,])[-+]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)"
            r"(?:\.[0-9]+)?(?![0-9A-Za-z-]|[.,][0-9])", text
        )
        return any(Decimal(token.replace(",", "")) == Decimal(needle) for token in tokens)
    return needle in text


@dataclass(frozen=True)
class FinalAnswer:
    structured: dict | None = None
    required: tuple[tuple[str, ...], ...] = ()
    forbidden: tuple[str, ...] = ()

    def check(self, text: str) -> list[str]:
        if not text.strip():
            return ["empty final answer"]
        if self.structured is not None:
            try:
                if equal(self.structured, decode_object(text)):
                    return []
            except ValueError:
                pass
            return ["structured answer differs from independent expectations"]
        missing = [f"missing required fact {group[0]!r}" for group in self.required
                   if not any(_contains(text, choice) for choice in group)]
        return missing + [f"reported forbidden fact {item!r}" for item in self.forbidden
                          if _contains(text, item)]


@dataclass(frozen=True)
class Effect:
    tool: str
    table: str
    resource_id: str
    before: dict | None
    after: dict | None
    requires_confirmation: bool = True
    stage: str = "committed"


@dataclass(frozen=True)
class StateOracle:
    before: dict | None
    after: dict | None
    effects: tuple[Effect, ...] = ()

    def check(self, snapshot: dict, audit: list[dict], matched_calls: dict[str, tuple[str, dict]],
              before_snapshot: dict | None = None) -> list[tuple[str, str]]:
        failures = []
        if before_snapshot is not None and not equal(self.before, before_snapshot):
            failures.append(("F11_BUSINESS_STATE_ERROR", "initial database differs from oracle"))
        if not equal(self.after, snapshot):
            failures.append(("F11_BUSINESS_STATE_ERROR", "final database differs from oracle"))
        effects = [row for row in audit if row.get("status") in {"committed", "drafted"}]
        keys = [(row.get("tool"), row.get("table"), row.get("resource_id"), row["status"]) for row in effects]
        expected = [(item.tool, item.table, item.resource_id, item.stage) for item in self.effects]
        if Counter(keys) != Counter(expected):
            failures.append(("F11_BUSINESS_STATE_ERROR", "missing, unexpected or duplicate persisted effects"))
        ids, idempotency_keys = {}, {}
        for row, key in zip(effects, keys):
            txn, operation_key = row.get("transaction_id"), row.get("idempotency_key")
            identity = (row.get("call_id"), row.get("tool"), operation_key)
            if (not txn or not operation_key or ids.get(txn, identity) != identity
                    or idempotency_keys.get(operation_key, txn) != txn):
                failures.append(("F11_BUSINESS_STATE_ERROR", "missing or duplicate transaction identity"))
            ids[txn] = identity
            idempotency_keys[operation_key] = txn
            candidates = [item for item in self.effects
                          if (item.tool, item.table, item.resource_id, item.stage) == key]
            if row.get("authorization") != "allowed" or (
                any(item.requires_confirmation for item in candidates) and row.get("confirmation") != "confirmed"
            ):
                failures.append(("F08_AUTHORIZATION_DENIAL", "unauthorized or unconfirmed persisted effect"))
            match = matched_calls.get(row.get("call_id"))
            if match is None or match[0] != row.get("tool"):
                failures.append(("F11_BUSINESS_STATE_ERROR", "persisted effect has no matching verified call"))
            elif "validated_arguments" in row and not equal(match[1], row["validated_arguments"]):
                failures.append(("F11_BUSINESS_STATE_ERROR", "transaction arguments differ from the verified call"))
            if not any(equal(item.before, row.get("before")) and equal(item.after, row.get("after"))
                       for item in candidates):
                failures.append(("F11_BUSINESS_STATE_ERROR", "persisted before/after rows differ from oracle"))
            if "proposed" in row and not equal(row["after"], row["proposed"]):
                failures.append(("F11_BUSINESS_STATE_ERROR", "persisted after state differs from proposed state"))
        return failures
