"""Checks on the three reasoners.

Run with:  python -m unittest discover tests
"""

import unittest

from wumpus import fol, logic
from wumpus.knowledge import KnowledgeBase
from wumpus.logic import biconditional_clauses as bic
from wumpus.logic import clause, neg


class Resolution(unittest.TestCase):
    def test_no_breeze_clears_the_neighbours(self):
        kb = bic("B0,0", ["P1,0", "P0,1"]) + [clause(neg("B0,0"))]
        prover = logic.Prover()
        self.assertTrue(prover.entails(kb, neg("P1,0")))
        self.assertTrue(prover.entails(kb, neg("P0,1")))

    def test_a_breeze_alone_proves_nothing_about_one_cell(self):
        kb = bic("B0,0", ["P1,0", "P0,1"]) + [clause("B0,0")]
        prover = logic.Prover()
        self.assertFalse(prover.entails(kb, "P1,0"))
        self.assertFalse(prover.entails(kb, neg("P1,0")))

    def test_ruling_out_the_alternatives_locates_the_pit(self):
        kb = bic("B0,0", ["P1,0", "P0,1"])
        kb += [clause("B0,0"), clause(neg("P0,1"))]
        prover = logic.Prover()
        self.assertTrue(prover.entails(kb, "P1,0"))

    def test_contradiction_is_never_reported_as_a_proof_of_both(self):
        kb = bic("B1,1", ["P1,0", "P0,1", "P2,1", "P1,2"])
        kb += [clause("B1,1"), clause(neg("P1,0")), clause(neg("P0,1"))]
        prover = logic.Prover()
        self.assertFalse(prover.entails(kb, "P2,1"))
        self.assertFalse(prover.entails(kb, neg("P2,1")))


class ForwardChaining(unittest.TestCase):
    def test_a_rule_fires_once_its_premises_are_present(self):
        kb = fol.FolKB(fol.CAVE_RULES)
        kb.tell(("Cell", "0,0"))
        kb.tell(("Adjacent", "0,0", "1,0"))
        kb.tell(("Visited", "0,0"))
        kb.tell(("NoBreeze", "0,0"))
        kb.tell(("NoStench", "0,0"))
        kb.forward_chain()
        self.assertTrue(kb.holds(("Safe", "1,0")))

    def test_a_stench_blocks_the_safety_conclusion(self):
        kb = fol.FolKB(fol.CAVE_RULES)
        kb.tell(("Cell", "0,0"))
        kb.tell(("Adjacent", "0,0", "1,0"))
        kb.tell(("Visited", "0,0"))
        kb.tell(("NoBreeze", "0,0"))
        kb.tell(("Stench", "0,0"))
        kb.forward_chain()
        self.assertTrue(kb.holds(("NoPit", "1,0")))
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

    def test_pinning_the_wumpus_needs_a_single_survivor(self):
        kb = KnowledgeBase(4)
        kb.perceive((0, 0), _percepts())
        self.assertIsNone(kb.wumpus_location())
        kb.perceive((1, 0), _percepts(stench=True))
        kb.perceive((0, 1), _percepts(stench=True))
        self.assertEqual(kb.wumpus_location(), (1, 1))


class Safety(unittest.TestCase):
    def test_the_entrance_and_its_neighbours_come_out_safe(self):
        kb = KnowledgeBase(4)
        kb.perceive((0, 0), _percepts())
        self.assertEqual(kb.safe_cells(), {(0, 0), (1, 0), (0, 1)})

    def test_a_breeze_stops_the_agent_calling_a_cell_safe(self):
        kb = KnowledgeBase(4)
        kb.perceive((0, 0), _percepts(breeze=True))
        self.assertEqual(kb.safe_cells(), {(0, 0)})
        self.assertGreater(max(kb.pit_risk().values()), 0.16)


def _percepts(breeze=False, stench=False, glitter=False, scream=False):
    return {
        "breeze": breeze,
        "stench": stench,
        "glitter": glitter,
        "scream": scream,
        "bump": False,
    }


if __name__ == "__main__":
    unittest.main()
