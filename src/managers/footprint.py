"""Which sub-tile cells a square footprint covers on the battlefield grid.

Positions and sizes are pixels; cells are ``(x, y)`` sub-tiles of
``cell_size`` pixels.
"""

import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

from src.utils.constants import TILE_SIZE

Cell = tuple[int, int]


class Placed(Protocol):
    """Anything with a square footprint on the battlefield (pixels)."""

    @property
    def x(self) -> float: ...
    @property
    def y(self) -> float: ...
    @property
    def size(self) -> int: ...


if TYPE_CHECKING:
    from _typeshed import DataclassInstance

    class _PlacedDataclass(Placed, DataclassInstance, Protocol):
        """A ``Placed`` dataclass, which ``moved`` can copy at a new position."""

else:
    _PlacedDataclass = Placed


@dataclass(frozen=True)
class Footprint:
    """A plain square on the battlefield, such as the Base or a tank's rect (pixels)."""

    x: float
    y: float
    size: int


def size_in_cells(size: int, cell_size: int) -> int:
    """How many cells wide a footprint ``size`` px wide is, rounding up."""
    return math.ceil(size / cell_size)


def covered_cells(placed: Placed, cell_size: int) -> set[Cell]:
    """Every cell ``placed`` overlaps, even partly."""
    return {
        (x, y)
        for x in range(
            math.floor(placed.x / cell_size),
            math.ceil((placed.x + placed.size) / cell_size),
        )
        for y in range(
            math.floor(placed.y / cell_size),
            math.ceil((placed.y + placed.size) / cell_size),
        )
    }


def cells_at(cell: Cell, size_cells: int) -> set[Cell]:
    """The cells a tank ``size_cells`` wide covers with its top-left at ``cell``."""
    x, y = cell
    return {(x + dx, y + dy) for dx in range(size_cells) for dy in range(size_cells)}


def touching_cells(placed: Placed, size_cells: int, cell_size: int) -> set[Cell]:
    """Cells from which a tank ``size_cells`` wide overlaps ``placed``."""
    reach = size_cells - 1
    return {
        cell
        for x, y in covered_cells(placed, cell_size)
        for cell in cells_at((x - reach, y - reach), size_cells)
    }


def moved[P: _PlacedDataclass](placed: P, delta: tuple[int, int], distance: float) -> P:
    """``placed`` moved ``distance`` px along ``delta``, all else kept."""
    dx, dy = delta
    return replace(placed, x=placed.x + dx * distance, y=placed.y + dy * distance)


def swept_cells(
    placed: Placed, delta: tuple[int, int], distance: float, cell_size: int
) -> set[Cell]:
    """Every cell ``placed`` overlaps on its way ``distance`` px along ``delta``."""
    end = moved(Footprint(placed.x, placed.y, placed.size), delta, distance)
    left, top = min(placed.x, end.x), min(placed.y, end.y)
    right = max(placed.x, end.x) + placed.size
    bottom = max(placed.y, end.y) + placed.size
    return {
        (x, y)
        for x in range(math.floor(left / cell_size), math.ceil(right / cell_size))
        for y in range(math.floor(top / cell_size), math.ceil(bottom / cell_size))
    }


def spawn_point_footprint(spawn_point: Cell, cell_size: int) -> Footprint:
    """The square an Enemy spawning at ``spawn_point`` takes up."""
    x, y = spawn_point
    return Footprint(float(x * cell_size), float(y * cell_size), TILE_SIZE)


def blocks_spawn_point(placed: Placed, spawn_point: Cell, cell_size: int) -> bool:
    """Whether ``placed`` covers any part of the Enemy Spawn Point, blocking it."""
    return not covered_cells(placed, cell_size).isdisjoint(
        covered_cells(spawn_point_footprint(spawn_point, cell_size), cell_size)
    )
