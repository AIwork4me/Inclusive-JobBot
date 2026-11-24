from pathlib import Path

import pytest
from jsonschema import ValidationError

from business_tools import BusinessStore
from skill_engine.document_review import ReviewSession
from sop_engine import Step, Workflow

ROOT = Path(__file__).resolve().parents[2]
ORDER = {
    "order_id": "PO-R1", "supplier_id": "SU-R1", "currency": "CNY",
    "status": "receivable", "total_minor": 2500,
    "lines": [{"sku": "SKU-R1", "unit": "box", "quantity": 2, "unit_price_minor": 1250}],
}
NOTE = {
    "order_id": "PO-R1", "supplier_id": "SU-R1", "currency": "CNY", "total_minor": 2500,
    "lines": ORDER["lines"],
}


def session(tmp_path):
    store = BusinessStore(tmp_path / "review.sqlite", initial={
        "purchase_orders": {"PO-R1": ORDER},
        "suppliers": {"SU-R1": {"supplier_id": "SU-R1", "qualified": True}},
        "products": {"SKU-R1": {"sku": "SKU-R1", "unit": "box"}},
    })
    return ReviewSession(store, ROOT / "skills/document-review", "employee-1", "review-session",
                         "review-task", {"PO-R1"}, {"SU-R1"}, {"SKU-R1"}), store


def test_matched_delivery_stays_draft_until_explicit_confirmation(tmp_path):
    review, store = session(tmp_path)
    draft = review.propose(NOTE)
    assert draft["recommendation"] == "MATCH"
    assert store.snapshot()["approval_records"] == {}
    assert not store.snapshot()["review_drafts"]["review-task"]["submitted"]
    result = review.submit_confirmed()
    assert result["submitted"]
    assert store.snapshot()["review_drafts"]["review-task"]["submitted"]


def test_amount_mismatch_is_escalated_and_cannot_be_submitted(tmp_path):
    review, store = session(tmp_path)
    draft = review.propose({**NOTE, "total_minor": 2499})
    assert draft["recommendation"] == "ESCALATE"
    assert "total_minor" in draft["differences"]
    assert not store.snapshot()["review_drafts"]["review-task"]["submitted"]
    try:
        review.submit_confirmed()
    except ValueError:
        pass
    else:
        raise AssertionError("exceptional review submitted")


def test_access_policy_denies_unknown_order(tmp_path):
    from model_gateway import GatewayError

    review, store = session(tmp_path)
    with pytest.raises(GatewayError):
        review.propose({**NOTE, "order_id": "PO-OUTSIDE"})
    assert store.snapshot()["review_drafts"] == {}


def test_workflow_resolves_dependency_results_even_if_listed_first():
    flow = Workflow((Step("second", ("first",), "follow"), Step("first", (), "lookup")))
    log = []

    def lookup(_inputs, parents):
        log.append("first")
        assert not parents
        return {"id": "R1"}

    def follow(_inputs, parents):
        log.append("second")
        return parents["first"]["id"]

    assert flow.execute({}, {"lookup": lookup, "follow": follow})["second"] == "R1"
    assert log == ["first", "second"]


def test_workflow_rejects_cycles():
    with pytest.raises(ValueError, match="cycle"):
        Workflow((Step("first", ("second",), "a"), Step("second", ("first",), "b")))


@pytest.mark.parametrize("number", [True, 2500.0])
def test_trusted_intake_checks_minor_units_without_coercion(tmp_path, number):
    review, store = session(tmp_path)
    with pytest.raises(ValidationError):
        review.propose({**NOTE, "total_minor": number})
    assert store.snapshot()["review_drafts"] == {}
