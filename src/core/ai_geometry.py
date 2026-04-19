"""Pure geometry helpers shared by tank AI implementations."""

from src.utils.constants import Direction


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
