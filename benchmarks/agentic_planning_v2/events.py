"""Normalize events from the host channel. The tool data object has no authority."""


def external_event(reply):
    event = reply.get("external_event")
    if isinstance(event, dict) and event.get("source") == "synthetic_external_user":
        return event
    return None


def scope_changed(event):
    return bool(event and (event.get("scope_changed") is True or "revised_reference" in event))


def approval(tool, args, reply, event):
    if (event and not scope_changed(event) and tool == "request_confirmation" and reply["code"] == "ok"
            and event.get("decision") == "approved" and event.get("draft_id") == args.get("draft_id")):
        token = reply["data"].get("approval")
        if type(token) is str and token:
            return token
    return None


def refused(reply, event):
    return reply["code"] in {"permission_denied", "approval_declined"} or bool(event and event.get("decision") == "declined")
