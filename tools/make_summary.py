"""Builds SUMMARY.pdf, the one page technical sheet.

    python tools/make_summary.py

Needs reportlab. The numbers in MEASURED come from
`python run.py --benchmark 400 --seed 0`.
"""

import os
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

REPO = "https://github.com/suppprith/mars-rover-logic-agent"

INK = colors.HexColor("#111111")
RULE = colors.HexColor("#999999")
BAND = colors.HexColor("#eeeeee")

title = ParagraphStyle("title", fontName="Times-Bold", fontSize=14, leading=16, textColor=INK)
sub = ParagraphStyle("sub", fontName="Times-Roman", fontSize=8.5, leading=10.5, textColor=INK)
head = ParagraphStyle(
    "head", fontName="Times-Bold", fontSize=10, leading=12, textColor=INK, spaceBefore=6
)
cell = ParagraphStyle("cell", fontName="Times-Roman", fontSize=8, leading=9.6, textColor=INK)
cellb = ParagraphStyle("cellb", parent=cell, fontName="Times-Bold")
body = ParagraphStyle("body", parent=cell, fontSize=7.8, leading=9.4)


def p(text, style=cell):
    return Paragraph(text, style)


def grid(rows, widths, header_row=False):
    table = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    if header_row:
        style.append(("BACKGROUND", (0, 0), (-1, 0), BAND))
    else:
        style.append(("BACKGROUND", (0, 0), (0, -1), BAND))
    table.setStyle(TableStyle(style))
    return table


def header():
    return [
        p("Autonomous Mars Rover: a propositional logic agent", title),
        Spacer(1, 3),
        p(
            "BCA301-5 Artificial Intelligence &nbsp;&middot;&nbsp; AI Express Hackathon "
            "&nbsp;&middot;&nbsp; <b>Group 6</b><br/>"
            "Track 2: Autonomous Mars Rover (Unit 3, Propositional Logic Agent)",
            sub,
        ),
        Spacer(1, 2),
        p(
            "2441644 Pratyush Gupta &nbsp;&nbsp;|&nbsp;&nbsp; 2441661 Suprith R B "
            "&nbsp;&nbsp;|&nbsp;&nbsp; 2441647 Rohail Kuriakose Varghese",
            sub,
        ),
        Spacer(1, 2),
        p('Repository: <font face="Courier">%s</font>' % REPO, sub),
    ]


def peas():
    rows = [
        [
            p("Performance", cellb),
            p(
                "+1000 docking at the lander with the sample, -1000 losing the rover, -1 per action, "
                "-10 for the containment charge. Also logged: path cost, nodes expanded and generated, "
                "replans, clauses, resolution steps, reasoning time."
            ),
        ],
        [
            p("Environment", cellb),
            p(
                "6x6 grid of safe terrain, unknown hazards and one radiation zone, plus one sample "
                "cache. Each square beyond the lander and its neighbours holds a hazard with "
                "probability 0.16. Generation retries until the sample is reachable without crossing "
                "a hazard. Partially observable, deterministic, sequential, static, discrete, single "
                "agent."
            ),
        ],
        [
            p("Actuators", cellb),
            p(
                "Drive north, south, east or west to an adjacent square; Collect the sample; "
                "Neutralise the radiation zone along a bearing with the single charge; Dock."
            ),
        ],
        [
            p("Sensors", cellb),
            p(
                "Hazard warning (hazard adjacent), radiation alert (zone adjacent), sample beacon "
                "(cache on this square), neutralise confirmation, bump. Readings are local: the rover "
                "never sees a square it has not parked on."
            ),
        ],
    ]
    return grid(rows, [24 * mm, 158 * mm])


