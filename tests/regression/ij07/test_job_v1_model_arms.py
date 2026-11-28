import json

from benchmarks.job_productivity_v1.holdout.dataset import load
from benchmarks.job_productivity_v1.holdout.model_arms import Session, model_messages, run_case
from business_tools import BusinessStore
from model_gateway import Proposal


class Wire:
    base_url = "synthetic"

    def __init__(self, steps):
        self.requests = []
        self.steps = iter(steps)

    def chat(self, _url, body):
        payload = next(self.steps)
        reply = {"choices": [{"message": {"role": "assistant", **payload},
                              "finish_reason": "tool_calls" if payload.get("tool_calls") else "stop"}],
                 "usage": {"prompt_tokens": 8, "completion_tokens": 4}}
        self.requests.append({"request": body, "http_status": 200, "render_status": 200,
                              "source_generation": {"capture": "fixture"}, "raw_response": json.dumps(reply)})
        return reply


def call(call_id, name, **arguments):
    return {"tool_calls": [{"id": call_id, "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments)}}]}


def test_treatments_preserve_same_input_and_causal_contrasts(tmp_path):
    case = load().cases["JOB-PRD-128"]
    host = BusinessStore(tmp_path / "tools.sqlite", initial=case.world["state"])
    assert [tool["function"]["name"] for tool in Session(case, host, "A").tools()] == ["read_record", "stage_draft"]
    assert [tool["function"]["name"] for tool in Session(case, host, "B").tools()] == [
        "get_purchase_order", "get_supplier", "get_product", "get_inventory", "stage_delivery_review"]
    assert Session(case, host, "C").tools() == []
    a, b, c, d, e = [model_messages(case, arm)[0] for arm in "ABCDE"]
    assert a[0] == b[0] and a[1:] == b[1:] == c[1:] == d[1:] == e[1:]
    assert c[0] != d[0] and d == e
    assert len(d) == 3 and d[-1]["role"] == "user"


def test_a_b_free_reads_and_c_e_deterministic_flows_score_same_case(tmp_path):
    case = load().cases["JOB-PRD-001"]
    expected = case.expected["answer"]
    bill = {"sku": expected["sku"], "warehouse": expected["warehouse"]}
    for arm in "AB":
        sku, inventory = bill["sku"], f'{bill["sku"]}|{bill["warehouse"]}'
        left = call("a", "read_record", table="products", key=sku) if arm == "A" else call("a", "get_product", sku=sku)
        right = (call("b", "read_record", table="inventory", key=inventory) if arm == "A"
                 else call("b", "get_inventory", inventory_id=inventory))
        result = run_case(case, tmp_path / f"{arm}.sqlite", arm, "synthetic", Wire([
            left, right, {"content": json.dumps(expected)}]), seed=17)
        assert result["status"] == "PASS" and result["model_calls"] == 3
        assert result["model_tool_calls"] == 2
    for arm in "CDE":
        reply = {"workflow": "product-information", "fields": bill}
        result = run_case(case, tmp_path / f"{arm}.sqlite", arm, "synthetic", Wire([
            {"content": json.dumps(reply)}]), seed=17)
        assert result["status"] == "PASS" and result["model_calls"] == 1
        assert result["model_tool_calls"] == 0 and result["host_gateway_transactions"] == 2


def test_a_b_cannot_bypass_draft_provenance_or_scope(tmp_path):
    case = load().cases["JOB-DOC-001"]
    store = BusinessStore(tmp_path / "review.sqlite", initial=case.world["state"])
    session = Session(case, store, "B")
    note = case.expected["native_input"]
    draft = dict(note=note, recommendation="MATCH", differences=[])
    result = session.execute(Proposal("guess", "stage_delivery_review", json.dumps(draft)))
    assert result["error"] and store.snapshot()["review_drafts"] == {}
    for proposed in (call("a", "get_purchase_order", order_id=note["order_id"]),
                     call("b", "get_supplier", supplier_id=note["supplier_id"]),
                     call("c", "get_product", sku=note["lines"][0]["sku"])):
        entry = proposed["tool_calls"][0]
        assert "error" not in session.execute(Proposal(entry["id"], entry["function"]["name"], entry["function"]["arguments"]))
    result = session.execute(Proposal("bad", "stage_delivery_review", json.dumps({**draft, "recommendation": "ESCALATE"})))
    assert result["error"] and store.snapshot()["review_drafts"] == {}
    result = session.execute(Proposal("valid", "stage_delivery_review", json.dumps(draft)))
    assert result["submitted"] is False and store.snapshot()["review_drafts"]


def test_illegal_same_turn_draft_and_invalid_c_intake_fail_closed(tmp_path):
    case = load().cases["JOB-DOC-001"]
    note = case.expected["native_input"]
    proposed = [call("a", "get_purchase_order", order_id=note["order_id"]),
                call("b", "get_supplier", supplier_id=note["supplier_id"]),
                call("c", "get_product", sku=note["lines"][0]["sku"]),
                call("w", "stage_delivery_review", note=note, recommendation="MATCH", differences=[])]
    same_batch = {"tool_calls": [item["tool_calls"][0] for item in proposed]}
    wire = Wire([same_batch, {"content": json.dumps(case.expected["answer"])}])
    row = run_case(case, tmp_path / "same-turn.sqlite", "B", "synthetic", wire, seed=17)
    assert row["status"] == "FAIL" and row["after_sqlite"]["review_drafts"] == {}
    assert row["model_tool_trace"][-1]["result"] == {"error": "BUSINESS_VALIDATION_ERROR"}

    wire = Wire([{"content": '{"workflow":"document-review","fields":{"order_id":"PO-1"}}'}])
    row = run_case(case, tmp_path / "invalid.sqlite", "C", "synthetic", wire, seed=17)
    assert row["status"] == "FAIL" and row["tool_calls"] == 0
    assert row["after_sqlite"]["review_drafts"] == {}
