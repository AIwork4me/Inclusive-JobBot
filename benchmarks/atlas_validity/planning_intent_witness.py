"""Resolve public zero-action planning requests in English and Chinese."""

import re

REFERENCE = re.compile(r"(?<![A-Za-z0-9-])REF-[0-9]+-[0-9]+(?![A-Za-z0-9-])")


def understand(prompt):
    """Return the disposition and facts justified by the visible request."""
    ids = REFERENCE.findall(prompt)
    if len(ids) != 1:
        raise ValueError("the public request must identify one subject")
    subject = ids[0]
    text = prompt.casefold()
    if ("forgot" in text and "date" in text) or "忘记给日期" in text:
        return {"disposition": "clarify", "facts": {"subject": subject, "reason": "date_range_required"}}
    if ("publish" in text and "read-only" in text) or ("发布" in text and "只读" in text):
        return {"disposition": "clarify", "facts": {"subject": subject, "reason": "conflicting_instructions"}}
    if "do not perform a lookup" in text or "先别查" in text:
        return {"disposition": "understood", "facts": {"subject": subject, "objective": "current_status",
                                                      "constraint": "deferred", "needs_tool": True}}
    if ("summarize" in text and "read-only" in text) or ("仅理解" in text and "只读" in text):
        return {"disposition": "understood", "facts": {"subject": subject, "objective": "review",
                                                      "constraint": "read_only", "needs_tool": False}}
    raise ValueError("unsupported public zero-action request")

def solve_read_only(prompt, tools, execute):
    """Resolve a public status or classification request with observed references."""
    refs = REFERENCE.findall(prompt)
    if len(refs) != 1:
        raise ValueError("the read-only witness needs one public reference")
    reference = refs[0]
    names = {tool["function"]["name"] for tool in tools}
    facts = {"subject": reference}

    def call(tool, **arguments):
        if tool not in names:
            raise ValueError(f"public tool is unavailable: {tool}")
        response = execute(tool, arguments)
        if response["code"] != "ok":
            raise ValueError(f"public tool did not return requested facts: {tool}")
        return response["data"]

    if "check_policy" in names:
        found = call("lookup", reference=reference)
        key = found["id"]
        if found["kind"] != "policy":
            seen = set()
            while key not in seen and len(seen) < 20:
                seen.add(key)
                row = call("read_record", id=key)
                if "policy_id" in row:
                    key = row["policy_id"]
                    break
                key = row["linked_id"]
            else:
                raise ValueError("primary dependency did not resolve to a policy")
        facts["classification"] = call("check_policy", id=key)["classification"]
    else:
        if "status" in prompt:
            facts["status"] = call("status", reference=reference)["status"]
        if "classification" in prompt:
            facts["classification"] = call("archive", reference=reference)["classification"]
    return {"disposition": "completed", "facts": facts}
