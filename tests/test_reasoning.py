"""Checks on the three reasoners.

Run with:  python -m unittest discover tests
"""

import unittest

from rover import fol, logic
from rover.knowledge import KnowledgeBase
from rover.logic import biconditional_clauses as bic
from rover.logic import clause, neg


class Resolution(unittest.TestCase):
    def test_no_warning_clears_the_neighbours(self):
        kb = bic("T0,0", ["C1,0", "C0,1"]) + [clause(neg("T0,0"))]
        prover = logic.Prover()
        self.assertTrue(prover.entails(kb, neg("C1,0")))
        self.assertTrue(prover.entails(kb, neg("C0,1")))

    def test_a_warning_alone_proves_nothing_about_one_square(self):
        kb = bic("T0,0", ["C1,0", "C0,1"]) + [clause("T0,0")]
        prover = logic.Prover()
        self.assertFalse(prover.entails(kb, "C1,0"))
        self.assertFalse(prover.entails(kb, neg("C1,0")))

    def test_ruling_out_the_alternatives_locates_the_pit(self):
        kb = bic("T0,0", ["C1,0", "C0,1"])
        kb += [clause("T0,0"), clause(neg("C0,1"))]
        prover = logic.Prover()
        self.assertTrue(prover.entails(kb, "C1,0"))

    def test_contradiction_is_never_reported_as_a_proof_of_both(self):
        kb = bic("T1,1", ["C1,0", "C0,1", "C2,1", "C1,2"])
        kb += [clause("T1,1"), clause(neg("C1,0")), clause(neg("C0,1"))]
        prover = logic.Prover()
        self.assertFalse(prover.entails(kb, "C2,1"))
        self.assertFalse(prover.entails(kb, neg("C2,1")))


class SearchOrder(unittest.TestCase):
    """The budget has to be spent where the refutation actually is.

    Resolving a clause against the whole knowledge base, and expanding
    the support set first in first out, used to burn the step budget
    before reaching proofs that were only a few unit resolutions away.
    """

    def test_a_square_pinned_by_several_readings_is_proved(self):
        kb = bic("W1,2", ["H0,2", "H1,1", "H1,3", "H2,2"])
        kb += [clause("W1,2"), clause(neg("H0,2")), clause(neg("H1,1")), clause(neg("H1,3"))]
        prover = logic.Prover()
        self.assertTrue(prover.entails(kb, "H2,2"))
        self.assertLess(prover.steps, 200)

    def test_the_proof_survives_a_knowledge_base_full_of_noise(self):
        kb = bic("W1,2", ["H0,2", "H1,1", "H1,3", "H2,2"])
        kb += [clause("W1,2"), clause(neg("H0,2")), clause(neg("H1,1")), clause(neg("H1,3"))]
        for x in range(3, 9):
            for y in range(3, 9):
                kb += bic("W%d,%d" % (x, y), ["H%d,%d" % (x + 1, y), "H%d,%d" % (x, y + 1)])
        prover = logic.Prover()
        self.assertTrue(prover.entails(kb, "H2,2"))

    def test_an_unentailed_query_is_still_refused(self):
        kb = bic("W1,2", ["H0,2", "H1,1", "H1,3", "H2,2"])
        kb += [clause("W1,2"), clause(neg("H0,2"))]
        prover = logic.Prover()
        self.assertFalse(prover.entails(kb, "H2,2"))
        self.assertFalse(prover.entails(kb, neg("H2,2")))


class ForwardChaining(unittest.TestCase):
    def test_a_rule_fires_once_its_premises_are_present(self):
        kb = fol.FolKB(fol.TERRAIN_RULES)
        kb.tell(("Cell", "0,0"))
        kb.tell(("Adjacent", "0,0", "1,0"))
        kb.tell(("Visited", "0,0"))
        kb.tell(("NoWarning", "0,0"))
        kb.tell(("NoAlert", "0,0"))
        kb.forward_chain()
        self.assertTrue(kb.holds(("Safe", "1,0")))

    def test_an_alert_blocks_the_safety_conclusion(self):
        kb = fol.FolKB(fol.TERRAIN_RULES)
        kb.tell(("Cell", "0,0"))
        kb.tell(("Adjacent", "0,0", "1,0"))
        kb.tell(("Visited", "0,0"))
        kb.tell(("NoWarning", "0,0"))
        kb.tell(("Alert", "0,0"))
        kb.forward_chain()
        self.assertTrue(kb.holds(("NoHazard", "1,0")))
        self.assertFalse(kb.holds(("Safe", "1,0")))

    def test_unify_refuses_to_bind_one_variable_two_ways(self):
        self.assertIsNone(fol.unify(("Adjacent", "?c", "?c"), ("Adjacent", "0,0", "1,0"), {}))
        self.assertEqual(
            fol.unify(("Adjacent", "?a", "?b"), ("Adjacent", "0,0", "1,0"), {}),
            {"?a": "0,0", "?b": "1,0"},
        )


class ModelCounting(unittest.TestCase):
    def test_the_prior_shifts_the_posterior(self):
        at_least_one = lambda a: a["x"] or a["y"]
        flat = logic.model_count(["x", "y"], [at_least_one], prior=0.5)
        rare = logic.model_count(["x", "y"], [at_least_one], prior=0.16)
        self.assertAlmostEqual(flat["x"], 2 / 3)
        self.assertLess(rare["x"], flat["x"])

    def test_pinning_the_source_needs_a_single_survivor(self):
        kb = KnowledgeBase(4)
        kb.perceive((0, 0), _percepts())
        self.assertIsNone(kb.radiation_location())
        kb.perceive((1, 0), _percepts(alert=True))
        kb.perceive((0, 1), _percepts(alert=True))
        self.assertEqual(kb.radiation_location(), (1, 1))


class Safety(unittest.TestCase):
    def test_the_entrance_and_its_neighbours_come_out_safe(self):
        kb = KnowledgeBase(4)
        kb.perceive((0, 0), _percepts())
        self.assertEqual(kb.safe_cells(), {(0, 0), (1, 0), (0, 1)})

    def test_a_warning_stops_the_rover_calling_a_square_safe(self):
        kb = KnowledgeBase(4)
        kb.perceive((0, 0), _percepts(warning=True))
        self.assertEqual(kb.safe_cells(), {(0, 0)})
        self.assertGreater(max(kb.hazard_risk().values()), 0.16)


def _percepts(warning=False, alert=False, signal=False, spike=False):
    return {
        "warning": warning,
        "alert": alert,
        "signal": signal,
        "spike": spike,
        "bump": False,
    }


if __name__ == "__main__":
    unittest.main()
