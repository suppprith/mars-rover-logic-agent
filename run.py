"""Entry point.

    python run.py                     window plus live log, the demo setup
    python run.py --seed 7            same cave every time, handy for the video
    python run.py --ascii             terminal only, no Tkinter needed
    python run.py --benchmark 200     no drawing, prints averages over many caves
"""

import argparse
import statistics
import sys

from wumpus.session import Session


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Wumpus World agent with A* replanning")
    p.add_argument("--size", type=int, default=6, help="grid is size x size, default 6")
    p.add_argument("--pit-prob", type=float, default=0.16, help="chance of a pit per cell")
    p.add_argument("--seed", type=int, default=None, help="fix the cave layout")
    p.add_argument("--delay", type=int, default=650, help="milliseconds between turns")
    p.add_argument("--risk", type=float, default=0.25, help="highest pit estimate worth stepping on")
    p.add_argument("--max-steps", type=int, default=250, help="give up after this many turns")
    p.add_argument("--ascii", action="store_true", help="render in the terminal instead")
    p.add_argument("--headless", action="store_true", help="log only, no map")
    p.add_argument("--reveal", action="store_true", help="draw the hazards from the start")
    p.add_argument("--benchmark", type=int, metavar="N", help="run N caves and report averages")
    return p.parse_args(argv)


def build(args, seed):
    return Session(
        size=args.size,
        pit_prob=args.pit_prob,
        seed=seed,
        risk_limit=args.risk,
        max_steps=args.max_steps,
    )


def benchmark(args):
    rows = []
    base = args.seed if args.seed is not None else 0
    for i in range(args.benchmark):
        session = build(args, base + i)
        session.run()
        m = session.agent.metrics()
        m["score"] = session.cave.score
        m["won"] = session.cave.escaped and session.cave.has_gold
        m["survived"] = session.cave.alive
        rows.append(m)

    def avg(key):
        return statistics.mean(r[key] for r in rows)

    print("%d caves, %dx%d, pit probability %.2f" % (args.benchmark, args.size, args.size, args.pit_prob))
    print("gold recovered   %.1f%%" % (100 * sum(r["won"] for r in rows) / len(rows)))
    print("survived         %.1f%%" % (100 * sum(r["survived"] for r in rows) / len(rows)))
    print("mean score       %.1f" % avg("score"))
    print("mean turns       %.1f" % avg("steps"))
    print("mean path cost   %.1f moves" % avg("moves"))
    print("mean replans     %.1f" % avg("replans"))
    print("mean nodes expanded  %.1f" % avg("nodes_expanded"))
    print("mean nodes generated %.1f" % avg("nodes_generated"))
    print("mean clauses     %.1f" % avg("clauses"))
    print("mean resolution steps %.1f over %.1f queries" % (avg("resolution_steps"), avg("resolution_calls")))
    print("mean reasoning time  %.1f ms" % avg("thinking_ms"))


def main(argv=None):
    args = parse_args(argv)

    if args.benchmark:
        benchmark(args)
        return 0

    session = build(args, args.seed)
    print("cave %dx%d, pit probability %.2f, seed %s" % (args.size, args.size, args.pit_prob, args.seed))
    print("agent starts at (0, 0) knowing only that the entrance is safe")
    print()

    if args.headless:
        session.run()
        print("\n".join(session.log))
        return 0

    if args.ascii:
        from wumpus import console

        console.enable_ansi()
        console.play(session, delay=args.delay / 1000.0, reveal=args.reveal)
        return 0

    try:
        from wumpus import gui
    except ImportError:
        print("Tkinter is missing, falling back to the terminal renderer")
        from wumpus import console

        console.enable_ansi()
        console.play(session, delay=args.delay / 1000.0, reveal=args.reveal)
        return 0

    gui.launch(session, delay=args.delay, reveal=args.reveal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
