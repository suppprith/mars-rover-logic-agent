"""Terminal renderer, for when Tkinter is not available.

Redraws the belief map in place between turns and prints the same log the
window prints. Same session object, same run, just fewer pixels.
"""

import os
import sys
import time

GLYPH = {
    "dark": "  ",
    "unknown": "??",
    "safe": "ok",
    "seen": "..",
    "hazard": "XX",
    "radiation": "RR",
}


def clear():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def board(session, reveal=False):
    terrain = session.terrain
    rows = []
    for y in range(session.size - 1, -1, -1):
        cells = []
        for x in range(session.size):
            cell = (x, y)
            if cell == terrain.rover:
                token = "@@"
            elif reveal and cell in terrain.hazards:
                token = "XX"
            elif reveal and cell == terrain.sample and not terrain.has_sample:
                token = "$$"
            elif reveal and cell == terrain.radiation and terrain.radiation_active:
                token = "WW"
            else:
                token = GLYPH[session.belief(cell)]
            cells.append(" %s " % token)
        rows.append("%d |%s|" % (y, "|".join(cells)))
    footer = "  " + " ".join(" %d  " % x for x in range(session.size))
    edge = "  +" + "+".join(["----"] * session.size) + "+"
    return "\n".join([edge] + [r for row in rows for r in (row, edge)] + [footer])


def legend():
    return (
        "@@ rover   ok proved safe   .. surveyed   ?? frontier   "
        "XX hazard   RR radiation   $$ sample"
    )


def play(session, delay=0.6, reveal=False, redraw=True):
    tail = []
    while not session.done:
        fresh = session.advance()
        tail.extend(fresh)
        tail = tail[-14:]
        if redraw and sys.stdout.isatty():
            clear()
            print(board(session, reveal))
            print(legend())
            print()
            print("\n".join(tail))
        else:
            for line in fresh:
                print(line, flush=True)
        time.sleep(delay)

    if redraw and sys.stdout.isatty():
        clear()
        print(board(session, reveal=True))
        print(legend())
        print()
    print("\n".join(session.log[-10:]) if not redraw else "\n".join(tail))
    return session.outcome


def enable_ansi():
    """Windows terminals need to be asked before they honour escape codes."""
    if os.name != "nt":
        return
    try:
        import ctypes

        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass
