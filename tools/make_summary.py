"""Builds SUMMARY.pdf, the one page technical sheet.

    python tools/make_summary.py

Needs reportlab. Numbers in the complexity table come from
`python run.py --benchmark 400 --seed 0`.
"""

import os
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

REPO = "https://github.com/suppprith/wumpus-astar-agent"

INK = colors.HexColor("#111111")
RULE = colors.HexColor("#999999")
BAND = colors.HexColor("#eeeeee")

title = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=13, leading=15, textColor=INK)
sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=8, leading=10, textColor=INK)
head = ParagraphStyle(
    "head", fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=INK, spaceBefore=5
)
body = ParagraphStyle(
    "body", fontName="Helvetica", fontSize=7.4, leading=9.2, textColor=INK, alignment=TA_JUSTIFY
)
cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=7.2, leading=8.8, textColor=INK)
cellb = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")


def p(text, style=cell):
    return Paragraph(text, style)


def grid(rows, widths, shade_first_column=True):
    table = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    if shade_first_column:
        style.append(("BACKGROUND", (0, 0), (0, -1), BAND))
    table.setStyle(TableStyle(style))
    return table


def header():
    members = (
        "2441644 Pratyush Gupta &nbsp;&nbsp;|&nbsp;&nbsp; "
        "2441661 Suprith R B &nbsp;&nbsp;|&nbsp;&nbsp; "
        "2441647 Rohail Kuriakose Varghese"
    )
    return [
        p("Wumpus World: a logical agent that plans with A*", title),
        Spacer(1, 2),
        p(
            "BCA301-5 Artificial Intelligence &nbsp;&middot;&nbsp; AI Express Hackathon "
            "&nbsp;&middot;&nbsp; <b>Group 6</b> &nbsp;&middot;&nbsp; "
            "Track: knowledge-based agent, propositional and first-order reasoning driving "
            "A* with dynamic replanning",
            sub,
        ),
        Spacer(1, 1.5),
        p(members, sub),
        Spacer(1, 1.5),
        p('Repository: <font face="Courier">%s</font>' % REPO, sub),
    ]


def peas():
    rows = [
        [
            p("Performance", cellb),
            p(
                "+1000 for carrying the gold out of the entrance, -1000 for dying, -1 per action, "
                "-10 for firing the arrow. Secondary measures logged every run: path cost in moves, "
                "A* nodes expanded and generated, number of replans, clauses held, resolution steps, "
                "reasoning time.",
            ),
        ],
        [
            p("Environment", cellb),
            p(
                "6x6 grid cave. Each square outside the entrance and its neighbours holds a pit with "
                "probability 0.16, plus one wumpus and one bar of gold. Generation retries until the "
                "gold is reachable without crossing a hazard. Partially observable (percepts are local "
                "only), deterministic, sequential, static, discrete, single agent.",
            ),
        ],
        [
            p("Actuators", cellb),
            p(
                "Move to an orthogonally adjacent square (north, south, east, west), Grab, "
                "Shoot in a direction with the single arrow, Climb out at the entrance.",
            ),
        ],
        [
            p("Sensors", cellb),
            p(
                "Breeze (a pit is adjacent), Stench (the wumpus is adjacent), Glitter (the gold is on "
                "this square), Scream (the arrow hit), Bump (walked into a wall). Nothing else is "
                "visible: the agent never sees a square it has not stood on.",
            ),
        ],
    ]
    return grid(rows, [24 * mm, 158 * mm])


