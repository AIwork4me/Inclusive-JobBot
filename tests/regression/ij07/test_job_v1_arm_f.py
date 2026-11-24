from copy import deepcopy
import json

import pytest

from benchmarks.job_productivity_v1.holdout.arm_f import intake
from benchmarks.job_productivity_v1.holdout.dataset import load
from benchmarks.job_productivity_v1.holdout.run_f import create_plan, execute, run_case


def test_deterministic_intake_extracts_explicit_product_fields():
    request = {"operator_message": "Please check stock and availability for this request.",
               "attachments": [{"name": "request.txt", "text": "Stock at east warehouse for SKU-A12"}]}
    result = intake(request, [])
    assert result.workflow == "product-information"
    assert result.fields == {"sku": "SKU-A12", "warehouse": "east"}


def test_customer_intake_uses_explicit_receipt_correction_in_mixed_language():
    request = {"operator_message": "Please follow up on this support ticket.",
               "attachments": [{"name": "ticket.txt", "text": "Package for PO-A12 is overdue."}]}
    corrected = intake(request, ["The receipt corrected to PO-B34，旧号 PO-A12 作废。"])
    assert corrected.fields == {"order_id": "PO-B34", "subject": "Late delivery"}
    assert intake(request, ["Quantity corrected to PO-B34，旧号 PO-A12。"]).reason == "followup_ambiguous"
    assert intake(request, ["Receipt corrected to PO-B34 or use PO-C56."]).reason == "followup_ambiguous"


def test_conflicting_or_missing_inputs_stop_before_reads(tmp_path):
    freeze = load()
    for key, reason in (("JOB-DOC-076", "order_reference_missing"),
                        ("JOB-DOC-101", "order_references_conflict"),
                        ("JOB-PRD-076", "warehouse_missing")):
        case = freeze.cases[key]
        row = run_case(case, tmp_path / f"{key}.sqlite")
        assert row["status"] == "PASS"
        assert row["answer"] == {"status": "clarify", "reason": reason}
        assert row["reads"] == []
        assert row["after_sqlite"]["review_drafts"] == {}


def test_native_f_observes_followup_and_business_state(tmp_path):
    freeze = load()
    case = next(case for case in freeze.cases.values() if case.plan["category"] == "product-information"
                and case.task["facet"] == "user_followup" and case.task["language"] == "en")
    row = run_case(case, tmp_path / "followup.sqlite")
    assert row["status"] == "PASS"
    assert row["model_calls"] == row["prompt_tokens"] == row["completion_tokens"] == 0
    assert row["delivered_followups"] == ["revision-1"]
    assert row["pairing_sha256"] == case.plan["pairing_sha256"]

    case = freeze.cases["JOB-DOC-001"]
    row = run_case(case, tmp_path / "review.sqlite")
    assert row["status"] == "PASS"
    assert list(row["after_sqlite"]["review_drafts"]) == [case.plan["case_id"]]
    assert row["after_sqlite"]["review_drafts"][case.plan["case_id"]]["submitted"] is False


def test_missing_input_cannot_be_replaced_by_the_oracle(tmp_path):
    freeze = load()
    case = freeze.cases["JOB-DOC-001"]
    original = deepcopy(case.task["attachments"])
    case.task["attachments"].clear()
    row = run_case(case, tmp_path / "missing.sqlite")
    assert row["status"] == "FAIL"
    assert row["after_sqlite"]["review_drafts"] == {}
    case.task["attachments"][:] = original


def test_gateway_denial_is_measured_without_a_draft_write(tmp_path):
    case = load().cases["JOB-DOC-151"]
    row = run_case(case, tmp_path / "denied.sqlite")
    assert row["status"] == "PASS"
    assert row["correct_refusal"] and not row["completed"]
    assert row["tool_calls"] == 1 and row["business_writes"] == 0
    assert [kind["authorization"] for kind in row["after_sqlite"]["audit_events"].values()] == ["DENY"]


def test_f_rejects_changed_checkpoint_and_uses_exact_repeat_panel(tmp_path):
    freeze = load()
    roster = create_plan(freeze, "repeat", [])
    assert len(roster) == 150
    assert {trial["case_id"] for trial in roster.values()} == {row["case_id"] for row in freeze.repeat["cases"]}
    selections = create_plan(freeze, "primary", ["JOB-DOC-001", "JOB-DOC-076"])
    config = {"planned": selections, "scope": "diagnostic", "panel": "primary",
              "freeze_sha256": freeze.manifest["freeze_sha256"]}
    summary = execute(tmp_path, freeze, config)
    assert summary["outcomes"]["PASS"] == 2 and summary["model_calls"] == 0
    assert execute(tmp_path, freeze, config, resume=True) == summary
    checkpoint = next((tmp_path / "cases").glob("*.json"))
    row = json.loads(checkpoint.read_bytes())
    row["answer"] = "tampered"
    checkpoint.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="checkpoint"):
        execute(tmp_path, freeze, config, resume=True)
