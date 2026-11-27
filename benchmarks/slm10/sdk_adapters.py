"""Opt-in SDK development adapters at the request, callback and terminal boundaries."""

from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import re
from threading import Lock
from time import monotonic, perf_counter_ns

from referencing import Registry

from model_gateway.errors import ErrorCode, GatewayError
from model_gateway.openai_protocol import CALL_ID
from model_gateway.strict_json import strict_object
from model_gateway.tool_validation import STRICT_SCHEMA, validate_schema

from .tc_verification import SDK_RESULT


REGISTRY = Path(__file__).resolve().parents[2] / "atlas/slm/v1.0/sdk-adapter-profiles.json"
REGISTRY_VERSION = "IJ-SLM-SDK-ADAPTER-PROFILES/1.0"
VERSIONS = {
    "reference": "unchanged/1.0",
    "prompt_compiler": "sdk-style-directive/1.0",
    "compact_result_codec": "sdk-result-json/1.0",
    "action_state": "sdk-observed-action-ids/1.0",
    "duplicate_execution_guard": "verified-immutable-read/1.0",
    "termination_policy": "existing-terminal-state/1.0",
    "structured_output_contract": "strict-json-schema/1.0",
}
REQUEST_COMPONENTS = frozenset(("prompt_compiler", "compact_result_codec", "action_state"))
STYLE_LINE = "- Format your responses in github-style markdown.\n"
TOOL_NAME = re.compile(r"[a-z_]{1,64}")
MAX_REQUEST_BYTES = 1 << 20
MAX_RESULT_BYTES = 65_536


@dataclass(frozen=True, slots=True)
class AdapterProfile:
    component: str = "reference"
    version: str = VERSIONS["reference"]

    def __post_init__(self):
        if self.component not in VERSIONS or VERSIONS[self.component] != self.version:
            raise ValueError("unsupported SDK adapter component or version")


def load_profiles(path=REGISTRY):
    """Load the explicit reference and single-factor treatments."""
    registry = strict_object(Path(path).read_bytes())
    if registry.get("version") != REGISTRY_VERSION or registry.get("default") != "reference":
        raise ValueError("unsupported SDK adapter registry version or unsafe default")
    profiles = {
        row["component"]: AdapterProfile(row["component"], row["version"])
        for row in registry["profiles"]
    }
    if set(profiles) != VERSIONS.keys() or len(registry["profiles"]) != len(profiles):
        raise ValueError("SDK adapter registry must enumerate each single factor exactly once")
    return profiles


@dataclass(frozen=True, slots=True)
class Scope:
    run_id: str
    session_id: str
    principal_id: str
    revision: str
    role_id: str

    def __post_init__(self):
        if not all(isinstance(value, str) and value for value in
                   (self.run_id, self.session_id, self.principal_id, self.revision, self.role_id)):
            raise ValueError("complete trusted scope is required")


@dataclass(frozen=True, slots=True)
class CallbackReceipt:
    """Trusted post-callback evidence from the existing SDK and host audit path."""

    scope: Scope
    provider_request_id: str
    completion_id: str
    call_id: str
    tool: str
    arguments: bytes
    result: bytes
    status: str

    @property
    def source(self):
        return self.provider_request_id, self.completion_id, self.call_id


@dataclass(frozen=True, slots=True)
class RequestContext:
    scope: Scope
    provider_request_id: str
    sdk_system_sha256: str
    callbacks: tuple[CallbackReceipt, ...] = ()


@dataclass(frozen=True, slots=True)
class RequestAudit:
    profile: AdapterProfile
    provider_request_id: str
    before_sha256: str
    after_sha256: str
    before_bytes: int
    after_bytes: int
    message_indices: tuple[int, ...]
    callback_sources: tuple[tuple[str, str, str], ...]
    elapsed_ns: int


def _compact(value) -> str:
    """Serialize parsed JSON without a float or a Decimal-to-integer conversion."""
    if isinstance(value, Decimal):
        number = str(value)
        return number if "." in number or "E" in number else number + ".0"
    if isinstance(value, dict):
        return "{" + ",".join(f"{_compact(key)}:{_compact(value[key])}" for key in sorted(value)) + "}"
    if isinstance(value, list):
        return "[" + ",".join(map(_compact, value)) + "]"
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _bound_system(messages, expected_digest):
    matches = [index for index, message in enumerate(messages)
               if message.get("role") == "system" and isinstance(message.get("content"), str)
               and sha256(message["content"].encode()).hexdigest() == expected_digest]
    return matches[0] if len(matches) == 1 else None


