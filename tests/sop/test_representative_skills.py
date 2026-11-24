from pathlib import Path

from business_tools import BusinessStore
from skill_engine.representative import run_representative

ROOT = Path(__file__).resolve().parents[2] / "skills"


def test_product_lookup_uses_scoped_catalog_and_inventory(tmp_path):
    store = BusinessStore(tmp_path / "product.sqlite", initial={
        "products": {"SKU-R1": {"sku": "SKU-R1", "unit": "box"}},
        "inventory": {"SKU-R1|east": {"available": 18}},
    })
    result = run_representative(ROOT / "product-information", store, "employee", "session",
                                {"products": {"SKU-R1"}, "inventory": {"SKU-R1|east"}},
                                {"sku": "SKU-R1", "warehouse": "east"})
    assert (result["available"], result["unit"]) == (18, "box")


def test_ticket_recommendation_inherits_verified_order(tmp_path):
    store = BusinessStore(tmp_path / "customer.sqlite", initial={
        "purchase_orders": {"PO-R1": {"order_id": "PO-R1", "delivery_status": "overdue"}},
    })
    result = run_representative(ROOT / "customer-service", store, "employee", "session",
                                {"purchase_orders": {"PO-R1"}}, {"order_id": "PO-R1", "subject": "Late delivery"})
    assert result["priority"] == "high"
    assert result["order_id"] == "PO-R1"
    assert store.snapshot()["tickets"] == {}
