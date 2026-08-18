"""What the agent believes, and how it gets there.

Three reasoning layers sit behind one interface:

  * A first-order forward chainer holds the cave rules and grinds out the
    easy conclusions, mostly "no breeze here so nothing next door".
  * Resolution proves the harder pit questions, the ones where a breeze
    is only explained away once you combine several observations.
  * Model checking pins the wumpus down, since there is exactly one of it
    and enumerating its possible cells is cheap.

Everything the agent later prints as a reason comes from here.
"""

from . import fol
from . import logic
from .world import neighbours


def pit(cell):
    return "P%d,%d" % cell


def wumpus(cell):
    return "W%d,%d" % cell


def breeze(cell):
    return "B%d,%d" % cell


def stench(cell):
    return "S%d,%d" % cell


class KnowledgeBase:
    def __init__(self, size, pit_prior=0.16, focus_radius=2):
        self.size = size
        self.pit_prior = pit_prior
        self.focus_radius = focus_radius
        self.cells = [(x, y) for x in range(size) for y in range(size)]

        self.fol = fol.FolKB(fol.CAVE_RULES)
        self.prover = logic.Prover()
        self.clauses = []

        self.visited = set()
        self.breezy = set()
        self.calm = set()
        self.smelly = set()
        self.fresh = set()
        self.wumpus_dead = False
        self.axiom_cells = set()
        self.proved = {}
        self.attempted = {}

        for cell in self.cells:
            self.fol.tell(("Cell", self._name(cell)))
            for n in neighbours(cell, size):
                self.fol.tell(("Adjacent", self._name(cell), self._name(n)))

    # ---- naming -----------------------------------------------------

    @staticmethod
    def _name(cell):
        return "%d,%d" % cell

    @staticmethod
    def _cell(name):
        x, y = name.split(",")
        return (int(x), int(y))

    # ---- telling ----------------------------------------------------

    def perceive(self, cell, percepts):
        """Record one round of percepts and re-run every reasoner.

        Returns the lines worth printing: fresh conclusions only, so the
        console log shows the knowledge base actually growing rather than
        repeating itself.
        """
        notes = []
        self.visited.add(cell)
        self.fol.tell(("Visited", self._name(cell)), "walked there")

        if percepts.get("scream"):
            self.wumpus_dead = True
            self.fol.tell(("WumpusDead", "yes"), "heard the scream")
            notes.append("scream heard, the wumpus is dead and every cell is clear of it")

        if percepts["breeze"]:
            self.breezy.add(cell)
            self.fol.tell(("Breeze", self._name(cell)), "felt a breeze")
        else:
            self.calm.add(cell)
            self.fol.tell(("NoBreeze", self._name(cell)), "no breeze")

        if percepts["stench"]:
            self.smelly.add(cell)
            self.fol.tell(("Stench", self._name(cell)), "smelled a stench")
        else:
            self.fresh.add(cell)
            self.fol.tell(("NoStench", self._name(cell)), "no stench")

        self._add_axioms(cell)
        self.clauses.append(logic.clause(logic.neg(pit(cell))))
        self.clauses.append(logic.clause(logic.neg(wumpus(cell))))
        self.clauses.append(
            logic.clause(breeze(cell) if percepts["breeze"] else logic.neg(breeze(cell)))
        )
        self.clauses.append(
            logic.clause(stench(cell) if percepts["stench"] else logic.neg(stench(cell)))
        )

        before = set(self.fol.facts)
        self.fol.forward_chain()
        notes.extend(self._report(self.fol.facts - before))

        notes.extend(self._prove_frontier())
        notes.extend(self._locate_wumpus())
        return notes

    def _report(self, new_facts, limit=5):
        """Turn a batch of derived facts into a few readable lines.

        Only Safe and Pit conclusions are worth printing. The NoPit and
        NoWumpus steps behind them show up inside the explanation, and a
        single scream can derive thirty of those at once, which buries
        the log for no gain.
        """
        picked = sorted(f for f in new_facts if f[0] in ("Safe", "Pit"))
        lines = [self._explain(f) for f in picked[:limit]]
        if len(picked) > limit:
            lines.append("and %d more cells settled the same way" % (len(picked) - limit))
        return lines

    def _explain(self, fact):
        name = fact[1]
        if fact[0] != "Safe":
            return "%s(%s) because %s" % (fact[0], name, self.fol.why(fact))
        parts = []
        for premise in ("NoPit", "NoWumpus"):
            reason = self.fol.why((premise, name))
            parts.append("%s from %s" % (premise, reason.split(" applied to ")[0]))
        return "Safe(%s): %s" % (name, ", ".join(parts))

    def _add_axioms(self, cell):
        """Sensor axioms for a cell, added once, the first time it is seen."""
        if cell in self.axiom_cells:
            return
        self.axiom_cells.add(cell)
        adj = neighbours(cell, self.size)
        self.clauses.extend(logic.biconditional_clauses(breeze(cell), [pit(n) for n in adj]))
        self.clauses.extend(logic.biconditional_clauses(stench(cell), [wumpus(n) for n in adj]))

    # ---- asking -----------------------------------------------------

    def _focus(self, cell):
        """Symbols close enough to the query to possibly matter."""
        out = set()
        r = self.focus_radius
        for other in self.cells:
            if abs(other[0] - cell[0]) + abs(other[1] - cell[1]) <= r:
                out.update((pit(other), wumpus(other), breeze(other), stench(other)))
        return out

    def _prove_frontier(self):
        """Run resolution on the cells the agent might step into next."""
        notes = []
        for cell in sorted(self.frontier()):
            key = ("nopit", cell)
            settled = self.fol.holds(("NoPit", self._name(cell))) or self.fol.holds(
                ("Pit", self._name(cell))
            )
            if self.proved.get(key) or settled:
                continue
            # A failed refutation stays failed until the clause set grows,
            # so there is no point paying for the same search twice.
            if self.attempted.get(cell) == len(self.clauses):
                continue
            self.attempted[cell] = len(self.clauses)
            focus = self._focus(cell)
            if self.prover.entails(self.clauses, logic.neg(pit(cell)), focus):
                self.proved[key] = True
                self.fol.tell(("NoPit", self._name(cell)), "resolution refutation")
                notes.append("resolution proves no pit at %s" % (cell,))
            elif self.prover.entails(self.clauses, pit(cell), focus):
                self.proved[("pit", cell)] = True
                self.fol.tell(("Pit", self._name(cell)), "resolution refutation")
                notes.append("resolution proves a pit at %s, that cell is off limits" % (cell,))
        if notes:
            self.fol.forward_chain()
        return notes

    def _locate_wumpus(self):
        """Model checking over the one and only wumpus.

        Every cell that survives all the stench and no-stench reports is a
        candidate. One survivor means the location is known.
        """
        if self.wumpus_dead:
            return []
        candidates = [c for c in self.cells if self._wumpus_possible(c)]
        if len(candidates) == 1 and not self.fol.holds(("Wumpus", self._name(candidates[0]))):
            spot = candidates[0]
            self.fol.tell(("Wumpus", self._name(spot)), "only cell left after model checking")
            self.fol.forward_chain()
            return ["model checking pins the wumpus at %s" % (spot,)]
        return []

    def _wumpus_possible(self, cell):
        if cell in self.visited:
            return False
        for seen in self.smelly:
            if cell not in neighbours(seen, self.size):
                return False
        for seen in self.fresh:
            if cell in neighbours(seen, self.size):
                return False
        return True

    def wumpus_location(self):
        found = self.fol.query("Wumpus")
        if len(found) == 1 and not self.wumpus_dead:
            return self._cell(next(iter(found))[1])
        return None

    def safe(self, cell):
        return self.fol.holds(("Safe", self._name(cell)))

    def safe_cells(self):
        return {self._cell(f[1]) for f in self.fol.query("Safe")}

    def known_pits(self):
        return {self._cell(f[1]) for f in self.fol.query("Pit")}

    def frontier(self):
        """Unvisited cells that touch somewhere the agent has already been."""
        out = set()
        for cell in self.visited:
            for n in neighbours(cell, self.size):
                if n not in self.visited:
                    out.add(n)
        return out

    def unexplored_safe(self):
        return sorted(self.safe_cells() - self.visited)

    def why(self, cell):
        for predicate in ("Safe", "Pit", "Wumpus", "NoPit", "NoWumpus"):
            fact = (predicate, self._name(cell))
            if self.fol.holds(fact):
                return "%s: %s" % (predicate, self.fol.why(fact))
        return "nothing proved about %s yet" % (cell,)

    # ---- gambling ---------------------------------------------------

    def pit_risk(self):
        """Rough chance of a pit for each frontier cell with no proof.

        Counts the satisfying assignments of the frontier pit variables
        against the breeze reports and reports how often each cell comes
        out holding a pit. When the frontier is too wide to enumerate it
        falls back on counting breezy neighbours, which orders the cells
        the same way most of the time and costs nothing.
        """
        unknown = [
            c
            for c in sorted(self.frontier())
            if not self.fol.holds(("NoPit", self._name(c)))
            and not self.fol.holds(("Pit", self._name(c)))
        ]
        if not unknown:
            return {}

        index = {cell: pit(cell) for cell in unknown}
        constraints = []
        for seen in self.visited:
            adj = neighbours(seen, self.size)
            free = [index[n] for n in adj if n in index]
            settled = any(self.fol.holds(("Pit", self._name(n))) for n in adj)
            if seen in self.breezy:
                if not settled and free:
                    constraints.append(lambda a, group=tuple(free): any(a[s] for s in group))
            else:
                if free:
                    constraints.append(lambda a, group=tuple(free): not any(a[s] for s in group))

        scores = logic.model_count(index.values(), constraints, self.pit_prior)
        if scores:
            return {cell: scores[index[cell]] for cell in unknown}

        fallback = {}
        for cell in unknown:
            witnesses = sum(1 for n in neighbours(cell, self.size) if n in self.breezy)
            fallback[cell] = min(0.9, 0.25 * witnesses) if witnesses else 0.1
        return fallback

    # ---- reporting --------------------------------------------------

    def stats(self):
        return {
            "clauses": len(self.clauses),
            "fol_facts": len(self.fol.facts),
            "fol_derivations": self.fol.derivations,
            "resolution_calls": self.prover.calls,
            "resolution_steps": self.prover.steps,
            "resolution_proofs": self.prover.proofs,
        }
