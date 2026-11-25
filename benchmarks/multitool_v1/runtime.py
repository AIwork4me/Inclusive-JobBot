"""Deterministic test tools with no access to the expected workflow or answer."""

from collections import Counter
from copy import deepcopy

from benchmarks.tool_calling_v2.evaluator import VALIDATOR, evaluate
from benchmarks.tool_calling_v2.oracle import decode_object
from benchmarks.tool_calling_v2.persisted import evaluate_persisted
from business_tools import BusinessStore
from model_gateway import ExecutionContext, Gateway, Grant, Policy, Proposal, ToolSpec
from model_gateway.errors import GatewayError


def _create_draft(transaction, args, _context):
    key = args["record_id"]
    transaction.put("review_drafts", key, {"review_ref": key, "submitted": False, "reason": args["reason"]})
    return {"status": "drafted", "draft_ref": key}


class Scenario:
    def __init__(self, case, path=None, *, require_observed_draft=False):
        # No workflow or answer is read by the runtime. Prompt metadata selects
        # available tools, and the separate world contains all state and events.
        self._world = case.world
        self._records = case.world["records"]
        self._validators = {tool: VALIDATOR(case.tools[tool]["parameters"]) for tool in case.prompt["tools"]}
        self._faults = {(item["tool"], item["record_id"]): item for item in case.world["faults"]}
        self._attempts = Counter()
        self._pending_events = []
        self._published_event = False
        self._draft_review_turns = {} if require_observed_draft else None
        self._store = None
        self._gateway = None
        if "create_hold_draft" in self._validators and path is not None:
            self._store = BusinessStore(path, initial={})
            spec = ToolSpec(case.tools["create_hold_draft"]["parameters"], lambda args: args["record_id"],
                            _create_draft, write=True, draft_only=True)
            grant = Grant("synthetic_worker", "reviewer", "create_hold_draft",
                          frozenset(case.world["draft_ids"]), frozenset({"under_review"}), True)
            self._gateway = Gateway(self._store, {"create_hold_draft": spec}, Policy((grant,)), max_attempts=1)

    def snapshot(self):
        return self._store.snapshot() if self._store is not None else None

    def take_events(self):
        """Drain private event IDs paired with ordinary user messages for the next turn."""
        events, self._pending_events = self._pending_events, []
        return events

    def call(self, call_id, tool, raw_arguments, *, turn=None):
        if tool not in self._validators:
            return {"error": "unknown_tool"}
        try:
            arguments = decode_object(raw_arguments)
        except ValueError:
            return {"error": "invalid_json"}
        if not self._validators[tool].is_valid(arguments):
            return {"error": "schema_mismatch"}
        if tool == "commit_hold":
            return {"error": "authorization_denied"}
        if tool == "assess_load":
            maximum = arguments["policy"]["maximum"]
            return {"above_limit": [reading["record_id"] for reading in arguments["reading_set"]
                                    if reading["reading"] > maximum]}
        key = arguments["record_id"]
        if tool == "create_hold_draft":
            if self._gateway is None:
                return {"error": "authorization_denied"}
            reviews = self._draft_review_turns
            authorized = reviews is None or (key in reviews and type(turn) is int and reviews[key] < turn)
            state = "under_review" if authorized else "awaiting_review"
            context = ExecutionContext("synthetic_worker", "reviewer", "multitool", state, key)
            try:
                return self._gateway.execute(Proposal(call_id, tool, raw_arguments), context)
            except GatewayError as error:
                return {"error": str(error.code)}
        if self._draft_review_turns is not None and tool == "read_review":
            self._draft_review_turns.pop(key, None)
        fault = self._faults.get((tool, key))
        if fault:
            count = self._attempts[(tool, key)]
            self._attempts[(tool, key)] += 1
            responses = fault["responses"]
            if count < len(responses) or fault["persistent"]:
                return deepcopy(responses[min(count, len(responses) - 1)])
        event = self._world["event"]
        updated_scope = False
        if event and not self._published_event and (tool, key) == (event["after_tool"], event["record_id"]):
            self._published_event = True
            updated_scope = True
            self._pending_events.append((event["id"], {"role": "user", "content": event["text"]}))
            if self._draft_review_turns is not None:
                self._draft_review_turns.clear()
        observed = self._records.get(tool, {}).get(key, {"error": "not_found", "retryable": False})
        if (self._draft_review_turns is not None and tool == "read_review" and not updated_scope
                and type(turn) is int and turn >= 0 and observed.get("superseded") is False
                and observed.get("draft_permission") is True and observed.get("current_ref") == key):
            self._draft_review_turns[key] = turn
        return deepcopy(observed)


def score(case, calls, final_text, *, before=None, after=None, delivered_events=()):
    """Score observed proposals, user events and independently collected snapshots."""
    workflow = case.workflow()
    if workflow.state is not None and before is not None and after is not None:
        result = evaluate_persisted(workflow, calls, final_text, before, after)
    elif "event" in case.oracle:
        trigger = case.world["event"]["after_tool"]
        turns = [call.turn for call in calls if call.name == trigger]
        expected = ((turns[0], case.oracle["event"]),) if turns else ()
        issue = ()
        if not expected or tuple(delivered_events) != expected:
            issue = (("F15_INSUFFICIENT_EVIDENCE", "expected user message delivery missing or mistimed"),)
        result = evaluate(workflow, calls, final_text, trace_problems=issue)
    else:
        result = evaluate(workflow, calls, final_text)
    result["expected_outcome"] = case.oracle["outcome"]
    return result
