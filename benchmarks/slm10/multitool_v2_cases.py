"""Author independent read-only MULTITOOL-V2 candidate workflows."""

from copy import deepcopy
from hashlib import sha256

from evaluation.aeve.runtime import canonical

VERSION = "MULTITOOL-V2/candidate-0.1"
LANGUAGES = ("en", "zh", "mixed")
TEXT = {"type": "string"}
INT = {"type": "integer"}


def obj(**properties):
    return {"type": "object", "properties": properties, "required": sorted(properties), "additionalProperties": False}


def array(items):
    return {"type": "array", "items": items, "minItems": 1, "maxItems": 20}


KEY = obj(ref=TEXT)
ENTRY = obj(caption_id=TEXT, milliseconds=INT, text=TEXT)
TOOLS = {
    "read_calibration": ("Read the confirmed sensor calibration value for a reference.", KEY),
    "read_tolerance": ("Read the confirmed instrument tolerance value for a reference.", KEY),
    "read_label": ("Read a signage lineage record and its successor, if present.", KEY),
    "read_translation": ("Read a signage translation and its successor, if present.", KEY),
    "read_layout_revision": ("Read a signage layout revision and its successor, if present.", KEY),
    "read_archive_total": ("Read the archived unit count for a collection.", KEY),
    "read_live_totals": ("Read current counts for the supplied collection references.", obj(refs=array(TEXT))),
    "read_maintenance_gate": ("Read whether the main route is open and both route starts.", KEY),
    "read_open_route": ("Read an open-route record.", KEY),
    "read_bypass_route": ("Read a bypass-route record.", KEY),
    "read_caption": ("Read the exact caption entry for a reference.", KEY),
    "preview_caption": ("Run a read-only format preview using the caption entries in the submitted order.",
                        obj(preview=obj(entries=array(ENTRY), preserve_order={"type": "boolean"},
                                        format=TEXT | {"enum": ["srt", "vtt"]}))),
    "read_image_source": ("Read the primary image source. Retry once only for a retryable result.", KEY),
    "read_alternate_source": ("Read the independent mirror identified in a non-retryable response.", KEY),
    "read_image_metadata": ("Read the image metadata record and its successor, if present.", KEY),
    "read_booking": ("Read the draft booking roster for a venue; wait for the next user scope message.", KEY),
    "read_venue_access": ("Read an access feature for the supplied venue and reference.", obj(venue=TEXT, ref=TEXT)),
    "read_consent": ("Read the current permission record and its next review or allowed guide link.", KEY),
    "read_public_excerpt": ("Read only a permitted public excerpt.", KEY),
    "read_redaction_guide": ("Read instructions for a withholding decision.", KEY),
}

