"""Independent public-input witness for the frozen TC-V2 holdout tasks."""

from ast import literal_eval
from decimal import Decimal
import re

from .quote_witness import read_current_quote

REFERENCE = re.compile(r"(?<![A-Z0-9-])[A-Z]+(?:-[A-Z0-9]+)+(?![A-Z0-9-])")
FORM_EN = re.compile(
    r"count (?P<count>\d+), enabled (?P<enabled>true|false), factor (?P<factor>[0-9.]+), "
    r"zone sequence (?P<first>[A-Z]+) then (?P<last>[A-Z]+), primary label (?P<label>.+)"
    r" and a null secondary label\."
)
FORM_ZH = re.compile(
    r"件数 (?P<count>\d+)，启用为(?P<enabled>是|否)，系数 (?P<factor>[0-9.]+)，"
    r"区域顺序先 (?P<first>[A-Z]+) 后 (?P<last>[A-Z]+)，主标签为「(?P<label>.+)」，次标签为 null。"
)


def allocation_fields(prompt, reference):
    matched = FORM_EN.search(prompt)
    if matched:
        label = literal_eval(matched["label"])
    else:
        matched = FORM_ZH.search(prompt)
        if not matched:
            raise ValueError("public allocation form fields are missing")
        label = matched["label"]
    if type(label) is not str:
        raise ValueError("public primary label is not text")
    return {
        "form_id": reference, "count": int(matched["count"]), "enabled": matched["enabled"] in {"true", "是"},
        "factor": Decimal(matched["factor"]), "zones": [matched["first"], matched["last"]],
        "label": {"primary": label, "secondary": None},
    }


def solve(prompt, tools, execute):
    """Emit permitted tool requests using the visible task and previous observations."""
    names = {tool["function"]["name"] for tool in tools}
    references = REFERENCE.findall(prompt)
    if len(references) != 1:
        raise ValueError("expected one catalog, bin, lane or form reference")
    reference = references[0]

    def call(tool, **args):
        if tool not in names:
            raise ValueError(f"public tool is unavailable: {tool}")
        observed = execute(tool, args)
        if "error" in observed and (tool != "read_lane" or observed["error"] != "LANE_RETIRED"):
            raise ValueError(f"authorized witness call failed: {tool}")
        return observed

    if "rate" in prompt and "currency" in prompt:
        return read_current_quote(prompt, tools, execute)
    if "accepted" in prompt:
        form = allocation_fields(prompt, reference)
        return {"accepted": call("validate_allocation", **form)["accepted"]}
    if "service_code" in prompt:
        visited = {reference}
        lane = call("read_lane", lane_id=reference)
        while lane.get("error") == "LANE_RETIRED":
            successor = lane["successor"]
            if successor in visited or len(visited) >= 7:
                raise ValueError("replacement route is cyclic or exceeds the public turn budget")
            visited.add(successor)
            lane = call("read_lane", lane_id=successor)
        return {"service_code": lane["service_code"]}
    if "packing_mark" in prompt:
        return {"packing_mark": call("read_item", item_id=reference)["packing_mark"]}
    if "pick_count" in prompt and "overflow_count" in prompt:
        item = call("read_item", item_id=reference)
        pick = call("read_bin", bin_id=item["pick_face"])
        overflow = call("read_bin", bin_id=item["overflow"])
        return {"pick_count": pick["on_hand"], "overflow_count": overflow["on_hand"]}
    if "change_applied" in prompt:
        linked = "linked to SKU" in prompt or "关联库位" in prompt
        bin_id = call("read_item", item_id=reference)["bin_id"] if linked else reference
        return {"reserve": call("read_bin", bin_id=bin_id)["reserve"], "change_applied": False}
    if "signed" in prompt or "签署" in prompt:
        item = call("read_item", item_id=reference)
        return call("set_reserve", bin_id=item["reserve_bin"], reserve=item["reorder_level"])
    if "below_reserve" in prompt:
        row = call("read_bin", bin_id=reference)
        return {"below_reserve": row["on_hand"] < row["reserve"]}
    if "on_hand" in prompt:
        return {"on_hand": call("read_bin", bin_id=reference)["on_hand"]}
    raise ValueError("unknown public TC-V2 task")
