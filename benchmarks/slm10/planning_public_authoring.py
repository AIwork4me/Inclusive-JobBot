"""Public requirements for the independently authored Planning V2 candidate."""

from dataclasses import dataclass
from typing import NamedTuple

from .planning_controls import LEVELS


class LocalText(NamedTuple):
    en: str
    zh: str


@dataclass(frozen=True)
class Desk:
    code: str
    item: LocalText
    business_check: str


DESKS = (
    Desk("gallery", LocalText("exhibition crate", "展品周转箱"), "humidity_log"),
    Desk("nursery", LocalText("seedling tray", "育苗盘"), "watering_log"),
    Desk("ferry", LocalText("dock equipment bin", "码头设备箱"), "tide_window"),
    Desk("bakery", LocalText("packaging batch", "包材批次"), "lot_labels"),
    Desk("library", LocalText("mobile collection box", "流动馆藏箱"), "catalog_match"),
    Desk("theater", LocalText("rehearsal prop case", "排练道具箱"), "cue_sheet"),
    Desk("laundry", LocalText("linen return cart", "布草回收车"), "wash_cycle_log"),
    Desk("clinic", LocalText("waiting-room supply bin", "候诊区物资箱"), "supply_count"),
    Desk("workshop", LocalText("demonstration kit", "演示套件"), "parts_inventory"),
    Desk("depot", LocalText("route signage bundle", "路线标识包"), "route_sheet"),
)

OPERATIONS = (
    ("return_to_storage", LocalText("return it to storage", "归还库房")),
    ("place_on_display", LocalText("put it on display", "移至展示区")),
    ("send_to_inspection", LocalText("send it for inspection", "送检")),
    ("hold_for_pickup", LocalText("hold it for pickup", "留待领取")),
    ("reserve_for_demo", LocalText("reserve it for a demonstration", "预留给演示")),
    ("transfer_to_spare_pool", LocalText("transfer it to the spare pool", "转入备用库")),
    ("flag_for_relabeling", LocalText("flag it for relabeling", "标记为待更换标签")),
    ("schedule_count", LocalText("schedule a count", "安排盘点")),
    ("route_to_sorting", LocalText("route it to the sorting desk", "转交分拣台")),
    ("close_handoff", LocalText("close the handoff", "结清交接")),
)

CHECKS = (
    "quantity", "label_legibility", "handoff_record", "storage_capacity", "booking_window",
    "position_register", "return_route", "handling_note", "custody_record", "access_window",
    "exception_log", "stock_class", "inspection_date", "destination_record", "availability",
    "condition_record", "movement_hold",
)

TOPICS = (
    LocalText("before opening", "开门前"),
    LocalText("during intake", "收件时"),
    LocalText("for the noon handoff", "为午间交接"),
    LocalText("for the closing team", "为闭馆班组"),
    LocalText("before tomorrow's booking", "在明天的预约前"),
    LocalText("while reconciling the register", "在核对台账时"),
    LocalText("for the next shift", "为下一班组"),
    LocalText("at the collection desk", "在领取台"),
    LocalText("for the planning board", "为排程看板"),
    LocalText("before confirming the move", "在确认移交前"),
)

REQUESTS = {
    "L1": LocalText("Read the current status and report its value.", "查询当前状态并返回状态值。"),
    "L2": LocalText("Report both current status and the applicable handling limit. Obtain each "
                    "independently from its own service.", "报告当前状态及适用的处理限额，两项分别向各自服务查询。"),
    "L3": LocalText("Resolve the intake reference to the current service key, then use that key "
                    "to retrieve the status.", "先将收件编号解析为当前服务键，再用该键查询状态。"),
    "L4": LocalText("Read status from the primary register. If it directs you to the alternate "
                    "register, use that source to report the current status.", "先查主台账。若主台账要求改用备用台账，就从备用台账查询并报告当前状态。"),
    "L5": LocalText("Read the current status. If the primary service is unavailable, consult the alternate "
                    "service. If the reviewer supplies a replacement reference, use that reference and "
                    "discard the old status. Escalate if access is denied.",
                    "查询当前状态。主服务暂不可用时查备用服务；若审核人更换编号，按新编号查询并舍弃旧状态；权限被拒时上报。"),
    "L6": LocalText("To {action}, collect these checks: {checks}. Complete the first check before the others, "
                    "then collect the rest in any order. Either register may supply a check. "
                    "After all checks finish, obtain the audit assessment and create a "
                    "pending draft using it. Escalate if a check or the audit is denied.",
                    "为{action}，完成这些检查：{checks}。先完成第一项，其余可任意排序。可向任一台账查询。"
                    "全部完成后获取审核结论并据此建待审草稿。检查或审核被拒时上报。"),
    "L7": LocalText("I want to {action}. Read the audit assessment and create a draft based on it. "
                    "Request external confirmation for that exact draft. Commit on approval, or "
                    "escalate if the audit is denied or the external confirmation is declined or unverifiable.",
                    "我想{action}。请先读取审核结论并据此建立草稿。就该草稿请求外部确认。批准后提交。审核被拒、外部确认被拒或无法验证时上报。"),
}

OUTPUT = {
    "identify_request": "reference", "request_reference": "missing_field",
    "L1": "value", "L2": "value, limit", "L3": "value", "L4": "value",
    "L5": "value | reason", "L6": "draft_id | reason",
    "L7": "audit_ref | reason | reason, draft_id",
}