INSTRUCTIONS = {
    "parallel": (
        "Read each calibration or tolerance with the listed tool. Return JSON with values keyed by reference.",
        "用列表中的工具读取校准或公差值。仅返回 JSON，values 对象以编号为键。",
        "按给出的 tool 读取 calibration 或 tolerance。Return JSON with values keyed by reference.",
    ),
    "serial": (
        "Start at the specified signage record and follow each next_tool and next_ref until next_ref is null. Return JSON with label.",
        "从指定标识记录开始，按 next_tool 和 next_ref 逐步查询，直到 next_ref 为 null。仅返回含 label 的 JSON。",
        "从 start 查 signage，follow next_tool 和 next_ref until null。JSON only with label.",
    ),
    "aggregation": (
        "Read archived counts for every listed collection, then read all live counts together. "
        "Return JSON with total from live counts and conflicts in the listed order.",
        "读取所有列出的馆藏历史计数，再批量查询实时计数。仅返回 JSON：total 为实时合计，conflicts 按列表顺序。",
        "先查 archive counts，再查 live counts 一次。Return live total and conflicts in source order in JSON.",
    ),
    "conditional": (
        "Inspect the maintenance gate. Follow the main route only if open, otherwise the bypass. "
        "Follow links to the destination and return JSON with destination.",
        "先查检修闸门。开放时只走主路线，关闭时只走旁路。查询后续链接，最终仅返回含 destination 的 JSON。",
        "查 gate。If open follow 主路线，otherwise 走 bypass。Follow links and return JSON with destination.",
    ),
    "typed_transfer": (
        "Read each caption entry in the listed order. Preview the exact entries with preserve_order true "
        "and the requested format. Return JSON with preview_id.",
        "按顺序读取字幕条目。使用原始条目、preserve_order=true 和指定格式预览。仅返回含 preview_id 的 JSON。",
        "按列出顺序查 captions，preview exact entries with preserve_order true 和指定 format。只输出 JSON preview_id。",
    ),
    "recovery": (
        "Read the primary image source. Retry exactly once when retryable, or use the stated mirror when non-retryable. "
        "Follow remaining links. Return JSON with checksum.",
        "查主图像来源。可重试则仅重试一次；不可重试则用返回的镜像。查询后续链接，仅返回含 checksum 的 JSON。",
        "查 primary image source。Retry only once if retryable，otherwise 使用返回的镜像。Return JSON with checksum.",
    ),
    "scope_update": (
        "Read the initial venue booking and wait for the next user scope message. "
        "Use only that update for access reads. Return JSON with venue and features keyed by reference.",
        "读取初始场馆预约，等待下一条用户范围消息。仅依更新查询无障碍功能，返回含 venue 与 features 的 JSON。",
        "查 initial venue booking，然后 wait for new scope。按更新查 access features，JSON only with venue and features.",
    ),
    "authorization": (
        "Follow current consent reviews. Use the allowed public excerpt if permitted, or the redaction guide if withheld. "
        "No write or release is requested. Return JSON with decision and note.",
        "逐条查询当前同意记录。许可时仅读公开节选；不许可则查隐去指南。不进行写入或发布。仅返回 decision 和 note。",
        "Follow current consent reviews。获准才读 public excerpt，否则查 redaction guide。No writes。JSON decision and note.",
    ),
}
CATEGORIES = tuple(INSTRUCTIONS)


class Author:
    def __init__(self, category, depth, language, variant):
        self.identity = f"MT2-C01-{category}-{depth:02}-{language}-{variant}"
        self.category, self.depth, self.language, self.variant = category, depth, language, variant
        self.actions, self.records = [], {}
        self.event = None

    def ref(self, group, index=0):
        token = sha256(f"{self.identity}/{group}/{index}".encode()).hexdigest()[:12].upper()
        return f"{group}-{token}"

    def record(self, tool, arguments, result):
        locator = canonical(arguments).decode()
        self.records.setdefault(tool, {}).setdefault(locator, []).append(deepcopy(result))

    def add(self, tool, arguments, result, deps=(), sources=None):
        identity = f"step-{len(self.actions) + 1}"
        self.actions.append({"action_id": identity, "tool": tool, "arguments": arguments, "observation": result,
                             "depends_on": list(deps), "input_sources": sources or {}})
        self.record(tool, arguments, result)
        return identity

    def finish(self, inputs, answer, tools):
        if len(self.actions) != self.depth:
            raise ValueError("authored action count differs from roster")
        tools = {name: {"description": TOOLS[name][0], "parameters": TOOLS[name][1]} for name in tools}
        label = INSTRUCTIONS[self.category][LANGUAGES.index(self.language)]
        public = {"case_id": self.identity, "category": self.category, "language": self.language,
                  "required_actions": self.depth, "split": "candidate_holdout", "tools": tools,
                  "message": label + "\nDATA " + canonical(inputs).decode()}
        ranks = {}
        for node in self.actions:
            ranks[node["action_id"]] = 1 + max((ranks[parent] for parent in node["depends_on"]), default=0)
        world = {"case_id": self.identity, "records": self.records, "event": self.event}
        graph = {"case_id": self.identity, "actions": self.actions,
                 "schemas": {name: detail["parameters"] for name, detail in tools.items()},
                 "answer": answer, "critical_path": max(ranks.values())}
        return public, world, graph


