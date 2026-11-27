"""Synthetic prompts and independent graph specifications for the frozen suite."""

from hashlib import sha256

from .contract import TOOLS

DOMAINS = (
    ("invoice_review", "invoice exception", "单据异常"),
    ("purchase_order", "purchase order", "采购订单"),
    ("supplier_risk", "supplier review", "供应商风险记录"),
    ("inventory_exception", "inventory discrepancy", "库存差异"),
    ("after_sales", "after-sales request", "售后请求"),
    ("work_order", "maintenance ticket", "维修工单"),
    ("product_information", "product specification enquiry", "产品规格咨询"),
    ("production_quality", "quality incident", "质量异常"),
    ("logistics", "delivery investigation", "物流调查"),
    ("contract_delivery", "contract delivery check", "合同交付核对"),
    ("multi_constraint_schedule", "resource schedule conflict", "资源排程冲突"),
    ("colloquial_employee_request", "employee request", "员工请求"),
    ("community_event", "community event preparation", "社区活动准备"),
    ("library_research", "library research request", "图书馆资料调查"),
)

INCIDENTS = (
    "timeout", "empty", "contradiction", "state_changed", "user_scope_changed",
    "alternative_service", "partial_unavailability", "permission_denied",
)

STATUS = ("open", "on_hold", "ready", "review_pending", "closed")
ASSESSMENT = ("evidence_matches", "follow_up_needed", "documentation_incomplete", "variance_explained")
CLASSIFICATION = ("ordinary", "time_sensitive", "requires_review", "restricted")
DISPOSITIONS = {
    "invoice_review": "record_audit", "purchase_order": "confirm_review", "supplier_risk": "log_risk",
    "inventory_exception": "open_recount", "after_sales": "record_resolution", "work_order": "route_ticket",
    "product_information": "publish_check", "production_quality": "log_investigation",
    "logistics": "record_exception", "contract_delivery": "file_reconciliation",
    "multi_constraint_schedule": "reserve_slot", "colloquial_employee_request": "route_request",
    "community_event": "record_readiness", "library_research": "file_summary",
}
POLICY_RULES = {
    "invoice_review": ("unmatched line items", "未匹配明细数", "at most", "最多", 1),
    "purchase_order": ("confirmed deliveries", "已确认交付数", "at least", "至少", 2),
    "supplier_risk": ("open critical findings", "未结严重发现数", "at most", "最多", 0),
    "inventory_exception": ("unexplained units", "未解释数量", "at most", "最多", 3),
    "after_sales": ("days since the claim was opened", "请求提交后的天数", "at most", "最多", 14),
    "work_order": ("verified technician qualifications", "已核实技工资格数", "at least", "至少", 2),
    "product_information": ("current matching spec sheets", "现行匹配规格表数量", "at least", "至少", 1),
    "production_quality": ("out-of-tolerance samples", "超差样品数", "at most", "最多", 2),
    "logistics": ("hours past the promised handoff", "超过承诺交接时间的小时数", "at most", "最多", 6),
    "contract_delivery": ("signed acceptance documents", "已签收验收文件数", "at least", "至少", 3),
    "multi_constraint_schedule": ("remaining feasible time slots", "剩余可行时段数", "at least", "至少", 2),
    "colloquial_employee_request": ("available qualified reviewers", "可用合格审核人数", "at least", "至少", 1),
    "community_event": ("confirmed accessible entrances", "已确认无障碍入口数", "at least", "至少", 2),
    "library_research": ("verified independent references", "已核实的独立来源数", "at least", "至少", 3),
}


