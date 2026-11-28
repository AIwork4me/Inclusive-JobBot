"""Batch C task families, C17-C24 (IJ-NANO-1.3S N03-B2).

Executable typed task worlds with explicit preconditions/effects. Plan
validity is established by SIMULATION against the goal predicate - never by
equality with a preferred sequence, so alternative valid plans score
correctly. Ground truth is public-recomputable (C17/C18/C20/C21 partially,
C23/C24) or construction-authored with independent rule tables (C22).
"""
from __future__ import annotations

from .core import Family

# -- mini world engine (typed slots; equality preconditions) ----------------
def simulate(state: dict, actions: dict, plan: list[str]):
    """Returns (ok, final_state, failure_index). Preconditions are equality
    checks on declared slots; effects are assignments."""
    st = dict(state)
    for i, step in enumerate(plan):
        spec = actions.get(step)
        if spec is None or any(st.get(k) != v for k, v in
                               spec.get("pre", {}).items()):
            return False, st, i
        for k, v in spec["eff"].items():
            st[k] = v
    return True, st, None


def goal_holds(state: dict, goal: dict) -> bool:
    return all(state.get(k) == v for k, v in goal.items())


# world definitions: three distinct worlds, each with typed state semantics
_WORLDS_C = {
    "orderflow": {
        "init": {"stage": "cart", "paid": False, "reserved": False,
                 "shipped": False},
        "goal": {"shipped": True, "paid": True},
        "actions": {
            "reserve_items": {"pre": {"stage": "cart"},
                              "eff": {"reserved": True, "stage": "reserved"}},
            "take_payment": {"pre": {"reserved": True},
                             "eff": {"paid": True, "stage": "paid"}},
            "dispatch_parcel": {"pre": {"paid": True},
                                "eff": {"shipped": True, "stage": "shipped"}},
            "email_receipt": {"pre": {"paid": True},
                              "eff": {"notified": True}},
            "restock_items": {"pre": {"stage": "cart"},
                              "eff": {"stage": "restocked"}}}},
    "devops": {
        "init": {"service": "degraded", "config_loaded": False,
                 "cache_cleared": False, "deployed": "v1"},
        "goal": {"service": "healthy", "deployed": "v2"},
        "actions": {
            "clear_cache": {"pre": {"service": "degraded"},
                            "eff": {"cache_cleared": True}},
            "load_config": {"pre": {"cache_cleared": True},
                            "eff": {"config_loaded": True}},
            "deploy_v2": {"pre": {"config_loaded": True},
                          "eff": {"deployed": "v2"}},
            "restart_service": {"pre": {"deployed": "v2"},
                                "eff": {"service": "healthy"}},
            "rollback_v1": {"pre": {},
                            "eff": {"deployed": "v1"}},
            "scale_replicas": {"pre": {"service": "healthy"},
                               "eff": {"replicas": 4}}}},
    "labflow": {  # confirmation world
        "init": {"sample": "received", "labeled": False, "measured": False,
                 "reported": False},
        "goal": {"reported": True, "measured": True},
        "actions": {
            "label_sample": {"pre": {"sample": "received"},
                             "eff": {"labeled": True}},
            "run_assay": {"pre": {"labeled": True},
                          "eff": {"measured": True, "sample": "assayed"}},
            "write_report": {"pre": {"measured": True},
                             "eff": {"reported": True}},
            "archive_sample": {"pre": {"measured": True},
                               "eff": {"sample": "archived"}},
            "quarantine_sample": {"pre": {"sample": "received"},
                                  "eff": {"sample": "quarantined"}}}},
}


_LEGAL_CHAIN = {
    "orderflow": ["reserve_items", "take_payment", "dispatch_parcel"],
    "devops": ["clear_cache", "load_config", "deploy_v2",
               "restart_service"],
    "labflow": ["label_sample", "run_assay", "write_report"],
}


def _legal_prefix(world_key: str, seq: int) -> list[str]:
    return _LEGAL_CHAIN[world_key][:seq % 3]


def _public_actions(actions: dict) -> dict:
    return {name: {"preconditions": dict(s.get("pre", {})),
                   "effects": dict(s["eff"])}
            for name, s in actions.items()}


