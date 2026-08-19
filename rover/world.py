"""The patch of Mars the rover drives on.

Coordinates are (x, y) with the origin at the bottom-left. The lander
sits at (0, 0), the rover starts there facing east, and that square plus
its neighbours are guaranteed clear of hazards and radiation.

Three things are hidden in the grid: hazards, which end the mission if
the rover drives into one; a single radiation zone, which does the
same; and one sample cache the rover has to collect and carry back to
the lander.
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
CHARGE_COST = 10
SAMPLE_REWARD = 1000
LOSS_PENALTY = 1000

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


class Terrain:
    """Environment state plus the rules for acting on it.

    The generator retries until the sample can be reached without crossing
    a hazard or the radiation zone, so every run has a winning line
    available. That keeps the demo honest: when a run ends badly it is the
    reasoning that failed, not the dice.
    """

    def __init__(self, size=6, hazard_prob=0.16, seed=None):
        if size < 3:
            raise ValueError("the survey grid needs to be at least 3x3")
        self.size = size
        self.hazard_prob = hazard_prob
        self.rng = random.Random(seed)
        self.seed = seed

        for _ in range(400):
            if self._generate():
                break
        else:
            raise RuntimeError("could not build a solvable terrain, try a lower --hazard-prob")

        self.rover = START
        self.facing = "east"
        self.has_charge = True
        self.has_sample = False
        self.radiation_active = True
        self.operational = True
        self.docked = False
        self.score = 0
        self.spike = False
        self.bump = False

    # ---- generation -------------------------------------------------

    def _generate(self):
        size = self.size
        safe_zone = {START} | set(neighbours(START, size))
        cells = [(x, y) for x in range(size) for y in range(size)]

        self.hazards = set()
        for c in cells:
            if c not in safe_zone and self.rng.random() < self.hazard_prob:
                self.hazards.add(c)

        free = [c for c in cells if c not in self.hazards and c != START]
        if not free:
            return False

        far = [c for c in free if c not in safe_zone]
        self.radiation = self.rng.choice(far or free)

        cache_options = [c for c in free if c != self.radiation]
        if not cache_options:
            return False
        self.sample = self.rng.choice(cache_options)

        return self._reachable(self.sample)

    def _reachable(self, target):
        blocked = self.hazards | {self.radiation}
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
        cell = self.rover
        adj = neighbours(cell, self.size)
        p = {
            "warning": any(n in self.hazards for n in adj),
            "alert": self.radiation_active and any(n == self.radiation for n in adj),
            "signal": (not self.has_sample) and cell == self.sample,
            "spike": self.spike,
            "bump": self.bump,
        }
        self.spike = False
        self.bump = False
        return p

    # ---- acting -----------------------------------------------------

    def act(self, action, argument=None):
        """Apply one action and return a short line describing what happened."""
        if not self.operational or self.docked:
            return "the mission has already ended"

        if action == "move":
            return self._move(argument)
        if action == "collect":
            return self._collect()
        if action == "seal":
            return self._seal(argument)
        if action == "dock":
            return self._dock()
        raise ValueError("unknown action: %r" % (action,))

    def _move(self, target):
        if target not in neighbours(self.rover, self.size):
            self.bump = True
            self.score -= MOVE_COST
            return "hit the edge of the survey area trying to reach %s" % (target,)

        dx = target[0] - self.rover[0]
        dy = target[1] - self.rover[1]
        for name, delta in DIRECTIONS.items():
            if delta == (dx, dy):
                self.facing = name
                break

        self.rover = target
        self.score -= MOVE_COST

        if target in self.hazards:
            self.operational = False
            self.score -= LOSS_PENALTY
            return "drove into the hazard at %s, rover lost" % (target,)
        if self.radiation_active and target == self.radiation:
            self.operational = False
            self.score -= LOSS_PENALTY
            return "drove into the radiation zone at %s, rover lost" % (target,)
        return "moved to %s" % (target,)

    def _collect(self):
        self.score -= MOVE_COST
        if not self.has_sample and self.rover == self.sample:
            self.has_sample = True
            return "collected the sample cache at %s" % (self.rover,)
        return "nothing to collect on this square"

    def _seal(self, direction):
        self.score -= MOVE_COST
        if not self.has_charge:
            return "the containment charge is already spent"
        self.has_charge = False
        self.score -= CHARGE_COST
        if direction not in DIRECTIONS:
            return "charge fired with no bearing set"

        dx, dy = DIRECTIONS[direction]
        x, y = self.rover
        while True:
            x, y = x + dx, y + dy
            if not (0 <= x < self.size and 0 <= y < self.size):
                return "charge ran off the survey area, the %s line is clear" % direction
            if self.radiation_active and (x, y) == self.radiation:
                self.radiation_active = False
                self.spike = True
                return "charge neutralised the radiation zone at %s" % ((x, y),)

    def _dock(self):
        self.score -= MOVE_COST
        if self.rover != START:
            return "the rover can only dock at the lander"
        self.docked = True
        if self.has_sample:
            self.score += SAMPLE_REWARD
            return "docked at the lander with the sample"
        return "docked at the lander with nothing"

    # ---- helpers ----------------------------------------------------

    @property
    def finished(self):
        return self.docked or not self.operational

    def hazard_at(self, cell):
        if cell in self.hazards:
            return "hazard"
        if self.radiation_active and cell == self.radiation:
            return "radiation"
        if cell == self.sample and not self.has_sample:
            return "sample"
        return None

    def render(self, reveal=False):
        """ASCII picture of the grid, used by the terminal renderer."""
        rows = []
        for y in range(self.size - 1, -1, -1):
            row = []
            for x in range(self.size):
                cell = (x, y)
                marks = []
                if cell == self.rover:
                    marks.append("A")
                if reveal:
                    if cell in self.hazards:
                        marks.append("P")
                    if cell == self.radiation:
                        marks.append("W" if self.radiation_active else "w")
                    if cell == self.sample and not self.has_sample:
                        marks.append("G")
                row.append("".join(marks).ljust(3) if marks else " . ")
            rows.append("|".join(row))
        width = len(rows[0])
        return ("\n" + "-" * width + "\n").join(rows)
