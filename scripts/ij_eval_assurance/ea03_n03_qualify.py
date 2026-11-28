#!/usr/bin/env python
"""EA03 N03 Batch A — Obligation A qualification run (v2 oracle).

Runs, against the PINNED IJ-NANO dataset snapshot in
``evidence/IJEVAL/EA03_N03/pinned/`` (raw-file digests recorded at intake,
matching the handoff package manifest):

1. Independent ground-truth validation of all 160 development cases
   (corrected verdicts; the prior 133/27 run stays immutable in git
   history and is reconciled case-by-case, never silently removed).
2. GT-D01..GT-D05 defect probes: the source-level concerns from the
   qualification order, each reproduced RED against the repaired oracle
   (a probe that still yields VALID is an escape -> exit 1).
3. Ground-truth mutation coverage, classes A-F per dev case:
   A corrupted final answer, B corrupted construction metadata,
   C coupled metadata+answer corruption, D public task changed with the
   expected answer unchanged, E valid alternative answer, F ambiguous or
   insufficient public information. Semantic mutations, not just
   malformed values. A-D and F must NOT yield VALID; E must NOT yield
   INVALID (AMBIGUOUS admitted where the alternative genuinely competes).
4. Obligation B integrated witnesses: positive and negative raw-response
   witnesses per primitive executed through the independent interpreter
   and reference oracle.

Outputs (evidence/IJEVAL/EA03_N03/):
- ground_truth_qualification_dev160_v2.json
- gt_mutation_coverage_dev160.json
- reconciliation_dev160.json
- response_witnesses.json

Exit 0 only when: zero mutation escapes, zero GT-D escapes, zero silent
removals, and every applicable primitive reaches an independent verdict.
"""
from __future__ import annotations

import copy
import json
import pathlib
import re
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance.reference import interpreter as interp  # noqa: E402
from eval_assurance.reference import oracle as _oracle      # noqa: E402
from eval_assurance.reference.oracle import (               # noqa: E402
    GroundTruthVerdict, evaluate_response, validate_ground_truth)


def _tie_text(catalog_labels, stored, rules, zh):
    """Construct a text with EXACTLY balanced evidence for the stored
    label and one other catalog member (an ambiguity probe against the
    oracle's own tie logic — the battery is adversarial by design).
    Substring collisions between patterns (e.g. '取消' inside '取消预定')
    are exactly the keyword-collision hazard under test, so the combined
    text is score-simulated and only accepted when the top score is a
    genuine tie."""
    strong = ("everything", "all the", "all the lights", "全部", "所有",
              "所有灯", "several devices", "together")
    labels = [l for l in sorted(catalog_labels)
              if l in rules and l != stored]
    cands_stored = [p for p in rules.get(stored, ())
                    if bool(re.search(r"[一-龥]", p)) == zh]

    def balanced(text):
        scores = {}
        for l in catalog_labels:
            if l not in rules:
                continue
            s = sum(2 if p in strong else 1
                    for p in rules[l] if p in text.lower())
            if s:
                scores[l] = s
        if not scores:
            return False
        top = max(scores.values())
        winners = [l for l, s in scores.items() if s == top]
        return len(winners) > 1 and top > 0

    for other in labels:
        for p1 in cands_stored:
            for p2 in [p for p in rules[other]
                       if bool(re.search(r"[一-龥]", p)) == zh]:
                if p1 == p2 or p1 in p2 or p2 in p1:
                    continue
                text = f"{p1}，同时{p2}" if zh else f"{p1} and also {p2}"
                if balanced(text):
                    return text
    return None

PINNED = ROOT / "evidence" / "IJEVAL" / "EA03_N03" / "pinned"
OUT = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
PINNED_REV = "d23de5abe596e43743a5a2c7437ccd1b5e7de7f9"


