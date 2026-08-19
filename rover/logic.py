"""Propositional clauses and a resolution theorem prover.

A literal is a string. A leading "~" negates it, so "P2,1" and "~P2,1"
are complements. A clause is a frozenset of literals, read as a
disjunction. A knowledge base is a list of clauses, read as a
conjunction.

Proving that the terrain is safe at some cell means proving KB entails
~P(cell). Resolution does that by refutation: assume the opposite, add
it to the KB, and try to derive the empty clause.
"""

import itertools

MAX_CLAUSE_LEN = 8


def neg(literal):
    return literal[1:] if literal.startswith("~") else "~" + literal


def symbol(literal):
    return literal[1:] if literal.startswith("~") else literal


def clause(*literals):
    return frozenset(literals)


def is_tautology(cl):
    return any(neg(lit) in cl for lit in cl)


def resolve(a, b):
    """All resolvents of two clauses, skipping tautologies."""
    out = []
    for lit in a:
        if neg(lit) in b:
            merged = (a - {lit}) | (b - {neg(lit)})
            if not is_tautology(merged):
                out.append(frozenset(merged))
    return out


def biconditional_clauses(head, body):
    """Clauses for `head <=> body1 or body2 or ...`.

    Used for the sensor axioms: a square reads a warning exactly when at
    least one neighbour holds a hazard.
    """
    out = [frozenset([neg(head)] + list(body))]
    for lit in body:
        out.append(frozenset([neg(lit), head]))
    return out


class Prover:
    """Resolution refutation with a set of support.

    The set of support starts as the negated query and every resolution
    step must involve a clause derived from it. The background KB is
    satisfiable by construction (it describes a real terrain), so this
    restriction keeps refutation completeness while cutting out the huge
    number of useless KB-against-KB resolutions.

    Two more cuts keep the search finite on a 6x6 grid: clauses longer
    than MAX_CLAUSE_LEN are dropped, and the whole thing gives up after
    a step budget. Giving up is reported as "not proved", never as
    "proved false", so a timeout can only make the agent more cautious.
    """

    def __init__(self, max_steps=2500):
        self.max_steps = max_steps
        self.steps = 0
        self.calls = 0
        self.proofs = 0

    def entails(self, kb, query, focus=None):
        """Does kb entail the single literal `query`?"""
        self.calls += 1
        clauses = self._restrict(kb, focus)

        goal = frozenset([neg(query)])
        if goal in clauses:
            return False

        support = [goal]
        seen = set(clauses) | {goal}
        budget = self.max_steps

        while support and budget > 0:
            current = support.pop(0)
            partners = list(clauses) + support
            # Unit clauses first: they shrink the resolvent every time.
            partners.sort(key=len)
            for other in partners:
                budget -= 1
                self.steps += 1
                if budget <= 0:
                    break
                for resolvent in resolve(current, other):
                    if not resolvent:
                        self.proofs += 1
                        return True
                    if len(resolvent) > MAX_CLAUSE_LEN or resolvent in seen:
                        continue
                    seen.add(resolvent)
                    support.append(resolvent)
            clauses.append(current)
        return False

    def _restrict(self, kb, focus):
        """Keep only the clauses that can matter to the query.

        `focus` is the set of symbols within a couple of hops of the cell
        being asked about. A clause mentioning nothing in that set cannot
        contribute to the refutation, so it is dropped before the search
        starts. Unit clauses stay regardless because they are cheap and
        they prune aggressively.
        """
        if focus is None:
            return list(kb)
        kept = []
        for cl in kb:
            if len(cl) == 1 or any(symbol(lit) in focus for lit in cl):
                kept.append(cl)
        return kept


def model_count(symbols, constraints, prior=0.5, limit=1 << 16):
    """Weighted model counting over a handful of symbols.

    Each full assignment is weighted by how likely it is under an
    independent prior of `prior` per symbol, then the weights of the
    assignments that satisfy every constraint are summed. What comes back
    is P(symbol is true | constraints) for each symbol.

    Uniform counting would answer a different question. With one warning
    and three unknown neighbours it calls every one of them 57% likely,
    because it treats "all three are hazards" as being just as plausible
    as "exactly one is". Weighting by the generation probability fixes
    that and gives the textbook numbers.
    """
    symbols = list(symbols)
    if not symbols or 2 ** len(symbols) > limit:
        return {}

    totals = dict.fromkeys(symbols, 0.0)
    evidence = 0.0
    for bits in itertools.product((False, True), repeat=len(symbols)):
        assignment = dict(zip(symbols, bits))
        if not all(check(assignment) for check in constraints):
            continue
        weight = 1.0
        for value in bits:
            weight *= prior if value else 1.0 - prior
        evidence += weight
        for sym, value in assignment.items():
            if value:
                totals[sym] += weight

    if evidence <= 0.0:
        return {}
    return {sym: totals[sym] / evidence for sym in symbols}
