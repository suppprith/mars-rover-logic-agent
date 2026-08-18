"""The cave the agent lives in.

Coordinates are (x, y) with the origin at the bottom-left, the way the
grid is drawn in the textbook. The agent always starts at (0, 0) facing
east, and (0, 0) is guaranteed free of pits and of the wumpus.
"""

import random
from collections import deque

DIRECTIONS = {
    "east": (1, 0),
    "west": (-1, 0),
    "north": (0, 1),
    "south": (0, -1),
}

MOVE_COST = 1
ARROW_COST = 10
GOLD_REWARD = 1000
DEATH_PENALTY = 1000

START = (0, 0)


def neighbours(cell, size):
    """The up to four cells orthogonally adjacent to cell."""
    x, y = cell
    out = []
    for dx, dy in DIRECTIONS.values():
        nx, ny = x + dx, y + dy
        if 0 <= nx < size and 0 <= ny < size:
            out.append((nx, ny))
    return out


class Cave:
    """Environment state plus the rules for acting on it.

    The generator retries until it produces a cave where the gold can be
    reached without walking through a pit or the wumpus, so every run has
    a winning line available. That keeps the demo honest: if the agent
    fails, the reasoning failed, not the dice.
    """

    def __init__(self, size=6, pit_prob=0.16, seed=None):
        if size < 3:
            raise ValueError("cave needs to be at least 3x3")
        self.size = size
        self.pit_prob = pit_prob
        self.rng = random.Random(seed)
        self.seed = seed

        for _ in range(400):
            if self._generate():
                break
        else:
            raise RuntimeError("could not build a solvable cave, try a lower --pit-prob")

        self.agent = START
        self.facing = "east"
        self.has_arrow = True
        self.has_gold = False
        self.wumpus_alive = True
        self.alive = True
        self.escaped = False
        self.score = 0
        self.scream = False
        self.bump = False

    # ---- generation -------------------------------------------------

    def _generate(self):
        size = self.size
        safe_zone = {START} | set(neighbours(START, size))
        cells = [(x, y) for x in range(size) for y in range(size)]

        self.pits = set()
        for c in cells:
            if c not in safe_zone and self.rng.random() < self.pit_prob:
                self.pits.add(c)

        free = [c for c in cells if c not in self.pits and c != START]
        if not free:
            return False

        far = [c for c in free if c not in safe_zone]
        self.wumpus = self.rng.choice(far or free)

        gold_options = [c for c in free if c != self.wumpus]
        if not gold_options:
            return False
        self.gold = self.rng.choice(gold_options)

        return self._reachable(self.gold)

    def _reachable(self, target):
        blocked = self.pits | {self.wumpus}
        seen = {START}
        queue = deque([START])
        while queue:
            cell = queue.popleft()
            if cell == target:
                return True
            for n in neighbours(cell, self.size):
                if n not in seen and n not in blocked:
                    seen.add(n)
                    queue.append(n)
        return False

    # ---- sensing ----------------------------------------------------

    def percepts(self):
        cell = self.agent
        adj = neighbours(cell, self.size)
        p = {
            "breeze": any(n in self.pits for n in adj),
            "stench": self.wumpus_alive and any(n == self.wumpus for n in adj),
            "glitter": (not self.has_gold) and cell == self.gold,
            "scream": self.scream,
            "bump": self.bump,
        }
        self.scream = False
        self.bump = False
        return p

    # ---- acting -----------------------------------------------------

    def act(self, action, argument=None):
        """Apply one action and return a short line describing what happened."""
        if not self.alive or self.escaped:
            return "episode is already over"

        if action == "move":
            return self._move(argument)
        if action == "grab":
            return self._grab()
        if action == "shoot":
            return self._shoot(argument)
        if action == "climb":
            return self._climb()
        raise ValueError("unknown action: %r" % (action,))

    def _move(self, target):
        if target not in neighbours(self.agent, self.size):
            self.bump = True
            self.score -= MOVE_COST
            return "bumped a wall trying to reach %s" % (target,)

        dx = target[0] - self.agent[0]
        dy = target[1] - self.agent[1]
        for name, delta in DIRECTIONS.items():
            if delta == (dx, dy):
                self.facing = name
                break

        self.agent = target
        self.score -= MOVE_COST

        if target in self.pits:
            self.alive = False
            self.score -= DEATH_PENALTY
            return "fell into the pit at %s" % (target,)
        if self.wumpus_alive and target == self.wumpus:
            self.alive = False
            self.score -= DEATH_PENALTY
            return "walked into the wumpus at %s" % (target,)
        return "moved to %s" % (target,)

    def _grab(self):
        self.score -= MOVE_COST
        if not self.has_gold and self.agent == self.gold:
            self.has_gold = True
            return "picked up the gold at %s" % (self.agent,)
        return "nothing to grab here"

    def _shoot(self, direction):
        self.score -= MOVE_COST
        if not self.has_arrow:
            return "no arrow left"
        self.has_arrow = False
        self.score -= ARROW_COST
        if direction not in DIRECTIONS:
            return "arrow flew off in no direction at all"

        dx, dy = DIRECTIONS[direction]
        x, y = self.agent
        while True:
            x, y = x + dx, y + dy
            if not (0 <= x < self.size and 0 <= y < self.size):
                return "arrow hit the wall, %s is clear" % direction
            if self.wumpus_alive and (x, y) == self.wumpus:
                self.wumpus_alive = False
                self.scream = True
                return "arrow killed the wumpus at %s" % ((x, y),)

    def _climb(self):
        self.score -= MOVE_COST
        if self.agent != START:
            return "can only climb out from the entrance"
        self.escaped = True
        if self.has_gold:
            self.score += GOLD_REWARD
            return "climbed out carrying the gold"
        return "climbed out empty handed"

    # ---- helpers ----------------------------------------------------

    @property
    def finished(self):
        return self.escaped or not self.alive

    def hazard_at(self, cell):
        if cell in self.pits:
            return "pit"
        if self.wumpus_alive and cell == self.wumpus:
            return "wumpus"
        if cell == self.gold and not self.has_gold:
            return "gold"
        return None

    def render(self, reveal=False):
        """ASCII picture of the cave, used by the terminal renderer."""
        rows = []
        for y in range(self.size - 1, -1, -1):
            row = []
            for x in range(self.size):
                cell = (x, y)
                marks = []
                if cell == self.agent:
                    marks.append("A")
                if reveal:
                    if cell in self.pits:
                        marks.append("P")
                    if cell == self.wumpus:
                        marks.append("W" if self.wumpus_alive else "w")
                    if cell == self.gold and not self.has_gold:
                        marks.append("G")
                row.append("".join(marks).ljust(3) if marks else " . ")
            rows.append("|".join(row))
        width = len(rows[0])
        return ("\n" + "-" * width + "\n").join(rows)