# ---------------------------------------------------------------- C17 ----
def _c17_state(fam_id, world_key, split, predicates):
    w = _WORLDS_C[world_key]

    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        # vary the observed state by applying a legal prefix
        steps = _legal_prefix(world_key, seq)
        ok, state, _ = simulate(w["init"], w["actions"], steps)
        assert ok
        preds = [{"predicate": p, "slot": s, "op": "==", "value": v}
                 for (p, s, v) in predicates]
        truth = [state.get(pr["slot"]) == pr["value"] for pr in preds]
        if language == "en":
            instr = ("For each queried predicate, judge whether it holds in "
                     "the state. Report true/false per predicate id.")
        else:
            instr = "判断每个查询谓词在当前状态下是否成立，按谓词编号输出真假。"
        return {"public": {"state": state, "predicates": preds,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"truth": truth},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C17",
                  world=f"{world_key}_world", split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ['{"P1": true, "P2": false}'],
                             "negative": ["predicate judged from the "
                                          "INITIAL state after transitions",
                                          "predicate invented outside the "
                                          "query set"]})


C17_FAMILIES = [
    _c17_state("orderstate", "orderflow", "development",
               [("P1", "paid", False), ("P2", "reserved", True),
                ("P3", "shipped", False)]),
    _c17_state("svcstate", "devops", "development",
               [("P1", "cache_cleared", False), ("P2", "deployed", "v1"),
                ("P3", "service", "degraded")]),
    _c17_state("labstate", "labflow", "confirmation",
               [("P1", "labeled", False), ("P2", "measured", False),
                ("P3", "reported", False)]),
]

# ---------------------------------------------------------------- C18 ----
def _c18_deps(fam_id, world_key, split):
    w = _WORLDS_C[world_key]

    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        names = sorted(w["actions"])[:4 + seq % 2]
        edges = []
        for a in names:
            for b in names:
                if a == b:
                    continue
                eff = set(w["actions"][a]["eff"])
                pre = set(w["actions"][b].get("pre", {}))
                if eff & pre:
                    edges.append([a, b])
        edges.sort()
        if language == "en":
            instr = ("Given action preconditions and effects, list every "
                     "direct dependency edge 'a before b' where an effect "
                     "of a is a precondition of b.")
        else:
            instr = ("根据动作的前置条件与效果，列出所有直接依赖边"
                     "'a before b'（a的某效果是b的前置条件）。")
        return {"public": {"actions": _public_actions(
                    {n: w["actions"][n] for n in names}),
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"edges": edges},
                "alternatives": ["edge order within the list irrelevant"]}
    return Family(family_id=fam_id, primitive="C18",
                  world=f"{world_key}_world", split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": [["reserve_items", "take_payment"]],
                             "negative": [["clear_cache", "deploy_v2"],
                                          "cycle among independent "
                                          "actions"]})


C18_FAMILIES = [
    _c18_deps("orderdeps", "orderflow", "development"),
    _c18_deps("svcdeps", "devops", "development"),
    _c18_deps("labdeps", "labflow", "confirmation"),
]

# ---------------------------------------------------------------- C19 ----
def _c19_planning(fam_id, world_key, split):
    w = _WORLDS_C[world_key]

    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        # reference plans of varying length, all valid AND goal-reaching
        plans = {
            "orderflow": [["reserve_items", "take_payment",
                           "dispatch_parcel"],
                          ["reserve_items", "take_payment",
                           "dispatch_parcel", "email_receipt"],
                          ["reserve_items", "take_payment",
                           "dispatch_parcel"]],
            "devops": [["clear_cache", "load_config", "deploy_v2",
                        "restart_service"],
                       ["clear_cache", "load_config", "deploy_v2",
                        "restart_service", "scale_replicas"],
                       ["clear_cache", "load_config", "deploy_v2",
                        "restart_service"]],
            "labflow": [["label_sample", "run_assay", "write_report"],
                        ["label_sample", "run_assay", "write_report",
                         "archive_sample"],
                        ["label_sample", "run_assay", "write_report"]]}
        plan = plans[world_key][seq % 3]
        ok, final, _ = simulate(w["init"], w["actions"], plan)
        assert ok and goal_holds(final, w["goal"])
        if language == "en":
            instr = ("Produce an ordered action list that transforms the "
                     "initial state into the goal. Any simulated-valid "
                     "plan reaching the goal is correct.")
        else:
            instr = ("给出将初始状态转变为目标状态的有序动作序列。任何经模拟"
                     "验证合法且达成目标的序列都算正确。")
        return {"public": {"initial_state": w["init"], "goal": w["goal"],
                           "actions": _public_actions(w["actions"]),
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"reference_plan": plan,
                             "must_reach_goal": True},
                "alternatives": ["ANY plan that simulates validly from the "
                                 "initial state and satisfies the goal "
                                 "predicate is CORRECT - the reference "
                                 "plan is one witness, not the answer key"]}
    return Family(family_id=fam_id, primitive="C19",
                  world=f"{world_key}_world", split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ["reserve_items -> take_payment "
                                          "-> dispatch_parcel"],
                             "negative": ["take_payment first (precondition "
                                          "reserved=false fails)",
                                          "plan that never sets shipped"]})