def formulation():
    rows = [
        [
            p("State space", cellb),
            p(
                "(position, knowledge base, has_sample, has_charge, radiation_active). The planner "
                "searches a subgraph: vertices are squares proved safe or already driven on, less "
                "squares proved to hold a hazard; edges join orthogonal neighbours. That vertex set "
                "grows with every reading, which is what forces the replan."
            ),
        ],
        [
            p("Initial state", cellb),
            p(
                "Rover at the lander (0,0), charge unused, no sample. KB holds Visited(0,0) and the "
                "grid adjacency facts. Nothing about hazards, the radiation zone or the cache is given."
            ),
        ],
        [
            p("Goal test", cellb),
            p(
                "Mission: Dock at (0,0) while has_sample. Search: n equals the target square, which is "
                "the cheapest safe unsurveyed square, or (0,0) once the sample is aboard."
            ),
        ],
        [
            p("Path cost", cellb),
            p("g(n) = number of moves from the current square, one unit per edge."),
        ],
        [
            p("Heuristic", cellb),
            p(
                "h(n) = |x<sub>n</sub> - x<sub>goal</sub>| + |y<sub>n</sub> - y<sub>goal</sub>| , "
                "f(n) = g(n) + h(n).<br/>"
                "Admissible: each move changes Manhattan distance by exactly 1, so no path is shorter "
                "than h(n). Consistent: h(n) &lt;= c(n,n') + h(n') = 1 + h(n') for adjacent n, n' , so "
                "A* with a closed set is optimal and never reopens a node."
            ),
        ],
        [
            p("Propositional axioms", cellb),
            p(
                "W<sub>x,y</sub> &lt;=&gt; OR over n in Adj(x,y) of H<sub>n</sub> &nbsp;&nbsp;and"
                "&nbsp;&nbsp; A<sub>x,y</sub> &lt;=&gt; OR over n in Adj(x,y) of Z<sub>n</sub><br/>"
                "W hazard warning, A radiation alert, H unknown hazard, Z radiation zone. Added in CNF "
                "the first time a square is seen, with unit clauses not H<sub>c</sub>, not "
                "Z<sub>c</sub> for every square driven on and the observed W<sub>c</sub> or not "
                "W<sub>c</sub>."
            ),
        ],
        [
            p("Entailment", cellb),
            p(
                "KB entails a query iff KB with the negated query is unsatisfiable. Tested by "
                "resolution refutation: set of support seeded on the negated query, a relevance filter "
                "dropping clauses over two moves from the query square, maximum clause length 8, and a "
                "2500 step budget. Exhausting the budget returns not proved, never proved false."
            ),
        ],
        [
            p("First-order rules", cellb),
            p(
                "Visited(c) =&gt; NoHazard(c) &nbsp;&middot;&nbsp; Visited(c) =&gt; NoRadiation(c)<br/>"
                "Visited(c) and NoWarning(c) and Adjacent(c,n) =&gt; NoHazard(n)<br/>"
                "Visited(c) and NoAlert(c) and Adjacent(c,n) =&gt; NoRadiation(n)<br/>"
                "NoHazard(c) and NoRadiation(c) =&gt; Safe(c) &nbsp;&middot;&nbsp; "
                "RadiationSealed and Cell(c) =&gt; NoRadiation(c)<br/>"
                "Forward chained to a fixpoint, unified against the ground adjacency facts."
            ),
        ],
        [
            p("Risk, no proof", cellb),
            p(
                "P(H<sub>c</sub> | evidence) = [ sum of w(m) over models satisfying the evidence with "
                "H<sub>c</sub> true ] / [ sum of w(m) over all models satisfying the evidence ], "
                "w(m) = product of p over true hazard variables and (1-p) over false, p = 0.16. "
                "Enumerated over unproved frontier variables. The rover drives onto the minimum at or "
                "below 0.25, otherwise it returns to the lander."
            ),
        ],
    ]
    return grid(rows, [26 * mm, 156 * mm])


def complexity(m):
    rows = [
        [p("Component", cellb), p("Theoretical", cellb), p("Observed, 400 maps", cellb)],
        [
            p("A* per search"),
            p(
                "N = n<sup>2</sup> = 36 squares, branching 4. O(N log N) with a closed set and a "
                "consistent heuristic; O(b<sup>d</sup>) worst case without one. Space O(N)."
            ),
            p(
                "%.1f expanded per search, %.1f per map over %.1f replans, %.1f generated"
                % (m["expanded"] / m["replans"], m["expanded"], m["replans"], m["generated"])
            ),
        ],
        [
            p("Forward chaining"),
            p(
                "Adjacency bounded at 4, so O(n<sup>2</sup>) ground rule instances. O(n<sup>2</sup>) "
                "per pass, O(n<sup>4</sup>) to fixpoint."
            ),
            p("%.0f facts derived per map, %.0f ground facts held" % (m["derived"], m["facts"])),
        ],
        [
            p("Resolution"),
            p(
                "O(2<sup>m</sup>) worst case for m symbols. m = 4n<sup>2</sup> = 144, cut to about 52 "
                "by the relevance window, then bounded by the 2500 step budget."
            ),
            p(
                "%.1f queries per map, %.0f steps per query against the 2500 cap"
                % (m["queries"], m["steps"] / m["queries"])
            ),
        ],
        [
            p("Model counting"),
            p("O(2<sup>k</sup>) over k unproved frontier variables, skipped above 2<sup>16</sup>."),
            p("k stays between 2 and 9, so under 512 assignments per call"),
        ],
        [
            p("Whole mission"),
            p("Turns bounded by the 250 step cap. Memory O(n<sup>2</sup>) facts and clauses."),
            p(
                "%.1f turns, %.1f moves, %.1f clauses; %.1f%% survived, "
                "%.1f%% recovered the sample, mean score %.1f"
                % (
                    m["turns"],
                    m["moves"],
                    m["clauses"],
                    m["survived"],
                    m["recovered"],
                    m["score"],
                )
            ),
        ],
    ]
    return grid(rows, [24 * mm, 76 * mm, 82 * mm], header_row=True)


MEASURED = {
    "recovered": 63.5,
    "survived": 93.2,
    "score": 544.2,
    "turns": 21.1,
    "moves": 19.3,
    "replans": 19.3,
    "expanded": 67.4,
    "generated": 117.2,
    "clauses": 190.7,
    "facts": 259.0,
    "derived": 64.0,
    "queries": 77.9,
    "steps": 91564.0,
}


def build(path, m=MEASURED):
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=10 * mm,
        title="Autonomous Mars Rover, technical summary",
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
    story.append(p("3. Complexity, theory against measurement", head))
    story.append(Spacer(1, 2))
    story.append(complexity(m))
    story.append(Spacer(1, 5))
    story.append(
        p(
            'Measurements: <font face="Courier">python run.py --benchmark 400 --seed 0</font> on '
            'Python 3.11. Recorded run: <font face="Courier">python run.py --seed 114 --delay 2400'
            "</font>, where resolution proves a hazard at (2,0) and model checking pins the radiation "
            "zone at (1,1). 19 turns, 16 moves, 47 nodes expanded, 14 resolution queries, 3 proofs, "
            "score 971.",
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