def parallel(author):
    targets, values = [], {}
    for i in range(author.depth):
        tool = "read_calibration" if i % 2 else "read_tolerance"
        ref, value = author.ref("CAL", i), (i * 13 + int(author.ref("VAL", i).split("-")[1][-2:], 16)) % 300
        author.add(tool, {"ref": ref}, {"value": value})
        author.record(tool, {"ref": ref + "X"}, {"value": value + 1})
        targets.append({"tool": tool, "ref": ref})
        values[ref] = value
    return author.finish({"targets": targets}, {"values": values}, ("read_calibration", "read_tolerance"))


def add_chain(author, targets, final, parent=None, source_field="next_ref"):
    for index, current in enumerate(targets):
        future = targets[index + 1] if index + 1 < len(targets) else None
        result = {"next_tool": future["tool"], "next_ref": future["ref"]} if future else final
        links = {"ref": [parent, source_field]} if parent else {}
        parent = author.add(current["tool"], {"ref": current["ref"]}, result, (parent,) if parent else (), links)
        source_field = "next_ref"


def serial(author):
    tools = ("read_label", "read_translation", "read_layout_revision")
    targets = [{"tool": tools[i % 3], "ref": author.ref("SIGN", i)} for i in range(author.depth)]
    answer = {"label": author.ref("DISPLAY")}
    add_chain(author, targets, answer | {"next_ref": None})
    return author.finish({"start": targets[0]}, answer, tools)


def aggregation(author):
    refs = [author.ref("ARC", i) for i in range(author.depth - 1)]
    live, conflicts, archived_actions = {}, [], []
    for i, ref in enumerate(refs):
        before = (i + len(refs)) * 7
        current = before + (i + author.variant + 1) % 3
        archived_actions.append(author.add("read_archive_total", {"ref": ref}, {"units": before}))
        live[ref] = current
        if current != before:
            conflicts.append(ref)
    author.add("read_live_totals", {"refs": refs}, {"counts": live}, archived_actions)
    return author.finish({"collections": refs}, {"total": sum(live.values()), "conflicts": conflicts},
                         ("read_archive_total", "read_live_totals"))


def conditional(author):
    gate = author.ref("GATE")
    opened = int(gate[-1], 16) % 2 == 0
    main, bypass = author.ref("MAIN"), author.ref("BYP")
    selected, choice_field, opposing = ("read_open_route", "main_ref", "read_bypass_route") if opened else (
        "read_bypass_route", "bypass_ref", "read_open_route")
    root = author.add("read_maintenance_gate", {"ref": gate}, {"open": opened, "main_ref": main, "bypass_ref": bypass})
    targets = [{"tool": selected, "ref": (main if opened else bypass) if i == 0 else author.ref("PATH", i)}
               for i in range(author.depth - 1)]
    answer = {"destination": author.ref("ROOM")}
    add_chain(author, targets, answer | {"next_ref": None}, root, choice_field)
    author.record(opposing, {"ref": bypass if opened else main}, {"destination": "wrong-branch", "next_ref": None})
    return author.finish({"gate": gate}, answer, ("read_maintenance_gate", "read_open_route", "read_bypass_route"))


def typed_transfer(author):
    refs = [author.ref("CAP", i) for i in range(author.depth - 1)]
    entries = [{"caption_id": ref, "milliseconds": i * 777, "text": f" caption 字幕 {i} "}
               for i, ref in enumerate(refs)]
    parents = [author.add("read_caption", {"ref": ref}, {"entry": entry}) for ref, entry in zip(refs, entries, strict=True)]
    fmt = "srt" if int(refs[0][-1], 16) % 2 else "vtt"
    answer = {"preview_id": author.ref("PREVIEW")}
    author.add("preview_caption", {"preview": {"entries": entries, "preserve_order": True, "format": fmt}},
               answer, parents)
    return author.finish({"captions": refs, "format": fmt}, answer, ("read_caption", "preview_caption"))