C19_FAMILIES = [
    _c19_planning("orderplan", "orderflow", "development"),
    _c19_planning("svcplan", "devops", "development"),
    _c19_planning("labplan", "labflow", "confirmation"),
]

# ---------------------------------------------------------------- C20 ----
def _c20_branch(fam_id, world_key, split):
    w = _WORLDS_C[world_key]

    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        steps = _legal_prefix(world_key, seq)
        ok, state, _ = simulate(w["init"], w["actions"], steps)
        stable_slot = {"orderflow": ("stage", "cart"),
                       "devops": ("service", "degraded"),
                       "labflow": ("sample", "received")}[world_key]
        branches = [
            {"id": "BR-A", "condition": {"slot": "paid", "op": "==",
                                          "value": False},
             "action": "request_payment"},
            {"id": "BR-B", "condition": {"slot": "paid", "op": "==",
                                          "value": True},
             "action": "send_receipt"},
            {"id": "BR-C", "condition": {"slot": stable_slot[0], "op": "==",
                                          "value": stable_slot[1]},
             "action": "start_over"}]
        holding = [b["id"] for b in branches
                   if state.get(b["condition"]["slot"]) ==
                   b["condition"]["value"]]
        if language == "en":
            instr = ("Select every branch whose condition holds in the "
                     "given state; mutually exclusive branches must not "
                     "both be selected.")
        else:
            instr = "选出条件在给定状态下成立的分支；互斥分支不得同时选中。"
        return {"public": {"state": state, "branches": branches,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"holding": holding},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C20",
                  world=f"{world_key}_world", split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ["BR-A (unpaid state)"],
                             "negative": ["BR-A and BR-B together (mutually "
                                          "exclusive)",
                                          "BR-B while paid=false"]})


C20_FAMILIES = [
    _c20_branch("orderbranch", "orderflow", "development"),
    _c20_branch("svcbranch", "devops", "development"),
    _c20_branch("labbranch", "labflow", "confirmation"),
]

# ---------------------------------------------------------------- C21 ----
def _c21_replan(fam_id, world_key, split):
    w = _WORLDS_C[world_key]

    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        plans = {
            "orderflow": {"orig": ["reserve_items", "take_payment",
                                   "dispatch_parcel"],
                          "prefix": ["reserve_items"],
                          "change": "payment gateway outage resolved; "
                                    "payment retry now possible",
                          "cont": ["take_payment", "dispatch_parcel"]},
            "devops": {"orig": ["clear_cache", "load_config", "deploy_v2",
                                "restart_service"],
                       "prefix": ["clear_cache", "load_config"],
                       "change": "v2 image was rolled back; redeploy "
                                 "required",
                       "cont": ["deploy_v2", "restart_service"]},
            "labflow": {"orig": ["label_sample", "run_assay",
                                 "write_report"],
                        "prefix": ["label_sample"],
                        "change": "assay instrument restarted after "
                                  "calibration loss; rerun required",
                        "cont": ["run_assay", "write_report"]}}
        p = plans[world_key]
        ok, current, _ = simulate(w["init"], w["actions"], p["prefix"])
        assert ok
        ok2, final, _ = simulate(current, w["actions"], p["cont"])
        assert ok2 and goal_holds(final, w["goal"])
        if language == "en":
            instr = ("The original plan was interrupted after the executed "
                     "prefix and the world changed. Emit the continuation "
                     "plan FROM THE CURRENT STATE that reaches the goal. "
                     "Do not re-execute completed steps.")
        else:
            instr = ("原计划在已执行前缀后中断且世界已变化。请给出从当前状态"
                     "出发、能达成目标的后续计划。不要重复已完成的步骤。")
        return {"public": {"original_plan": p["orig"],
                           "executed_prefix": p["prefix"],
                           "change": p["change"],
                           "current_state": current, "goal": w["goal"],
                           "actions": _public_actions(w["actions"]),
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"continuation": p["cont"],
                             "current_state_digest": True},
                "alternatives": ["any simulated-valid continuation from "
                                 "current state reaching the goal without "
                                 "re-executing the prefix is CORRECT"]}
    return Family(family_id=fam_id, primitive="C21",
                  world=f"{world_key}_world", split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ["take_payment -> dispatch_parcel"],
                             "negative": ["reserve_items -> take_payment "
                                          "-> ... (re-executes prefix)",
                                          "plan assuming payment already "
                                          "succeeded"]})


