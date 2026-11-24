"""Freeze original synthetic JOB-V1 inputs, state and expected outcomes."""

from argparse import ArgumentParser
from hashlib import sha256
from pathlib import Path

from .dataset import (CATEGORIES, FILES, LANGUAGES, ROOT, Case, canonical, digest,
                      experiment_contract, repeat_selection)


FACETS = ("colloquial", "implicit_intent", "multi_document", "missing_field", "conflicting_evidence",
          "user_followup", "scope_denied", "nonroutine")


def phrase(language, english, chinese, mixed):
    return (english, chinese, mixed)[LANGUAGES.index(language)]


class Fixture:
    def __init__(self, prefix, category, index, language):
        self.case_id = f"JOB-{prefix}-{index + 1:03}"
        self.facet = FACETS[index // 25]
        self.language = language
        self.plan = {"case_id": self.case_id, "category": category,
                     "routine": self.facet in {"colloquial", "implicit_intent", "multi_document"}}
        self.task = {"case_id": self.case_id, "language": language, "facet": self.facet,
                     "operator_message": None, "attachments": [], "followups": []}
        self.world = {"case_id": self.case_id, "state": {}, "permitted_reads": {}, "draft_allowed": False}
        self.gold = {"case_id": self.case_id, "disposition": "completed", "answer": None, "reads": [],
                     "native_input": None, "draft": None}

    def say(self, english, chinese, mixed):
        return phrase(self.language, english, chinese, mixed)

    def key(self, prefix):
        opaque = sha256(f"IJ07:JOB1:{self.case_id}:{prefix}".encode()).hexdigest()[:10].upper()
        return f"{prefix}-{opaque}"

    def attach(self, name, text):
        self.task["attachments"].append({"name": name, "format": "text/plain", "text": text})

    def follow_up(self, text):
        self.task["followups"].append({"id": "revision-1", "release": "before_final_delivery", "text": text})

    def row(self, table, key, contents, *, allowed=True, expected=False):
        self.world["state"].setdefault(table, {})[key] = contents
        if allowed:
            self.world["permitted_reads"].setdefault(table, []).append(key)
        if expected:
            self.gold["reads"].append([table, key])

    def stop(self, status, reason):
        self.gold["disposition"] = status
        self.gold["answer"] = {"status": status, "reason": reason}

    def freeze(self):
        case = Case(self.plan, self.task, self.world, self.gold)
        self.plan["pairing_sha256"] = case.pairing_sha256()
        return case


def document(case, index):
    order, supplier, sku, note_id = (case.key(prefix) for prefix in ("PO", "SUP", "SKU", "NOTE"))
    location = ("Dock Lime", "Gate Glass", "North Apron", "Pier Sand")[index % 4]
    subject = case.say(f"At {location}: could you see if the delivery can pass review? Save a draft if the material is complete.",
                       f"{location} 这车货能不能过审核？资料足够的话先做草稿，莫提交。",
                       f"{location} 来了一车货。Check whether it matches and save a review draft if there is enough evidence.")
    if case.facet == "implicit_intent":
        subject = case.say(f"The dock team at {location} wants to know what to flag before sign-off. Leave your findings in the draft queue.",
                           f"{location} 收货同事想知道签字之前有没有要提醒的地方，请把结论先放到草稿队列。",
                           f"{location} 收货单 about to be signed off. Leave what the supervisor should see in the draft queue.")
    case.task["operator_message"] = subject
    ordered = 3 + index % 17
    price = 250 + index % 9 * 25
    defective = case.facet == "nonroutine"
    delivered = ordered - 1 if defective else ordered
    row_order = {"sku": sku, "unit": "box", "quantity": ordered, "unit_price_minor": price}
    row_note = {**row_order, "quantity": delivered}
    amount = delivered * price
    note = {"order_id": order, "supplier_id": supplier, "currency": "CNY", "lines": [row_note], "total_minor": amount}
    status = case.facet in {"missing_field", "conflicting_evidence", "scope_denied"}
    order_record = {"order_id": order, "supplier_id": supplier, "currency": "CNY",
                    "lines": [row_order], "total_minor": ordered * price, "status": "receivable"}
    case.row("purchase_orders", order, order_record,
             allowed=case.facet != "scope_denied", expected=not status)
    case.row("suppliers", supplier, {"supplier_id": supplier, "qualified": True}, expected=not status)
    case.row("products", sku, {"sku": sku, "unit": "box"}, expected=not status)
    header = case.say(f"Dock log, scanned as text. Reference: {note_id}. Supplier dispatch: {supplier}.",
                      f"码头手写记录的文字版。签收单 {note_id}，供货方代码 {supplier}。",
                      f"签收 note {note_id} from supplier {supplier}。现场手写记录：")
    payload = case.say(f"Unloaded {delivered} boxes of {sku}. They're billed at CNY {price / 100:.2f} a box.",
                       f"卸下 {sku} 共 {delivered} 箱，单价人民币 {price / 100:.2f} 元。",
                       f"{sku} 卸货 {delivered} 箱，billed CNY {price / 100:.2f} per box。")
    amount_text = case.say(f"Total written on the receipt is CNY {amount / 100:.2f}.",
                           f"签收单手写总额人民币 {amount / 100:.2f} 元。", f"票据 total CNY {amount / 100:.2f}。")
    order_text = case.say(f"Dock attached this to order {order}.", f"码头将本签收单挂到采购单 {order}。",
                          f"与 purchase order {order} 对应。")
    if case.facet == "missing_field":
        alternate = case.key("OTHER")
        case.row("purchase_orders", alternate, {**order_record, "order_id": alternate})
        case.attach("dock-notes.txt", "\n".join((header, payload, amount_text)))
        case.stop("clarify", "order_reference_missing")
        return
    if case.facet == "conflicting_evidence":
        alternative = case.key("OTHER")
        case.row("purchase_orders", alternative, {**order_record, "order_id": alternative})
        case.attach("morning-notes.txt", "\n".join((header, payload, amount_text, order_text)))
        other = case.say(f"Second signed note for {note_id}: charge the same delivery to {alternative}.",
                         f"签收单 {note_id} 的第二张已签同日记录，要求相同交货挂至 {alternative}。",
                         f"Another signed record for {note_id} says use {alternative}。")
        case.attach("same-authority-note.txt", other)
        case.stop("clarify", "order_references_conflict")
        return
    if case.facet == "multi_document":
        case.attach("physical-count.txt", "\n".join((header, payload)))
        case.attach("signed-billing-note.txt", "\n".join((order_text, amount_text)))
    elif case.facet == "user_followup":
        obsolete = case.key("OLD")
        case.attach("dock-notes.txt", "\n".join((header, payload, amount_text, f"Order: {obsolete}")))
        case.follow_up(case.say(f"Correction from receiving: the printed order {obsolete} is void. Link to {order} for this review.",
                                f"收货更正：印在签收单上的 {obsolete} 已作废，本次请按 {order} 核对。",
                                f"Void 旧号 {obsolete}。Use {order} for this review。"))
    else:
        case.attach("dock-notes.txt", "\n".join((header, payload, amount_text, order_text)))
    if case.facet == "scope_denied":
        case.stop("refused", "order_access_denied")
        return
    differences = [f"{sku}.quantity", "total_minor"] if defective else []
    recommendation = "ESCALATE" if defective else "MATCH"
    case.world["draft_allowed"] = True
    case.gold.update(disposition="escalated" if defective else "completed", native_input=note,
                     answer={"order_id": order, "recommendation": recommendation, "differences": differences},
                     draft={"order_id": order, "supplier_id": supplier, "skus": [sku],
                            "recommendation": recommendation, "differences": differences, "submitted": False})


def customer(case, index):
    order, alternate, thread = (case.key(prefix) for prefix in ("PO", "ALT", "CHAT"))
    late = index % 2 == 1 or case.facet == "nonroutine"
    subject = "Late delivery" if late else "Delivery status"
    request = case.say(f"Could you draft a follow-up recommendation from chat {thread}? Don't open a ticket yet.",
                       f"看下对话 {thread}，帮我拟个跟进工单建议，先别建工单。",
                       f"Chat {thread} 帮我起个 ticket recommendation，别真的创建。")
    if case.facet == "implicit_intent":
        request = case.say(f"Could support work out the next thing to tell the customer in {thread}?",
                           f"客服看一下 {thread}，这客户下一步该怎么跟进？",
                           f"Support 下一步怎么回 chat {thread}? Give me the proposed follow-up.")
    case.task["operator_message"] = request
    complaint = (case.say("They promised it yesterday and I still haven't got the parcel.",
                          "说好昨天到的，包裹到现在没影。", "ETA was yesterday，包裹还没影。") if late else
                 case.say("Just putting it out there: can someone say where my parcel is?",
                          "想问一下我那个包裹现在到哪儿了。", "My parcel 呢？想查下进度。"))
    order_line = case.say(f"My signed receipt has {order} next to my purchase.", f"我的购买回执写的是 {order}。",
                          f"我的 receipt 上单号 {order}。")
    denied = case.facet == "scope_denied"
    stop = denied or case.facet in {"missing_field", "conflicting_evidence"}
    order_record = {"order_id": order, "delivery_status": "overdue" if late else "in_transit"}
    case.row("purchase_orders", order, order_record, allowed=not denied, expected=not stop)
    if case.facet in {"missing_field", "conflicting_evidence"}:
        case.row("purchase_orders", alternate, {**order_record, "order_id": alternate})
    if case.facet == "missing_field":
        case.attach("customer-chat.txt", f"{thread}\n{complaint}")
        case.stop("clarify", "order_reference_missing")
    elif case.facet == "conflicting_evidence":
        other = case.say(f"Customer: my receipt also says {alternate}; I don't know which is affected.",
                         f"客户：另一张回执写着 {alternate}，我也不知道是哪个订单。",
                         f"另一张 receipt says {alternate}，不确定哪个包裹。")
        case.attach("customer-chat.txt", f"{thread}\n{complaint}\n{order_line}\n{other}")
        case.stop("clarify", "order_references_conflict")
    elif case.facet == "multi_document":
        case.attach("customer-chat.txt", f"{thread}\n{complaint}")
        case.attach("receipt-transcript.txt", order_line)
    elif case.facet == "user_followup":
        case.attach("customer-chat.txt", f"{thread}\n{complaint}\nOrder {alternate}")
        case.follow_up(case.say(f"The customer corrected the order reference to {order}. Use that order instead of {alternate}.",
                                f"客户更正了单号，改用 {order}，不用 {alternate}。",
                                f"Receipt corrected to {order}，旧号 {alternate} ignore。"))
    else:
        case.attach("customer-chat.txt", f"{thread}\n{complaint}\n{order_line}")
    if denied:
        case.stop("refused", "order_access_denied")
    if not stop:
        case.gold.update(native_input={"order_id": order, "subject": subject},
                         answer={"order_id": order, "subject": subject,
                                 "priority": "high" if late else "normal", "status": "recommended"})


def product(case, index):
    sku, reference = (case.key(prefix) for prefix in ("SKU", "REQ"))
    site, other = ("east", "west") if index % 2 else ("north", "south")
    units = ("case", "box", "pallet")[index % 3]
    available = 0 if case.facet == "nonroutine" else 1 + index * 7 % 83
    denied = case.facet == "scope_denied"
    stop = denied or case.facet in {"missing_field", "conflicting_evidence"}
    case.task["operator_message"] = case.say(
        f"Can we tell planning what we actually have for {reference}? Give the unit and available quantity at that warehouse.",
        f"排产在问 {reference} 实际能用多少，给仓点的单位和可用数。",
        f"Planning 问 {reference} 货有多少。Give unit and available quantity at the requested warehouse.")
    if case.facet == "implicit_intent":
        case.task["operator_message"] = case.say(
            f"Planning keeps saying '{reference}, ready to pick?' A quick stock check would settle it.",
            f"排产反复问 {reference} 能不能拿货，帮忙查一下准备发出的库存。",
            f"Planning 想知道 {reference} ready to pick 没，查可用库存。")
    case.row("products", sku, {"sku": sku, "unit": units}, allowed=not denied, expected=not stop)
    inventory = f"{sku}|{site}"
    case.row("inventory", inventory, {"available": available}, allowed=not denied, expected=not stop)
    case.row("inventory", f"{sku}|{other}", {"available": available + 9}, allowed=not denied)
    about = case.say(f"Pick chat {reference}: the sticker says {sku}. ", f"备货消息 {reference}：标签上写着 {sku}。",
                     f"Pick chat {reference}：标签 {sku}。")
    location = case.say(f"We need {site} warehouse stock for this.", f"这次看 {site} 仓的现货。", f"Check {site} 仓库存。")
    if case.facet == "missing_field":
        case.attach("pick-chat.txt", about)
        case.stop("clarify", "warehouse_missing")
    elif case.facet == "conflicting_evidence":
        ambiguity = case.say(f"A separate message of the same age reserves the request for {other}; neither was marked final.",
                             f"同时收到另一条消息要求查 {other} 仓，两条都没有确认。",
                             f"同一时间另一条 says {other}，neither confirmed。")
        case.attach("pick-chat.txt", about + location)
        case.attach("dispatch-chat.txt", ambiguity)
        case.stop("clarify", "warehouses_conflict")
    elif case.facet == "multi_document":
        case.attach("label-transcript.txt", about)
        case.attach("planning-request.txt", location)
    elif case.facet == "user_followup":
        case.attach("pick-chat.txt", about + f"Warehouse from earlier note: {other}.")
        case.follow_up(case.say(f"I switched this check to {site} warehouse. Use the new warehouse.",
                                f"我把这次库存核对改到 {site} 仓，以新仓为准。",
                                f"改查 {site} 仓。Use this new warehouse。"))
    else:
        case.attach("pick-chat.txt", about + location)
    if denied:
        case.stop("refused", "product_access_denied")
    if not stop:
        case.gold.update(native_input={"sku": sku, "warehouse": site},
                         answer={"sku": sku, "warehouse": site, "unit": units, "available": available})


def fixtures():
    for category_index, (category, prefix, family) in enumerate(zip(CATEGORIES, ("DOC", "CUS", "PRD"),
                                                                   (document, customer, product))):
        for index in range(200):
            case = Fixture(prefix, category, index, LANGUAGES[(index + category_index) % len(LANGUAGES)])
            family(case, index)
            yield case.freeze()


def generate(output):
    cases = list(fixtures())
    plans = [case.plan for case in cases]
    files = dict(zip(FILES, (canonical(plans),
                             b"".join(canonical(case.task) for case in cases),
                             b"".join(canonical(case.world) for case in cases),
                             b"".join(canonical(case.expected) for case in cases),
                             canonical(repeat_selection(plans)), canonical(experiment_contract()))))
    hashes = {filename: sha256(raw).hexdigest() for filename, raw in files.items()}
    manifest = {"version": "JOB-V1", "split": "independent_synthetic_holdout", "case_count": 600,
                "sha256": hashes, "freeze_sha256": digest(hashes)}
    output.mkdir(parents=True, exist_ok=True)
    for filename, raw in files.items():
        (output / filename).write_bytes(raw)
    (output / "manifest.json").write_bytes(canonical(manifest))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT)
    generate(parser.parse_args().output)
