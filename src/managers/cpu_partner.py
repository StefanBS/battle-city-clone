"""CPU Partner: a PlayerInput that drives P2 from the World View (ADR 0001)."""

import itertools
import math

import pygame

from src.core.tile import TileType
from src.managers.world_view import EnemyView, PlayerView, WorldView
from src.utils.constants import BULLET_SIZE, CPU_PARTNER_ALIGN_TOLERANCE, Direction

_BULLET_BLOCKING_TILES = frozenset({TileType.BRICK, TileType.STEEL, TileType.BASE})
_TANK_BLOCKING_TILES = frozenset(
    {TileType.BRICK, TileType.STEEL, TileType.WATER, TileType.BASE}
)


def _center(view: PlayerView | EnemyView) -> tuple[float, float]:
    return view.x + view.size / 2, view.y + view.size / 2


def _distance(a: PlayerView | EnemyView, b: PlayerView | EnemyView) -> float:
    """Manhattan distance between two tanks' centers, in pixels."""
    (ax, ay), (bx, by) = _center(a), _center(b)
    return abs(ax - bx) + abs(ay - by)


def _distance_ahead(
    tank: PlayerView | EnemyView,
    origin: tuple[float, float],
    facing: Direction,
    lane: tuple[float, float],
) -> float | None:
    """Px from ``origin`` to where a bullet in ``lane`` would first touch ``tank``.

    ``None`` when the tank is outside the lane or behind the origin.
    """
    horizontal = facing in (Direction.LEFT, Direction.RIGHT)
    along, across = (tank.x, tank.y) if horizontal else (tank.y, tank.x)
    if across + tank.size <= lane[0] or across >= lane[1]:
        return None
    step = facing.delta[0] if horizontal else facing.delta[1]
    start = origin[0] if horizontal else origin[1]
    # Signed distances to the tank's two edges along the direction of travel.
    edges = sorted(((along - start) * step, (along + tank.size - start) * step))
    if edges[1] <= 0:
        return None
    return max(edges[0], 0.0)


def _along_step(direction: Direction, horizontal: bool) -> int:
    """``direction``'s step along the lane axis: -1, 0 or 1."""
    return direction.delta[0] if horizontal else direction.delta[1]


def _bullet_lane(
    own: PlayerView,
) -> tuple[bool, tuple[float, float], tuple[float, float]]:
    """Where ``own``'s next bullet would fly.

    Returns whether it flies horizontally, its origin (the tank's center) and
    its lane: the span it sweeps across the direction of travel.
    """
    horizontal = own.direction in (Direction.LEFT, Direction.RIGHT)
    origin = _center(own)
    cross = origin[1] if horizontal else origin[0]
    return horizontal, origin, (cross - BULLET_SIZE / 2, cross + BULLET_SIZE / 2)


def is_line_of_fire_safe(world: WorldView, own: PlayerView, target: EnemyView) -> bool:
    """Whether ``own`` may fire at ``target`` along its current facing.

    Unsafe when the bullet could hit the Base or a Base Wall cell before a
    solid tile stops it (even beyond the target, since a miss carries on), or
    when a live Human Player stands in the Line of Fire before both the target
    and that solid tile. Half-bricks don't count as solid.
    """
    facing = own.direction
    horizontal, origin, lane = _bullet_lane(own)
    start = origin[0] if horizontal else origin[1]

    tile_size = world.tile_size
    height = len(world.tiles)
    width = len(world.tiles[0]) if world.tiles else 0
    lane_cells = range(math.floor(lane[0] / tile_size), math.ceil(lane[1] / tile_size))
    step = _along_step(facing, horizontal)
    row_or_col = math.floor(start / tile_size)
    limit = width if horizontal else height

    blocked_at = math.inf
    while 0 <= row_or_col < limit:
        cells = [(row_or_col, c) if horizontal else (c, row_or_col) for c in lane_cells]
        cells = [(x, y) for x, y in cells if 0 <= x < width and 0 <= y < height]
        blocking_cells = [
            cell
            for cell in cells
            if world.tiles[cell[1]][cell[0]] in _BULLET_BLOCKING_TILES
        ]
        if any(
            c in world.base_cells or c in world.base_wall_cells for c in blocking_cells
        ):
            return False
        # A half-brick may leave the lane open, so only a solid tile is sure
        # to stop the bullet.
        if any(c not in world.half_brick_cells for c in blocking_cells):
            edge = row_or_col * tile_size if step > 0 else (row_or_col + 1) * tile_size
            blocked_at = max((edge - start) * step, 0.0)
            break
        row_or_col += step

    target_at = _distance_ahead(target, origin, facing, lane)
    nearest_stop = min(blocked_at, math.inf if target_at is None else target_at)
    for player in world.players:
        if player.player_id == own.player_id or not player.alive:
            continue
        human_at = _distance_ahead(player, origin, facing, lane)
        if human_at is not None and human_at < nearest_stop:
            return False
    return True


def _blocks_tanks(world: WorldView, x: int, y: int) -> bool:
    """Whether a tank can't enter cell ``(x, y)``; off the map counts as a wall."""
    if not (0 <= y < len(world.tiles) and 0 <= x < len(world.tiles[y])):
        return True
    return world.tiles[y][x] in _TANK_BLOCKING_TILES