C21_FAMILIES = [
    _c21_replan("orderreplan", "orderflow", "development"),
    _c21_replan("svcreplan", "devops", "development"),
    _c21_replan("labreplan", "labflow", "confirmation"),
]

# ---------------------------------------------------------------- C22 ----
_C22_CODES = ["E_TIMEOUT", "E_AUTH", "E_SCHEMA", "E_NOT_FOUND",
              "E_CONFLICT", "E_RATE"]
_C22_DESC = {"E_TIMEOUT": "the call exceeded its deadline",
             "E_AUTH": "credentials were rejected",
             "E_SCHEMA": "arguments failed schema validation",
             "E_NOT_FOUND": "target entity does not exist",
             "E_CONFLICT": "state conflict on the server",
             "E_RATE": "quota exhausted"}


def _c22_errors(fam_id, world, split, wrapper):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        is_error = seq % 3 != 2                # 2 of 3 are errors
        code = _C22_CODES[seq % len(_C22_CODES)]
        if is_error:
            err = {"error": {"code": code,
                             "message": _C22_DESC[code]}}
            doc = {"http_status": 200, "body": err} if wrapper else err
            detail = {"en": f"The tool failed: {_C22_DESC[code]}.",
                      "zh": f"工具调用失败：{_C22_DESC[code]}。"}
        else:
            doc = {"http_status": 200, "body": {"result": "ok",
                                                "items": seq % 3 + 1}}
            detail = {"en": "The tool returned results.",
                      "zh": "工具返回了结果。"}
            code = None
        catalog = {c: _C22_DESC[c] for c in _C22_CODES}
        if language == "en":
            instr = ("Classify the tool response: is it an error, and if "
                     "so which catalog code? A 200 status does NOT clear "
                     "an error envelope inside the body.")
        else:
            instr = ("判断该工具响应是否为错误；若是，给出目录中的错误码。"
                     "HTTP 200 不能清除响应体内的错误封套。")
        return {"public": {"response": doc, "error_catalog": catalog,
                           "instruction": instr,
                           "context": detail[language]},
                "difficulty": difficulty,
                "expected": {"is_error": is_error, "code": code,
                             "construction": {"wrapper": wrapper}},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C22", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ['{"is_error": true, '
                                          '"code": "E_TIMEOUT"}',
                                          '{"is_error": false}'],
                             "negative": ["valid data flagged as error",
                                          "error body treated as results "
                                          "(the masking failure)"]})


C22_FAMILIES = [
    _c22_errors("bare", "helpdesk", "development", False),
    _c22_errors("wrapped", "retail_ops", "development", True),
    _c22_errors("deep", "finance_backoffice", "confirmation", True),
]

