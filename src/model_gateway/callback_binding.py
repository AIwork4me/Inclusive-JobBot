"""Bind a typed SDK callback to a current, authorized provider proposal."""

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from math import isfinite
from threading import Lock

from referencing import Registry

from .base import Proposal
from .openai_protocol import parse_proposal
from .tool_validation import STRICT_SCHEMA


@dataclass(frozen=True, slots=True)
class BindingContext:
    """Trusted execution metadata supplied by the host, outside model arguments."""

    session_id: str
    scope: str
    revision: int
    authorization_binding: str
    observation_revision: int


@dataclass(frozen=True, slots=True)
class CallbackBinding:
    proposal: Proposal
    context: BindingContext
    parsed_arguments: dict
    callback_arguments: dict
    normalized_arguments: dict
    integer_conversions: tuple[tuple[str | int, ...], ...]


def _match(expected, actual, schema, path, conversions):
    schema = schema if isinstance(schema, dict) else {}
    if type(expected) is dict and type(actual) is dict and expected.keys() == actual.keys():
        for key, value in expected.items():
            child = schema.get("properties", {}).get(key)
            if child is None and not schema.get("patternProperties"):
                child = schema.get("additionalProperties")
            _match(value, actual[key], child, (*path, key), conversions)
    elif type(expected) is list and type(actual) is list and len(expected) == len(actual):
        prefix = schema.get("prefixItems", [])
        for index, (value, received) in enumerate(zip(expected, actual, strict=True)):
            child = prefix[index] if index < len(prefix) else schema.get("items")
            _match(value, received, child, (*path, index), conversions)
    elif type(actual) is float and isfinite(actual):
        if (type(expected) is int and schema.get("type") == "integer"
                and abs(expected) < 2**53 and actual.is_integer() and int(actual) == expected):
            conversions.append(path)
        elif type(expected) is not Decimal or Decimal.from_float(actual) != expected:
            raise ValueError("SDK callback number differs from the wire proposal")
    elif type(expected) is not type(actual) or type(expected) in (dict, list) or expected != actual:
        raise ValueError("SDK callback arguments differ from the wire proposal")


class CallbackBinder:
    """A single-session proposal batch. Each ID is published and claimed at most once.

    The host supplies the current context and an authorization predicate. The
    predicate sees the validated wire values. Execution still applies its own
    live policy at the point where it uses or changes state.
    """

    def __init__(self, schemas, authorize):
        self._validators = {}
        for tool, schema in deepcopy(schemas).items():
            STRICT_SCHEMA.check_schema(schema)
            self._validators[tool] = STRICT_SCHEMA(schema, registry=Registry())
        self._authorize = authorize
        self._pending = {}
        self._seen = set()
        self._session_id = None
        self._closed = False
        self._lock = Lock()

    def publish(self, proposals, context):
        with self._lock:
            self._pending.clear()
            if self._closed or self._session_id not in (None, context.session_id):
                raise ValueError("SDK proposal batch belongs to a different or closed session")
            pending = {}
            for proposal in proposals:
                ident = proposal.call_id
                if ident in pending or ident in self._seen:
                    raise ValueError("Duplicate wire call ID")
                parsed = parse_proposal(proposal)
                validator = self._validators.get(proposal.name)
                if validator is not None and validator.is_valid(parsed):
                    pending[ident] = (proposal, parsed, context, validator.schema)
                else:
                    # Reserve rejected IDs too, so a later response cannot reuse one.
                    pending[ident] = None
            self._session_id = context.session_id
            self._seen.update(pending)
            self._pending.update(pending)

    def claim(self, call_id, tool, arguments, context):
        with self._lock:
            entry = self._pending.get(call_id)
            if entry is None or entry[0].name != tool or entry[2] != context:
                raise ValueError("SDK callback lacks a current wire proposal with matching identity")
            proposal, parsed, _, schema = entry
            conversions = []
            _match(parsed, arguments, schema, (), conversions)
            if not self._authorize(context, tool, deepcopy(parsed)):
                raise ValueError("SDK callback is outside the current authorization")
            del self._pending[call_id]
            return CallbackBinding(proposal, context, deepcopy(parsed), deepcopy(arguments),
                                   deepcopy(parsed), tuple(conversions))

    def close(self):
        with self._lock:
            self._closed = True
            self._pending.clear()
