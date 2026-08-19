"""A small first-order forward chainer.

Only what the survey needs: definite clauses, constants and variables, no
functions. Terms are plain strings; a string starting with "?" is a
variable. A literal is a tuple (predicate, term, term, ...).

    Visited(?c) and NoWarning(?c) and Adjacent(?c, ?n)  =>  NoHazard(?n)

is written as

    Rule([("Visited", "?c"), ("NoWarning", "?c"), ("Adjacent", "?c", "?n")],
         ("NoHazard", "?n"))

Forward chaining runs to a fixpoint. Every derived fact keeps the rule
name and the bindings that produced it, so the agent can print the
reason behind a conclusion instead of just the conclusion.
"""


def is_var(term):
    return isinstance(term, str) and term.startswith("?")


def substitute(literal, bindings):
    out = [literal[0]]
    for term in literal[1:]:
        out.append(bindings.get(term, term) if is_var(term) else term)
    return tuple(out)


def unify(pattern, fact, bindings):
    """Match a literal that may contain variables against a ground fact.

    Returns a new binding dict, or None if the two cannot be matched.
    """
    if pattern[0] != fact[0] or len(pattern) != len(fact):
        return None
    result = dict(bindings)
    for p, f in zip(pattern[1:], fact[1:]):
        if is_var(p):
            if p in result:
                if result[p] != f:
                    return None
            else:
                result[p] = f
        elif p != f:
            return None
    return result


class Rule:
    def __init__(self, premises, conclusion, name=""):
        self.premises = [tuple(p) for p in premises]
        self.conclusion = tuple(conclusion)
        self.name = name or conclusion[0]

    def __repr__(self):
        body = " and ".join("%s(%s)" % (p[0], ", ".join(p[1:])) for p in self.premises)
        head = "%s(%s)" % (self.conclusion[0], ", ".join(self.conclusion[1:]))
        return "%s => %s" % (body, head)


class FolKB:
    def __init__(self, rules):
        self.rules = list(rules)
        self.facts = set()
        self.support = {}
        self.by_predicate = {}
        self.derivations = 0

    def tell(self, fact, reason="observed"):
        fact = tuple(fact)
        if fact in self.facts:
            return False
        self.facts.add(fact)
        self.support[fact] = reason
        self.by_predicate.setdefault(fact[0], set()).add(fact)
        return True

    def holds(self, fact):
        return tuple(fact) in self.facts

    def query(self, predicate):
        """Every ground fact stored under a predicate name."""
        return self.by_predicate.get(predicate, set())

    def why(self, fact):
        return self.support.get(tuple(fact), "not derived")

    def forward_chain(self):
        """Fire rules until nothing new appears. Returns the new facts."""
        added = []
        changed = True
        while changed:
            changed = False
            for rule in self.rules:
                for bindings in self._match(rule.premises, 0, {}):
                    head = substitute(rule.conclusion, bindings)
                    if any(is_var(t) for t in head[1:]):
                        continue
                    reason = "%s applied to %s" % (
                        rule.name,
                        ", ".join(
                            "%s(%s)" % (p[0], ", ".join(substitute(p, bindings)[1:]))
                            for p in rule.premises
                        ),
                    )
                    if self.tell(head, reason):
                        self.derivations += 1
                        added.append(head)
                        changed = True
        return added

    def _match(self, premises, index, bindings):
        if index == len(premises):
            yield bindings
            return
        pattern = premises[index]
        for fact in list(self.by_predicate.get(pattern[0], ())):
            merged = unify(pattern, fact, bindings)
            if merged is not None:
                yield from self._match(premises, index + 1, merged)


# The knowledge engineering part: the terrain rules written once, in FOL.
TERRAIN_RULES = [
    Rule([("Visited", "?c")], ("NoHazard", "?c"), "R1 a square already driven holds no hazard"),
    Rule([("Visited", "?c")], ("NoRadiation", "?c"), "R2 a square already driven holds no radiation"),
    Rule(
        [("Visited", "?c"), ("NoWarning", "?c"), ("Adjacent", "?c", "?n")],
        ("NoHazard", "?n"),
        "R3 no warning means no hazard next door",
    ),
    Rule(
        [("Visited", "?c"), ("NoAlert", "?c"), ("Adjacent", "?c", "?n")],
        ("NoRadiation", "?n"),
        "R4 no alert means no radiation next door",
    ),
    Rule(
        [("NoHazard", "?c"), ("NoRadiation", "?c")],
        ("Safe", "?c"),
        "R5 a square with neither hazard is safe",
    ),
    Rule(
        [("RadiationSealed", "yes"), ("Cell", "?c")],
        ("NoRadiation", "?c"),
        "R6 a neutralised zone emits nothing anywhere",
    ),
]
