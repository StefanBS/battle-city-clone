"""Pure geometry helpers shared by tank AI implementations."""

from src.utils.constants import Direction

_ALL_DIRECTIONS = list(Direction)


def manhattan(a: tuple[float, float], b: tuple[float, float]) -> float:
    """L1 distance between two points."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def filter_candidate_directions(
    current: Direction, blocked: set[Direction]
) -> list[Direction]:
    """Directions the tank may pick next.

    Prefers directions that are neither blocked nor the reverse of `current`.
    Falls back to allowing the reverse when every other non-blocked direction
    is gone, and returns an empty list only when every direction is blocked.
    """
    opposite = current.opposite
    filtered = [d for d in _ALL_DIRECTIONS if d not in blocked and d != opposite]
    if filtered:
        return filtered
    return [d for d in _ALL_DIRECTIONS if d not in blocked]


def direction_moves_toward(
    pos: tuple[float, float],
    direction: Direction,
    target: tuple[float, float],
) -> bool:
    """True if moving from pos along direction reduces distance to target."""
    dx, dy = direction.delta
    x, y = pos
    tx, ty = target
    if dx != 0:
        return (dx > 0 and tx > x) or (dx < 0 and tx < x)
    return (dy > 0 and ty > y) or (dy < 0 and ty < y)


def is_aligned_with(
    pos: tuple[float, float],
    direction: Direction,
    tile_size: int,
    target: tuple[float, float],
) -> bool:
    """True if facing direction and within one tile on the perpendicular axis."""
    x, y = pos
    tx, ty = target
    dx, dy = direction.delta
    if dx != 0:
        if abs(y - ty) > tile_size:
            return False
    else:
        if abs(x - tx) > tile_size:
            return False
    return direction_moves_toward(pos, direction, target)