def formulation():
    rows = [
        [
            p("State space", cellb),
            p(
                "Agent state is (position, knowledge base, has_gold, has_arrow, wumpus_alive). The "
                "planner searches a smaller graph: vertices are the squares currently proved safe or "
                "already visited, minus squares proved to hold a pit; edges join orthogonal neighbours. "
                "That vertex set changes after every percept, which is what forces the replan.",
            ),
        ],
        [
            p("Initial state", cellb),
            p(
                "Agent at (0,0) facing east, arrow unused, no gold. KB holds only Visited(0,0) plus the "
                "adjacency facts for the grid. Nothing about pits, the wumpus or the gold is given.",
            ),
        ],
        [
            p("Goal test", cellb),
            p(
                "Episode: Climb executed at (0,0) while has_gold. Search: n = target square, where the "
                "target is the cheapest safe square not yet visited, or (0,0) once the gold is held.",
            ),
        ],
        [
            p("Path cost", cellb),
            p(
                "g(n) = number of moves from the current square, one unit per edge, so g(n) is the "
                "length of the path in the search graph.",
            ),
        ],
        [
            p("Heuristic", cellb),
            p(
                "h(n) = |x<sub>n</sub> - x<sub>goal</sub>| + |y<sub>n</sub> - y<sub>goal</sub>| , "
                "f(n) = g(n) + h(n).<br/>"
                "Admissible: every move changes Manhattan distance by exactly 1, so no path can be "
                "shorter than h(n). Consistent: for adjacent n, n' , h(n) &lt;= c(n,n') + h(n') = "
                "1 + h(n') , so A* with a closed set returns an optimal path and never reopens a node.",
            ),
        ],
        [
            p("First-order rules", cellb),
            p(
                "Visited(c) =&gt; NoPit(c) &nbsp;&middot;&nbsp; Visited(c) =&gt; NoWumpus(c)<br/>"
                "Visited(c) and NoBreeze(c) and Adjacent(c,n) =&gt; NoPit(n)<br/>"
                "Visited(c) and NoStench(c) and Adjacent(c,n) =&gt; NoWumpus(n)<br/>"
                "NoPit(c) and NoWumpus(c) =&gt; Safe(c) &nbsp;&middot;&nbsp; "
                "WumpusDead and Cell(c) =&gt; NoWumpus(c)<br/>"
                "Applied by forward chaining to a fixpoint, with unification against the ground "
                "adjacency facts.",
            ),
        ],
        [
            p("Propositional axioms", cellb),
            p(
                "B<sub>x,y</sub> &lt;=&gt; OR over n in Adj(x,y) of P<sub>n</sub> &nbsp;&nbsp;and"
                "&nbsp;&nbsp; S<sub>x,y</sub> &lt;=&gt; OR over n in Adj(x,y) of W<sub>n</sub> , "
                "added in CNF the first time a square is seen, together with the unit clauses "
                "not P<sub>c</sub>, not W<sub>c</sub> for every square walked on and the observed "
                "B<sub>c</sub> or not B<sub>c</sub>.",
            ),
        ],
        [
            p("Entailment", cellb),
            p(
                "KB entails a query iff KB together with the negated query is unsatisfiable. Tested by resolution "
                "refutation with a set-of-support strategy seeded on the negated query, a relevance filter "
                "that drops clauses whose symbols lie more than two moves from the query square, a "
                "maximum clause length of 8, and a 2500 step budget. Exhausting the budget returns "
                "&quot;not proved&quot;, so the agent can only become more cautious, never less.",
            ),
        ],
        [
            p("Risk when no proof exists", cellb),
            p(
                "P(P<sub>c</sub> | evidence) = [ sum of w(m) over the models that satisfy the "
                "evidence and set P<sub>c</sub> true ] / [ sum of w(m) over every model that "
                "satisfies the evidence ], where w(m) is the product of p over the true pit "
                "variables and (1-p) over the false ones, p = 0.16. Enumerated over the unproved frontier "
                "variables only. The agent steps onto the minimum if it is at or below 0.25, otherwise "
                "it walks home and climbs out.",
            ),
        ],
    ]
    return grid(rows, [30 * mm, 152 * mm])


def complexity():
    rows = [
        [p("Component", cellb), p("Theoretical", cellb), p("Observed over 400 caves", cellb)],
        [
            p("A* per search"),
            p(
                "N = n<sup>2</sup> = 36 squares, branching 4. Time O(N log N) with a closed set and a "
                "consistent heuristic, worst case O(b<sup>d</sup>) = 4<sup>10</sup> without one. "
                "Space O(N) = 36."
            ),
            p("3.5 nodes expanded per search, 67.8 per cave over 19.3 replans; 117.4 generated"),
        ],
        [
            p("Forward chaining"),
            p(
                "Adjacency is bounded at 4, so the rules have O(n<sup>2</sup>) ground instances. "
                "O(n<sup>2</sup>) work per pass, O(n<sup>4</sup>) to reach the fixpoint."
            ),
            p("64 facts derived per cave, 259 ground facts held at the end"),
        ],
        [
            p("Resolution"),
            p(
                "Propositional resolution is O(2<sup>m</sup>) in the worst case for m symbols. Here "
                "m = 4n<sup>2</sup> = 144, cut to roughly 52 by the relevance window and then capped "
                "by the 2500 step budget, so each query is bounded."
            ),
            p("127.7 queries per cave, 1258 steps per query against the 2500 cap"),
        ],
        [
            p("Model counting"),
            p(
                "O(2<sup>k</sup>) over k unproved frontier variables, skipped entirely when "
                "2<sup>k</sup> &gt; 65536."
            ),
            p("k stays in the range 2 to 9 in practice, so under 512 assignments per call"),
        ],
        [
            p("Whole episode"),
            p("Turns bounded by the 250 step cap; memory O(n<sup>2</sup>) facts plus O(n<sup>2</sup>) clauses"),
            p(
                "21.1 turns, 19.3 moves, 190.4 clauses, 260.3 ms of reasoning per cave; "
                "94.2% survived, 64.5% recovered the gold, mean score 564.2"
            ),
        ],
    ]
    table = grid(rows, [24 * mm, 76 * mm, 82 * mm], shade_first_column=False)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), BAND)]))
    return table


def build(path):
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=10 * mm,
        title="Wumpus World logical agent, technical summary",
        author="Group 6",
    )
    story = []
    story.extend(header())
    story.append(Spacer(1, 6))
    story.append(p("1. PEAS framework", head))
    story.append(Spacer(1, 2))
    story.append(peas())
    story.append(p("2. Core algorithmic formulation", head))
    story.append(Spacer(1, 2))
    story.append(formulation())
    story.append(p("3. Complexity analysis, theory against measurement", head))
    story.append(Spacer(1, 2))
    story.append(complexity())
    story.append(Spacer(1, 4))
    story.append(
        p(
            "Measurements reproduce with <font face=\"Courier\">python run.py --benchmark 400 "
            "--seed 0</font> on Python 3.11. The recorded demo run is "
            "<font face=\"Courier\">python run.py --seed 114 --delay 1800</font>: 19 turns, "
            "16 moves, 47 nodes expanded, 34 resolution queries with 2 proofs, final score 971.",
            body,
        )
    )
    doc.build(story)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "SUMMARY.pdf")
    build(out)
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
