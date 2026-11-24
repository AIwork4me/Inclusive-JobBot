"""Isolated synthetic tools. This module never reads the scoring graph."""

from copy import deepcopy
import secrets

from .contract import TOOLS


class SyntheticSandbox:
    def __init__(self, world):
        self._responses = {(row["tool"], tuple(sorted(row["args"].items()))): row["observation"]
                           for row in world["responses"]}
        self._delivery = world["delivery"]
        self._drafts = {}
        self._deliverables = {}
        self._audit_observed = False
        self._grant = None

    def snapshot(self):
        return deepcopy({"drafts": self._drafts, "deliverables": self._deliverables})

    def invoke(self, tool, args):
        if type(tool) is not str or tool not in TOOLS or type(args) is not dict or args.keys() != set(TOOLS[tool][1]) or any(
            type(value) is not str for value in args.values()
        ):
            return {"code": "invalid_call", "data": {}}
        key = (tool, tuple(sorted(args.items())))
        result = self._responses.get(key)
        if tool in {"stage", "request_confirmation", "commit", "verify_delivery", "verify_draft"}:
            return self._delivery_tool(tool, args, result)
        if result is None:
            return {"code": "not_found", "data": {}}
        if tool == "audit_read" and result["code"] == "ok":
            self._audit_observed = True
        return deepcopy(result)

    def _delivery_tool(self, tool, args, result):
        denied = {"code": "permission_denied", "data": {}}
        if self._delivery is None or result is None:
            return denied
        draft_id = self._delivery["draft_id"]
        audit_ref = self._delivery["audit_ref"]
        if tool == "stage":
            if draft_id in self._drafts:
                return {"code": "duplicate_mutation", "data": {}}
            if not self._audit_observed:
                return denied
            self._drafts[draft_id] = {**args, "state": "pending"}
        elif tool == "request_confirmation":
            if self._drafts.get(draft_id, {}).get("state") != "pending":
                return denied
            if self._delivery["approved"]:
                self._grant = result["data"]["approval"]
        elif tool == "commit":
            if audit_ref in self._deliverables:
                return {"code": "duplicate_mutation", "data": {}}
            if self._grant is None or not secrets.compare_digest(args["approval"], self._grant):
                return denied
            self._drafts[draft_id]["state"] = "committed"
            self._deliverables[audit_ref] = {**self._delivery["draft_args"], "draft_id": draft_id}
            self._grant = None
        elif tool == "verify_delivery" and audit_ref not in self._deliverables:
            return denied
        elif tool == "verify_draft" and self._drafts.get(draft_id, {}).get("state") != "pending":
            return denied
        return deepcopy(result)