def _proposal(messages, tool_index, call_id):
    matches = [(index, call) for index, message in enumerate(messages)
               if message.get("role") == "assistant" and isinstance(message.get("tool_calls"), list)
               for call in message["tool_calls"] if isinstance(call, dict) and call.get("id") == call_id]
    if len(matches) != 1 or matches[0][0] >= tool_index:
        raise GatewayError(ErrorCode.PROTOCOL_ERROR, "callback lacks a unique preceding proposal")
    call = matches[0][1]
    if call.get("type") != "function" or not isinstance(call.get("function"), dict):
        raise GatewayError(ErrorCode.PROTOCOL_ERROR, "callback proposal is not a function")
    return call["function"]


def _observed_callbacks(messages, context):
    callbacks = {}
    for callback in context.callbacks:
        if (callback.scope != context.scope or callback.status != "EXECUTED"
                or callback.provider_request_id == context.provider_request_id):
            continue
        if (not all(callback.source) or not CALL_ID.fullmatch(callback.call_id)
                or not TOOL_NAME.fullmatch(callback.tool) or callback.call_id in callbacks):
            raise GatewayError(ErrorCode.PROTOCOL_ERROR, "ambiguous trusted callback receipt")
        callbacks[callback.call_id] = callback
    observed, seen = [], set()
    for index, message in enumerate(messages):
        call_id = message.get("tool_call_id")
        if message.get("role") != "tool" or not isinstance(call_id, str) or call_id not in callbacks:
            continue
        callback = callbacks[call_id]
        if call_id in seen:
            raise GatewayError(ErrorCode.PROTOCOL_ERROR, "callback result appears more than once")
        seen.add(call_id)
        proposal = _proposal(messages, index, call_id)
        if proposal.get("name") != callback.tool or message.get("name") != callback.tool:
            raise GatewayError(ErrorCode.PROTOCOL_ERROR, "callback tool identity differs from proposal")
        if _compact(strict_object(proposal.get("arguments"))) != _compact(strict_object(callback.arguments)):
            raise GatewayError(ErrorCode.PROTOCOL_ERROR, "callback arguments differ from proposal")
        matched = SDK_RESULT.fullmatch(message["content"]) if isinstance(message.get("content"), str) else None
        if matched is None or matched[1] != callback.tool:
            raise GatewayError(ErrorCode.PROTOCOL_ERROR, "callback wrapper differs from the SDK contract")
        wrapper = strict_object(matched[2], max_bytes=MAX_RESULT_BYTES)
        if wrapper.keys() != {"result"}:
            raise GatewayError(ErrorCode.PROTOCOL_ERROR, "callback wrapper lacks a unique result")
        result = strict_object(wrapper["result"], max_bytes=MAX_RESULT_BYTES)
        expected = strict_object(callback.result, max_bytes=MAX_RESULT_BYTES)
        if _compact(result) != _compact(expected):
            raise GatewayError(ErrorCode.PROTOCOL_ERROR, "delivered result differs from trusted callback")
        if "error" not in result:
            observed.append((index, callback, result))
    return tuple(observed)


