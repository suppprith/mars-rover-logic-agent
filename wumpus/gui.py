"""Tkinter view of the cave.

Left half is the grid the agent walks. Right half is the live read-out of
its state and the counters. Every line the window draws also goes to
stdout, so putting the terminal next to the window gives you the map and
the reasoning trace side by side.

Keys: space pauses and resumes, right arrow steps once while paused,
r reveals the hazards, q quits.
"""

import tkinter as tk

BG = "#11151c"
PANEL = "#171d26"
GRID_LINE = "#2b3442"
TEXT = "#dfe6f0"
DIM = "#7c8798"

FILL = {
    "dark": "#1b2029",
    "unknown": "#3a2f1e",
    "safe": "#1d3a2c",
    "seen": "#24303f",
    "pit": "#4a1f24",
    "wumpus": "#43244a",
}

ACCENT = "#e2b33c"
PATH = "#4d9de0"
DANGER = "#e05c5c"


class Window:
    def __init__(self, session, delay=650, reveal=False, echo=True):
        self.session = session
        self.delay = delay
        self.reveal = reveal
        self.echo = echo
        self.paused = False

        size = session.size
        self.pad = 24
        self.cell = 78 if size <= 6 else 56
        board = self.cell * size

        self.root = tk.Tk()
        self.root.title("Wumpus World: logical agent with A* replanning")
        self.root.configure(bg=BG)

        self.canvas = tk.Canvas(
            self.root,
            width=board + self.pad * 2,
            height=board + self.pad * 2,
            bg=BG,
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, padx=10, pady=10)

        self.panel = tk.Frame(self.root, bg=PANEL, width=330)
        self.panel.grid(row=0, column=1, sticky="ns", padx=(0, 10), pady=10)
        self.panel.grid_propagate(False)

        self.status = tk.Label(
            self.panel,
            text="",
            justify="left",
            anchor="nw",
            bg=PANEL,
            fg=TEXT,
            font=("Consolas", 10),
            wraplength=306,
        )
        self.status.pack(fill="both", expand=True, padx=12, pady=12)

        self.root.bind("<space>", self._toggle)
        self.root.bind("<Right>", lambda e: self._once())
        self.root.bind("r", self._flip_reveal)
        self.root.bind("q", lambda e: self.root.destroy())

        self.board = board

    # ---- loop -------------------------------------------------------

    def run(self):
        self.draw()
        self.root.after(600, self._pump)
        self.root.mainloop()

    def _pump(self):
        if not self.paused:
            self._once()
        if self.session.done:
            self.reveal = True
            self.draw()
            return
        self.root.after(self.delay, self._pump)

    def _once(self):
        if self.session.done:
            return
        for line in self.session.advance():
            if self.echo:
                print(line, flush=True)
        self.draw()

    def _toggle(self, _event=None):
        self.paused = not self.paused
        self.draw()

    def _flip_reveal(self, _event=None):
        self.reveal = not self.reveal
        self.draw()

    # ---- drawing ----------------------------------------------------

    def _box(self, cell):
        x, y = cell
        left = self.pad + x * self.cell
        top = self.pad + (self.session.size - 1 - y) * self.cell
        return left, top, left + self.cell, top + self.cell

    def _centre(self, cell):
        l, t, r, b = self._box(cell)
        return (l + r) / 2, (t + b) / 2

    def draw(self):
        self.canvas.delete("all")
        session = self.session
        risk = session.agent.kb.pit_risk()

        for x in range(session.size):
            for y in range(session.size):
                self._draw_cell((x, y), risk)

        self._draw_path()
        self._draw_agent()
        self._draw_labels()
        self._write_status()

    def _draw_cell(self, cell, risk):
        session = self.session
        cave = session.cave
        kb = session.agent.kb
        l, t, r, b = self._box(cell)
        state = session.belief(cell)

        self.canvas.create_rectangle(l, t, r, b, fill=FILL[state], outline=GRID_LINE, width=1)

        marks = []
        if cell in kb.breezy:
            marks.append("breeze")
        if cell in kb.smelly:
            marks.append("stench")
        if marks:
            self.canvas.create_text(
                (l + r) / 2,
                t + 14,
                text=" ".join(marks),
                fill=DIM,
                font=("Consolas", 8),
            )

        if state == "unknown" and cell in risk:
            self.canvas.create_text(
                (l + r) / 2,
                b - 14,
                text="pit %.0f%%" % (risk[cell] * 100),
                fill=ACCENT,
                font=("Consolas", 8),
            )
        elif state == "safe":
            self.canvas.create_text(
                (l + r) / 2, b - 14, text="proved safe", fill="#63c08a", font=("Consolas", 8)
            )
        elif state == "pit":
            self.canvas.create_text(
                (l + r) / 2, b - 14, text="pit proved", fill=DANGER, font=("Consolas", 8)
            )

        if self.reveal:
            hidden = []
            if cell in cave.pits:
                hidden.append("PIT")
            if cell == cave.wumpus:
                hidden.append("WUMPUS" if cave.wumpus_alive else "dead wumpus")
            if cell == cave.gold and not cave.has_gold:
                hidden.append("GOLD")
            if hidden:
                self.canvas.create_text(
                    (l + r) / 2,
                    (t + b) / 2 + 2,
                    text="\n".join(hidden),
                    fill=DANGER if "PIT" in hidden or "WUMPUS" in hidden else ACCENT,
                    font=("Consolas", 9, "bold"),
                )

    def _draw_path(self):
        decision = self.session.last
        if not decision or len(decision.path) < 2:
            return
        points = []
        for cell in decision.path:
            points.extend(self._centre(cell))
        style = () if decision.action != "shoot" else (6, 4)
        self.canvas.create_line(
            *points,
            fill=DANGER if decision.action == "shoot" else PATH,
            width=3,
            dash=style,
            arrow="last",
            smooth=False,
        )

    def _draw_agent(self):
        cx, cy = self._centre(self.session.cave.agent)
        radius = self.cell * 0.22
        colour = ACCENT if self.session.cave.alive else DANGER
        self.canvas.create_oval(
            cx - radius, cy - radius, cx + radius, cy + radius, fill=colour, outline=""
        )
        if self.session.cave.has_gold:
            self.canvas.create_text(cx, cy, text="G", fill="#11151c", font=("Consolas", 11, "bold"))

    def _draw_labels(self):
        for i in range(self.session.size):
            l, t, r, b = self._box((i, 0))
            self.canvas.create_text(
                (l + r) / 2, self.pad + self.board + 11, text=str(i), fill=DIM, font=("Consolas", 8)
            )
            l, t, r, b = self._box((0, i))
            self.canvas.create_text(
                self.pad - 11, (t + b) / 2, text=str(i), fill=DIM, font=("Consolas", 8)
            )

    def _write_status(self):
        session = self.session
        cave = session.cave
        m = session.agent.metrics()
        decision = session.last

        frontier = len(session.agent.kb.frontier())
        safe_left = len(session.agent.kb.unexplored_safe())

        lines = [
            "turn %d%s" % (session.tick, "   [paused]" if self.paused else ""),
            "",
            "position     %s facing %s" % (cave.agent, cave.facing),
            "score        %d" % cave.score,
            "gold         %s" % ("carried" if cave.has_gold else "not found"),
            "arrow        %s" % ("ready" if cave.has_arrow else "spent"),
            "wumpus       %s" % ("alive" if cave.wumpus_alive else "dead"),
            "",
            "search",
            "  nodes expanded   %d" % m["nodes_expanded"],
            "  nodes generated  %d" % m["nodes_generated"],
            "  replans          %d" % m["replans"],
            "  path cost so far %d" % m["moves"],
            "",
            "knowledge",
            "  clauses          %d" % m["clauses"],
            "  facts held       %d" % m["fol_facts"],
            "  forward chained  %d" % m["fol_derivations"],
            "  resolution asks  %d" % m["resolution_calls"],
            "  proofs found     %d" % m["resolution_proofs"],
            "  resolution steps %d" % m["resolution_steps"],
            "",
            "map",
            "  safe unvisited   %d" % safe_left,
            "  frontier cells   %d" % frontier,
            "",
        ]
        if decision:
            label = decision.action
            if decision.argument is not None:
                label = "%s %s" % (decision.action, decision.argument)
            lines.append("last move: %s" % label)
            lines.append("why: %s" % decision.reason)
        if session.outcome:
            lines.append("")
            lines.append("outcome: %s" % session.outcome)
        lines.append("")
        lines.append("space pause   right step   r reveal   q quit")

        self.status.config(text="\n".join(lines))


def launch(session, delay=650, reveal=False, echo=True):
    Window(session, delay=delay, reveal=reveal, echo=echo).run()