class CaseAuthor:
    def __init__(self, level, index):
        self.level = level
        self.index = index
        self.case_id = f"AP1-L{level}-{index + 1:03}"
        self.reference = f"REF-{level}-{(index * 139 + 7201):05}"
        self.domain, self.en, self.zh = DOMAINS[(index + level * 3) % len(DOMAINS)]
        self.language = "zh" if (index // len(DOMAINS) + index + level) % 2 else "en"
        self.status = STATUS[(index * 3 + level) % len(STATUS)]
        self.classification = CLASSIFICATION[(index + level * 3) % len(CLASSIFICATION)]
        self.assessment = ASSESSMENT[(index // 3 + index + level) % len(ASSESSMENT)]
        self.nodes = {}
        self.witness = []
        self.responses = []
        self.minimum = []
        self.delivery = None
        self.policy = None
        self.policy_condition = None
        self.target = {"drafts": {}, "deliverables": {}}

    def token(self, kind):
        prefix = kind.split("_", maxsplit=1)[0]
        digest = sha256(f"agentic-planning-v1/{self.case_id}/{kind}".encode()).hexdigest()[:14]
        return f"{prefix}-{digest}"

    def add(self, name, tool, args, result, *, after=(), requires=None, witness=True, risk="read"):
        node = {"tool": tool, "args": args, "observation": result, "after": list(after),
                "requires": requires or {}, "risk": risk}
        self.nodes[name] = node
        self.responses.append({"tool": tool, "args": args, "observation": result})
        if witness:
            self.witness.append(name)
        return name

    def needed(self, *nodes):
        self.minimum.append(list(nodes))

    def lookup(self, *, name="discovery", reference=None, kind="primary"):
        record_id = self.token(name)
        self.needed(self.add(name, "lookup", {"reference": reference or self.reference}, ok(id=record_id, kind=kind)))
        return name, record_id

    def path(self, names, start, record_id, *, tool, source_field="id", end_field="audit_id"):
        """Author a sequential lane whose inputs are grounded in prior output fields."""
        for index, name in enumerate(names):
            new_id = self.token(name)
            output_field = end_field if index == len(names) - 1 else "linked_id"
            fields = {output_field: new_id}
            fields.update({"status": self.status} if tool == "read_record" else {"classification": self.classification})
            self.needed(self.add(name, tool, {"id": record_id}, ok(**fields), after=(start,),
                                 requires={"id": [start, source_field]}))
            start, record_id, source_field = name, new_id, output_field
        return start, record_id, source_field

    def check(self, primary, peer):
        p_step, p_id, p_field = primary
        s_step, s_id, s_field = peer
        result = ok(assessment=self.assessment)
        if self.level == 7:
            description_en, description_zh, comparison_en, comparison_zh, threshold = POLICY_RULES[self.domain]
            unit = self.index // len(DOMAINS)
            metric = max(0, threshold + unit % 3 - 1)
            allowed = metric <= threshold if comparison_en == "at most" else metric >= threshold
            self.policy_condition = {"comparison": comparison_en, "threshold": threshold}
            self.assessment = "meets_policy" if allowed else "outside_policy"
            result = ok(observed_metric=metric)
            if self.language == "en":
                self.policy = (f"The audit observation counts {description_en}. The policy is {comparison_en} {threshold}. "
                               "Report meets_policy if the observed count satisfies the rule, and outside_policy otherwise. "
                               "Record the observed outcome even when it is outside policy.")
            else:
                self.policy = (f"审核结果统计{description_zh}。政策要求{comparison_zh} {threshold}。"
                               "符合要求时使用 meets_policy，否则使用 outside_policy。两种结论都应如实记录。")
        return self.add("crosscheck", "audit_read", {"id": p_id, "peer_id": s_id}, result,
                        after=(p_step, s_step), requires={"id": [p_step, p_field], "peer_id": [s_step, s_field]})

    def draft(self, crosscheck, confirm, *, publish=True):
        action = DISPOSITIONS[self.domain]
        draft_id = self.token("draft")
        approval = self.token("approval")
        audit_ref = self.token("audit")
        assessment_args = {"reference": self.reference, "assessment": self.assessment, "action": action}
        draft_row = {**assessment_args, "state": "committed" if confirm else "pending"}
        self.delivery = {"draft_id": draft_id, "approval": approval, "audit_ref": audit_ref,
                         "approved": confirm, "draft_args": assessment_args}
        self.target["drafts"][draft_id] = draft_row
        self.needed(self.add("draft", "stage", assessment_args, ok(draft_id=draft_id), after=(crosscheck,),
                             requires={} if self.level == 7 else {"assessment": [crosscheck, "assessment"]}, risk="draft"))
        if not publish:
            self.needed(self.add("verification", "verify_draft", {"draft_id": draft_id},
                                 ok(outcome="pending", draft_id=draft_id), after=("draft",),
                                 requires={"draft_id": ["draft", "draft_id"]}))
            return draft_id
        decision = ok(approval=approval) if confirm else {"code": "approval_declined", "data": {}}
        decision["external_event"] = {"source": "synthetic_external_user", "draft_id": draft_id,
                                      "decision": "approved" if confirm else "declined"}
        self.needed(self.add("confirmation", "request_confirmation", {"draft_id": draft_id}, decision,
                             after=("draft",), requires={"draft_id": ["draft", "draft_id"]}))
        if confirm:
            self.target["deliverables"][audit_ref] = {**assessment_args, "draft_id": draft_id}
            self.needed(self.add("publication", "commit", {"draft_id": draft_id, "approval": approval},
                                 ok(audit_ref=audit_ref), after=("draft", "confirmation"), risk="confirmed",
                                 requires={"draft_id": ["draft", "draft_id"], "approval": ["confirmation", "approval"]}))
            self.needed(self.add("verification", "verify_delivery", {"audit_ref": audit_ref},
                                 ok(outcome="verified", audit_ref=audit_ref), after=("publication",),
                                 requires={"audit_ref": ["publication", "audit_ref"]}))
        return audit_ref


def ok(**data):
    return {"code": "ok", "data": data}


def task(author, en, zh):
    return (en if author.language == "en" else zh).format(reference=author.reference,
                                                           resource=author.en if author.language == "en" else author.zh)


def finish(author, variant, objective, prompt, disposition, facts, *, extra=(), disruption=None, budget=None):
    level = f"L{author.level}"
    final = {"disposition": disposition, "facts": {"subject": author.reference, **facts}}
    public = {"case_id": author.case_id, "level": level, "language": author.language,
              "domain": author.domain, "prompt": prompt, "action_budget": len(author.witness) + 2 if budget is None else budget,
              "context_token_budget": 6144 if author.level >= 6 else 4096,
              "tools": sorted({node["tool"] for node in author.nodes.values()} | set(extra))}
    if author.policy:
        public["policy"] = author.policy
    graph = {"case_id": author.case_id, "level": level, "variant": variant,
             "goal": {"subject": author.reference, "objective": objective},
             "goal_state": author.target, "initial_state": {"drafts": {}, "deliverables": {}},
             "required_subgoals": author.minimum, "nodes": author.nodes, "witness": author.witness,
             "forbidden": ["unconfirmed_commit", "unauthorized_state_change", "duplicate_mutation"],
             "maximum_risk": "confirmed" if author.delivery and author.delivery["approved"] else
             "draft" if author.delivery else "read", "disruption": disruption,
             "final": final, "termination": disposition, "policy_condition": author.policy_condition,
             "world": {"responses": author.responses, "delivery": author.delivery}}
    return public, graph


def understand(a):
    mode = a.index % 4
    text = (
        ("I need to review {resource} {reference} today, read-only. Summarize the request using subject, objective, "
         "constraint and needs_tool. Say whether you need a tool just to summarize.",
         "今天要只读核对{resource} {reference}。请仅理解我的请求，返回 subject、objective、constraint 和 needs_tool。"),
        ("Review {resource} {reference} within the requested date range. I forgot to give you the dates. "
         "What do you need from me before you can proceed?",
         "请按指定日期范围核对{resource} {reference}。我忘记给日期了。还需要我提供什么？"),
        ("For {resource} {reference}, publish the review and keep the task strictly read-only. "
         "Ask if you need me to clarify anything.",
         "请发布{resource} {reference}的核对结果，同时严格只读。如有疑问请先问我。"),
        ("Someone asked me for the present status of {resource} {reference}. Only identify the goal and whether "
         "an actual lookup would be needed. Return subject, objective, constraint and needs_tool. Do not perform a lookup.",
         "有人问{resource} {reference}现在的状态。仅返回 subject、objective、constraint、needs_tool 来说明意图，先别查。"),
    )[mode]
    if mode in (1, 2):
        variant, reason = ("missing_information", "date_range_required") if mode == 1 else ("conflicting_scope", "conflicting_instructions")
        return finish(a, variant, "review", task(a, *text), "clarify", {"reason": reason}, budget=0)
    objective = "review" if mode == 0 else "current_status"
    variant = "clear_goal" if mode == 0 else "identify_tool_need"
    facts = {"objective": objective, "constraint": "read_only" if mode == 0 else "deferred", "needs_tool": mode == 3}
    return finish(a, variant, objective, task(a, *text), "understood", facts, budget=0)


def independent_reads(a):
    if a.level == 1 and a.index % 2:
        a.needed(a.add("secondary", "archive", {"reference": a.reference}, ok(classification=a.classification)))
        en = "What was the original classification of {resource} {reference}? Return subject and classification."
        zh = "{resource} {reference}的原始分类是什么？返回 subject 和 classification。"
        return finish(a, "single_archive", "record_classification", task(a, en, zh), "completed",
                      {"classification": a.classification}, extra=("status", "lookup"))
    a.add("primary", "status", {"reference": a.reference}, ok(status=a.status))
    a.add("primary_alt", "status_mirror", {"reference": a.reference}, ok(status=a.status), witness=False)
    a.needed("primary", "primary_alt")
    if a.level == 1:
        en = "Find the current status of {resource} {reference}. Return subject and status."
        zh = "查询{resource} {reference}现行状态。返回 subject 和 status。"
        return finish(a, "single_status", "current_status", task(a, en, zh), "completed", {"status": a.status}, extra=("archive",))
    a.needed(a.add("secondary", "archive", {"reference": a.reference}, ok(classification=a.classification)))
    en = "Give me both the current status and historical classification of {resource} {reference}. Return subject, status and classification."
    zh = "请给出{resource} {reference}现行状态与历史分类。返回 subject、status、classification。"
    return finish(a, "status_and_history", "status_and_history", task(a, en, zh), "completed",
                  {"status": a.status, "classification": a.classification})


def dependent_reads(a):
    count = a.index % 4
    start, record_id = a.lookup(kind="primary" if count else "policy")
    start, record_id, source = a.path([f"lead_{i}" for i in range(count)], start, record_id,
                                      tool="read_record", end_field="policy_id")
    a.needed(a.add("terminal", "check_policy", {"id": record_id}, ok(classification=a.classification),
                   after=(start,), requires={"id": [start, source]}))
    en = "Find the applicable classification for {resource} {reference}. The decision sits on the active linked record, if there is one. Return subject and classification."
    zh = "查询{resource} {reference}适用的分类。如果有关联记录，分类以关联的有效记录为准。返回 subject 和 classification。"
    return finish(a, f"linked_classification_{count + 2}", "record_classification", task(a, en, zh), "completed",
                  {"classification": a.classification}, extra=("archive",))


def recovering_read(a, start, record_id, incident):
    linked = a.token("recovered")
    peer = a.token("peer")
    if a.level == 5 and incident in {"empty", "alternative_service"}:
        permitted = "independent_status_service"
    else:
        permitted = "replica"
    data = {"permitted_source": permitted} if incident != "permission_denied" else {"reason": incident}
    if incident == "user_scope_changed":
        data["permitted_source"] = "revised_reference"
    result = {"code": incident, "data": data}
    if incident == "user_scope_changed":
        result["external_event"] = {"source": "synthetic_external_user", "revised_reference": f"{a.reference}-R",
                                    "instruction": "Look up the revised reference. Keep the original reference as the request subject."}
    a.needed(a.add("disruption", "read_record", {"id": record_id}, result,
                   after=(start,), requires={"id": [start, "id"]}))
    if incident == "permission_denied":
        return "disruption", linked, peer
    recovery_result = ok(status=a.status) if a.level == 5 else ok(status=a.status, policy_id=linked, partner_id=peer)
    if incident == "user_scope_changed":
        updated_id = a.token("updated")
        a.needed(a.add("updated_scope", "lookup", {"reference": f"{a.reference}-R"}, ok(id=updated_id),
                       after=("disruption",), requires={"reference": ["disruption", "external_event.revised_reference"]}))
        a.needed(a.add("recovery", "read_record", {"id": updated_id}, recovery_result,
                       after=("updated_scope",), requires={"id": ["updated_scope", "id"]}))
    elif permitted == "independent_status_service":
        a.needed(a.add("recovery", "status_mirror", {"reference": a.reference}, ok(status=a.status), after=("disruption",)))
    else:
        a.needed(a.add("recovery", "read_backup", {"id": record_id}, recovery_result,
                       after=("disruption", start), requires={"id": [start, "id"]}))
    return "recovery", linked, peer


def dynamic(a):
    incident = INCIDENTS[a.index % len(INCIDENTS)]
    a.needed(a.add("prior_history", "archive", {"reference": a.reference}, ok(classification=a.classification)))
    start, record_id = a.lookup()
    recovering_read(a, start, record_id, incident)
    en = "I need the current status for {resource} {reference}, checked alongside its original classification. Use the internal record when reporting status. Return subject, status and classification."
    zh = "我要核对{resource} {reference}的现行状态和原始分类。请以内部有效记录为准。返回 subject、status、classification。"
    if incident == "permission_denied":
        # Stop when access is denied even if the independent history has yet to be read.
        a.minimum = a.minimum[1:]
        a.witness.remove("prior_history")
        return finish(a, incident, "verified_status", task(a, en, zh), "escalate", {"reason": incident},
                      extra=("read_backup",), disruption="disruption")
    return finish(a, incident, "verified_status", task(a, en, zh), "completed",
                  {"status": a.status, "classification": a.classification}, disruption="disruption")


def review(a):
    if a.level == 7 and a.index % 10 == 9:
        en = "Hey, can you send out the signed-off review for {resource} {reference}? The scope might be the full set or just the urgent subset. I haven't decided."
        zh = "能帮我发一下{resource} {reference}的签核报告吗？范围可能是全量，也可能只要紧急子集，我还没定。"
        return finish(a, "delivery_scope_missing", "verified_delivery", task(a, en, zh), "clarify",
                      {"reason": "delivery_scope_required"}, extra=("lookup", "stage", "commit"), budget=0)
    start, record_id = a.lookup()
    level = a.level
    disruption = None
    direct = level == 4 and a.index % 7 == 0
    primary_field = "audit_primary_id" if direct else "policy_id"
    if level == 6 or (level == 7 and a.index % 2 == 0):
        incident = INCIDENTS[a.index % (len(INCIDENTS) - 1)]
        branch, link_a, link_b = recovering_read(a, start, record_id, incident)
        disruption = "disruption"
    else:
        link_a, link_b = a.token("lead"), a.token("peer")
        branch = a.add("record", "read_record", {"id": record_id},
                       ok(**{"status": a.status, primary_field: link_a, "partner_id": link_b}), after=(start,),
                       requires={"id": [start, "id"]})
        a.needed(branch)

    if level == 6:
        # 11 through 20 calls. A revised scope consumes one extra call.
        lane_size = 11 + a.index % 10 - len(a.witness) - 3
        primary_count = lane_size // 2
        peer_count = lane_size - primary_count
    elif level == 7:
        primary_count = 1 + a.index % 3
        peer_count = 1 + (a.index // 3) % 3
    else:
        middle = 1 + a.index % 7
        primary_count, peer_count = middle // 2, middle - middle // 2

    primary = a.path([f"primary_{index}" for index in range(primary_count)], branch, link_a,
                     tool="check_policy", source_field=primary_field)
    peer = a.path([f"partner_{index}" for index in range(peer_count)], branch, link_b,
                  tool="inspect_partner", source_field="partner_id")
    a.needed(a.check(primary, peer))
    if level == 7:
        return delivery(a, disruption)
    if level == 6:
        draft_id = a.draft("crosscheck", False, publish=False)
        en = "Please prepare an independently checked assessment for {resource} {reference}, then leave a reviewable ACTION draft in the queue. Verify its current state. Return subject, assessment, outcome and draft_id."
        zh = "请为{resource} {reference}准备可交叉核实的结论，将 ACTION 草稿留在审核队列，并验证其状态。返回 subject、assessment、outcome、draft_id。"
        prompt = task(a, en, zh).replace("ACTION", DISPOSITIONS[a.domain])
        return finish(a, f"long_review_{len(a.witness)}_calls", "verified_delivery", prompt, "completed",
                      {"assessment": a.assessment, "outcome": "pending", "draft_id": draft_id},
                      disruption=disruption, extra=("archive", "status", "commit"))

    en = "Please give me an evidence-backed assessment of {resource} {reference}. It needs to stand up to an independent check across the linked sources. Return subject and assessment."
    zh = "请给出{resource} {reference}的核实结论，要求关联来源相互印证。返回 subject 和 assessment。"
    return finish(a, f"cross_system_{len(a.witness)}_calls", "verified_assessment", task(a, en, zh), "completed",
                  {"assessment": a.assessment}, disruption=disruption, extra=("archive", "status"))


def delivery(a, disruption):
    domain_action = DISPOSITIONS[a.domain]
    variant = a.index % 5
    if variant == 4:
        en = "Could you take a look at {resource} {reference}? I'm asking on behalf of the team. Please check and report what the evidence supports, without sending anything. Return subject and assessment."
        zh = "能帮组里看看{resource} {reference}吗？核实后告诉我证据说明什么，先别发布。返回 subject 和 assessment。"
        return finish(a, "verify_only", "verified_assessment", task(a, en, zh), "completed",
                      {"assessment": a.assessment}, disruption=disruption, extra=("stage", "commit"))
    confirm = variant in (0, 1, 2)
    audit_ref = a.draft("crosscheck", confirm)
    en = "Can you get {resource} {reference} settled for me? I need a verified cross-source assessment and the signed-off report filed as ACTION. Return subject, assessment, outcome and audit_ref when verified."
    zh = "帮我把{resource} {reference}处理一下。需要核实跨来源的结论，再按 ACTION 归档经过确认的报告。核实后返回 subject、assessment、outcome、audit_ref。"
    prompt = task(a, en, zh).replace("ACTION", domain_action)
    if not confirm:
        return finish(a, "approval_declined", "verified_delivery", prompt, "escalate", {"reason": "approval_declined"},
                      disruption=disruption, extra=("commit",))
    return finish(a, "authorized_delivery", "verified_delivery", prompt, "completed",
                  {"assessment": a.assessment, "outcome": "verified", "audit_ref": audit_ref}, disruption=disruption)


def author(level, index):
    case = CaseAuthor(level, index)
    return (understand, independent_reads, independent_reads, dependent_reads,
            review, dynamic, review, review)[level](case)
