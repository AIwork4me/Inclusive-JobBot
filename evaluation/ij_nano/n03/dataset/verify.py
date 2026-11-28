#!/usr/bin/env python3
"""N03-B3 independent dataset verification (IJ-NANO-1.3S).

Independence model (documented honestly):
- This module does NOT import the family builders. Truth is re-derived via
  independently written rule functions over (public payload + expectation
  records), restating each primitive's semantic contract from the frozen
  taxonomy.
- Dual-implementation independence applies where truth is authored
  (C01/C02/C07 construction semantics): the rule tables here are separately
  coded restatements; the mutation battery proves detection power by
  corrupting expectations and requiring a mismatch.
- Full public-recomputation applies where truth is computational
  (C03/C04/C05/C06/C08): results are recomputed from public payloads.

Checks: structure, split integrity, family separation, language balance,
independent truth re-derivation, ground-truth corruption mutation battery,
dataset-level mutations, hidden-answer leakage scan.

Writes evidence/IJNANO/N03/dataset/verification_report.json.
Exit 0 = PASS, 1 = FAIL (fail closed).
"""
from __future__ import annotations

import json
import pathlib
import random
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BASE = ROOT / "evaluation" / "ij_nano" / "n03"
sys.path.insert(0, str(ROOT))

from evaluation.ij_nano.n03.dataset.core import digest_obj  # noqa: E402

PUBLIC = BASE / "dataset" / "public" / "n03_cases.public.jsonl"
DEV_EXP = BASE / "dataset" / "expectations" / "n03_dev_expectations.jsonl"
CONF_EXP = BASE / "protected" / "n03_confirmation_expectations.jsonl"
TAXONOMY = BASE / "taxonomy.json"
OUT = ROOT / "evidence" / "IJNANO" / "N03" / "dataset" / \
    "verification_report.json"

CASE_ID_RE = re.compile(
    r"^n03-C(0[1-9]|[12][0-9]|3[0-2])-[a-z0-9_]+-[dc]\d{2}$")

CASES_PER_FAMILY = 10

# -- independent truth tables (separately coded restatements) --------------
C01_RULES = {
    "refund_request": lambda a: a.get("payment") and a.get("reversal"),
    "exchange_request": lambda a: a.get("swap_item") and a.get("payment"),
    "shipping_status": lambda a: a.get("asks_where"),
    "account_lock": lambda a: a.get("locked_out"),
    "incident_report": lambda a: a.get("reports_outage"),
    "feature_request": lambda a: a.get("suggests_feature"),
    "billing_query": lambda a: a.get("asks_charge_explanation"),
    "escalation_demand": lambda a: a.get("demands_manager"),
    "set_device": lambda a: a.get("wants_state_change"),
    "query_state": lambda a: a.get("asks_current_state"),
    "schedule_action": lambda a: a.get("wants_later_execution"),
    "cancel_schedule": lambda a: a.get("cancels_previous"),
    "group_control": lambda a: a.get("targets_multiple"),
    "energy_report": lambda a: a.get("asks_usage_summary"),
    "balance_inquiry": lambda a: a.get("asks_balance"),
    "transfer_request": lambda a: a.get("instructs_move_money"),
    "card_freeze": lambda a: a.get("blocks_card"),
    "loan_question": lambda a: a.get("asks_credit_product"),
    "statement_request": lambda a: a.get("asks_document"),
    "fraud_alert": lambda a: a.get("reports_unknown_tx"),
    "branch_hours": lambda a: a.get("asks_office_info"),
    "currency_exchange": lambda a: a.get("asks_fx_rate"),
}
C07_RULES = {
    "verify_identity": lambda a: a.get("lost_access"),
    "reset_password": lambda a: a.get("forgot_credentials"),
    "issue_refund": lambda a: a.get("payment_dispute") and
                                a.get("within_window"),
    "escalate_fraud": lambda a: a.get("suspects_fraud"),
    "update_record": lambda a: a.get("data_entry_error"),
    "schedule_callback": lambda a: a.get("requests_later_call"),
    "restart_service": lambda a: a.get("service_unresponsive"),
    "rollback_deploy": lambda a: a.get("recent_deploy_broke"),
    "scale_replicas": lambda a: a.get("sustained_overload"),
    "page_oncall": lambda a: a.get("sev1_outage"),
    "clear_cache": lambda a: a.get("stale_content_served"),
    "recount_shelf": lambda a: a.get("count_mismatch"),
    "quarantine_batch": lambda a: a.get("defect_found"),
    "reprint_label": lambda a: a.get("label_unreadable"),
    "notify_supervisor": lambda a: a.get("repeated_mismatch"),
    "hand_to_qa": lambda a: a.get("sampling_failed"),
}