def load_pinned():
    cases = [json.loads(l) for l in
             (PINNED / "n03_cases.public.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip()]
    exps = {}
    for l in (PINNED / "n03_dev_expectations.jsonl").read_text(
            encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            exps[r["case_id"]] = r
    dev = [c for c in cases if c.get("split") == "development"
           and c["primitive"] <= "C08"]
    assert len(dev) == 160, f"expected 160 dev cases, got {len(dev)}"
    return cases, exps, dev


# ---------------------------------------------------------------------------
# per-primitive semantic mutators: (case, expectation) -> mutated pair
# ---------------------------------------------------------------------------
def _other(items, current):
    """A different element than ``current`` (deterministic)."""
    for x in items:
        if x != current:
            return x
    return None


def _mutate_A(case, exp):
    """Class A: corrupt the FINAL expected answer semantically."""
    prim, e = case["primitive"], exp["expected"]
    pp = case["public_payload"]
    m = copy.deepcopy(exp)
    me = m["expected"]
    if prim == "C01":
        me["label"] = _other(list(pp["intent_catalog"]), e["label"])
    elif prim == "C02":
        me["action"] = _other(["migrate", "submit", "approve", "review",
                               "archive"], e["action"])
    elif prim == "C03":
        if "lines" in e:
            if not e["lines"]:
                me["lines"] = ["ghost-item"]        # spurious line
            elif len(e["lines"]) > 1:
                me["lines"] = e["lines"][:-1]       # drop one line
            else:
                flipped = e["lines"][0].upper() \
                    if not e["lines"][0].isupper() else e["lines"][0].lower()
                if flipped == e["lines"][0]:        # zh: case is a no-op
                    names = [i["name"] for i in pp.get("items") or []
                             if i["name"] != e["lines"][0]]
                    if not names:
                        return None
                    flipped = names[0]              # wrong single line
                me["lines"] = [flipped]
        elif "field" in e:
            me["value"] = (e["value"] or "") + "X"
        else:
            me["line"] = (e["line"] or "") + "X"
    elif prim == "C04":
        ids = list(e["ids"])
        if len(ids) > 1:
            ids = ids[:-1]                          # drop one id
        else:
            allids = [i["id"] for i in pp["items"]]
            ids = [_other(allids, ids[0])]
        me["ids"] = ids
    elif prim == "C05":
        me["decision"] = not e["decision"]
    elif prim == "C06":
        me["choice"] = _other([o["id"] for o in pp["options"]],
                              e["choice"])
    elif prim == "C07":
        me["action"] = _other(list(pp["action_catalog"]), e["action"])
    elif prim == "C08":
        me["tool_id"] = _other([t["id"] for t in pp["tools"]],
                               e["tool_id"])
    return case, m


def _mutate_B(case, exp):
    """Class B: corrupt CONSTRUCTION metadata, answer unchanged."""
    prim, e = case["primitive"], exp["expected"]
    m = copy.deepcopy(exp)
    me = m["expected"]
    con = me.get("construction")
    if con is None:
        return None                                  # not applicable
    if prim == "C04":
        me["constraints"] = [["price<=", 10 ** 6], ["stock>", -1]]
    elif prim == "C05":
        if "limit" in con:
            con["limit"] = con["limit"] + 7
        elif "stock" in con:
            con["stock"] = con["stock"] + 5
    elif prim == "C06":
        if "seats" in con.get("need", {}):
            con["need"]["seats"] = con["need"]["seats"] + 1
        elif "iso" in con.get("need", {}):
            con["need"]["iso"] = not con["need"]["iso"]
    elif prim == "C08":
        # add a tag to a non-winning tool; winner set unchanged
        for tid, tags in con["registry_tags"].items():
            if tid != me["tool_id"] and "email" not in tags:
                con["registry_tags"][tid] = tags + ["email"]
                break
        else:
            return None
    else:
        return None
    return case, m


def _mutate_C(case, exp):
    """Class C: COUPLED corruption — metadata and final answer changed
    together, kept internally consistent. The oracle must still detect
    the contradiction with the PUBLIC task (GT-D02/D03/D04)."""
    prim, e = case["primitive"], exp["expected"]
    pp = case["public_payload"]
    m = copy.deepcopy(exp)
    me = m["expected"]
    con = me.get("construction")
    if prim == "C04":
        # weaken the bound and recompute ids for the WEAKENED constraint
        me["constraints"] = [["price<=", 10 ** 6]]
        me["ids"] = sorted(i["id"] for i in pp["items"]
                           if i.get("stock", 0) > 0)
        if me["order"]:
            me["order"] = None
        m["alternatives"] = ["ties in unspecified keys may differ"]
    elif prim == "C05" and con and "limit" in con:
        con["limit"] = 10 ** 6
        me["decision"] = True
    elif prim == "C05" and con and "stock" in con:
        con["stock"] = 0
        con["backorder"] = True
        me["decision"] = True
    elif prim == "C06" and con and "seats" in con.get("need", {}):
        con["need"]["seats"] = 1
        cheapest = min(pp["options"], key=lambda o: o["price"])
        me["choice"] = cheapest["id"]
    elif prim == "C08" and con:
        # make the FIRST non-expected tool the unique superset and point
        # the expected answer at it — public objective/descriptions rule
        victim = _other([t["id"] for t in pp["tools"]], me["tool_id"])
        req = sorted(con["required_tags"])
        con["registry_tags"] = {tid: (req if tid == victim else
                                      (tags if isinstance(tags, list)
                                       else list(tags)))
                                for tid, tags in
                                con["registry_tags"].items()}
        for tid in con["registry_tags"]:
            if tid != victim:
                con["registry_tags"][tid] = ["unrelated"]
        me["tool_id"] = victim
    else:
        return None
    return case, m


_C02_EN_ZH_VERB = {"migrate": "迁移", "submit": "提交", "approve": "审批",
                   "review": "评审", "archive": "归档"}


def _mutate_D(case, exp, siblings=None):
    """Class D: change the PUBLIC task, keep the expected answer."""
    prim = case["primitive"]
    e = exp["expected"]
    m = copy.deepcopy(exp)
    c = copy.deepcopy(case)
    pp = c["public_payload"]
    orig = case["public_payload"]
    if prim == "C01":
        # a sibling utterance whose stored label differs
        for s in siblings or []:
            if s["expected"].get("label") != e.get("label"):
                pp["utterance"] = s["case"]["public_payload"]["utterance"]
                break
        else:
            return None
    elif prim == "C02":
        new_verb = _other(sorted(_C02_EN_ZH_VERB), e.get("action"))
        if case["language"] == "en":
            pp["message"] = re.sub(
                r"\b(migrate|submit|approve|review|archive)\b",
                new_verb, orig["message"], count=1)
            if pp["message"] == orig["message"]:
                return None
        else:
            old_zh = _C02_EN_ZH_VERB[e.get("action")]
            if old_zh not in orig["message"]:
                return None
            pp["message"] = orig["message"].replace(
                old_zh, _C02_EN_ZH_VERB[new_verb], 1)
    elif prim == "C03":
        if "instruction" in orig:
            instr = orig["instruction"]
            if "没有库存" in instr:
                pp["instruction"] = instr.replace("没有库存", "有库存")
            elif "有库存" in instr:
                pp["instruction"] = instr.replace("有库存", "没有库存")
            elif "NOT in stock" in instr:
                pp["instruction"] = instr.replace("NOT in stock", "in stock")
            elif "NOT in-stock" in instr:
                pp["instruction"] = instr.replace("NOT in-stock", "in-stock")
            elif "in-stock" in instr:
                pp["instruction"] = instr.replace("in-stock", "NOT in-stock")
            else:
                return None
        else:                                        # formfill: mutate value
            val = e.get("value")
            if not val:
                return None
            mutated_val = (val[:-1] + "9") if val[-1].isdigit() \
                else val + "X"
            if mutated_val == val or val not in orig["message"]:
                return None
            pp["message"] = orig["message"].replace(val, mutated_val, 1)
    elif prim == "C04":
        pp["instruction"] = re.sub(
            r"\b(60|100)\b", "1",
            re.sub(r"\b(3\.0|3\.5)\b", "0.1", orig["instruction"]))
        if pp["instruction"] == orig["instruction"]:
            return None
    elif prim == "C05":
        if "within" in orig["policy"] or "不超过" in orig["policy"]:
            pp["policy"] = re.sub(r"within (\d+) days", "within 0 days",
                                  orig["policy"])
            pp["policy"] = re.sub(r"不超过(\d+)天", "不超过0天",
                                  pp["policy"])
            if pp["policy"] == orig["policy"]:
                return None
        else:                                        # fulfillment family
            def _bump(mm):
                return f"requested {int(mm.group(1)) + 999} units"

            def _bump_zh(mm):
                return f"请求{int(mm.group(1)) + 999}件"

            pp["facts"] = re.sub(r"requested (\d+) units?", _bump,
                                 orig["facts"])
            pp["facts"] = re.sub(r"请求\s*(\d+)\s*件", _bump_zh,
                                 pp["facts"])
            if pp["facts"] == orig["facts"]:
                return None
    elif prim == "C06":
        instr = orig["instruction"]
        if "seats" in instr or "席位" in instr:
            pp["instruction"] = re.sub(r"at least (\d+) seats",
                                       "at least 999 seats", instr)
            pp["instruction"] = re.sub(r"至少\s*(\d+)\s*(?:个)?席位",
                                       "至少999个席位",
                                       pp["instruction"])
            if pp["instruction"] == instr:
                return None
        elif "BOTH ISO certification AND a passed audit" in instr:
            pp["instruction"] = instr.replace(
                "BOTH ISO certification AND a passed audit",
                "ISO certification with a failed audit")
        elif "同时具备ISO认证且通过审计" in instr:
            pp["instruction"] = instr.replace(
                "同时具备ISO认证且通过审计", "具备ISO认证但未通过审计")
        else:
            return None
    elif prim == "C07":
        for s in siblings or []:
            if s["expected"].get("action") != e.get("action"):
                pp["situation"] = s["case"]["public_payload"]["situation"]
                break
        else:
            return None
    elif prim == "C08":
        objs_en = ["I need to email and send out for our customers.",
                   "I need to generate and invoice for our customers.",
                   "I need to look up and support ticket for our "
                   "customers.",
                   "I need to dataset and export for our customers.",
                   "I need to calendar and schedule for our customers."]
        objs_zh = ["我需要起草并邮件。", "我需要邮件并生成并发票并发送。",
                   "我需要关闭并工单。", "我需要报表并排期。",
                   "我需要数据集并校验。"]
        pool = objs_zh if case["language"] == "zh" else objs_en
        new_obj = _other(pool, orig.get("objective"))
        if new_obj is None:
            return None
        pp["objective"] = new_obj
    return c, m


def _mutate_E(case, exp):
    """Class E: VALID ALTERNATIVE answer (must NOT be INVALID)."""
    prim, e = case["primitive"], exp["expected"]
    m = copy.deepcopy(exp)
    me = m["expected"]
    if prim == "C04" and not e.get("order") and len(e["ids"]) > 1:
        me["ids"] = list(reversed(e["ids"]))     # declared tie freedom
        return case, m
    if prim == "C03" and "lines" in e and case["language"] == "en":
        # same lines, alternative casing is NOT valid (uppercase required
        # or not) — no valid alternative exists here
        return None
    return None


def _mutate_F(case, exp):
    """Class F: ambiguous / insufficient public information."""
    prim = case["primitive"]
    e = exp["expected"]
    c = copy.deepcopy(case)
    pp = c["public_payload"]
    if prim == "C01":
        text = _tie_text(list(pp.get("intent_catalog") or {}),
                         e.get("label"), _oracle._C01_RULES,
                         case["language"] == "zh")
        if text is None:
            return None
        pp["utterance"] = text
    elif prim == "C02":
        # verb intact (matches), object surface removed: partial only
        if case["language"] == "zh":
            zh = {"migrate": "迁移", "submit": "提交", "approve": "审批",
                  "review": "评审", "archive": "归档"}.get(e["action"])
            if zh is None:
                return None
            cc = "完成标准是能在系统里看到。" \
                if e.get("completion_criterion") else ""
            pp["message"] = f"请{zh}一下它。{cc}"
        else:
            cc = " Completion means it is visible in the system." \
                if e.get("completion_criterion") else ""
            dl = f" by {e['deadline']}" if e.get("deadline") else ""
            pp["message"] = f"Please {e['action']} it{dl}.{cc}"
    elif prim == "C03":
        if "instruction" in pp:
            pp["instruction"] = "List the items."
        else:
            pp["message"] = "Fill the form."
    elif prim == "C04":
        pp["instruction"] = "List the matching item ids. Requirements: " \
                            "color is festive; vibe is good."
    elif prim == "C05":
        pp["policy"] = "Return policy: use your best judgement."
        pp["facts"] = "A while ago, probably."
    elif prim == "C06":
        pp["instruction"] = "Choose the best plan. Emit exactly one id."
    elif prim == "C07":
        text = _tie_text(list(pp.get("action_catalog") or {}),
                         e.get("action"), _oracle._C07_RULES,
                         case["language"] == "zh")
        if text is None:
            return None
        pp["situation"] = text
    elif prim == "C08":
        pp["objective"] = "ベストなツールを選んでください。"
    return c, copy.deepcopy(exp)


MUTATORS = {"A": _mutate_A, "B": _mutate_B, "C": _mutate_C,
            "D": _mutate_D, "E": _mutate_E, "F": _mutate_F}


def run_mutation_battery(dev, exps):
    rows = []
    escapes = []
    applicable = Counter()
    siblings = {
        p: [{"case": c, "expected": exps[c["case_id"]]["expected"],
             "case_id": c["case_id"]}
            for c in dev if c["primitive"] == p]
        for p in {c["primitive"] for c in dev}
    }
    for case in dev:
        exp = exps[case["case_id"]]
        for cls, fn in MUTATORS.items():
            mutated = fn(case, exp, siblings[case["primitive"]]) \
                if cls == "D" else fn(case, exp)
            if mutated is None:
                rows.append({"case_id": case["case_id"], "class": cls,
                             "applicable": False})
                continue
            mc, me = mutated
            applicable[cls] += 1
            v = validate_ground_truth(mc, me).verdict.value
            if cls == "E":
                ok = v in ("VALID", "AMBIGUOUS")
            else:
                ok = v != "VALID"
            rows.append({"case_id": case["case_id"], "primitive":
                         case["primitive"], "class": cls, "applicable": True,
                         "verdict": v, "detected": ok})
            if not ok:
                escapes.append((case["case_id"], cls, v))
    return rows, escapes, applicable


# ---------------------------------------------------------------------------
# GT-D01..GT-D05 probes (source-level concerns; each must be detected)
# ---------------------------------------------------------------------------
def gt_probes(dev, exps):
    by_id = {c["case_id"]: c for c in dev}
    probes = []

    def probe(pid, desc, case, exp, expect_not_valid=True, expect=None):
        r = validate_ground_truth(case, exp)
        got = r.verdict.value
        if expect is not None:
            ok = got == expect
        else:
            ok = got != "VALID"
        probes.append({"probe": pid, "description": desc,
                       "case_id": case.get("case_id", ""), "verdict": got,
                       "expected": expect or "not VALID", "passed": ok,
                       "reasons": list(r.reasons[:2])})
        return ok

    # -- GT-D01 C02 partial semantic validation ---------------------------
    c = copy.deepcopy(by_id["n03-C02-project-d00"])
    e = copy.deepcopy(exps["n03-C02-project-d00"])
    for fld, val in (("action", "submit"), ("object", "audit_trail"),
                     ("completion_criterion", "visible_in_system")):
        m = copy.deepcopy(e)
        m["expected"][fld] = val       # wrong but syntactically canonical
        probe(f"GT-D01/{fld}", f"mutated {fld} must not be VALID",
              c, m)
    m = copy.deepcopy(e)               # flag flip
    m["expected"]["unknown_flags"]["deadline"] = True
    probe("GT-D01/flag-flip", "deadline flag flipped with a stated date",
          c, m)
    m = copy.deepcopy(e)               # missing required field
    del m["expected"]["action"]
    probe("GT-D01/missing-field", "required field removed", c, m)
    m = copy.deepcopy(e)               # unexpected extra field
    m["expected"]["priority"] = "high"
    probe("GT-D01/extra-field", "unexpected additional field", c, m)
    m = copy.deepcopy(e)               # deadline mutated
    m["expected"]["deadline"] = "2030-01-01"
    probe("GT-D01/deadline", "deadline mutated", c, m)
    # partial derivation must be NOT_ESTABLISHED, never VALID
    c2 = copy.deepcopy(c)
    c2["public_payload"]["message"] = "Please migrate it by 2026-12-11."
    probe("GT-D01/partial", "object surface removed, action/deadline "
          "match -> NOT_ESTABLISHED (partial, never VALID)",
          c2, copy.deepcopy(e), expect="NOT_ESTABLISHED")

    # -- GT-D02 C04 circular/coupled validation ---------------------------
    c = copy.deepcopy(by_id["n03-C04-retail-d00"])
    e = copy.deepcopy(exps["n03-C04-retail-d00"])
    m = copy.deepcopy(e)               # coupled constraints+ids
    m["expected"]["constraints"] = [["price<=", 200]]
    m["expected"]["ids"] = ["SKU-001", "SKU-002"]
    m["alternatives"] = ["ties in unspecified keys may differ"]
    probe("GT-D02/coupled", "coupled constraints+ids corruption "
          "(public instruction unchanged)", c, m)
    m = copy.deepcopy(e)               # sort ignored / wrong direction
    c = copy.deepcopy(by_id["n03-C04-retail-d02"])
    e = copy.deepcopy(exps["n03-C04-retail-d02"])
    m = copy.deepcopy(e)
    m["expected"]["ids"] = list(reversed(m["expected"]["ids"]))
    probe("GT-D02/sequence", "sort-declared sequence reversed", c, m)
    m = copy.deepcopy(e)
    m["expected"]["constraints"] = [["price<=", 60], ["stock>", 5]]
    probe("GT-D02/metadata-only", "stored constraints corrupt, ids same",
          c, m)
    # zh coupled probe
    cz = copy.deepcopy(by_id["n03-C04-retail-d01"])
    ez = copy.deepcopy(exps["n03-C04-retail-d01"])
    mz = copy.deepcopy(ez)
    mz["expected"]["constraints"] = [["stock>", 0]]
    mz["expected"]["ids"] = sorted(i["id"] for i in
                                   cz["public_payload"]["items"]
                                   if i.get("stock", 0) > 0)
    mz["expected"]["order"] = None
    probe("GT-D02/coupled-zh", "zh coupled corruption", cz, mz)

    # -- GT-D03 C06 counterexamples ---------------------------------------
    def c6(desc, instr, options, choice, alternatives=(), need=None,
           expect="not VALID"):
        cc = {"case_id": "probe-C06", "primitive": "C06",
              "public_payload": {"instruction": instr, "options": options}}
        ee = {"case_id": "probe-C06",
              "expected": {"choice": choice,
                           "construction": {"need": need or {}}},
              "alternatives": list(alternatives)}
        return probe(f"GT-D03/{desc}", desc, cc, ee,
                     expect=None if expect == "not VALID" else expect)

    plans = [
        {"id": "P-CHEAP-NOREC", "price": 10, "seats": 10,
         "recording": False},
        {"id": "P-COSTLY-REC", "price": 99, "seats": 10,
         "recording": True},
    ]
    c6("cheapest-lacks-recording-en",
       "Choose the cheapest plan offering at least 5 seats WITH recording "
       "included. Emit exactly one plan id.", plans, "P-CHEAP-NOREC",
       need={"seats": 5, "recording": True})
    c6("correct-costly-recording-en",
       "Choose the cheapest plan offering at least 5 seats WITH recording "
       "included. Emit exactly one plan id.", plans, "P-COSTLY-REC",
       need={"seats": 5, "recording": True}, expect="VALID")
    c6("recording-excluded-en",
       "Choose the cheapest plan offering at least 5 seats WITHOUT "
       "recording. Emit exactly one plan id.", plans, "P-COSTLY-REC",
       need={"seats": 5, "recording": False})
    c6("recording-excluded-correct-en",
       "Choose the cheapest plan offering at least 5 seats WITHOUT "
       "recording. Emit exactly one plan id.", plans, "P-CHEAP-NOREC",
       need={"seats": 5, "recording": False}, expect="VALID")
    c6("recording-unmentioned-en",
       "Choose the cheapest plan offering at least 5 seats. Emit exactly "
       "one plan id.", plans, "P-COSTLY-REC",
       need={"seats": 5})
    plans_tie = plans + [{"id": "P-TIE-REC", "price": 99, "seats": 10,
                          "recording": True}]
    c6("tie-undeclared",
       "Choose the cheapest plan offering at least 5 seats WITH recording "
       "included. Emit exactly one plan id.", plans_tie, "P-COSTLY-REC",
       need={"seats": 5, "recording": True}, expect="AMBIGUOUS")
    c6("tie-declared",
       "Choose the cheapest plan offering at least 5 seats WITH recording "
       "included. Emit exactly one plan id.", plans_tie, "P-COSTLY-REC",
       alternatives=("tie between P-COSTLY-REC and P-TIE-REC",),
       need={"seats": 5, "recording": True}, expect="VALID")
    c6("zh-含录制",
       "选择提供至少5个席位且含录制的最便宜方案。只输出一个方案编号。",
       plans, "P-CHEAP-NOREC", need={"seats": 5, "recording": True})
    c6("zh-不含录制",
       "选择提供至少5个席位且不含录制的最便宜方案。只输出一个方案编号。",
       plans, "P-COSTLY-REC", need={"seats": 5, "recording": False})
    sups = [
        {"id": "S-NOISO", "price": 10, "iso": False, "audit": True},
        {"id": "S-BOTH", "price": 50, "iso": True, "audit": True},
        {"id": "S-NOAUDIT", "price": 20, "iso": True, "audit": False},
    ]
    c6("iso-absent-from-instruction",
       "Choose the cheapest supplier that passed an audit. Emit exactly "
       "one supplier id.", sups, "S-BOTH", need={"audit": True},
       expect="INVALID")
    c6("iso-negated",
       "Choose the cheapest supplier WITHOUT ISO certification. Emit "
       "exactly one supplier id.", sups, "S-BOTH",
       need={"iso": False})
    c6("audit-negated",
       "Choose the cheapest supplier with ISO certification whose audit "
       "was failed. Emit exactly one supplier id.", sups, "S-BOTH",
       need={"iso": True, "audit": False})
    c6("zh-supplier",
       "选择同时具备ISO认证且通过审计的最便宜供应商。只输出一个编号。",
       sups, "S-NOISO", need={"iso": True, "audit": True})

    # -- GT-D04 C08 hidden construction consistency -----------------------
    c = copy.deepcopy(by_id["n03-C08-biztools-d00"])
    e = copy.deepcopy(exps["n03-C08-biztools-d00"])
    m = copy.deepcopy(e)
    victim = "meeting_notifier"
    m["expected"]["tool_id"] = victim
    m["expected"]["construction"]["registry_tags"][victim] = \
        ["email", "send"]
    probe("GT-D04/coupled-registry+answer",
          "registry tags and tool id mutated together (public inventory "
          "unchanged)", c, m)
    m = copy.deepcopy(e)
    m["expected"]["construction"]["required_tags"] = ["calendar", "post"]
    probe("GT-D04/required-tags", "required tags contradict the public "
          "objective", c, m)
    m = copy.deepcopy(e)
    m["expected"]["construction"]["registry_tags"]["email_sender"] = \
        ["email"]                      # drop 'send' -> no superset
    probe("GT-D04/registry-thinning", "registry tag removed contradicts "
          "the public description", c, m)
    m = copy.deepcopy(e)
    m["expected"]["construction"]["registry_tags"]["ghost_tool"] = \
        ["email", "send"]
    probe("GT-D04/registry-ghost", "registry references a tool absent "
          "from the public inventory", c, m)
    del m["expected"]["construction"]["registry_tags"]["email_sender"]
    probe("GT-D04/registry-missing-public",
          "public tool missing from the registry", c, m)

    # -- GT-D05 C03 recoverable NOT_ESTABLISHED ---------------------------
    c = copy.deepcopy(by_id["n03-C03-formfill-d00"])
    e = copy.deepcopy(exps["n03-C03-formfill-d00"])
    probe("GT-D05/formfill-valid", "formfill independently established",
          c, e, expect="VALID")
    m = copy.deepcopy(e)
    m["expected"]["value"] = "+31-10-555999"
    probe("GT-D05/formfill-value", "formfill value mutated", c, m)
    m = copy.deepcopy(e)
    m["expected"]["field"] = "delivery_city"
    probe("GT-D05/formfill-field", "formfill field mutated", c, m)
    cf = copy.deepcopy(by_id["n03-C03-formatting-d02"])
    ef = copy.deepcopy(exps["n03-C03-formatting-d02"])
    probe("GT-D05/formatting-upper-valid",
          "not_in_stock_upper independently established", cf, ef,
          expect="VALID")
    c4u = copy.deepcopy(by_id["n03-C03-formatting-d04"])
    e4u = copy.deepcopy(exps["n03-C03-formatting-d04"])
    m4u = copy.deepcopy(e4u)
    m4u["expected"]["lines"] = [ln.lower()
                                for ln in m4u["expected"]["lines"]]
    probe("GT-D05/formatting-case", "uppercase requirement violated",
          c4u, m4u)
    c4 = copy.deepcopy(by_id["n03-C03-formatting-d00"])
    e4 = copy.deepcopy(exps["n03-C03-formatting-d00"])
    m4 = copy.deepcopy(e4)
    m4["expected"]["lines"] = list(reversed(m4["expected"]["lines"]))
    probe("GT-D05/formatting-sequence",
          "line order swapped is not silently VALID (sequence != set)",
          c4, m4, expect="AMBIGUOUS")
    mf = copy.deepcopy(ef)
    mf["expected"]["lines"] = mf["expected"]["lines"] + ["extra"]
    probe("GT-D05/formatting-extra", "extra line added", cf, mf)
    mf = copy.deepcopy(ef)
    mf["expected"]["rule"] = "in_stock"
    probe("GT-D05/formatting-rule", "stored rule contradicts instruction",
          cf, mf)
    return probes


# ---------------------------------------------------------------------------
# Obligation B integrated witnesses
# ---------------------------------------------------------------------------
def render_witness(primitive, case, truth):
    """Render the established truth on the accepted output surface."""
    if primitive == "C01":
        return truth
    if primitive == "C02":
        return json.dumps(truth, ensure_ascii=False)
    if primitive == "C03":
        if isinstance(truth, dict):
            return json.dumps(truth, ensure_ascii=False)
        return "\n".join(truth)
    if primitive == "C04":
        return ", ".join(truth)
    if primitive == "C05":
        return "TRUE" if truth["decision"] else "FALSE"
    if primitive == "C06":
        return truth["choice"] if isinstance(truth, dict) else truth
    if primitive == "C07":
        return truth
    if primitive == "C08":
        return truth["choice"] if isinstance(truth, dict) else truth
    raise AssertionError(primitive)


def response_witnesses(dev, exps):
    rows = []
    per_prim = {}
    for case in dev:
        per_prim.setdefault(case["primitive"], case)   # first per prim
    negatives = {
        "C01": "free text answer about refunds please",
        "C02": "sure, the goal is to finish it soon",
        "C03": "- bullet one\n- bullet two",
        "C04": "SKU-000",
        "C05": "probably yes I think",
        "C06": "PLN-BASIC",
        "C07": "do the needful",
        "C08": "ghost_tool_id",
    }
    for prim, case in sorted(per_prim.items()):
        exp = exps[case["case_id"]]
        gt = validate_ground_truth(case, exp)
        truth = gt.recomputed
        pos = render_witness(prim, case, truth)
        r = evaluate_response(case, exp, pos)
        rows.append({"primitive": prim, "witness": "positive",
                     "raw": pos[:120], "verdict": r.verdict.value,
                     "expected": "CORRECT",
                     "passed": r.verdict.value == "CORRECT"})
        neg = evaluate_response(case, exp, negatives[prim])
        rows.append({"primitive": prim, "witness": "negative-malformed",
                     "raw": negatives[prim][:120],
                     "verdict": neg.verdict.value, "expected": "INCORRECT",
                     "passed": neg.verdict.value == "INCORRECT"})
        # wrong-but-wellformed witness: a different valid surface value
        wrong = _wrong_witness(prim, case, truth)
        if wrong is not None:
            w = evaluate_response(case, exp, wrong)
            rows.append({"primitive": prim, "witness": "negative-wrong",
                         "raw": str(wrong)[:120],
                         "verdict": w.verdict.value, "expected": "INCORRECT",
                         "passed": w.verdict.value == "INCORRECT"})
        empty = evaluate_response(case, exp, "   ")
        rows.append({"primitive": prim, "witness": "empty",
                     "raw": "", "verdict": empty.verdict.value,
                     "expected": "EMPTY_OUTPUT",
                     "passed": empty.verdict.value == "EMPTY_OUTPUT"})
        # software error never becomes a model failure
        class _Boom:
            def __getattr__(self, k):
                raise RuntimeError("parser exploded")
        boom_case = dict(case)
        boom_case["public_payload"] = _Boom()
        sw = evaluate_response(boom_case, exp, "TRUE")
        rows.append({"primitive": prim, "witness": "software-error",
                     "raw": "TRUE", "verdict": sw.verdict.value,
                     "expected": "NOT_EVALUABLE",
                     "passed": sw.verdict.value == "NOT_EVALUABLE"})
    return rows


def _wrong_witness(prim, case, truth):
    if prim == "C01":
        cat = list(case["public_payload"]["intent_catalog"])
        return _other(cat, truth)
    if prim == "C02":
        t = copy.deepcopy(truth)
        t["action"] = _other(["migrate", "submit", "approve", "review",
                              "archive"], t["action"])
        return json.dumps(t, ensure_ascii=False)
    if prim == "C03":
        if isinstance(truth, dict):
            t = dict(truth)
            t["value"] = str(t["value"]) + "X"
            return json.dumps(t, ensure_ascii=False)
        return "\n".join(list(reversed(truth))[:1] or ["zzz"])
    if prim == "C04":
        return ", ".join(list(truth)[:-1] or ["zzz"])
    if prim == "C05":
        return "FALSE" if truth["decision"] else "TRUE"
    if prim == "C06":
        ids = [o["id"] for o in case["public_payload"]["options"]]
        return _other(ids, truth["choice"] if isinstance(truth, dict)
                      else truth)
    if prim == "C07":
        cat = list(case["public_payload"]["action_catalog"])
        return _other(cat, truth)
    if prim == "C08":
        ids = [t["id"] for t in case["public_payload"]["tools"]]
        return _other(ids, truth["choice"] if isinstance(truth, dict)
                      else truth)
    return None


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    cases, exps, dev = load_pinned()
    # -- 1. corrected ground-truth qualification -------------------------
    per_case = []
    stats = Counter()
    by_prim = {}
    for case in dev:
        r = validate_ground_truth(case, exps[case["case_id"]])
        stats[r.verdict.value] += 1
        by_prim.setdefault(case["primitive"], Counter())[r.verdict.value] += 1
        per_case.append({
            "case_id": case["case_id"], "primitive": case["primitive"],
            "verdict": r.verdict.value,
            "recomputed": r.recomputed, "reasons": list(r.reasons),
            "verified_fields": list(r.verified_fields),
            "unverified_fields": list(r.unverified_fields),
        })
    qual = {
        "schema": "ijeval.ea03_n03.ground_truth_qualification_dev160.v2",
        "schema_version": 2,
        "generated_by": "scripts/ij_eval_assurance/ea03_n03_qualify.py",
        "oracle": "src/eval_assurance/reference/oracle.py (v2: full-field "
                  "independent semantic derivation per GT-D01..GT-D05)",
        "pinned_ij_nano_revision": PINNED_REV,
        "scope": "160 development cases, primitives C01-C08 (obligation A)",
        "independence": ("no IJ-NANO production or builder code imported; "
                         "every field recomputed from public payloads "
                         "(GT-D01..GT-D05); stored construction metadata "
                         "cross-checked, never authoritative"),
        "summary": {"total": 160, **{k: stats.get(k, 0) for k in
                                     ("VALID", "INVALID", "AMBIGUOUS",
                                      "NOT_ESTABLISHED")}},
        "by_primitive": {p: dict(c) for p, c in sorted(by_prim.items())},
        "per_case": per_case,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ground_truth_qualification_dev160_v2.json").write_text(
        json.dumps(qual, ensure_ascii=False, indent=1), encoding="utf-8")

    # -- 2. GT-D probes ---------------------------------------------------
    probes = gt_probes(dev, exps)
    probe_fail = [p for p in probes if not p["passed"]]

    # -- 3. mutation battery ---------------------------------------------
    rows, escapes, applicable = run_mutation_battery(dev, exps)
    mut = {
        "schema": "ijeval.ea03_n03.gt_mutation_coverage_dev160",
        "schema_version": 1,
        "generated_by": "scripts/ij_eval_assurance/ea03_n03_qualify.py",
        "pinned_ij_nano_revision": PINNED_REV,
        "classes": {
            "A": "corrupted final expected answer (semantic)",
            "B": "corrupted construction metadata (answer unchanged)",
            "C": "coupled corruption of metadata and answer (internally "
                 "consistent)",
            "D": "public task changed, expected answer unchanged",
            "E": "valid alternative answer (must NOT be INVALID)",
            "F": "ambiguous or insufficient public information",
        },
        "applicable_counts": dict(applicable),
        "total_mutations": sum(applicable.values()),
        "escapes": [{"case_id": c, "class": k, "verdict": v}
                    for c, k, v in escapes],
        "gt_d_probes": probes,
        "per_case": rows,
    }
    (OUT / "gt_mutation_coverage_dev160.json").write_text(
        json.dumps(mut, ensure_ascii=False, indent=1), encoding="utf-8")

    # -- 4. reconciliation vs the immutable historical run ----------------
    prior_path = OUT / "ground_truth_qualification_dev160.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8")) \
        if prior_path.exists() else None
    prior_by = {r["case_id"]: r["verdict"] for r in
                (prior or {}).get("per_case", [])}
    recon_rows = []
    changes = Counter()
    for row in per_case:
        pv = prior_by.get(row["case_id"])
        cv = row["verdict"]
        if pv != cv:
            changes[f"{pv}->{cv}"] += 1
        recon_rows.append({
            "case_id": row["case_id"], "primitive": row["primitive"],
            "prior_verdict": pv, "corrected_verdict": cv,
            "verified_semantic_fields": row["verified_fields"],
            "unverified_semantic_fields": row["unverified_fields"],
            "independent_truth_basis": _truth_basis(row["primitive"]),
            "prior_recomputed": None,   # historical record preserved in v1
            "reasons": row["reasons"],
        })
    silent_removals = [r for r in recon_rows if r["prior_verdict"] is None]
    recon = {
        "schema": "ijeval.ea03_n03.reconciliation_dev160",
        "schema_version": 1,
        "generated_by": "scripts/ij_eval_assurance/ea03_n03_qualify.py",
        "historical_run": {"artifact": "ground_truth_qualification_dev160"
                           ".json", "commit": "3ec4c28",
                           "summary": (prior or {}).get("summary"),
                           "status": "immutable historical evidence"},
        "corrected_run": {"artifact":
                          "ground_truth_qualification_dev160_v2.json",
                          "summary": qual["summary"]},
        "verdict_changes": dict(changes),
        "silent_removals": len(silent_removals),
        "dataset_defects": 0 if stats.get("INVALID", 0) == 0 else
                           "see INVALID rows",
        "correction_requests_to_ij_nano": [],
        "per_case": recon_rows,
    }
    (OUT / "reconciliation_dev160.json").write_text(
        json.dumps(recon, ensure_ascii=False, indent=1), encoding="utf-8")

    # -- 5. Obligation B witnesses ----------------------------------------
    wrows = response_witnesses(dev, exps)
    wfail = [r for r in wrows if not r["passed"]]
    wit = {
        "schema": "ijeval.ea03_n03.response_witnesses",
        "schema_version": 1,
        "generated_by": "scripts/ij_eval_assurance/ea03_n03_qualify.py",
        "path": "raw response -> independent interpreter -> reference "
                "oracle (obligation B reference leg)",
        "rows": wrows,
        "failures": wfail,
    }
    (OUT / "response_witnesses.json").write_text(
        json.dumps(wit, ensure_ascii=False, indent=1), encoding="utf-8")

    # -- verdict ----------------------------------------------------------
    ok = (not escapes and not probe_fail and not wfail
          and not silent_removals and stats.get("INVALID", 0) == 0
          and len(per_case) == 160)
    print(f"obligation A: {dict(stats)}")
    print(f"GT-D probes: {len(probes) - len(probe_fail)}/{len(probes)} "
          f"passed")
    print(f"mutation battery: {sum(applicable.values())} applicable, "
          f"{len(escapes)} escapes")
    print(f"reconciliation: {dict(changes)}, silent removals "
          f"{len(silent_removals)}")
    print(f"response witnesses: {len(wrows) - len(wfail)}/{len(wrows)} "
          f"passed")
    if not ok:
        for c, k, v in escapes:
            print(f"  ESCAPE {c} class {k} -> {v}")
        for p in probe_fail:
            print(f"  PROBE-FAIL {p['probe']} -> {p['verdict']}")
        for r in wfail:
            print(f"  WITNESS-FAIL {r['primitive']}/{r['witness']} -> "
                  f"{r['verdict']}")
        return 1
    print("EA03 obligation A v2 + mutation coverage + obligation B "
          "witnesses: PASS")
    return 0


def _truth_basis(prim: str) -> str:
    return {
        "C01": "independent rule table over public utterance+catalog "
               "(negation vetoes)",
        "C02": "full-field derivation from public message (verb/noun "
               "phrase normalization, ISO deadline, CC phrase, flag "
               "nullness)",
        "C03": "instruction-parsed rule (polarity+uppercase) over public "
               "items in payload order / formfill field+value from public "
               "directive and message",
        "C04": "constraints+sort parsed from public instruction; id "
               "set/sequence recomputed; stored metadata cross-checked",
        "C05": "policy/facts predicate recomputation; construction "
               "cross-checked",
        "C06": "requirements parsed from public instruction (inclusion/"
               "exclusion, zh+en); cheapest qualifying recomputed",
        "C07": "independent rule table over public situation+catalog "
               "(negation vetoes)",
        "C08": "required tags from public objective; per-tool tags from "
               "public descriptions; registry cross-checked",
    }.get(prim, "n/a")


if __name__ == "__main__":
    raise SystemExit(main())
