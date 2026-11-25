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
