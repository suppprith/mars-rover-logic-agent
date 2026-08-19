import time

from . import planner
from .knowledge import KnowledgeBase
from .world import START, neighbours

RISK_LIMIT = 0.25


class Decision:
    def __init__(self, action, argument=None, reason="", path=None):
        self.action = action
        self.argument = argument
        self.reason = reason
        self.path = path or []


class Agent:
    def __init__(self, size, risk_limit=RISK_LIMIT, hazard_prior=0.16):
        self.size = size
        self.risk_limit = risk_limit
        self.kb = KnowledgeBase(size, hazard_prior=hazard_prior)

        self.position = START
        self.has_sample = False
        self.has_charge = True
        self.plan = []
        self.goal = None
        self.notes = []

        self.steps = 0
        self.moves = 0
        self.replans = 0
        self.nodes_expanded = 0
        self.nodes_generated = 0
        self.thinking_time = 0.0

    def step(self, position, percepts):
        """Take in the world, hand back the next action."""
        started = time.perf_counter()
        self.position = position
        self.steps += 1
        self.notes = self.kb.perceive(position, percepts)
        decision = self._decide(percepts)
        self.thinking_time += time.perf_counter() - started
        if decision.action == "move":
            self.moves += 1
        return decision

    def _decide(self, percepts):
        if percepts["signal"]:
            self.has_sample = True
            self.goal = None
            return Decision("collect", None, "the sample cache is on this square")

        if self.has_sample:
            return self._head_home("carrying the sample, heading back to the lander")

        target = self._pick_target()
        if target is not None:
            cell, result = target
            self.goal = cell
            self.plan = result.path[1:]
            reason = "nearest safe square not surveyed yet is %s, A* cost %d over %d expansions" % (
                cell,
                result.cost,
                result.expanded,
            )
            return Decision("move", self.plan[0], reason, result.path)

        shot = self._consider_sealing()
        if shot is not None:
            return shot

        gamble = self._consider_risk()
        if gamble is not None:
            return gamble

        return self._head_home("nothing safe left to try, returning to the lander")

    def _passable(self):
        """Cells A* is allowed to route through."""
        return (self.kb.safe_cells() | self.kb.visited) - self.kb.known_hazards()

    def _pick_target(self):
        candidates = [c for c in self.kb.unexplored_safe() if c != self.position]
        if not candidates:
            return None
        result = planner.nearest(self.position, candidates, self._passable(), self.size)
        self._count(result)
        if not result.found or len(result.path) < 2:
            return None
        return result.path[-1], result

    def _head_home(self, reason):
        if self.position == START:
            return Decision("dock", None, reason)
        result = planner.astar(self.position, START, self._passable(), self.size)
        self._count(result)
        if not result.found or len(result.path) < 2:
            return Decision("dock", None, "no route back, attempting to dock from here")
        self.goal = START
        self.plan = result.path[1:]
        full = "%s, A* cost %d over %d expansions" % (reason, result.cost, result.expanded)
        return Decision("move", self.plan[0], full, result.path)

    def _consider_sealing(self):
        if not self.has_charge or self.kb.radiation_sealed:
            return None
        spot = self.kb.radiation_location()
        if spot is None:
            return None
        direction = self._line_of_sight(spot)
        if direction is None:
            return None
        self.has_charge = False
        self.goal = spot
        return Decision(
            "seal",
            direction,
            "the radiation zone is proved to sit at %s, straight %s of here" % (spot, direction),
            [self.position, spot],
        )

    def _line_of_sight(self, spot):
        x, y = self.position
        tx, ty = spot
        if x == tx:
            return "north" if ty > y else "south"
        if y == ty:
            return "east" if tx > x else "west"
        return None

    def _consider_risk(self):
        risk = self.kb.hazard_risk()
        reachable = {}
        for cell, score in risk.items():
            if self.kb.fol.holds(("Radiation", self.kb._name(cell))) and not self.kb.radiation_sealed:
                continue
            if any(n in self.kb.visited for n in neighbours(cell, self.size)):
                reachable[cell] = score
        if not reachable:
            return None

        cell, score = min(reachable.items(), key=lambda item: (item[1], item[0]))
        if score > self.risk_limit:
            return None

        result = planner.astar(self.position, cell, self._passable(), self.size)
        self._count(result)
        if not result.found or len(result.path) < 2:
            return None

        self.goal = cell
        self.plan = result.path[1:]
        reason = "nothing proved safe, %s carries the lowest hazard estimate at %.0f%%" % (
            cell,
            score * 100,
        )
        return Decision("move", self.plan[0], reason, result.path)

    def _count(self, result):
        self.replans += 1
        self.nodes_expanded += result.expanded
        self.nodes_generated += result.generated

    def metrics(self):
        data = {
            "steps": self.steps,
            "moves": self.moves,
            "replans": self.replans,
            "nodes_expanded": self.nodes_expanded,
            "nodes_generated": self.nodes_generated,
            "thinking_ms": round(self.thinking_time * 1000, 1),
        }
        data.update(self.kb.stats())
        return data