def can_evade_shot(world: WorldView, own: PlayerView, target: EnemyView) -> bool:
    """Whether ``target`` could slip out of ``own``'s Line of Fire in time.

    Only an Enemy hemmed in by walls on both sides of the Line of Fire is
    judged: it evades if it can drive to a corridor exit wide enough for a
    tank and clear the bullet's lane before the bullet arrives. It drives the
    way it faces, or either way when it faces a wall. On open ground there
    are no exits to judge by, so the shot is taken.
    """
    if world.enemies_frozen or target.speed <= 0:
        return False
    horizontal, origin, lane = _bullet_lane(own)
    gap = _distance_ahead(target, origin, own.direction, lane)
    if gap is None:
        return False

    def blocked(along_cell: int, across_cell: int) -> bool:
        if horizontal:
            return _blocks_tanks(world, along_cell, across_cell)
        return _blocks_tanks(world, across_cell, along_cell)

    # "Along" runs with the bullet; "across" is sideways, out of the lane.
    tile_size = world.tile_size
    along, across = (target.x, target.y) if horizontal else (target.y, target.x)
    first = math.floor(across / tile_size)
    last = math.ceil((across + target.size) / tile_size) - 1
    beside_now = range(
        math.floor(along / tile_size), math.ceil((along + target.size) / tile_size)
    )
    if not all(
        any(blocked(a, side) for a in beside_now) for side in (first - 1, last + 1)
    ):
        return False

    # For each side: how far the target must drive sideways to clear the lane,
    # and the cells beside it that drive takes.
    to_clear_after = lane[1] - across
    to_clear_before = across + target.size - lane[0]
    exits = [
        (
            to_clear_after,
            range(last + 1, last + 1 + math.ceil(to_clear_after / tile_size)),
        ),
        (
            to_clear_before,
            range(first - 1, first - 1 - math.ceil(to_clear_before / tile_size), -1),
        ),
    ]
    corridor = range(first, last + 1)
    size_cells = math.ceil(target.size / tile_size)
    bullet_step = _along_step(own.direction, horizontal)
    target_step = _along_step(target.direction, horizontal)
    for step in [target_step] if target_step else [-1, 1]:
        # The bullet closes the gap more slowly while the target drives away.
        closing = own.bullet_speed - step * bullet_step * target.speed
        if closing <= 0:
            return True
        time_left = gap / closing
        start = round(along / tile_size)
        for k in itertools.count():
            cell = start + k * step
            footprint = range(cell, cell + size_cells)
            travelled = abs(cell * tile_size - along)
            if travelled / target.speed >= time_left or (
                k and any(blocked(a, c) for a in footprint for c in corridor)
            ):
                break
            for sideways, side_cells in exits:
                open_exit = not any(
                    blocked(a, c) for a in footprint for c in side_cells
                )
                if open_exit and (travelled + sideways) / target.speed < time_left:
                    return True
    return False


class CpuPartnerInput:
    """Computer-controlled input for the CPU Partner in the P2 slot.

    Reads the World View once per frame in :meth:`observe` and turns it into
    a movement direction and shoot requests, exactly like a human input.
    """

    def __init__(self) -> None:
        self._movement: tuple[int, int] = (0, 0)
        self._shoot_requested: bool = False
        self._target_id: int | None = None

    def reset(self) -> None:
        """Forget the current target (called on stage start and respawn)."""
        self._target_id = None
        self._movement = (0, 0)
        self._shoot_requested = False

    def handle_event(self, event: pygame.event.Event) -> None:
        """The CPU Partner ignores pygame events."""

    def observe(self, world: WorldView) -> None:
        """Decide this frame's movement and shooting from the World View."""
        self._movement = (0, 0)
        self._shoot_requested = False
        own = world.own_player
        if own is None or not own.alive:
            return
        target = self._pick_target(own, world.enemies)
        if target is None:
            return
        ox, oy = _center(own)
        ex, ey = _center(target)
        dx, dy = ex - ox, ey - oy
        vertical = Direction.DOWN if dy > 0 else Direction.UP
        horizontal = Direction.RIGHT if dx > 0 else Direction.LEFT
        if abs(dx) <= CPU_PARTNER_ALIGN_TOLERANCE:
            facing = vertical
        elif abs(dy) <= CPU_PARTNER_ALIGN_TOLERANCE:
            facing = horizontal
        else:
            # Not lined up: close the shorter gap first to get into the
            # target's row or column.
            self._movement = (horizontal if abs(dx) <= abs(dy) else vertical).delta
            return
        if own.direction == facing:
            self._shoot_requested = is_line_of_fire_safe(
                world, own, target
            ) and not can_evade_shot(world, own, target)
        else:
            self._movement = facing.delta

    def _pick_target(
        self, own: PlayerView, enemies: tuple[EnemyView, ...]
    ) -> EnemyView | None:
        """Hunt: keep the current target while it lives, else take the nearest."""
        for enemy in enemies:
            if enemy.enemy_id == self._target_id:
                return enemy
        if not enemies:
            self._target_id = None
            return None
        target = min(enemies, key=lambda e: _distance(own, e))
        self._target_id = target.enemy_id
        return target

    def get_movement_direction(self) -> tuple[int, int]:
        return self._movement

    def consume_shoot(self) -> bool:
        requested = self._shoot_requested
        self._shoot_requested = False
        return requested

    def clear_pending_shoot(self) -> None:
        self._shoot_requested = False
