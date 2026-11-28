"""N05A mutation tests: weakened evaluators must be detected.

Each mutant removes exactly one scoring rule (drops one reason code). A
mutant is DETECTED when it wrongly accepts at least one critical negative
whose only failure reason was the dropped rule - i.e. every scoring rule is
load-bearing. Substring-style weakening is covered by the entity mutant
(folding replaced with containment) to show why substring matching is
forbidden as a primary method.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from nanoagent.eval import CognitiveEvaluator  # noqa: E402
from nanoagent.eval import contracts, controls  # noqa: E402
from nanoagent.eval.contracts import Response  # noqa: E402


def registry():
    return {c.case_id: c for c in controls.battery()}


class MutantEvaluator(CognitiveEvaluator):
    """Drops every occurrence of one reason code (a removed scoring rule)."""

    dropped: str = ""

    def evaluate(self, case_id, response):  # type: ignore[override]
        r = super().evaluate(case_id, response)
        if r.passed or self.dropped not in r.reasons:
            return r
        kept = tuple(x for x in r.reasons if x != self.dropped)
        return contracts.EvaluationResult(r.case_id, r.family,
                                          not kept, kept)


class SubstringEntityMutantEvaluator(CognitiveEvaluator):
    """Weakened to substring containment for entity comparisons: any label
    that contains (or is contained in) an expected label is accepted."""

    def evaluate(self, case_id, response):  # type: ignore[override]
        c = registry()[case_id]
        if c.family == "entity_reference":
            from nanoagent.eval.comparators import canonical_label
            got = {canonical_label(str(e)) for e in response.entities}
            exp_ids = {canonical_label(str(e)) for e in c.expectation.entity_ids}
            if got and all(any(g in e or e in g for e in exp_ids) for g in got):
                return contracts.EvaluationResult(case_id, c.family, True, ())
        return super().evaluate(case_id, response)


def make_mutant(cls_dropped):
    return type("Mutant", (MutantEvaluator,), {"dropped": cls_dropped})()


class TestMutationDetection(unittest.TestCase):
    def _critical_negative(self, ev: CognitiveEvaluator, rule: str):
        """A single-defect negative whose only reason is `rule`; the mutant
        must accept it (rule removed) while the true evaluator rejects it."""
        reg = registry()
        for cid, c in reg.items():
            if c.control_class != f"negative:{rule}":
                continue
            true_r = CognitiveEvaluator().evaluate(cid, c.response)
            mut_r = ev.evaluate(cid, c.response)
            if true_r.reasons == (rule,) and mut_r.passed:
                return cid
        return None

    def test_every_scoring_rule_is_load_bearing(self):
        rules = set()
        for c in registry().values():
            if c.control_class.startswith("negative:"):
                rules.add(c.control_class.split(":", 1)[1])
        self.assertGreaterEqual(len(rules), 12)
        for rule in sorted(rules):
            detected = self._critical_negative(make_mutant(rule), rule)
            self.assertIsNotNone(
                detected,
                f"mutant dropping {rule} was NOT detected: no critical "
                f"negative solely protected by this rule")

    def test_substring_entity_mutant_detected(self):
        # A substring-weakened entity check accepts a superstring entity id
        # ("C-9-vip" contains "C-9"); the true evaluator must reject it with
        # ENTITY_MISMATCH - this is why substring matching is forbidden as a
        # primary correctness method.
        ev = CognitiveEvaluator()
        r = ev.evaluate("entity.pos", Response(entities=("ORD-1042", "C-9-vip")))
        self.assertFalse(r.passed)
        self.assertEqual(r.reasons, ("ENTITY_MISMATCH",))
        mut = SubstringEntityMutantEvaluator()
        rm = mut.evaluate("entity.pos", Response(entities=("ORD-1042", "C-9-vip")))
        self.assertTrue(rm.passed, "substring mutant should wrongly accept")

    def test_unit_blind_mutant_detected_via_money(self):
        # Dropping UNIT_MISMATCH accepts 120 USD as 120 CNY.
        mut = make_mutant("UNIT_MISMATCH")
        reg = registry()
        c = reg["num.neg.unit_mismatch"]
        self.assertTrue(mut.evaluate("num.neg.unit_mismatch", c.response).passed)
        self.assertFalse(
            CognitiveEvaluator().evaluate("num.neg.unit_mismatch", c.response).passed)

    def test_polarity_blind_mutant_detected(self):
        # Dropping DECISION_MISMATCH accepts premature stop.
        mut = make_mutant("DECISION_MISMATCH")
        reg = registry()
        c = reg["stop.neg.premature"]
        self.assertTrue(mut.evaluate("stop.neg.premature", c.response).passed)
        self.assertFalse(
            CognitiveEvaluator().evaluate("stop.neg.premature", c.response).passed)


if __name__ == "__main__":
    unittest.main()
