"""Checks on A* and on the environment it searches over."""

import unittest

from rover import planner
from rover.world import Terrain, neighbours


def open_grid(size, blocked=()):
    return {(x, y) for x in range(size) for y in range(size)} - set(blocked)


class Heuristic(unittest.TestCase):
    def test_manhattan_never_overestimates_on_an_open_grid(self):
        size = 6
        passable = open_grid(size)
        for goal in ((5, 5), (3, 0), (0, 4)):
            result = planner.astar((0, 0), goal, passable, size)
            self.assertEqual(result.cost, planner.manhattan((0, 0), goal))


class Search(unittest.TestCase):
    def test_it_routes_around_a_wall(self):
        size = 5
        wall = [(2, y) for y in range(4)]
        result = planner.astar((0, 0), (4, 0), open_grid(size, wall), size)
        self.assertTrue(result.found)
        self.assertNotIn((2, 0), result.path)
        self.assertEqual(result.cost, len(result.path) - 1)

    def test_a_sealed_goal_returns_no_path(self):
        size = 4
        walls = [(0, 1), (1, 1), (1, 0)]
        result = planner.astar((0, 0), (3, 3), open_grid(size, walls), size)
        self.assertFalse(result.found)

    def test_every_step_of_a_path_is_a_legal_move(self):
        size = 6
        result = planner.astar((0, 0), (5, 5), open_grid(size, [(3, 3), (3, 4)]), size)
        for a, b in zip(result.path, result.path[1:]):
            self.assertIn(b, neighbours(a, size))

    def test_nearest_picks_the_cheapest_of_several_goals(self):
        size = 6
        passable = open_grid(size)
        result = planner.nearest((0, 0), [(5, 5), (1, 1), (4, 0)], passable, size)
        self.assertEqual(result.path[-1], (1, 1))
        self.assertEqual(result.cost, 2)


class Environment(unittest.TestCase):
    def test_the_lander_and_its_neighbours_hold_no_hazards(self):
        for seed in range(40):
            terrain = Terrain(size=6, hazard_prob=0.3, seed=seed)
            self.assertNotIn((0, 0), terrain.hazards)
            for cell in neighbours((0, 0), 6):
                self.assertNotIn(cell, terrain.hazards)

    def test_the_sample_is_always_reachable(self):
        for seed in range(40):
            terrain = Terrain(size=6, hazard_prob=0.25, seed=seed)
            self.assertTrue(terrain._reachable(terrain.sample))

    def test_the_same_seed_builds_the_same_map(self):
        a = Terrain(size=6, seed=99)
        b = Terrain(size=6, seed=99)
        self.assertEqual(a.hazards, b.hazards)
        self.assertEqual((a.radiation, a.sample), (b.radiation, b.sample))

    def test_driving_into_a_hazard_ends_the_run(self):
        terrain = Terrain(size=4, hazard_prob=0.0, seed=1)
        terrain.hazards = {(1, 0)}
        terrain.act("move", (1, 0))
        self.assertFalse(terrain.operational)
        self.assertLess(terrain.score, -1000 + 1)

    def test_the_charge_only_travels_in_a_straight_line(self):
        terrain = Terrain(size=4, hazard_prob=0.0, seed=2)
        terrain.radiation = (0, 3)
        terrain.act("seal", "east")
        self.assertTrue(terrain.radiation_active)
        terrain.has_charge = True
        terrain.act("seal", "north")
        self.assertFalse(terrain.radiation_active)


if __name__ == "__main__":
    unittest.main()
