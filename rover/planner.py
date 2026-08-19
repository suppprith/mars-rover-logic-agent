"""A* over the squares the rover currently believes are safe.

The graph is the grid: nodes are squares, edges join orthogonal
neighbours, every edge costs one move. The heuristic is Manhattan
distance, which never overestimates on a 4-connected unit-cost grid, so
A* returns an optimal path and the usual optimality argument holds.

The passable set changes every time the knowledge base learns something,
which is why the rover replans from scratch after each sensor reading
instead of following a route it planned earlier.
"""

import heapq

from .world import neighbours


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class Result:
    def __init__(self, path, cost, expanded, generated):
        self.path = path
        self.cost = cost
        self.expanded = expanded
        self.generated = generated

    @property
    def found(self):
        return self.path is not None

    def __repr__(self):
        if not self.found:
            return "Result(no path)"
        return "Result(cost=%d, expanded=%d)" % (self.cost, self.expanded)


def astar(start, goal, passable, size):
    """Shortest route from start to goal through squares in `passable`.

    `start` is always allowed even if it is not in `passable`, since the
    rover has to plan from wherever it is parked.
    """
    if start == goal:
        return Result([start], 0, 0, 1)

    counter = 0
    open_heap = [(manhattan(start, goal), 0, counter, start)]
    came_from = {}
    best_g = {start: 0}
    closed = set()
    expanded = 0
    generated = 1

    while open_heap:
        _, g, _, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        closed.add(current)
        expanded += 1

        if current == goal:
            return Result(_rebuild(came_from, current), g, expanded, generated)

        for n in neighbours(current, size):
            if n not in passable and n != goal:
                continue
            tentative = g + 1
            if tentative < best_g.get(n, float("inf")):
                best_g[n] = tentative
                came_from[n] = current
                counter += 1
                generated += 1
                heapq.heappush(open_heap, (tentative + manhattan(n, goal), tentative, counter, n))

    return Result(None, 0, expanded, generated)


def nearest(start, goals, passable, size):
    """Cheapest reachable goal out of a set, and the route to it.

    Runs one A* search per candidate and keeps the best. The candidate
    list is the safe unsurveyed frontier, so it stays small.
    """
    best = None
    expanded = 0
    generated = 0
    for goal in sorted(goals, key=lambda c: manhattan(start, c)):
        result = astar(start, goal, passable, size)
        expanded += result.expanded
        generated += result.generated
        if result.found and (best is None or result.cost < best.cost):
            best = result
        if best is not None and best.cost <= manhattan(start, goal):
            break

    if best is None:
        return Result(None, 0, expanded, generated)
    best.expanded = expanded
    best.generated = generated
    return best


def _rebuild(came_from, node):
    path = [node]
    while node in came_from:
        node = came_from[node]
        path.append(node)
    path.reverse()
    return path