GOALS = {
    "L1": "retrieve_status", "L2": "combine_status_limit", "L3": "resolve_current_status",
    "L4": "choose_status_source", "L5": "recover_current_status", "L6": "prepare_reviewed_draft",
    "L7": "confirm_and_commit",
}


def tool(inputs, outputs, description):
    return {"inputs": inputs, "outputs": outputs, "description": description,
            "input_schema": {"type": "object", "properties": dict.fromkeys(inputs, {"type": "string"}),
                             "required": inputs, "additionalProperties": False}}


def tools_for(level):
    lookup = tool(["reference"], ["code", "value"], "Read the primary register for the intake reference.")
    alternate = tool(["reference"], ["value"], "Read current status in the alternate register.")
    audit = tool(["reference"], ["code", "assessment"], "Read the current assessment for the exact item.")
    stage = tool(["reference", "action", "assessment"], ["draft_id"], "Create a pending draft from an audit assessment.")
    return {
        "L0": {},
        "L1": {"lookup": lookup},
        "L2": {"lookup": lookup, "limits": tool(["reference"], ["limit"], "Read the handling limit for the reference.")},
        "L3": {"resolve": tool(["reference"], ["key"], "Resolve an intake reference to the current service key."),
               "lookup": tool(["key"], ["value"], "Read status by current service key.")},
        "L4": {"lookup": lookup, "alternate": alternate},
        "L5": {"lookup": lookup, "alternate": alternate},
        "L6": {
            "check": tool(["reference", "check_id"], ["code", "assessment"], "Read one named check in the operations register."),
            "check_alternate": tool(["reference", "check_id"], ["code", "assessment"], "Read one named check from the archive."),
            "audit_read": audit, "stage": stage,
        },
        "L7": {
            "audit_read": audit, "stage": stage,
            "request_confirmation": tool(["draft_id"], ["code", "decision", "approval"], "Request an external decision on this draft."),
            "commit": tool(["draft_id", "approval"], ["audit_ref"], "Commit the draft with its trusted approval."),
        },
    }[level]


def text_for(level, language, desk, reference, topic, action, action_text, checks):
    visible_ref = f" ({reference})" if reference else ""
    en = f"For the {desk.item.en}{visible_ref} {topic.en}, "
    zh = f"{topic.zh}，关于{desk.item.zh}{visible_ref}。"
    if level == "L0":
        instructions = (
            LocalText(f"identify the intake reference for the note to {action_text.en}.",
                      f"请识别用于{action_text.zh}的收件编号。") if reference else
            LocalText(f"ask for the missing intake reference needed to {action_text.en}.",
                      f"如需{action_text.zh}，请询问缺失的收件编号。")
        )
    else:
        formatting = {"action": action_text.en, "checks": ", ".join(checks)}
        instructions = LocalText(
            REQUESTS[level].en.format(**formatting),
            REQUESTS[level].zh.format(action=action_text.zh, checks="、".join(checks)),
        )
        en = f"{en[:-2]}. "
    if level in {"L6", "L7"}:
        en += f"Operation code {action}. "
        zh += f"操作代码 {action}。"
    output_key = ("identify_request" if reference else "request_reference") if level == "L0" else level
    output = OUTPUT[output_key]
    en_format = f" Return one JSON object. Keys by outcome: {output}."
    zh_format = f" 返回一个 JSON 对象，按结果选择字段：{output}。"
    return {"en": en + instructions.en + en_format, "zh": zh + instructions.zh + zh_format,
            "mixed": zh + " " + instructions.en + en_format}[language]


def public_cases():
    for level in LEVELS:
        for index in range(100):
            desk = DESKS[index // 10]
            action, action_text = OPERATIONS[index % 10]
            topic = TOPICS[index % 10]
            language = ("en", "zh", "mixed")[(index + int(level[-1])) % 3]
            reference = f"{desk.code.upper()}-{(index * 337 + 431) % 1009:04}"
            checks = []
            options = {}
            if level == "L0":
                goal = "identify_request" if index % 2 == 0 else "request_reference"
                options = {"goal_options": ["identify_request", "request_reference"]}
                fields = ["reference"]
                data = {"reference": reference} if goal == "identify_request" else {}
                budget = 0
            elif level in {"L6", "L7"}:
                goal = GOALS[level]
                data = {"subject": reference, "action": action}
                if level == "L6":
                    offset = index // 10
                    rotated = CHECKS[offset:] + CHECKS[:offset]
                    checks = [desk.business_check, *rotated[:8 + index % 10]]
                    data["checks"] = checks
                fields = list(data)
                budget = len(checks) + 2 if level == "L6" else 4
            else:
                goal = GOALS[level]
                fields = ["reference"]
                data = {"reference": reference}
                budget = {"L1": 1, "L2": 2, "L3": 2, "L4": 2, "L5": 3}[level]
            events = {"L5": ["revised_reference"], "L7": ["decision", "draft_id", "approval"]}.get(level, [])
            yield {
                "case_id": f"SLM-AP2-{level}-{index + 1:03}", "level": level, "language": language,
                "task": text_for(level, language, desk, reference if data else None, topic, action, action_text, checks),
                "public": data,
                "contract": {"goal": goal, "tools": tools_for(level), "public_fields": fields,
                             "event_fields": events, "action_budget": budget, **options},
                "limits": {"tool_calls": budget, "model_requests": budget + 4,
                           "peak_context_tokens": 8192, "retries": 0},
            }