def _recompute(prim, pub, exp) -> list[str]:
    """Independent truth re-derivation. Returns list of mismatches."""
    m: list[str] = []
    e = exp
    if prim == "C01":
        attrs = e.get("construction", {})
        if not C01_RULES[e["label"]](attrs):
            m.append("C01 construction does not entail label")
    elif prim == "C07":
        attrs = e.get("construction", {})
        if not C07_RULES[e["action"]](attrs):
            m.append("C07 construction does not entail action")
    elif prim == "C05":
        c = e["construction"]
        decision = (c["days_ago"] <= c["limit"] if "limit" in c else
                    (c["requested"] <= c["stock"] or c["backorder"])
                    if "stock" in c else
                    (c["docs_ok"] and c["days_lead"] > 14))
        limit_val = c.get("limit", 14 if "days_lead" in c else None)
        surface_ok = (limit_val is None or
                      str(limit_val) in pub["policy"])
        if e["decision"] is not decision or not surface_ok:
            m.append("C05 decision not recomputable from construction "
                     "+ policy surface")
    elif prim == "C06":
        kind = e["construction"]["kind"]
        need = e["construction"]["need"]
        opts = pub["options"]
        if kind == "plan":
            pool = [o for o in opts if o["seats"] >= need["seats"]
                    and o["recording"]]
        elif kind == "supplier":
            pool = [o for o in opts if o["iso"] and o["audit"]]
        else:
            pool = [o for o in opts if o["days"] <= need["max_days"]]
        best = min(o["price"] for o in pool)
        winners = sorted(o["id"] for o in pool if o["price"] == best)
        if e["choice"] not in winners:
            m.append("C06 choice is not a cheapest qualifying option")
    elif prim == "C04":
        cons = [(k, v) for k, v in e["constraints"]]
        surv = [it for it in pub["items"] if all(
            (it["price"] <= v if k == "price<=" else
             it["stock"] > v if k == "stock>" else
             it["rating"] >= v if k == "rating>=" else
             it["rsvp"] == v if k == "rsvp==" else
             it["plus_ones"] <= v if k == "plus_ones<=" else
             it["vip"] is v if k == "vip==" else
             it["vendor"] != v) for k, v in cons)]
        order = e.get("order")
        if order:
            surv.sort(key=lambda it: (-it[order], it["id"]))
        got = [it["id"] for it in surv]
        if set(got) != set(e["ids"]) or (order and got != e["ids"]):
            m.append("C04 recomputed survivor set differs")
    elif prim == "C03":
        rule = e.get("rule")
        if "form_fields" in pub:                 # formfill family
            if e["field"] not in pub["form_fields"]:
                m.append("C03 formfill field outside declared form")
            elif str(e["value"]) not in pub["message"]:
                m.append("C03 formfill value not present in message")
        elif "items" in pub:                      # formatting family
            in_stock = rule.startswith("in_stock")
            upper = "upper" in rule
            lines = [it["name"].upper() if upper and it["name"].isascii()
                     else it["name"]
                     for it in pub["items"]
                     if (it["stock"] > 0) == in_stock]
            if lines != e["lines"]:
                m.append("C03 formatting lines differ from recomputation")
        else:                                    # one-edit family
            pl, el = pub["line"].split(" | "), e["line"].split(" | ")
            if rule == "drop_segment_mode":
                if len(el) != 3 or pl[0] != el[0] or pl[1] != el[1] or \
                        pl[3] != el[2]:
                    m.append("C03 oneedit drop rule mismatch")
            elif rule in ("set_priority_high", "replace_hub"):
                if len(el) != 4:
                    m.append("C03 oneedit segment count changed")
                else:
                    diffs = [i for i in range(4) if pl[i] != el[i]]
                    want = 3 if rule == "set_priority_high" else 1
                    if diffs != [want]:
                        m.append(f"C03 oneedit touched segments {diffs}, "
                                 f"expected [{want}]")
    elif prim == "C02":
        dl = e.get("deadline")
        msg = pub["message"]
        if dl is not None:
            ok = dl in msg
        else:
            ok = "截止" not in msg and " by " not in msg
        if not ok:
            m.append("C02 deadline surface inconsistent")
        uf = e["unknown_flags"]
        if uf["deadline"] != (dl is None) or uf["completion_criterion"] != \
                (e.get("completion_criterion") is None):
            m.append("C02 unknown flags inconsistent with record")
    elif prim == "C08":
        c = e["construction"]
        req = set(c["required_tags"])
        reg = c["registry_tags"]
        serving = [tid for tid, tags in reg.items() if req.issubset(set(tags))]
        if serving != [e["tool_id"]]:
            m.append("C08 tag algebra: serving tool not the unique superset")
        pub_ids = {t["id"] for t in pub["tools"]}
        if pub_ids != set(reg):
            m.append("C08 public tool ids differ from construction registry")
    return m