def recovery(author):
    primary, mirror = author.ref("IMAGE"), author.ref("MIRROR")
    retry = int(primary[-1], 16) % 2 == 0
    fault = {"status": "retryable"} if retry else {"status": "unavailable", "mirror_ref": mirror}
    root = author.add("read_image_source", {"ref": primary}, fault)
    tool, reference = ("read_image_source", primary) if retry else ("read_alternate_source", mirror)
    targets = [{"tool": "read_image_metadata", "ref": author.ref("META", i)} for i in range(author.depth - 2)]
    answer = {"checksum": author.ref("CHECK")}
    second_result = ({"next_tool": targets[0]["tool"], "next_ref": targets[0]["ref"]} if targets
                     else answer | {"next_ref": None})
    second = author.add(tool, {"ref": reference}, second_result, (root,), {} if retry else {"ref": [root, "mirror_ref"]})
    add_chain(author, targets, answer | {"next_ref": None}, second)
    return author.finish({"primary": primary}, answer, ("read_image_source", "read_alternate_source", "read_image_metadata"))


def scope_update(author):
    initial, current = author.ref("VENUE", 0), author.ref("VENUE", 1)
    outdated = [author.ref("OLD", i) for i in range(author.depth - 1)]
    refs = [author.ref("ACCESS", i) for i in range(author.depth - 1)]
    parent = author.add("read_booking", {"ref": initial}, {"venue": initial, "refs": outdated})
    label = {"en": "Updated access scope.", "zh": "更新后的无障碍查询范围。", "mixed": "更新 scope for access."}[author.language]
    author.event = {"event_id": author.ref("UPDATE"), "after_tool": "read_booking",
                    "message": label + "\nDATA " + canonical({"venue": current, "refs": refs}).decode()}
    features = {}
    for i, (obsolete, ref) in enumerate(zip(outdated, refs, strict=True)):
        feature = ("hearing_loop", "lift", "quiet_room")[i % 3]
        author.add("read_venue_access", {"venue": current, "ref": ref}, {"feature": feature}, (parent,))
        author.record("read_venue_access", {"venue": initial, "ref": obsolete}, {"feature": "obsolete"})
        features[ref] = feature
    return author.finish({"booking": initial}, {"venue": current, "features": features}, ("read_booking", "read_venue_access"))


def authorization(author):
    refs = [author.ref("CONSENT", i) for i in range(author.depth - 1)]
    permitted = int(refs[0][-1], 16) % 2 == 0
    decision = "permitted" if permitted else "withheld"
    tool = "read_public_excerpt" if permitted else "read_redaction_guide"
    opposite = "read_redaction_guide" if permitted else "read_public_excerpt"
    lookup, note = author.ref("GUIDE"), author.ref("NOTE")
    parent = None
    for i, ref in enumerate(refs):
        result = {"next_ref": refs[i + 1]} if i + 1 < len(refs) else {"decision": decision, "guide_ref": lookup}
        parent = author.add("read_consent", {"ref": ref}, result, (parent,) if parent else (),
                            {"ref": [parent, "next_ref"]} if parent else {})
    author.add(tool, {"ref": lookup}, {"note": note}, (parent,), {"ref": [parent, "guide_ref"]})
    author.record(opposite, {"ref": lookup}, {"note": "unapproved"})
    return author.finish({"consent": refs[0]}, {"decision": decision, "note": note},
                         ("read_consent", "read_public_excerpt", "read_redaction_guide"))


BUILDERS = {builder.__name__: builder for builder in (
    parallel, serial, aggregation, conditional, typed_transfer, recovery, scope_update, authorization
)}
