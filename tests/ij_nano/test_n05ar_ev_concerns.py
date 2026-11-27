"""N05A-R (IJ-NANO-1.2): red reproduction of the seven source-review
concerns EV01-EV07 against the N05A evaluator, then permanent regression
suite after repair.

Red phase: every test asserts the REQUIRED (contract v2) behaviour; against
the unrepaired implementation the EV-relevant assertions fail (or surface
as capability-absence failures via ``_require``). The red run is captured
verbatim in ``evidence/IJNANO/N05AR/red_run.txt`` before any repair.

Concerns (mission order IJ-NANO-1.2 section 2):
EV01 incomplete state predicates / positional matching
EV02 undeclared action arguments / no optional-argument contract
EV03 predicate semantics: expression equivalence vs truth vs world state
EV04 identifier collisions via blanket canonical folding
EV05 missing unit silently inherited from hidden expectations
EV06 comparator-level mutation testing (real weakened comparators)
EV07 reason-code coverage reconciliation + strict dataset qualification
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.eval import CognitiveEvaluator  # noqa: E402
from nanoagent.eval import comparators, contracts, controls  # noqa: E402
from nanoagent.eval.contracts import (  # noqa: E402
    Expectation, Quantity, Response, SlotSpec, StatePredicate)


def run(exp: Expectation, resp: Response) -> list[str]:
    return comparators.evaluate_family(exp, resp)


def _capability(test, description, fn):
    """Convert a missing-API capability into a clean assertion failure so
    the red run records it as FAIL (capability absent), not an error."""
    try:
        return fn()
    except (AttributeError, ImportError, TypeError) as e:
        test.fail(f"capability absent: {description} ({type(e).__name__}: {e})")


P_SHIP = lambda: StatePredicate("ORD-1042", "ship_status", "eq", "shipped")
P_PAID = lambda: StatePredicate("ORD-1042", "payment_status", "eq", "paid")
P_AGE = lambda: StatePredicate("ORD-1042", "days_since_order", "le", 30)


def _action_slots():
    return (SlotSpec("order_id", "entity", "ORD-1042"),
            SlotSpec("amount", "quantity", 120.0, unit="CNY"))


class TestEV01StatePredicates(unittest.TestCase):
    """state_interpretation must detect missing required predicates,
    duplicates, and accept any order (identity-based matching)."""

    def _exp(self, *preds, allow_extra=False):
        return Expectation("state_interpretation",
                           state_predicates=tuple(preds),
                           allow_extra_assertions=allow_extra)

    def test_all_required_correct_passes(self):
        self.assertEqual(run(self._exp(P_SHIP(), P_PAID(), P_AGE()),
                             Response(state_predicates=(P_SHIP(), P_PAID(), P_AGE()))), [])

    def test_missing_final_predicate_detected(self):
        reasons = run(self._exp(P_SHIP(), P_PAID()),
                      Response(state_predicates=(P_SHIP(),)))
        self.assertIn("MISSING_PREDICATE", reasons,
                      f"missing required predicate accepted: {reasons}")

    def test_missing_middle_predicate_detected(self):
        reasons = run(self._exp(P_SHIP(), P_PAID(), P_AGE()),
                      Response(state_predicates=(P_SHIP(), P_AGE())))
        self.assertIn("MISSING_PREDICATE", reasons,
                      f"missing middle predicate not reported: {reasons}")

    def test_only_first_predicate_correct_still_fails(self):
        reasons = run(self._exp(P_SHIP(), P_PAID()),
                      Response(state_predicates=(P_SHIP(),)))
        self.assertTrue(reasons, "single correct predicate accepted as complete")

    def test_duplicate_predicate_detected(self):
        # single-defect form: a redundant duplicate of an already-satisfied
        # predicate (the mixed (SHIP, SHIP) form also reports the then-missing
        # PAID predicate - two legitimate reasons for two defects)
        reasons = run(self._exp(P_SHIP(), P_PAID()),
                      Response(state_predicates=(P_SHIP(), P_PAID(), P_SHIP())))
        self.assertEqual(reasons, ["DUPLICATE_PREDICATE"],
                         f"duplicate claim must fail for exactly its reason: {reasons}")

    def test_contradictory_claims_detected_as_duplicate_identity(self):
        # eq + ne on the same (entity, property) is the one-claim-per-identity
        # violation; contradiction is reported before per-predicate comparison.
        contra = StatePredicate("ORD-1042", "payment_status", "ne", "paid")
        reasons = run(self._exp(P_SHIP(), P_PAID()),
                      Response(state_predicates=(P_SHIP(), P_PAID(), contra)))
        self.assertEqual(reasons, ["DUPLICATE_PREDICATE"],
                         f"contradictory duplicate identity: {reasons}")

    def test_valid_predicates_different_order_pass(self):
        reasons = run(self._exp(P_SHIP(), P_PAID()),
                      Response(state_predicates=(P_PAID(), P_SHIP())))
        self.assertEqual(reasons, [], f"valid predicates reordered rejected: {reasons}")

    def test_extra_incorrect_predicate_fails_for_exactly_extra(self):
        extra = StatePredicate("ORD-9999", "ship_status", "eq", "lost")
        reasons = run(self._exp(P_SHIP(), P_PAID()),
                      Response(state_predicates=(P_SHIP(), P_PAID(), extra)))
        self.assertEqual(reasons, ["EXTRA_ASSERTION"],
                         f"single-defect extra claim must map to exactly one reason: {reasons}")


class TestEV02UndeclaredActionArguments(unittest.TestCase):
    """action_representation must reject undeclared args and support an
    explicit optional-argument contract; not rely on extra_assertions."""

    def _exp(self, **kw):
        kw.setdefault("tool", "refunds.submit")
        kw.setdefault("slots", _action_slots())
        return Expectation("action_representation", **kw)

    def _correct_args(self):
        return {"order_id": "ORD-1042", "amount": {"value": 120.0, "unit": "CNY"}}

    def test_correct_required_arguments_pass(self):
        self.assertEqual(
            run(self._exp(), Response(tool="refunds.submit", args=self._correct_args())), [])

    def test_unknown_argument_field_rejected(self):
        args = self._correct_args()
        args["customer_tier"] = "gold"
        reasons = run(self._exp(), Response(tool="refunds.submit", args=args))
        self.assertIn("ARGUMENT_UNDECLARED", reasons,
                      f"unknown response.args key accepted: {reasons}")

    def test_consequential_unauthorized_option_rejected(self):
        args = self._correct_args()
        args["force_skip_policy"] = True
        reasons = run(self._exp(), Response(tool="refunds.submit", args=args))
        self.assertIn("ARGUMENT_UNDECLARED", reasons,
                      f"unauthorized consequential option accepted: {reasons}")

    def test_missing_required_argument_rejected(self):
        reasons = run(self._exp(),
                      Response(tool="refunds.submit", args={"order_id": "ORD-1042"}))
        self.assertIn("MISSING_SLOT", reasons)

    def test_declared_optional_arguments_pass_and_undeclared_still_fail(self):
        def build():
            slots = (SlotSpec("order_id", "entity", "ORD-1042"),
                     SlotSpec("notify_channel", "enum", "email", optional=True))
            return Expectation("action_representation",
                               tool="refunds.submit", slots=slots)
        exp = _capability(self, "optional SlotSpec contract", build)
        with_opt = Response(tool="refunds.submit",
                            args={"order_id": "ORD-1042", "notify_channel": "email"})
        self.assertEqual(run(exp, with_opt), [], "declared optional argument rejected")
        undeclared = Response(tool="refunds.submit",
                              args={"order_id": "ORD-1042", "escalate": True})
        self.assertIn("ARGUMENT_UNDECLARED", run(exp, undeclared))

    def test_duplicate_keys_in_raw_structured_output_rejected(self):
        raw = ('{"tool": "refunds.submit", "order_id": "ORD-1042", '
               '"order_id": "ORD-9999", "amount": {"value": 120.0, "unit": "CNY"}}')
        reasons = run(self._exp(),
                      Response(tool="refunds.submit", args=self._correct_args(), raw=raw))
        self.assertIn("PARSE_INVALID", reasons,
                      f"duplicate keys in raw output not detected: {reasons}")

    def test_extra_assertions_channel_is_not_the_only_guard(self):
        # No extra_assertions set at all - the undeclared-argument rule must
        # fire from response.args alone (no upstream parser help).
        args = self._correct_args()
        args["admin_override"] = "true"
        resp = Response(tool="refunds.submit", args=args, extra_assertions=())
        self.assertIn("ARGUMENT_UNDECLARED", run(self._exp(), resp))


class TestEV03PredicateSemantics(unittest.TestCase):
    """Separate predicate expression equivalence from predicate truth
    against an independently supplied world state; typed, crash-free."""

    def test_truth_against_world_state(self):
        def truth():
            world = {("ORD-1042", "days_since_order"): 45}
            return comparators.predicate_truth(
                StatePredicate("ORD-1042", "days_since_order", "le", 30), world)
        reasons = _capability(self, "predicate_truth(pred, world)", truth)
        self.assertTrue(reasons, "claim le 30 must not hold when world observes 45")

    def test_truth_operators_and_boundaries(self):
        def truth(pred, observed):
            world = {("INV-7", "qty"): observed}
            return comparators.predicate_truth(
                StatePredicate("INV-7", "qty", pred, 5), world)
        cases = [("eq", 5, True), ("eq", 5.0, True), ("eq", 6, False),
                 ("ne", 6, True), ("ne", 5, False),
                 ("gt", 5, False), ("gt", 5.0001, True), ("gt", 4, False),
                 ("ge", 5, True), ("ge", 4.999, False),
                 ("lt", 5, False), ("lt", 4.999, True),
                 ("le", 5, True), ("le", 5.0001, False)]
        for op, obs, want in cases:
            with self.subTest(op=op, obs=obs):
                reasons = _capability(self, "predicate_truth", lambda: truth(op, obs))
                self.assertEqual(not reasons, want, f"{op} vs {obs}: {reasons}")

    def test_truth_rejects_invalid_types_without_crashing(self):
        def truth():
            world = {("INV-7", "qty"): "high"}
            return comparators.predicate_truth(
                StatePredicate("INV-7", "qty", "gt", 100), world)
        reasons = _capability(self, "predicate_truth", truth)
        self.assertEqual(reasons, ["TYPE_MISMATCH"])

    def test_truth_with_units(self):
        def truth():
            world = {("ORD-1042", "total"): {"value": 120.0, "unit": "CNY"}}
            return comparators.predicate_truth(
                StatePredicate("ORD-1042", "total", "ge", 120.0, unit="CNY"), world)
        reasons = _capability(self, "predicate_truth with units", truth)
        self.assertEqual(reasons, [])
        def truth2():
            world = {("ORD-1042", "weight"): {"value": 1500.0, "unit": "m"}}
            return comparators.predicate_truth(
                StatePredicate("ORD-1042", "weight", "le", 2.0, unit="km"), world)
        self.assertEqual(_capability(self, "predicate_truth unit conversion", truth2), [])

    def test_expression_equivalence_is_exact_not_cross_operator(self):
        def equiv(a, b):
            return comparators.predicates_equivalent(a, b)
        base = StatePredicate("ORD-1042", "days_since_order", "ge", 5)
        same = StatePredicate("ORD-1042", "days_since_order", "ge", 5)
        cross_op = StatePredicate("ORD-1042", "days_since_order", "gt", 4)
        self.assertEqual(_capability(self, "predicates_equivalent",
                                     lambda: equiv(base, same)), [])
        reasons = _capability(self, "predicates_equivalent",
                              lambda: equiv(base, cross_op))
        self.assertTrue(reasons, "cross-operator equivalence is outside the contract")

    def test_equivalence_does_not_crash_on_invalid_value_type(self):
        # claimed value non-numeric where a numeric comparison is required:
        # must be TYPE_MISMATCH, never a Python TypeError crash (the v1
        # comparator raised TypeError here).
        exp_pred = StatePredicate("ORD-1042", "days_since_order", "le", 30)
        claimed = StatePredicate("ORD-1042", "days_since_order", "le", "thirty")
        reasons = comparators.predicates_equivalent(claimed, exp_pred)
        self.assertEqual(reasons, ["TYPE_MISMATCH"],
                         f"invalid value type must not crash or pass: {reasons}")

    def test_equivalence_checks_claimed_threshold_is_not_treated_as_observed(self):
        # The threshold-only comparison (claimed gt 100 vs expected gt 100)
        # must not be evidence that the business value exceeds 100; only
        # predicate_truth against a world observation can establish that.
        def truth():
            world = {("ORD-1042", "total"): 50.0}
            return comparators.predicate_truth(
                StatePredicate("ORD-1042", "total", "gt", 100), world)
        reasons = _capability(self, "predicate_truth", truth)
        self.assertTrue(reasons, "threshold agreement is not observed truth")


class TestEV04IdentifierCollisions(unittest.TestCase):
    """Folding belongs to closed-vocabulary labels only; tool / entity /
    action identifiers use exact identity unless an alias contract is
    declared."""

    def test_label_folding_still_applies_to_closed_vocab(self):
        exp = Expectation("intent", intent="refund_request")
        self.assertEqual(run(exp, Response(intent="Refund  Request")), [])

    def test_underscore_space_tool_collision_rejected(self):
        exp = Expectation("tool_selection", tool="adjust_stock")
        reasons = run(exp, Response(tool="adjust stock"))
        self.assertEqual(reasons, ["TOOL_MISMATCH"],
                         "blanket folding merges distinct tool identifiers")

    def test_entity_identifiers_are_case_sensitive(self):
        exp = Expectation("entity_reference", entity_ids=("ORD-1042", "C-9"))
        reasons = run(exp, Response(entities=("ord-1042", "c-9")))
        self.assertEqual(reasons, ["ENTITY_MISMATCH"],
                         "case folding must not merge distinct entity ids")

    def test_leading_zeros_do_not_collide(self):
        exp = Expectation("entity_reference", entity_ids=("C-07",))
        self.assertEqual(run(exp, Response(entities=("C-7",))), ["ENTITY_MISMATCH"])
        self.assertEqual(run(exp, Response(entities=("C-07",))), [])

    def test_unicode_variants_do_not_collide(self):
        exp = Expectation("entity_reference", entity_ids=("C-9",))
        self.assertEqual(run(exp, Response(entities=("\uff23-9",))), ["ENTITY_MISMATCH"])

    def test_action_tool_argument_entity_exact_identity(self):
        slots = (SlotSpec("order_id", "entity", "ORD-1042"),)
        exp = Expectation("action_representation", tool="refunds.submit", slots=slots)
        reasons = run(exp, Response(tool="Refunds.Submit",
                                    args={"order_id": "ORD-1042"}))
        self.assertIn("TOOL_MISMATCH", reasons, "tool ids must match exactly")

    def test_alias_contract_permits_declared_variants_only(self):
        def match():
            return comparators.identifier_matches(
                "ORD_1042", "ORD-1042", "entity",
                aliases={"ORD-1042": ("ORD_1042",)})
        self.assertTrue(_capability(self, "identifier_matches alias contract", match))
        def mismatch():
            return comparators.identifier_matches(
                "ORD1042", "ORD-1042", "entity",
                aliases={"ORD-1042": ("ORD_1042",)})
        self.assertFalse(_capability(self, "identifier_matches alias contract", mismatch))

    def test_canonical_label_documented_scope(self):
        # canonical_label itself remains, but only as the LABEL folding rule.
        self.assertEqual(comparators.canonical_label("Refund_Request"), "refund request")


class TestEV05MissingUnitHandling(unittest.TestCase):
    """A scalar must not silently inherit the hidden expected unit unless
    the unit is publicly declared for the slot."""

    def _exp(self, **slot_kw):
        slot = SlotSpec("amount", "quantity", 120.0, unit="CNY", **slot_kw)
        return Expectation("slot_value", slots=(slot,))

    def test_explicit_unit_passes(self):
        self.assertEqual(
            run(self._exp(), Response(args={"amount": {"value": 120.0, "unit": "CNY"}})), [])

    def test_scalar_without_public_declaration_rejected(self):
        reasons = run(self._exp(), Response(args={"amount": 120.0}))
        self.assertIn("UNIT_MISSING", reasons,
                      f"scalar silently inherited hidden expected unit: {reasons}")

    def test_scalar_with_publicly_declared_unit_passes(self):
        def go():
            return run(self._exp(unit_publicly_declared=True),
                       Response(args={"amount": 120.0}))
        self.assertEqual(_capability(
            self, "unit_publicly_declared contract", go), [])

    def test_incorrect_unit_rejected(self):
        reasons = run(self._exp(), Response(args={"amount": {"value": 120.0, "unit": "USD"}}))
        self.assertEqual(reasons, ["UNIT_MISMATCH"])

    def test_incompatible_dimension_rejected(self):
        reasons = run(self._exp(), Response(args={"amount": {"value": 120.0, "unit": "min"}}))
        self.assertEqual(reasons, ["UNIT_MISMATCH"])

    def test_currency_mismatch_is_unit_mismatch(self):
        reasons = run(self._exp(), Response(args={"amount": {"value": 120.0, "unit": "EUR"}}))
        self.assertEqual(reasons, ["UNIT_MISMATCH"])

    def test_non_finite_value_rejected(self):
        for bad in (float("nan"), float("inf")):
            reasons = run(self._exp(), Response(args={"amount": {"value": bad, "unit": "CNY"}}))
            self.assertEqual(reasons, ["TYPE_MISMATCH"], f"{bad}: {reasons}")

    def test_numeric_string_not_coerced(self):
        reasons = run(self._exp(), Response(args={"amount": {"value": "120", "unit": "CNY"}}))
        self.assertEqual(reasons, ["TYPE_MISMATCH"])


class TestEV06ComparatorLevelMutants(unittest.TestCase):
    """Real comparator-level mutants (weakened logic inside the comparator)
    must be rejected by the qualification gate: for every mutant class
    there is a battery or predicate-truth control the true evaluator
    rejects and the mutant accepts."""

    def test_every_comparator_mutant_is_detected(self):
        from nanoagent.eval.qualification import mutation_gate
        report = _capability(self, "mutation gate", lambda: mutation_gate())
        undetected = sorted(m for m, r in report.items() if not r["detected"])
        self.assertEqual(
            undetected, [],
            f"comparator mutants the gate fails to reject: {undetected} "
            f"(report: {report})")
        for m, r in report.items():
            self.assertTrue(r["witness"], f"{m} lacks a witness control")


class TestEV07CoverageReconciliation(unittest.TestCase):
    """Declared, reachable and tested reason codes must reconcile; strict
    validation rejects malformed evaluator inputs."""

    def test_every_declared_reason_code_has_a_negative_control(self):
        def declared():
            return set(contracts.REASON_CODES)
        codes = _capability(self, "REASON_CODES v2 contract", declared)
        tested = set()
        for c in controls.battery():
            if c.control_class.startswith("negative:"):
                tested.add(c.control_class.split(":", 1)[1])
        missing = sorted(codes - tested)
        self.assertEqual(missing, [], f"declared but untested reason codes: {missing}")

    def test_parse_invalid_has_a_negative_control(self):
        classes = {c.control_class for c in controls.battery()}
        self.assertIn("negative:PARSE_INVALID", classes)

    def test_obsolete_argument_mismatch_has_disposition(self):
        def disposition():
            return contracts.REASON_CODE_DISPOSITIONS["ARGUMENT_MISMATCH"]
        d = _capability(self, "reason-code disposition record", disposition)
        self.assertIn("obsolete", d["status"].lower())

    def test_malformed_expectation_rejected(self):
        def build():
            return Expectation("state_interpretation", state_predicates=())
        with self.assertRaises(ValueError, msg="empty state expectation accepted"):
            build()
        def build2():
            return Expectation("numeric_value_unit", quantity=Quantity(1.0, "lightyear"))
        with self.assertRaises(ValueError, msg="unregistered unit accepted"):
            build2()

    def test_malformed_control_battery_rejected(self):
        def build():
            bad = contracts.ControlCase(
                "bad.dup", "intent", "positive",
                Expectation("intent", intent="x"), Response(intent="x"))
            from nanoagent.eval.qualification import validate_control_battery
            return validate_control_battery([bad, bad])
        with self.assertRaises(ValueError):
            _capability(self, "validate_control_battery", build)

    def test_family_scope_qualification_contract(self):
        from nanoagent.eval.qualification import qualify_family_scope
        record = _capability(
            self, "qualify_family_scope",
            lambda: qualify_family_scope({
                "task_family": "n03.enumarated_action.v1",
                "evaluator_identity": "nanoagent.eval@2",
                "positive_witness": ["case-001"],
                "negative_controls": ["case-002"],
                "semantic_mutations": ["case-003"],
                "alternative_responses": [],
            }))
        self.assertEqual(record["status"], "QUALIFIED",
                         f"scope qualification rule broken: {record}")


if __name__ == "__main__":
    unittest.main()
