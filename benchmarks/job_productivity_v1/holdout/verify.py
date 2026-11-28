"""Validate the freeze and exercise the synthetic business reference paths."""

from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from business_tools import BusinessStore
from model_gateway import ExecutionContext, Gateway, GatewayError, Grant, Policy, Proposal, ToolSpec
from skill_engine.document_review import ID, ReviewSession, _object
from skill_engine.representative import run_representative

from .dataset import CATEGORIES, ROOT, canonical, experiment_contract, load, repeat_selection
from .generate import FACETS
from .oracle import ACTOR, evaluate


SKILLS = Path(__file__).resolve().parents[3] / "skills"
READ_TABLE = {"get_product": "products", "get_inventory": "inventory", "get_order": "purchase_orders",
              "get_purchase_order": "purchase_orders", "get_supplier": "suppliers"}


def require(check, message):
    if not check:
        raise ValueError(f"invalid JOB-V1 freeze: {message}")


def _verify_denial(case, store, session_id):
    table = "products" if case.plan["category"] == "product-information" else "purchase_orders"
    candidates = case.world["state"][table]
    resource = next(iter(candidates))
    granted = frozenset(case.world["permitted_reads"].get(table, ()))
    grant = Grant(ACTOR, "fixture", "lookup", granted, frozenset({"read"}))
    spec = ToolSpec(_object({"reference": ID}), lambda args: args["reference"],
                    lambda unit, args, _ctx: unit.get(table, args["reference"]))
    gateway = Gateway(store, {"lookup": spec}, Policy((grant,)))
    try:
        gateway.execute(Proposal("reject", "lookup", json.dumps({"reference": resource})),
                        ExecutionContext(ACTOR, "fixture", session_id, "read"))
    except GatewayError as error:
        require(str(error.code) == "POLICY_DENIED", "scope denial returned the wrong error")
    else:
        require(False, "scope-denied fixture allowed access")


def replay_reference(case, directory):
    """Test the skills using known-good intake, without claiming a treatment outcome."""
    identity, category = case.plan["case_id"], case.plan["category"]
    store = BusinessStore(directory / f"{identity}.sqlite3", initial=case.world["state"])
    before = store.snapshot()
    scopes = case.world["permitted_reads"]
    structured = case.expected["native_input"]
    if structured is None:
        # This protects the fixture's terminal decision and state assertions.
        # Deriving a terminal decision from the natural request is measured later.
        answer = case.expected["answer"]
        if case.expected["disposition"] == "refused":
            _verify_denial(case, store, identity)
    elif category == "document-review":
        session = ReviewSession(store, SKILLS / category, ACTOR, identity, identity,
                                set(scopes["purchase_orders"]), set(scopes["suppliers"]), set(scopes["products"]))
        result = session.propose(structured)
        answer = {name: result[name] for name in ("order_id", "recommendation", "differences")}
    elif category == "customer-service":
        result = run_representative(SKILLS / category, store, ACTOR, identity, scopes, structured)
        answer = {name: result[name] for name in ("order_id", "subject", "priority", "status")}
    else:
        result = run_representative(SKILLS / category, store, ACTOR, identity, scopes, structured)
        answer = {"sku": result["sku"], "warehouse": structured["warehouse"],
                  "unit": result["unit"], "available": result["available"]}
    after = store.snapshot()
    reads = [(READ_TABLE[event["tool"]], event["resource"], event["result"])
             for event in after["audit_events"].values() if event["status"] == "READ"]
    return {"answer": answer, "reads": reads, "before": before, "after": after,
            "delivered_followups": [event["id"] for event in case.task["followups"]]}


def verify(freeze, directory):
    require(freeze.manifest["version"] == "JOB-V1" and freeze.manifest["case_count"] == len(freeze.cases) == 600,
            "holdout identity and count")
    require(freeze.experiment == experiment_contract(), "six-arm experiment contract")
    require(freeze.repeat == repeat_selection([case.plan for case in freeze.cases.values()]), "repeat contract")
    distribution, outcome, physical_inputs = Counter(), Counter(), set()
    for case in freeze.cases.values():
        identity, category, facet = case.plan["case_id"], case.plan["category"], case.task["facet"]
        distribution[category, facet] += 1
        outcome[case.expected["disposition"]] += 1
        physical_inputs.add(canonical(case.input_initial()))
        require(bool(case.task["operator_message"]) and bool(case.task["attachments"]), f"{identity} task input")
        require(all(item["format"] == "text/plain" and isinstance(item["text"], str) and item["text"].strip()
                    for item in case.task["attachments"]), f"{identity} shared text extraction")
        if facet == "multi_document":
            require(len(case.task["attachments"]) >= 2, f"{identity} multiple documents")
        require(bool(case.task["followups"]) == (facet == "user_followup"), f"{identity} follow-up schedule")
        require((case.expected["draft"] is not None) == case.world["draft_allowed"], f"{identity} draft permission")
        result = evaluate(case, **replay_reference(case, directory))
        require(result["status"] == "PASS", f"{identity} reference replay: {result['findings']}")
    require(distribution == {(category, facet): 25 for category in CATEGORIES for facet in FACETS}, "category/facet balance")
    require(len(physical_inputs) == len(freeze.cases), "duplicate user-visible inputs")
    return {"fixture_status": "PASS", "fixture_cases": len(freeze.cases),
            "fixture_expected_outcomes": dict(outcome), "repeat_cases": len(freeze.repeat["cases"]),
            "trial_seeds": freeze.repeat["trial_seeds"], "measured_business_records": 0,
            "planned_business_records": freeze.experiment["planned_business_records"],
            "planned_repeat_records": freeze.experiment["planned_repeat_records"],
            "arm_status": {arm: entry["status"] for arm, entry in freeze.experiment["arms"].items()},
            "freeze_sha256": freeze.manifest["freeze_sha256"]}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT)
    with TemporaryDirectory(prefix="job-v1-holdout-") as directory:
        result = verify(load(parser.parse_args().data), Path(directory))
    print(canonical(result).decode("utf-8"), end="")
