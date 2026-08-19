"""What the rover believes, and how it gets there.

Three reasoning layers sit behind one interface:

  * A first-order forward chainer holds the terrain rules and grinds out
    the easy conclusions, mostly "no tremor here so nothing next door".
  * Resolution proves the harder crevasse questions, the ones where a
    tremor is only explained away once several readings are combined.
  * Model checking pins the radiation source down, since there is exactly
    one of it and enumerating its possible squares is cheap.

Everything the rover later prints as a reason comes from here.
"""

from . import fol
from . import logic
from .world import neighbours


def crevasse(cell):
    return "C%d,%d" % cell


def source(cell):
    return "R%d,%d" % cell


def tremor(cell):
    return "T%d,%d" % cell


def geiger(cell):
    return "G%d,%d" % cell


class KnowledgeBase:
    def __init__(self, size, hazard_prior=0.16, focus_radius=2):
        self.size = size
        self.hazard_prior = hazard_prior
        self.focus_radius = focus_radius
        self.cells = [(x, y) for x in range(size) for y in range(size)]

        self.fol = fol.FolKB(fol.TERRAIN_RULES)
        self.prover = logic.Prover()
        self.clauses = []

        self.visited = set()
        self.trembling = set()
        self.steady = set()
        self.irradiated = set()
        self.clean = set()
        self.source_sealed = False
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

        Returns the lines worth printing: clean conclusions only, so the
        console log shows the knowledge base actually growing rather than
        repeating itself.
        """
        notes = []
        self.visited.add(cell)
        self.fol.tell(("Visited", self._name(cell)), "walked there")

        if percepts.get("spike"):
            self.source_sealed = True
            self.fol.tell(("SourceSealed", "yes"), "telemetry spike confirmed the seal")
            notes.append(
                "telemetry spike: the source is sealed, every square is clear of it"
            )

        if percepts["tremor"]:
            self.trembling.add(cell)
            self.fol.tell(("Tremor", self._name(cell)), "felt a tremor")
        else:
            self.steady.add(cell)
            self.fol.tell(("NoTremor", self._name(cell)), "no tremor")

        if percepts["geiger"]:
            self.irradiated.add(cell)
            self.fol.tell(("Geiger", self._name(cell)), "smelled a geiger")
        else:
            self.clean.add(cell)
            self.fol.tell(("NoGeiger", self._name(cell)), "no geiger")

        self._add_axioms(cell)
        self.clauses.append(logic.clause(logic.neg(crevasse(cell))))
        self.clauses.append(logic.clause(logic.neg(source(cell))))
        self.clauses.append(
            logic.clause(tremor(cell) if percepts["tremor"] else logic.neg(tremor(cell)))
        )
        self.clauses.append(
            logic.clause(geiger(cell) if percepts["geiger"] else logic.neg(geiger(cell)))
        )

        before = set(self.fol.facts)
        self.fol.forward_chain()
        notes.extend(self._report(self.fol.facts - before))

        notes.extend(self._prove_frontier())
        notes.extend(self._locate_source())
        return notes

    def _report(self, new_facts, limit=5):
        """Turn a batch of derived facts into a few readable lines.

        Only Safe and Crevasse conclusions are worth printing. The NoCrevasse and
        NoSource steps behind them show up inside the explanation, and a
        single spike can derive thirty of those at once, which buries
        the log for no gain.
        """
        picked = sorted(f for f in new_facts if f[0] in ("Safe", "Crevasse"))
        lines = [self._explain(f) for f in picked[:limit]]
        if len(picked) > limit:
            lines.append("and %d more cells settled the same way" % (len(picked) - limit))
        return lines

    def _explain(self, fact):
        name = fact[1]
        if fact[0] != "Safe":
            return "%s(%s) because %s" % (fact[0], name, self.fol.why(fact))
        parts = []
        for premise in ("NoCrevasse", "NoSource"):
            reason = self.fol.why((premise, name))
            parts.append("%s from %s" % (premise, reason.split(" applied to ")[0]))
        return "Safe(%s): %s" % (name, ", ".join(parts))

    def _add_axioms(self, cell):
        """Sensor axioms for a cell, added once, the first time it is seen."""
        if cell in self.axiom_cells:
            return
        self.axiom_cells.add(cell)
        adj = neighbours(cell, self.size)
        self.clauses.extend(logic.biconditional_clauses(tremor(cell), [crevasse(n) for n in adj]))
        self.clauses.extend(logic.biconditional_clauses(geiger(cell), [source(n) for n in adj]))

    # ---- asking -----------------------------------------------------

    def _focus(self, cell):
        """Symbols close enough to the query to possibly matter."""
        out = set()
        r = self.focus_radius
        for other in self.cells:
            if abs(other[0] - cell[0]) + abs(other[1] - cell[1]) <= r:
                out.update((crevasse(other), source(other), tremor(other), geiger(other)))
        return out

    def _prove_frontier(self):
        """Run resolution on the cells the agent might step into next."""
        notes = []
        for cell in sorted(self.frontier()):
            key = ("nopit", cell)
            settled = self.fol.holds(("NoCrevasse", self._name(cell))) or self.fol.holds(
                ("Crevasse", self._name(cell))
            )
            if self.proved.get(key) or settled:
                continue
            # A failed refutation stays failed until the clause set grows,
            # so there is no point paying for the same search twice.
            if self.attempted.get(cell) == len(self.clauses):
                continue
            self.attempted[cell] = len(self.clauses)
            focus = self._focus(cell)
            if self.prover.entails(self.clauses, logic.neg(crevasse(cell)), focus):
                self.proved[key] = True
                self.fol.tell(("NoCrevasse", self._name(cell)), "resolution refutation")
                notes.append("resolution proves no crevasse at %s" % (cell,))
            elif self.prover.entails(self.clauses, crevasse(cell), focus):
                self.proved[("crevasse", cell)] = True
                self.fol.tell(("Crevasse", self._name(cell)), "resolution refutation")
                notes.append("resolution proves a crevasse at %s, that square is off limits" % (cell,))
        if notes:
            self.fol.forward_chain()
        return notes

    def _locate_source(self):
        """Model checking over the one and only rover.

        Every cell that survives all the geiger and no-geiger reports is a
        candidate. One survivor means the location is known.
        """
        if self.source_sealed:
            return []
        candidates = [c for c in self.cells if self._source_possible(c)]
        if len(candidates) == 1 and not self.fol.holds(("Source", self._name(candidates[0]))):
            spot = candidates[0]
            self.fol.tell(("Source", self._name(spot)), "the only square left after model checking")
            self.fol.forward_chain()
            return ["model checking pins the radiation source at %s" % (spot,)]
        return []

    def _source_possible(self, cell):
        if cell in self.visited:
            return False
        for seen in self.irradiated:
            if cell not in neighbours(seen, self.size):
                return False
        for seen in self.clean:
            if cell in neighbours(seen, self.size):
                return False
        return True

    def source_location(self):
        found = self.fol.query("Source")
        if len(found) == 1 and not self.source_sealed:
            return self._cell(next(iter(found))[1])
        return None

    def safe(self, cell):
        return self.fol.holds(("Safe", self._name(cell)))

    def safe_cells(self):
        return {self._cell(f[1]) for f in self.fol.query("Safe")}

    def known_crevasses(self):
        return {self._cell(f[1]) for f in self.fol.query("Crevasse")}

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
        for predicate in ("Safe", "Crevasse", "Source", "NoCrevasse", "NoSource"):
            fact = (predicate, self._name(cell))
            if self.fol.holds(fact):
                return "%s: %s" % (predicate, self.fol.why(fact))
        return "nothing proved about %s yet" % (cell,)

    # ---- gambling ---------------------------------------------------

    def crevasse_risk(self):
        """Rough chance of a crevasse for each frontier cell with no proof.

        Counts the satisfying assignments of the frontier crevasse variables
        against the tremor reports and reports how often each cell comes
        out holding a crevasse. When the frontier is too wide to enumerate it
        falls back on counting trembling neighbours, which orders the cells
        the same way most of the time and costs nothing.
        """
        unknown = [
            c
            for c in sorted(self.frontier())
            if not self.fol.holds(("NoCrevasse", self._name(c)))
            and not self.fol.holds(("Crevasse", self._name(c)))
        ]
        if not unknown:
            return {}

        index = {cell: crevasse(cell) for cell in unknown}
        constraints = []
        for seen in self.visited:
            adj = neighbours(seen, self.size)
            free = [index[n] for n in adj if n in index]
            settled = any(self.fol.holds(("Crevasse", self._name(n))) for n in adj)
            if seen in self.trembling:
                if not settled and free:
                    constraints.append(lambda a, group=tuple(free): any(a[s] for s in group))
            else:
                if free:
                    constraints.append(lambda a, group=tuple(free): not any(a[s] for s in group))

        scores = logic.model_count(index.values(), constraints, self.hazard_prior)
        if scores:
            return {cell: scores[index[cell]] for cell in unknown}

        fallback = {}
        for cell in unknown:
            witnesses = sum(1 for n in neighbours(cell, self.size) if n in self.trembling)
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
