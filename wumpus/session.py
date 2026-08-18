"""Ties the cave and the agent together and keeps the running log.

Both front ends drive the same Session, so the Tkinter window and the
terminal log always show the same run.
"""

import time

from .agent import Agent
from .world import Cave


class Session:
    def __init__(self, size=6, pit_prob=0.16, seed=None, risk_limit=0.25, max_steps=250):
        self.cave = Cave(size=size, pit_prob=pit_prob, seed=seed)
        self.agent = Agent(size=size, risk_limit=risk_limit, pit_prior=pit_prob)
        self.max_steps = max_steps
        self.size = size

        self.log = []
        self.tick = 0
        self.last = None
        self.started = time.perf_counter()
        self.elapsed = 0.0
        self.outcome = None

    @property
    def done(self):
        return self.cave.finished or self.tick >= self.max_steps

    def emit(self, text):
        line = "[%03d] %s" % (self.tick, text)
        self.log.append(line)
        return line

    def advance(self):
        """Run one perceive-think-act cycle. Returns the new log lines."""
        if self.done:
            return []

        self.tick += 1
        fresh = []
        cell = self.cave.agent
        percepts = self.cave.percepts()

        active = [k for k in ("breeze", "stench", "glitter", "scream") if percepts[k]]
        fresh.append(self.emit("at %s, senses: %s" % (cell, ", ".join(active) or "nothing")))

        decision = self.agent.step(cell, percepts)
        for note in self.agent.notes:
            fresh.append(self.emit("  kb  | %s" % note))

        label = decision.action
        if decision.argument is not None:
            label = "%s %s" % (decision.action, decision.argument)
        fresh.append(self.emit("  act | %s because %s" % (label, decision.reason)))

        outcome = self.cave.act(decision.action, decision.argument)
        fresh.append(self.emit("  env | %s" % outcome))

        self.last = decision
        self.elapsed = time.perf_counter() - self.started

        if self.cave.finished:
            fresh.extend(self.emit(line) for line in self.summary_lines())
        elif self.tick >= self.max_steps:
            self.outcome = "step limit reached"
            fresh.append(self.emit("step limit reached, stopping"))

        return fresh

    def run(self):
        while not self.done:
            self.advance()
        return self.outcome

    def summary_lines(self):
        cave = self.cave
        if cave.escaped and cave.has_gold:
            self.outcome = "escaped with the gold"
        elif cave.escaped:
            self.outcome = "escaped empty handed"
        elif not cave.alive:
            self.outcome = "died in the cave"
        else:
            self.outcome = "still going"

        m = self.agent.metrics()
        return [
            "result: %s, score %d" % (self.outcome, cave.score),
            "path cost %d moves, %d turns total, %d replans"
            % (m["moves"], m["steps"], m["replans"]),
            "A* expanded %d nodes and generated %d"
            % (m["nodes_expanded"], m["nodes_generated"]),
            "knowledge base: %d clauses, %d facts, %d forward chained"
            % (m["clauses"], m["fol_facts"], m["fol_derivations"]),
            "resolution: %d queries, %d proofs, %d resolution steps"
            % (m["resolution_calls"], m["resolution_proofs"], m["resolution_steps"]),
            "reasoning time %.1f ms over %.2f s wall clock" % (m["thinking_ms"], self.elapsed),
        ]

    def belief(self, cell):
        """One short tag per cell for the map overlay."""
        kb = self.agent.kb
        if cell in kb.visited:
            return "seen"
        if cell in kb.known_pits():
            return "pit"
        if kb.wumpus_location() == cell:
            return "wumpus"
        if kb.safe(cell):
            return "safe"
        if cell in kb.frontier():
            return "unknown"
        return "dark"
