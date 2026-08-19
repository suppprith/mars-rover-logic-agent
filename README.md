# Autonomous Mars Rover: a propositional logic agent

BCA301-5 Artificial Intelligence, AI Express Hackathon. Group 6.
**Track 2: Autonomous Mars Rover (Unit 3, Propositional Logic Agent).**

A rover is set down at the lander in the corner of a 6x6 survey grid it cannot
see. Unknown hazards are scattered through it, one radiation zone sits somewhere in
the field, and a sample cache is waiting to be collected. The rover only ever
gets readings from the square it is parked on: a hazard warning if a hazard is
next door, a radiation alert if the zone is, a beacon if the sample is underfoot. From that it has to work out which squares are safe to drive on,
collect the sample, and get back to the lander in one piece.

Two things are happening at once, and the point of the project is that they feed
each other. A knowledge base proves which squares are safe, and A* searches over
exactly those squares. Every new sensor reading changes what has been proved, so
the route gets thrown out and rebuilt on the next turn.

## Running it

Python 3.9 or newer. The simulation itself needs nothing outside the standard
library.

```bash
python run.py
```

That opens the Tkinter window and prints the reasoning log to the terminal at
the same time. The window carries its own copy of the log in a pane on the
right, so the run is readable even when the terminal is hidden behind it.

```bash
python run.py --seed 114 --delay 1800
```

Seed 114 is the run we recorded. The rover proves a hazard at (2, 0) by
resolution, works out by model checking that the radiation zone can only be at
(1, 1) and neutralises it with its containment charge, then drives up the left
edge to the sample at (1, 4) and back to the lander. Nineteen turns, final score 971. A
delay of 1800 ms stretches it to roughly forty seconds, which fits the video.

Other flags:

```bash
python run.py --ascii              # terminal rendering, no Tkinter needed
python run.py --headless           # log only
python run.py --reveal             # draw the hazards from the start
python run.py --size 8 --hazard-prob 0.2
python run.py --benchmark 400      # no drawing, averages over many maps
```

`--seed` fixes the map, so the same number always gives the same run.

Keys inside the window: space pauses, right arrow steps once while paused,
`r` reveals the hazards, `q` quits.

## Reading the screen

The grid shows what the rover believes, not what is really there. Grey squares
are unsurveyed and unreached. Green squares have been proved safe. Blue squares
have been driven on. An amber square is on the frontier with no proof either
way, and it carries the rover's estimate of the chance it holds a hazard. Red
means a hazard has been proved. The blue line is the current A* route, and a
dashed red line is the containment charge being fired.

The panel on the right carries the live counters: nodes expanded and generated,
number of replans, path cost so far, clause count, facts held, resolution
queries and proofs, and the reason behind the last action.

## How a turn works

1. Read the sensors on the current square and add the readings to the knowledge
   base.
2. Forward chain the first-order rules until nothing new comes out.
3. Run resolution on the frontier squares the easy rules could not settle.
4. Check whether the radiation zone has been narrowed down to one square.
5. Pick an action, in this order:
   - sample cache underfoot, collect it
   - carrying the sample, A* back to the lander and dock
   - somewhere proved safe and not yet surveyed, A* there
   - stuck but the radiation zone is located and the charge is unused, seal it
   - still stuck, drive onto the least likely hazard if the estimate is under 25%
   - otherwise drive home and dock with nothing

Step 5 runs from scratch every turn. Nothing is cached between turns except the
knowledge itself, which is what makes the replanning visible: watch the blue
line jump to a different corner of the map the moment a hazard warning rules the
old route out.

## The three reasoners

**Propositional resolution** (`rover/logic.py`) is the core of Track 2. Each
square gets a symbol `Hx,y` for an unknown hazard and `Zx,y` for a radiation
zone, and every square the rover parks on contributes the sensor axiom

```
Wx,y  <=>  H(n1) or H(n2) or ...      over its neighbours
Ax,y  <=>  Z(n1) or Z(n2) or ...
```

where `W` is the hazard warning the rover reads and `A` is the radiation alert.