# ---------------------------------------------------------------- C23 ----
def _c23_argfix(fam_id, world, split, kind):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        schema = {"order_id": "string", "quantity": "integer",
                  "currency": "enum:USD|EUR|JPY", "note": "string?"}
        if kind == "format":
            failed = {"order_id": "ORD/7741", "quantity": 3,
                      "currency": "USD"}
            diagnosis = {"field": "order_id",
                         "problem": "format", "detail":
                         "slash not allowed; canonical form uses a dash"}
            facts = {"canonical_order_id": "ORD-7741"}
            fixed = dict(failed, order_id="ORD-7741")
        elif kind == "entity":
            failed = {"order_id": "ORD-7741", "quantity": 3,
                      "currency": "usd"}
            diagnosis = {"field": "currency", "problem": "case",
                         "detail": "currency codes are uppercase"}
            facts = {"allowed_currencies": ["USD", "EUR", "JPY"]}
            fixed = dict(failed, currency="USD")
        else:  # value (confirmation)
            failed = {"order_id": "ORD-7741", "quantity": 0,
                      "currency": "USD"}
            diagnosis = {"field": "quantity", "problem": "range",
                         "detail": "quantity must be at least 1"}
            facts = {"last_known_quantity": 2}
            fixed = dict(failed, quantity=2)
        if language == "en":
            instr = ("Emit the corrected argument record for the retry. "
                     "Fix the diagnosed fault using the facts; do not "
                     "change unaffected arguments.")
        else:
            instr = ("输出重试所需的修正参数。只根据事实修复被诊断的缺陷，"
                     "不要改动未受影响的参数。")
        return {"public": {"failed_call": {"tool": "update_order",
                                           "arguments": failed},
                           "diagnosis": diagnosis, "facts": facts,
                           "argument_schema": schema,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"arguments": fixed,
                             "construction": {"kind": kind}},
                "alternatives": []}
    return Family(family_id=fam_id, primitive="C23", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "native_function_calling"],
                  build=build,
                  witnesses={"positive": ['{"order_id": "ORD-7741", '
                                          '"quantity": 3, '
                                          '"currency": "USD"}'],
                             "negative": ["retry identical to the failed "
                                          "call",
                                          "unaffected argument mutated"]})


C23_FAMILIES = [
    _c23_argfix("format", "retail_ops", "development", "format"),
    _c23_argfix("entity", "helpdesk", "development", "entity"),
    _c23_argfix("value", "finance_backoffice", "confirmation", "value"),
]

# ---------------------------------------------------------------- C24 ----
def _c24_fallback(fam_id, world, split):
    def build(rng, language, seq):
        difficulty = 1 + (seq % 3)
        fallbacks = [
            {"id": "FB-QUEUE", "condition": {"slot": "api_state",
                                             "op": "==", "value": "down"},
             "action": "queue_sync_job",
             "args_template": {"delay_min": 30}},
            {"id": "FB-BULK", "condition": {"slot": "record_count",
                                            "op": "<=", "value": 50},
             "action": "bulk_csv_export",
             "args_template": {"format": "csv"}},
            {"id": "FB-PORTAL", "condition": {"slot": "customer_tier",
                                              "op": "==", "value": "gold"},
             "action": "portal_manual_export",
             "args_template": {"notify": True}}]
        state = [{"api_state": "down", "record_count": 120,
                  "customer_tier": "standard"},
                 {"api_state": "up", "record_count": 40,
                  "customer_tier": "standard"},
                 {"api_state": "up", "record_count": 120,
                  "customer_tier": "gold"}][seq % 3]
        ok = [f for f in fallbacks if (
            state[f["condition"]["slot"]] == f["condition"]["value"]
            if f["condition"]["op"] == "=="
            else state[f["condition"]["slot"]] <= f["condition"]["value"])]
        chosen = ok[0]
        args = dict(chosen["args_template"])
        if language == "en":
            instr = ("The primary export API call failed. Choose the "
                     "applicable fallback and emit its action with "
                     "arguments.")
        else:
            instr = "主出口API调用失败。选择适用的兜底方案并给出动作及参数。"
        return {"public": {"primary_failure": "export_api unreachable "
                                              "for this scope",
                           "state": state, "fallbacks": fallbacks,
                           "instruction": instr},
                "difficulty": difficulty,
                "expected": {"fallback_id": chosen["id"],
                             "action": chosen["action"], "arguments": args,
                             "applicable": [f["id"] for f in ok]},
                "alternatives": [f["id"] for f in ok[1:]] or
                                ["no alternatives (unique applicable "
                                 "fallback)"]}
    return Family(family_id=fam_id, primitive="C24", world=world,
                  split=split,
                  protocols=["chat", "chat_json_schema",
                             "chat_bounded_reasoning_t2"],
                  build=build,
                  witnesses={"positive": ['{"fallback_id": "FB-QUEUE", '
                                          '"action": "queue_sync_job", '
                                          '"arguments": {"delay_min": 30}}'],
                             "negative": ["primary retried unchanged",
                                          "fallback whose condition fails"]})


C24_FAMILIES = [
    _c24_fallback("export", "retail_ops", "development"),
    _c24_fallback("sync", "helpdesk", "development"),
    _c24_fallback("portal", "finance_backoffice", "confirmation"),
]