def adapt_request(profile: AdapterProfile, raw: bytes, context: RequestContext) -> tuple[bytes, RequestAudit]:
    """Apply one request treatment and return exact before/after evidence for the caller."""
    started = perf_counter_ns()
    message_indices, callback_sources = (), ()
    output = raw
    if profile.component in REQUEST_COMPONENTS:
        body = strict_object(raw, max_bytes=MAX_REQUEST_BYTES, max_depth=48)
        messages = body.get("messages")
        if not isinstance(messages, list) or any(not isinstance(message, dict) for message in messages):
            raise GatewayError(ErrorCode.PROTOCOL_ERROR, "request messages must be a list of objects")
        system = _bound_system(messages, context.sdk_system_sha256)
        if profile.component == "prompt_compiler" and system is not None:
            content = messages[system]["content"]
            if content.splitlines(keepends=True).count(STYLE_LINE) == 1:
                messages[system]["content"] = "".join(
                    line for line in content.splitlines(keepends=True) if line != STYLE_LINE
                )
                message_indices = (system,)
        if profile.component == "compact_result_codec":
            observed = _observed_callbacks(messages, context)
            for index, _, result in observed:
                messages[index]["content"] = _compact(result)
            message_indices = tuple(index for index, _, _ in observed)
            callback_sources = tuple(callback.source for _, callback, _ in observed)
        if profile.component == "action_state" and system is not None:
            observed = _observed_callbacks(messages, context)
            if observed:
                state = [{"tool": callback.tool, "id": callback.call_id} for _, callback, _ in observed]
                messages[system]["content"] += (
                    "\nObserved completed actions (workflow evidence): " + _compact(state)
                    + "\nContinue applying user instructions, dependencies, and existing authority checks."
                )
                message_indices = (system,)
                callback_sources = tuple(callback.source for _, callback, _ in observed)
        if message_indices:
            output = _compact(body).encode()
            if len(output) > MAX_REQUEST_BYTES:
                raise GatewayError(ErrorCode.PROTOCOL_ERROR, "adapted request exceeds byte limit")
    before_sha = sha256(raw).hexdigest()
    after_sha = before_sha if output is raw else sha256(output).hexdigest()
    return output, RequestAudit(profile, context.provider_request_id, before_sha, after_sha, len(raw), len(output),
                                message_indices, callback_sources, perf_counter_ns() - started)


@dataclass(frozen=True, slots=True)
class GuardAuthorization:
    """Fresh trusted authority after the SDK callback claim and normal host permission checks."""

    scope: Scope
    provider_request_id: str
    call_id: str
    tool: str
    arguments: bytes
    resource: str
    immutable_revision: str | None
    read_only: bool
    repeat_intent: str
    permission: str
    reuse_allowed: bool


@dataclass(frozen=True, slots=True)
class GuardAudit:
    provider_request_id: str
    call_id: str
    source_request_id: str
    source_completion_id: str
    source_call_id: str
    tool: str
    result_sha256: str
    elapsed_ns: int
    attribution: str = "HOST"
    disposition: str = "REUSE_SELECTED"


@dataclass(frozen=True, slots=True)
class GuardHit:
    audit: GuardAudit
    result: bytes


class DuplicateExecutionGuard:
    """Per-run cache for separately claimed known redundant immutable reads."""

    def __init__(self, profile: AdapterProfile, eligible_tools: Iterable[str], audit: Callable[[GuardAudit], None],
                 *, ttl_seconds: float = 15, max_entries: int = 256, clock: Callable[[], float] = monotonic):
        if not isfinite(ttl_seconds) or ttl_seconds <= 0 or not 1 <= max_entries <= 4096 or not callable(audit):
            raise ValueError("guard requires bounded storage, a positive TTL and an audit sink")
        self._enabled = profile.component == "duplicate_execution_guard"
        self._eligible_tools = frozenset(eligible_tools)
        self._audit = audit
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._cache = OrderedDict()
        self._lock = Lock()

    def _key(self, authority):
        if (not self._enabled or authority.tool not in self._eligible_tools
                or authority.permission != "ALLOW" or authority.reuse_allowed is not True
                or authority.read_only is not True or not authority.immutable_revision
                or not authority.resource or not authority.provider_request_id
                or not CALL_ID.fullmatch(authority.call_id)):
            return None
        args = _compact(strict_object(authority.arguments))
        return authority.scope, authority.tool, args, authority.resource, authority.immutable_revision

    def remember(self, authority: GuardAuthorization, receipt: CallbackReceipt) -> None:
        key = self._key(authority)
        if key is None:
            return
        if (receipt.scope != authority.scope or receipt.tool != authority.tool or receipt.call_id != authority.call_id
                or receipt.provider_request_id != authority.provider_request_id or not receipt.completion_id
                or not isinstance(receipt.result, bytes)
                or _compact(strict_object(receipt.arguments)) != key[2]):
            raise GatewayError(ErrorCode.PROTOCOL_ERROR, "guard receipt differs from the authorized callback")
        with self._lock:
            self._cache.pop(key, None)
            reusable = (authority.repeat_intent in {"INITIAL", "REDUNDANT"} and receipt.status == "EXECUTED"
                        and "error" not in strict_object(receipt.result, max_bytes=MAX_RESULT_BYTES))
            if reusable:
                self._cache[key] = self._clock() + self._ttl, receipt
                if len(self._cache) > self._max_entries:
                    self._cache.popitem(last=False)

    def reuse(self, authority: GuardAuthorization, checkpoint: Callable[[], None]) -> GuardHit | None:
        """Return a reuse candidate only after a fresh authority and audit checkpoint."""
        started = perf_counter_ns()
        checkpoint()
        key = self._key(authority)
        if key is None:
            return None
        with self._lock:
            prior = self._cache.get(key)
            if prior is None:
                return None
            expires, receipt = prior
            if authority.repeat_intent != "REDUNDANT" or self._clock() >= expires:
                self._cache.pop(key, None)
                return None
            if authority.call_id == receipt.call_id or authority.provider_request_id == receipt.provider_request_id:
                return None
        checkpoint()
        audit = GuardAudit(authority.provider_request_id, authority.call_id, *receipt.source, receipt.tool,
                           sha256(receipt.result).hexdigest(), perf_counter_ns() - started)
        self._audit(audit)
        checkpoint()
        with self._lock:
            if self._cache.get(key) is not prior or self._clock() >= expires:
                return None
        return GuardHit(audit, receipt.result)