as CNF clauses, together with the unit clauses for what the sensors actually
said. To ask whether a square is safe the prover negates the query, adds it, and
looks for the empty clause. Three things keep it finite on a 6x6 grid: a
set-of-support strategy so every step involves the negated query, a relevance
filter that drops clauses about squares more than two moves away, and a step
budget. Running out of budget is reported as "not proved", never as "proved
false", so a timeout can only ever make the rover more careful.

**Weighted model counting** (`model_count` in `rover/logic.py`) does two jobs.
It pins the radiation zone down, since there is only one of it and enumerating
its possible squares is cheap. And when nothing is provable it enumerates the
frontier hazard variables, weights each assignment by the generation
probability, and reports how likely each square is to hold a hazard. A flat
count would answer the wrong question here: with one warning and three unknown
neighbours it calls each of them 57% likely, because it treats three hazards
as being as plausible as one. Weighting by the prior gives the numbers you would
expect.

**Forward chaining over first-order rules** (`rover/fol.py`) carries the routine
conclusions so resolution is only spent on the hard ones. The terrain rules are
written once, with variables, and a small unifier grounds them against the grid:

```
Visited(c)                                    => NoHazard(c)
Visited(c) and NoWarning(c) and Adjacent(c,n) => NoHazard(n)
Visited(c) and NoAlert(c) and Adjacent(c,n)   => NoRadiation(n)
NoHazard(c) and NoRadiation(c)                => Safe(c)
RadiationSealed and Cell(c)                   => NoRadiation(c)
```

Every derived fact stores the rule and the bindings that produced it, which is
where the explanations in the log come from.

## The search

The graph is the grid. Nodes are squares, edges join orthogonal neighbours, and
every edge costs one move. The heuristic is Manhattan distance, which never
overestimates on a 4-connected unit-cost grid, so A* returns an optimal path.

The part worth pointing at is the passable set. A* is only allowed through
squares the knowledge base has proved safe, plus squares already driven on,
minus squares proved to hold a hazard. That set is small at the start and
grows as the rover explores, so the same search over the same grid returns
different answers on consecutive turns.

Picking a destination runs one A* per candidate on the safe unsurveyed frontier
and keeps the cheapest. Because the candidates are sorted by Manhattan distance,
the loop can stop as soon as the best path found is no longer than the straight
line to the next candidate.

## Measured results

400 randomly generated 6x6 maps, hazard probability 0.16, seeds 0 to 399:

```
sample recovered      64.5%
rover survived        94.2%
mean score            564.2
mean turns            21.1
mean path cost        19.3 moves
mean replans          19.3
mean nodes expanded   67.8
mean nodes generated  117.4
mean clauses          190.4
mean resolution steps 137696 over 106.1 queries
mean reasoning time   371.4 ms per map
```

Reproduce with `python run.py --benchmark 400 --seed 0`.

The 6% that are lost are all cases where the rover had nothing proved safe left,
took the best gamble available, and lost. Raising the risk ceiling past 25%
finds more samples and loses more rovers; the mean score is worse either side of
it, which is how the default was chosen.

Nodes expanded per map is small because the graph is small and the heuristic is
tight. The cost is all in the reasoning, and most of that is spent on resolution
queries that come back unproved, since a refutation search only stops early when
it succeeds.

## Layout

```
run.py                  command line entry point
rover/world.py          the survey grid, sensors, actions, scoring
rover/logic.py          clauses, resolution prover, weighted model counting
rover/fol.py            unification and forward chaining
rover/knowledge.py      the rover's beliefs, all three reasoners behind one door
rover/planner.py        A*
rover/agent.py          the decision loop
rover/session.py        ties the grid and the rover together, owns the log
rover/gui.py            Tkinter window
rover/console.py        terminal renderer
tools/make_summary.py   rebuilds SUMMARY.pdf
tests/                  21 unit tests
SUMMARY.pdf             the one page technical sheet
```

## Tests

```bash
python -m unittest discover -s tests -t .
```

Covers the prover on cases where entailment holds and cases where it does not,
unification, the effect of the prior on the posterior, A* optimality and
optimality under obstacles, and the environment guarantees (the lander and its
neighbours are never hazards, the sample is always reachable, a seed always
rebuilds the same map).

## Group 6

| Register number | Name |
|---|---|
| 2441644 | Pratyush Gupta |
| 2441661 | Suprith R B |
| 2441647 | Rohail Kuriakose Varghese |
