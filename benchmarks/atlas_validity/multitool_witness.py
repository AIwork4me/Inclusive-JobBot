"""Resolve the public MULTITOOL-V1 tasks with trusted tool observations."""

import re

REFERENCE = re.compile(r"(?<![A-Z0-9-])[A-Z]+-[0-9A-F]{9}(?![A-Z0-9-])")


def separate_references(prompt, pivot):
    groups = re.split(pivot, prompt, maxsplit=1, flags=re.IGNORECASE)
    if len(groups) != 2:
        raise ValueError("the public request does not separate its reference groups")
    return (REFERENCE.findall(group) for group in groups)


def solve(model_input, execute, take_user_messages):
    """Choose the visible action, following links only when disclosed by a tool."""
    prompt = model_input["messages"][0]["content"]
    names = {tool["function"]["name"] for tool in model_input["tools"]}
    refs = REFERENCE.findall(prompt)
    if not refs:
        raise ValueError("no public reference in the task")

    def call(tool, **args):
        if tool not in names:
            raise ValueError(f"tool is unavailable: {tool}")
        return execute(tool, args)

    def read(tool, record_id):
        return call(tool, record_id=record_id)

    if "conflicts" in prompt:
        texts = re.split(r"current-only stock from|另计仅查询实时库存的", prompt, maxsplit=1)
        compared = REFERENCE.findall(texts[0])
        current = {ref: read("read_stock", ref)["units"] for ref in compared}
        conflicts = [ref for ref in compared if read("read_stock_archive", ref)["units"] != current[ref]]
        if len(texts) == 2:
            current.update({ref: read("read_stock", ref)["units"] for ref in REFERENCE.findall(texts[1])})
        return {"total": sum(current.values()), "conflicts": conflicts}
    if "read_cold_stock" in names and "stock_total" not in prompt:
        ambient, cold = separate_references(prompt, r"refrigerated depots|冷藏库")
        units = {ref: read("read_stock", ref)["units"] for ref in ambient}
        units.update({ref: read("read_cold_stock", ref)["units"] for ref in cold})
        return {"units": units}
    if "stock_total" in prompt and "demand_total" in prompt:
        stock, demand = separate_references(prompt, r"open demand|未完成需求")
        stock_total = sum(read("read_stock", ref)["units"] for ref in stock)
        demand_total = sum(read("read_backlog", ref)["units"] for ref in demand)
        return {"stock_total": stock_total, "demand_total": demand_total, "balance": stock_total - demand_total}
    if "assess_load" in names:
        ceiling = re.search(r"(?:ceiling|上限)\s*(\d+)", prompt)
        if ceiling is None:
            raise ValueError("public load ceiling is missing")
        readings = [{"record_id": ref, "reading": read("read_sensor", ref)["load"]} for ref in refs]
        return call("assess_load", reading_set=readings, policy={"maximum": int(ceiling[1]), "inclusive": True})
    if "read_registry" in names:
        codes = {}
        for ref in refs:
            row = read("read_registry", ref)
            if row.get("retryable") is True:
                row = read("read_registry", ref)
            if "error" in row and row.get("retryable") is False:
                row = read("read_mirror", ref)
            codes[ref] = row["verified_code"]
        return {"codes": codes}

    ref = refs[0]
    visited = set()

    def visit(tool, reference):
        key = (tool, reference)
        if key in visited or len(visited) >= 24:
            raise ValueError("the observed route is cyclic or exceeds the visible turn allowance")
        visited.add(key)
        return read(*key)

    if "read_event" in names:
        rosters = read("read_event", ref)["rosters"]
        choices = take_user_messages()
        if len(choices) != 1:
            raise ValueError("expected one moderator site update")
        update = choices[0]["content"]
        site = min(rosters, key=lambda name: update.find(name) if name in update else len(update))
        if site not in update:
            raise ValueError("the confirmed site is absent from the event's rosters")
        return {"site": site, "participants": sum(read("read_roster", item)["participants"] for item in rosters[site])}
    if "read_review" in names:
        row = visit("read_review", ref)
        while row["superseded"]:
            ref = row["current_ref"]
            row = visit("read_review", ref)
        if row["draft_permission"] is True:
            return call("create_hold_draft", record_id=ref, reason="route_review")
        return {"review_ref": ref, "status": "needs_authorization"}
    if "read_relief_lane" in names:
        tool = "read_checkpoint"
        row = visit(tool, ref)
        while "destination" not in row:
            branch = "main" if row["main_lane_open"] else "relief"
            tool = "read_live_lane" if branch == "main" else "read_relief_lane"
            row = visit(tool, row["leg"][branch])
        return {"destination": row["destination"]}

    starting_tools = [name for name in names if name in prompt]
    if len(starting_tools) != 1:
        raise ValueError("the initial service is not stated unambiguously")
    row = visit(starting_tools[0], ref)
    while "destination" not in row:
        row = visit(row["next_service"], row["next_ref"])
    return {"destination": row["destination"]}
