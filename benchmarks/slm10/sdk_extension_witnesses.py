"""Handwritten software witnesses for Extension workflows, independent of the graph generator."""


def observed(turn, call, tool, arguments, result, **sources):
    return {"turn": turn, "call_id": call, "completion_id": f"witness-completion-{turn}", "tool": tool,
            "arguments_raw": arguments, "observation": result,
            "observation_sources": {field: {"action_id": action, "call_id": producer, "key": key}
                                    for field, (action, producer, key) in sources.items()}}


WITNESSES = {
    "EXT-D-CATALOG": (
        "catalog_stock",
        [
            observed(0, "profile", "catalog_profile", '{"selector":{"filters":["youth","art"],"campus":"East"}}',
                     {"reference": "C-70"}),
            observed(1, "stock", "catalog_stock", '{"reference":"C-70"}', {"status": "ready"},
                     reference=("find-profile", "profile", "reference")),
        ],
        {"status": "ready"},
    ),
    "EXT-H-RESCAN": (
        "archive_scan_retry",
        [
            observed(0, "first-scan", "read_asset",
                     '{"filters":{"asset":"SCAN38","profile":{"lossless":true,"channels":["red","green"],"max_width":2048}}}',
                     {"status": "stale"}),
            observed(1, "second-scan", "read_asset",
                     '{"filters":{"asset":"SCAN38","profile":{"lossless":true,"channels":["red","green"],"max_width":2048}}}',
                     {"status": "fresh"}),
        ],
        {"status": "fresh"},
    ),
    "EXT-H-SEAT": (
        "accessibility_route",
        [
            observed(0, "eight", "show_seat", '{"seat":"R8","request":{"step_free":true,"entrances":["East"]}}',
                     {"available": True, "route": "RT-04"}),
            observed(0, "seven", "show_seat", '{"seat":"R7","request":{"step_free":true,"entrances":["East"]}}',
                     {"available": False}),
            observed(1, "route", "access_route", '{"route":"RT-04"}', {"step_free": True},
                     route=("inspect-seat-b", "eight", "route")),
        ],
        {"seat": "R8", "step_free": True},
    ),
    "EXT-H-RIGHTS": (
        "media_release_proof",
        [
            observed(0, "proof", "read_proof", '{"proofs":["attribution","license"],"job":"GRAPH09"}', {"receipt": "P-73"}),
            observed(1, "verify", "check_release", '{"receipt":"P-73"}', {"status": "verified"},
                     receipt=("read-proof", "proof", "receipt")),
        ],
        {"status": "verified"},
    ),
    "EXT-H-LAYOUT": (
        "document_layout",
        [
            observed(0, "page", "check_layout", '{"settings":{"pages":["cover","detail"],"reading_order":true},"page":7}',
                     {"finding": "order_valid"}),
        ],
        {"finding": "order_valid"},
    ),
}