@dataclass(frozen=True, slots=True)
class TerminalContext:
    finish_reason: str
    unresolved_calls: int
    proposed_calls: int
    model_calls: int
    tool_calls: int
    max_model_calls: int
    max_tool_calls: int
    cancelled: bool
    deadline_exceeded: bool
    authority_pending: bool
    workflow_complete: bool
    transport_complete: bool


@dataclass(frozen=True, slots=True)
class TerminalDecision:
    decision: str
    reason: str


def termination_decision(profile: AdapterProfile, context: TerminalContext) -> TerminalDecision:
    """Assess a boundary after existing SDK, transport and workflow checks."""
    if profile.component != "termination_policy":
        return TerminalDecision("DEFER", "profile disabled")
    if context.cancelled or context.deadline_exceeded:
        return TerminalDecision("BLOCK", "cancelled or deadline exceeded")
    if not context.transport_complete:
        return TerminalDecision("BLOCK", "incomplete transport")
    counts = (context.unresolved_calls, context.proposed_calls, context.model_calls, context.tool_calls,
              context.max_model_calls, context.max_tool_calls)
    if (any(type(value) is not int or value < 0 for value in counts) or context.model_calls < 1
            or context.model_calls > context.max_model_calls or context.tool_calls > context.max_tool_calls):
        return TerminalDecision("BLOCK", "invalid or exhausted budget")
    if context.finish_reason == "tool_calls" and context.proposed_calls:
        if (context.model_calls >= context.max_model_calls
                or context.tool_calls + context.proposed_calls > context.max_tool_calls):
            return TerminalDecision("BLOCK", "insufficient budget to continue")
        return TerminalDecision("CONTINUE", "existing policy controls proposed calls")
    if context.finish_reason != "stop" or context.unresolved_calls or context.proposed_calls:
        return TerminalDecision("BLOCK", "provider has no complete stop")
    if context.authority_pending or not context.workflow_complete:
        return TerminalDecision("BLOCK", "authoritative workflow is incomplete")
    return TerminalDecision("ALLOW_FINAL", "complete stop confirmed by host and provider")


def structured_output(profile: AdapterProfile, raw: bytes | str, schema: dict, *, terminal_allowed: bool) -> dict | None:
    """Validate the final JSON at the existing authorized output boundary."""
    if profile.component != "structured_output_contract":
        return None
    if terminal_allowed is not True:
        raise GatewayError(ErrorCode.PROTOCOL_ERROR, "structured output requires authorized terminal state")
    value = strict_object(raw, max_bytes=MAX_RESULT_BYTES)
    exact_schema = strict_object(_compact(schema), max_bytes=MAX_RESULT_BYTES)
    STRICT_SCHEMA.check_schema(exact_schema)
    validate_schema(STRICT_SCHEMA(exact_schema, registry=Registry()), value)
    return value
