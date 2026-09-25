"""A* over the World View's sub-tile grid for a tank's full footprint."""

import heapq
import itertools
from collections.abc import Collection

from src.managers.footprint import Cell, cells_at
from src.managers.world_view import WorldView
from src.utils.constants import CPU_PARTNER_BRICK_COST, Direction


class NavGrid:
    """Where a tank of ``size_cells`` x ``size_cells`` sub-tiles can stand.

    Cells are the tank's top-left sub-tile. Tiles that block tanks and
    can't be destroyed (steel, water, the Base), the map edges and Base Wall
    bricks (which must never be shot) are impassable. Other bricks are
    passable at a higher cost, since the tank must shoot its way through.
    Tanks are not obstacles; pass ``avoid`` to keep a tank's footprint out
    of the plan.
    """

    def __init__(
        self,
        world: WorldView,
        size_cells: int,
        avoid: Collection[Cell] = frozenset(),
    ) -> None:
        self._world = world
        self._size = size_cells
        self._avoid = avoid
        self._height = len(world.tiles)
        self._width = len(world.tiles[0]) if world.tiles else 0

    def passable(self, cell: Cell) -> bool:
        """Whether the tank fits at ``cell``, bricks included."""
        x, y = cell
        if not (
            0 <= x <= self._width - self._size and 0 <= y <= self._height - self._size
        ):
            return False
        return not any(
            c in self._avoid
            or (
                self._world.blocks_tanks(c)
                and (not self._is_brick(c) or c in self._world.base_wall_cells)
            )
            for c in cells_at(cell, self._size)
        )

    def has_brick(self, cell: Cell) -> bool:
        """Whether the tank's footprint at ``cell`` overlaps a brick to shoot."""
        return any(self._is_brick(c) for c in cells_at(cell, self._size))

    def _is_brick(self, cell: Cell) -> bool:
        """Whether ``cell`` blocks tanks until a bullet destroys it."""
        return (
            cell in self._world.tank_blocking_cells
            and cell in self._world.destructible_cells
        )

    def step_cost(self, cell: Cell) -> float:
        """Cost of moving onto ``cell`` from a neighbor."""
        return 1.0 + (CPU_PARTNER_BRICK_COST if self.has_brick(cell) else 0.0)

    def neighbors(self, cell: Cell) -> list[Cell]:
        """The passable cells one sub-tile up, down, left or right of ``cell``."""
        x, y = cell
        steps = ((x + d.delta[0], y + d.delta[1]) for d in Direction)
        return [n for n in steps if self.passable(n)]


def find_path(grid: NavGrid, start: Cell, goals: Collection[Cell]) -> list[Cell] | None:
    """Cheapest path from ``start`` to whichever of ``goals`` is cheapest to reach.

    Returns the cells from ``start`` to that goal inclusive, or ``None`` when
    no goal is reachable.
    """
    goals = [g for g in goals if grid.passable(g) or g == start]
    if not goals:
        return None

    def heuristic(cell: Cell) -> int:
        return min(abs(cell[0] - gx) + abs(cell[1] - gy) for gx, gy in goals)

    goal_set = set(goals)
    tie = itertools.count()
    open_heap: list[tuple[float, int, Cell]] = [(heuristic(start), next(tie), start)]
    cost_so_far: dict[Cell, float] = {start: 0.0}
    came_from: dict[Cell, Cell] = {}
    while open_heap:
        _, _, cell = heapq.heappop(open_heap)
        if cell in goal_set:
            path = [cell]
            while path[-1] != start:
                path.append(came_from[path[-1]])
            return path[::-1]
        for nxt in grid.neighbors(cell):
            cost = cost_so_far[cell] + grid.step_cost(nxt)
            if cost < cost_so_far.get(nxt, float("inf")):
                cost_so_far[nxt] = cost
                came_from[nxt] = cell
                heapq.heappush(open_heap, (cost + heuristic(nxt), next(tie), nxt))
    return None
