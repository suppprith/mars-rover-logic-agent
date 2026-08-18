# Wumpus World: a logical agent that plans with A*

BCA301-5 Artificial Intelligence, AI Express Hackathon. Group 6.

An agent is dropped into the bottom-left corner of a 6x6 cave it cannot see.
Pits and one wumpus are scattered through it, and a bar of gold sits somewhere
inside. The only thing the agent ever gets is a percept from the square it is
standing on: a breeze if a pit is next door, a stench if the wumpus is, a
glitter if the gold is underfoot. From that it has to work out where it is safe
to walk, find the gold, and get back out alive.

Two things are happening at once, and the point of the project is that they feed
each other. A knowledge base proves which squares are safe, and A* searches over
exactly those squares. Every new percept changes what has been proved, so the
route gets thrown out and rebuilt on the next turn.

## Running it

Python 3.9 or newer. The simulation itself needs nothing outside the standard
library.

```bash
python run.py
```

That opens the Tkinter window and prints the reasoning log to the terminal at
the same time. Put the two side by side and you can watch the agent move on the
left and read why it moved on the right.

```bash
python run.py --seed 114 --delay 1800
```

Seed 114 is the run we recorded. The agent proves a pit at (2, 0) by resolution,
works out that the wumpus can only be at (1, 1) and shoots it, then walks up the
left wall to the gold at (1, 4) and back out. Nineteen turns, final score 971.
A delay of 1800 ms stretches it to roughly forty seconds, which fits the video.

Other flags:

```bash
python run.py --ascii              # terminal rendering, no Tkinter needed
python run.py --headless           # log only
python run.py --reveal             # draw the hazards from the start
python run.py --size 8 --pit-prob 0.2
python run.py --benchmark 400      # no drawing, averages over many caves
```

`--seed` fixes the cave, so the same number always gives the same run.

Keys inside the window: space pauses, right arrow steps once while paused,
`r` reveals the hazards, `q` quits.

## Reading the screen

The grid shows what the agent believes, not what is really there. Grey squares
are unexplored and unreached. Green squares have been proved safe. Blue squares
have been walked on. An amber square is on the frontier with no proof either
way, and it carries the agent's estimate of the chance it holds a pit. Red means
a pit has been proved. The blue line is the current A* route, and a dashed red
line is an arrow shot.

The panel on the right carries the live counters: nodes expanded and generated,
number of replans, path cost so far, clause count, facts held, resolution
queries and proofs, and the reason behind the last action.

## How a turn works

1. Read the percepts for the current square and add them to the knowledge base.
2. Forward chain the first-order rules until nothing new comes out.
3. Run resolution on the frontier squares the easy rules could not settle.
4. Check whether the wumpus has been narrowed down to one square.
5. Pick an action, in this order:
   - gold underfoot, grab it
   - carrying the gold, A* home and climb out
   - somewhere proved safe and not yet visited, A* there
   - stuck but the wumpus is located and the arrow is unused, shoot it
   - still stuck, step on the least likely pit if the estimate is under 25%
   - otherwise walk home and climb out with nothing

Step 5 runs from scratch every turn. Nothing is cached between turns except the
knowledge itself, which is what makes the replanning visible: watch the blue
line jump to a different corner of the map the moment a breeze rules the old
route out.

## The three reasoners

**Forward chaining over first-order rules** (`wumpus/fol.py`). The cave rules are
written once, with variables, and a small unifier grounds them against the grid:

```
Visited(c)                                   => NoPit(c)
Visited(c) and NoBreeze(c) and Adjacent(c,n) => NoPit(n)
Visited(c) and NoStench(c) and Adjacent(c,n) => NoWumpus(n)
NoPit(c) and NoWumpus(c)                     => Safe(c)
WumpusDead and Cell(c)                       => NoWumpus(c)
```

This handles most of the work and it is cheap. Every derived fact stores the
rule and the bindings that produced it, which is where the explanations in the
log come from.

**Resolution refutation** (`wumpus/logic.py`) handles what the definite clauses
cannot: cases where a breeze is only explained once several observations are
combined. Each square gets a symbol `Px,y` for a pit and `Wx,y` for the wumpus,
and each visited square contributes the sensor axiom

```
Bx,y  <=>  P(n1) or P(n2) or ...      over its neighbours
```

as clauses. To ask whether a square is safe the prover negates the query, adds
it, and looks for the empty clause. Three things keep it finite on a 6x6 grid:
a set-of-support strategy so every step involves the negated query, a relevance
filter that drops clauses about squares more than two moves away, and a step
budget. Running out of budget is reported as "not proved", never as "proved
false", so a timeout can only ever make the agent more careful.

**Weighted model counting** (`model_count` in `wumpus/logic.py`) does two jobs.
It pins the wumpus down, since there is only one of it and enumerating its
possible squares is cheap. And when nothing is provable it enumerates the
frontier pit variables, weights each assignment by the generation probability,
and reports how likely each square is to hold a pit. A flat count would answer
the wrong question here: with one breeze and three unknown neighbours it says
each of them is 57% likely, because it treats three pits as being as plausible
as one. Weighting by the prior gives the numbers you would expect.

## The search

The graph is the grid. Nodes are squares, edges join orthogonal neighbours, and
every edge costs one move. The heuristic is Manhattan distance, which never
overestimates on a 4-connected unit-cost grid, so A* returns an optimal path.

The part worth pointing at is the passable set. A* is only allowed through
squares the knowledge base has proved safe, plus squares already walked on,
minus squares proved to hold a pit. That set is small at the start and grows as
the agent explores, so the same search over the same grid returns different
answers on consecutive turns.

Picking a destination runs one A* per candidate on the safe unvisited frontier
and keeps the cheapest. Because the candidates are sorted by Manhattan distance,
the loop can stop as soon as the best path found is no longer than the straight
line to the next candidate.

## Measured results

400 randomly generated 6x6 caves, pit probability 0.16, seeds 0 to 399:

```
gold recovered        64.5%
survived              94.2%
mean score            564.2
mean turns            21.1
mean path cost        19.3 moves
mean replans          19.3
mean nodes expanded   67.8
mean nodes generated  117.4
mean clauses          190.4
mean resolution steps 160678 over 127.7 queries
mean reasoning time   260.3 ms per cave
```

Reproduce with `python run.py --benchmark 400 --seed 0`.

The 6% that die are all cases where the agent had nothing proved safe left, took
the best gamble available, and lost. Raising the risk ceiling past 25% finds
more gold and dies more often; the mean score is worse either side of it, which
is how the default was chosen.

Nodes expanded per cave is small because the graph is small and the heuristic is
tight. The cost is all in the reasoning, and most of that is spent on resolution
queries that come back unproved, since a refutation search only stops early when
it succeeds.

## Layout

```
run.py                  command line entry point
wumpus/world.py         the cave, percepts, actions, scoring
wumpus/fol.py           unification and forward chaining
wumpus/logic.py         clauses, resolution prover, model counting
wumpus/knowledge.py     the agent's beliefs, all three reasoners behind one door
wumpus/planner.py       A*
wumpus/agent.py         the decision loop
wumpus/session.py       ties the cave and the agent together, owns the log
wumpus/gui.py           Tkinter window
wumpus/console.py       terminal renderer
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
optimality under obstacles, and the environment guarantees (the entrance and its
neighbours are never pits, the gold is always reachable, a seed always rebuilds
the same cave).

## Video

Recording of a full run: **[add the link here before submitting]**

## Group 6

| Register number | Name |
|---|---|
| 2441644 | Pratyush Gupta |
| 2441661 | Suprith R B |
| 2441647 | Rohail Kuriakose Varghese |