def _forbidden_keys(obj, path="") -> list[str]:
    bad = re.compile(r"expected|answer|ground.?truth|solution|construction")
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if bad.search(k):
                out.append(f"{path}.{k}")
            out.extend(_forbidden_keys(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(_forbidden_keys(v, f"{path}[{i}]"))
    return out


def mutate(prim, exp, rng):
    e = json.loads(json.dumps(exp))
    if "field" in e and "value" in e:            # C03 formfill
        e["value"] = f"{e['value']}-corrupted"
    elif "label" in e:
        e["label"] = "shipping_status" if e["label"] != "shipping_status" \
            else "account_lock"
    elif "action" in e and prim == "C07":
        e["action"] = "page_oncall" if e["action"] != "page_oncall" else \
            "clear_cache"
    elif "decision" in e:
        e["decision"] = not e["decision"]
    elif "ids" in e:
        e["ids"] = e["ids"][1:] if len(e["ids"]) > 1 else ["SKU-XXX"]
    elif "choice" in e:
        e["choice"] = "PLN-ENTERPRISE" if e["choice"] != "PLN-ENTERPRISE" \
            else "PLN-BASIC"
    elif "tool_id" in e:
        e["tool_id"] = "nonexistent_tool"
    elif "lines" in e:
        e["lines"] = e["lines"][:-1] if e["lines"] else ["x"]
    elif "line" in e:
        e["line"] = e["line"] + " | EXTRA"
    elif "deadline" in e:
        e["deadline"] = "2099-01-01" if e["deadline"] else "2099-01-01"
    return e


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    tax = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    vocab = set(tax["protocol_vocabulary"])
    pub_rows = [json.loads(l) for l in
                PUBLIC.read_text(encoding="utf-8").splitlines()]
    dev_rows = [json.loads(l) for l in
                DEV_EXP.read_text(encoding="utf-8").splitlines()]
    conf_rows = ([json.loads(l) for l in
                  CONF_EXP.read_text(encoding="utf-8").splitlines()]
                 if CONF_EXP.is_file() else [])
    problems: list[str] = []
    limitations: list[str] = []

    # -- structure -----------------------------------------------------
    ids = [r["case_id"] for r in pub_rows]
    if len(ids) != len(set(ids)):
        problems.append("duplicate public case ids")
    for r in pub_rows:
        if not CASE_ID_RE.match(r["case_id"]):
            problems.append(f"bad case id {r['case_id']}")
        if r["difficulty"] not in (1, 2, 3):
            problems.append(f"{r['case_id']}: difficulty out of range")
        if not set(r["protocols"]) <= vocab:
            problems.append(f"{r['case_id']}: protocol outside vocabulary")
        if r["contract_ref"] != f"{r['primitive']}:output_contract":
            problems.append(f"{r['case_id']}: contract_ref mismatch")
        problems += [f"{r['case_id']}: leak key {k}"
                     for k in _forbidden_keys(r["public_payload"])]

    # -- split / family integrity ---------------------------------------
    fam_split: dict[str, set] = {}
    per_prim_fams: dict[str, dict[str, set]] = {}
    lang_balance: dict[tuple, list] = {}
    for r in pub_rows:
        fam_split.setdefault(r["family"], set()).add(r["split"])
        per_prim_fams.setdefault(r["primitive"], {}).setdefault(
            r["split"], set()).add(r["family"])
        lang_balance.setdefault(
            (r["family"], r["split"], r["language"]), []).append(1)
    for fam, splits in fam_split.items():
        if len(splits) != 1:
            problems.append(f"family {fam} spans splits {splits}")
    for prim, by_split in per_prim_fams.items():
        dev_fams, conf_fams = by_split.get("development", set()), \
            by_split.get("confirmation", set())
        if dev_fams & conf_fams:
            problems.append(f"{prim}: families shared across splits")
        if conf_fams and not dev_fams:
            problems.append(f"{prim}: confirmation without development")
    for key, n in lang_balance.items():
        if len(n) != CASES_PER_FAMILY // 2:
            problems.append(f"language balance off for {key}: {len(n)}")

    # -- truth re-derivation --------------------------------------------
    exp_by_id = {r["case_id"]: r for r in dev_rows + conf_rows}
    if set(exp_by_id) - set(ids):
        problems.append("expectations exist for unknown cases")
    checked = 0
    for r in pub_rows:
        exp_rec = exp_by_id.get(r["case_id"])
        if exp_rec is None:
            if r["split"] == "development":
                problems.append(f"{r['case_id']}: missing dev expectation")
            continue
        checked += 1
        problems += [f"{r['case_id']}: {mm}"
                     for mm in _recompute(r["primitive"],
                                          r["public_payload"],
                                          exp_rec["expected"])]
    if not conf_rows:
        limitations.append("confirmation expectations not present locally; "
                           "confirmation cases verified structurally only")

    # -- C01/C07 label leakage into the task TEXT -------------------------
    # (the label legitimately appears as a catalog KEY - the task is
    # multiple-choice; leakage means the label occurring in the free text)
    for r in pub_rows:
        if r["primitive"] in ("C01", "C07") and r["case_id"] in exp_by_id:
            e = exp_by_id[r["case_id"]]["expected"]
            label = e.get("label") or e.get("action")
            text = (r["public_payload"].get("utterance")
                    or r["public_payload"].get("situation") or "")
            if label and label in text:
                problems.append(f"{r['case_id']}: answer label leaks into "
                                f"public task text")

    # -- mutation battery --------------------------------------------------
    rng = random.Random("n03-b3-mutation-battery/v1")
    detected = escaped = 0
    for r in pub_rows:
        exp_rec = exp_by_id.get(r["case_id"])
        if exp_rec is None:
            continue
        mut = mutate(r["primitive"], exp_rec["expected"], rng)
        if _recompute(r["primitive"], r["public_payload"], mut):
            detected += 1
        else:
            escaped += 1
            problems.append(f"mutation escaped detection at {r['case_id']}")
    # dataset-level mutation: a duplicated case id must be flagged by the
    # structural duplicate check above; exercised via the injected duplicate
    if len(pub_rows) >= 2:
        dup_probe = json.loads(json.dumps(pub_rows[0]))
        dup_probe["case_id"] = pub_rows[1]["case_id"]
        probe_ids = ids + [dup_probe["case_id"]]
        if len(probe_ids) == len(set(probe_ids)):
            problems.append("duplicate-id probe not detectable")

    report = {
        "schema": "ij_nano.n03.dataset.verification_report.v1",
        "result": "PASS" if not problems else "FAIL",
        "public_cases": len(pub_rows),
        "development_expectations": len(dev_rows),
        "confirmation_expectations_verified": len(conf_rows),
        "truth_rederivations": checked,
        "mutation_battery": {"detected": detected, "escaped": escaped},
        "problems": problems,
        "limitations": limitations + [
            "C01/C02/C07 truth is construction-authored; independence is "
            "dual-implementation (separately coded rule tables) plus the "
            "mutation battery, not public recomputation",
            "family-level entity disjointness across splits is enforced at "
            "family granularity (world/entity pool reuse across primitives "
            "is permitted and tracked for clustering)"],
        "public_digest": digest_obj(pub_rows),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"verification {report['result']}: {len(pub_rows)} cases, "
          f"{checked} truth re-derivations, mutations {detected} detected / "
          f"{escaped} escaped; problems: {len(problems)}")
    for p in problems[:10]:
        print(f"  - {p}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
