"""Checks on the three reasoners.

Run with:  python -m unittest discover tests
"""

import unittest

from rover import fol, logic
from rover.knowledge import KnowledgeBase
from rover.logic import biconditional_clauses as bic
from rover.logic import clause, neg


class Resolution(unittest.TestCase):
    def test_no_tremor_clears_the_neighbours(self):
        kb = bic("T0,0", ["C1,0", "C0,1"]) + [clause(neg("T0,0"))]
        prover = logic.Prover()
        self.assertTrue(prover.entails(kb, neg("C1,0")))
        self.assertTrue(prover.entails(kb, neg("C0,1")))

    def test_a_tremor_alone_proves_nothing_about_one_square(self):
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


class ForwardChaining(unittest.TestCase):
    def test_a_rule_fires_once_its_premises_are_present(self):
        kb = fol.FolKB(fol.TERRAIN_RULES)
        kb.tell(("Cell", "0,0"))
        kb.tell(("Adjacent", "0,0", "1,0"))
        kb.tell(("Visited", "0,0"))
        kb.tell(("NoTremor", "0,0"))
        kb.tell(("NoGeiger", "0,0"))
        kb.forward_chain()
        self.assertTrue(kb.holds(("Safe", "1,0")))

    def test_a_geiger_reading_blocks_the_safety_conclusion(self):
        kb = fol.FolKB(fol.TERRAIN_RULES)
        kb.tell(("Cell", "0,0"))
        kb.tell(("Adjacent", "0,0", "1,0"))
        kb.tell(("Visited", "0,0"))
        kb.tell(("NoTremor", "0,0"))
        kb.tell(("Geiger", "0,0"))
        kb.forward_chain()
        self.assertTrue(kb.holds(("NoCrevasse", "1,0")))
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
        self.assertIsNone(kb.source_location())
        kb.perceive((1, 0), _percepts(geiger=True))
        kb.perceive((0, 1), _percepts(geiger=True))
        self.assertEqual(kb.source_location(), (1, 1))


class Safety(unittest.TestCase):
    def test_the_entrance_and_its_neighbours_come_out_safe(self):
        kb = KnowledgeBase(4)
        kb.perceive((0, 0), _percepts())
        self.assertEqual(kb.safe_cells(), {(0, 0), (1, 0), (0, 1)})

    def test_a_tremor_stops_the_rover_calling_a_square_safe(self):
        kb = KnowledgeBase(4)
        kb.perceive((0, 0), _percepts(tremor=True))
        self.assertEqual(kb.safe_cells(), {(0, 0)})
        self.assertGreater(max(kb.crevasse_risk().values()), 0.16)


def _percepts(tremor=False, geiger=False, signal=False, spike=False):
    return {
        "tremor": tremor,
        "geiger": geiger,
        "signal": signal,
        "spike": spike,
        "bump": False,
    }


if __name__ == "__main__":
    unittest.main()
