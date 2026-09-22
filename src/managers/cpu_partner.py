"""CPU Partner: a PlayerInput that drives P2 from the World View (ADR 0001)."""

import itertools
import math
import random
from collections.abc import Collection
from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import Literal, Protocol

import pygame

from src.core.tile import TileType
from src.managers.pathfinding import Cell, NavGrid, find_path
from src.managers.world_view import EnemyView, PlayerView, PowerUpView, WorldView
from src.utils.constants import (
    BULLET_SIZE,
    CPU_PARTNER_ALIGN_TOLERANCE,
    CPU_PARTNER_AMBUSH_DISTANCE,
    CPU_PARTNER_DECISION_INTERVAL,
    CPU_PARTNER_GOAL_STICKINESS,
    CPU_PARTNER_HESITATION_CHANCE,
    CPU_PARTNER_HESITATION_TIME,
    CPU_PARTNER_POWER_UP_RANGE,
    CPU_PARTNER_REACTION_DELAY,
    CPU_PARTNER_STUCK_TIME,
    CPU_PARTNER_THREAT_RADIUS,
    FPS,
    TANK_ALIGN_THRESHOLD,
    TILE_SIZE,
    Direction,
)

_BULLET_BLOCKING_TILES = frozenset({TileType.BRICK, TileType.STEEL, TileType.BASE})
# Tiles a Player's bullet can't shoot its way through.
_BULLET_PROOF_TILES = frozenset({TileType.STEEL})
_TANK_BLOCKING_TILES = frozenset(
    {TileType.BRICK, TileType.STEEL, TileType.WATER, TileType.BASE}
)

# Identifies a tank in the World View: Enemy and Player ids can overlap.
_TankKey = tuple[Literal["enemy", "player"], int]


class _Placed(Protocol):
    """Anything with a square footprint on the battlefield (pixels)."""

    @property
    def x(self) -> float: ...
    @property
    def y(self) -> float: ...
    @property
    def size(self) -> int: ...


@dataclass(frozen=True)
class _Box:
    """A square footprint that isn't a tank, such as the Base."""

    x: float
    y: float
    size: int


def _center(view: _Placed) -> tuple[float, float]:
    return view.x + view.size / 2, view.y + view.size / 2


def _distance(a: PlayerView | EnemyView, b: PlayerView | EnemyView) -> float:
    """Manhattan distance between two tanks' centers, in pixels."""
    (ax, ay), (bx, by) = _center(a), _center(b)
    return abs(ax - bx) + abs(ay - by)


def _distance_ahead(
    tank: _Placed,
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
    own: PlayerView | EnemyView,
) -> tuple[bool, tuple[float, float], tuple[float, float]]:
    """Where ``own``'s next bullet would fly.

    Returns whether it flies horizontally, its origin (the tank's center) and
    its lane: the span it sweeps across the direction of travel.
    """
    horizontal = own.direction in (Direction.LEFT, Direction.RIGHT)
    origin = _center(own)
    cross = origin[1] if horizontal else origin[0]
    return horizontal, origin, (cross - BULLET_SIZE / 2, cross + BULLET_SIZE / 2)


def is_line_of_fire_safe(
    world: WorldView, own: PlayerView, target: EnemyView | None
) -> bool:
    """Whether ``own`` may fire at ``target`` along its current facing.

    Unsafe when the bullet could hit the Base or a Base Wall cell before a
    solid tile stops it (even beyond the target, since a miss carries on), or
    when a live Human Player stands in the Line of Fire before both the target
    and that solid tile. Half-bricks don't count as solid. With no target
    (shooting a brick out of the way), only the solid tile stops the bullet.
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

    target_at = (
        None if target is None else _distance_ahead(target, origin, facing, lane)
    )
    nearest_stop = min(blocked_at, math.inf if target_at is None else target_at)
    for player in world.players:
        if player.player_id == own.player_id or not player.alive:
            continue
        human_at = _distance_ahead(player, origin, facing, lane)
        if human_at is not None and human_at < nearest_stop:
            return False
    return True


def _lane_is_open(
    world: WorldView, own: PlayerView | EnemyView, target: _Placed
) -> bool:
    """Whether ``own``'s bullet would reach ``target`` through brick at worst."""
    horizontal, origin, lane = _bullet_lane(own)
    target_at = _distance_ahead(target, origin, own.direction, lane)
    if target_at is None:
        return False
    tile_size = world.tile_size
    start = origin[0] if horizontal else origin[1]
    step = _along_step(own.direction, horizontal)
    lane_cells = range(math.floor(lane[0] / tile_size), math.ceil(lane[1] / tile_size))
    height = len(world.tiles)
    width = len(world.tiles[0]) if world.tiles else 0
    row_or_col = math.floor(start / tile_size)
    while 0 <= row_or_col < (width if horizontal else height):
        edge = row_or_col * tile_size if step > 0 else (row_or_col + 1) * tile_size
        if max((edge - start) * step, 0.0) >= target_at:
            return True
        for c in lane_cells:
            x, y = (row_or_col, c) if horizontal else (c, row_or_col)
            if 0 <= x < width and 0 <= y < height:
                if world.tiles[y][x] in _BULLET_PROOF_TILES:
                    return False
        row_or_col += step
    return True


def _cell_of(world: WorldView, view: _Placed) -> Cell:
    """The sub-tile nearest a footprint's top-left corner."""
    return round(view.x / world.tile_size), round(view.y / world.tile_size)


def _covered_cells(world: WorldView, view: _Placed) -> set[Cell]:
    """Every sub-tile a footprint overlaps."""
    size = world.tile_size
    return {
        (x, y)
        for x in range(
            math.floor(view.x / size), math.ceil((view.x + view.size) / size)
        )
        for y in range(
            math.floor(view.y / size), math.ceil((view.y + view.size) / size)
        )
    }


def _firing_positions(world: WorldView, own: PlayerView, target: _Placed) -> set[Cell]:
    """Cells in ``target``'s row or column from which ``own`` could hit it.

    From each, the Line of Fire facing ``target`` is clear or blocked only by
    brick. Cells where ``own`` would overlap ``target`` are left out; cells a
    tank can't stand on are left to the pathfinder to reject.
    """
    tx, ty = _cell_of(world, target)
    size_cells = math.ceil(own.size / world.tile_size)
    height = len(world.tiles)
    width = len(world.tiles[0]) if world.tiles else 0
    positions: set[Cell] = set()
    for away in Direction:
        # Walk outward from the target; once steel cuts the Line of Fire,
        # every cell further out is cut off too.
        dx, dy = away.delta
        for distance in itertools.count(size_cells):
            x, y = tx + dx * distance, ty + dy * distance
            if not (0 <= x < width and 0 <= y < height):
                break
            shooter = replace(
                own,
                x=float(x * world.tile_size),
                y=float(y * world.tile_size),
                direction=away.opposite,
            )
            if not _lane_is_open(world, shooter, target):
                break
            positions.add((x, y))
    return positions


def _spawn_box(world: WorldView, spawn_point: Cell) -> _Box:
    """The footprint an Enemy spawning at ``spawn_point`` takes up."""
    x, y = spawn_point
    return _Box(float(x * world.tile_size), float(y * world.tile_size), TILE_SIZE)


def ambush_positions(world: WorldView, own: PlayerView, spawn_point: Cell) -> set[Cell]:
    """Firing Positions from which ``own`` can wait for Enemies at ``spawn_point``.

    Those at least the ambush distance from it, where ``own`` wouldn't stand
    on any Enemy Spawn Point and so keep Enemies from spawning there.
    """
    size_cells = math.ceil(own.size / world.tile_size)
    spawn_cells = set().union(
        *(_covered_cells(world, _spawn_box(world, s)) for s in world.enemy_spawn_points)
    )
    sx, sy = spawn_point
    return {
        (x, y)
        for x, y in _firing_positions(world, own, _spawn_box(world, spawn_point))
        if abs(x - sx) + abs(y - sy) >= CPU_PARTNER_AMBUSH_DISTANCE
        and not any(
            (x + dx, y + dy) in spawn_cells
            for dx in range(size_cells)
            for dy in range(size_cells)
        )
    }


def _touching_cells(
    world: WorldView, own: PlayerView, power_up: PowerUpView
) -> set[Cell]:
    """Cells from which ``own``'s footprint overlaps ``power_up``, collecting it."""
    size_cells = math.ceil(own.size / world.tile_size)
    return {
        (x - dx, y - dy)
        for x, y in _covered_cells(world, power_up)
        for dx in range(size_cells)
        for dy in range(size_cells)
    }


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


def _base_box(world: WorldView) -> _Box | None:
    """The Base's footprint, or ``None`` when the map has no Base."""
    if not world.base_cells:
        return None
    xs = [x for x, _ in world.base_cells]
    ys = [y for _, y in world.base_cells]
    size = (max(xs) - min(xs) + 1) * world.tile_size
    return _Box(
        float(min(xs) * world.tile_size), float(min(ys) * world.tile_size), size
    )


def _distance_to_base(base: _Box, enemy: EnemyView) -> float:
    """Straight-line px between the centers of ``enemy`` and the Base."""
    (bx, by), (ex, ey) = _center(base), _center(enemy)
    return math.hypot(ex - bx, ey - by)


def _is_base_threat(world: WorldView, base: _Box, enemy: EnemyView) -> bool:
    """Whether ``enemy`` is a Base Threat to ``base``.

    It is when its center is within the threat radius of the Base's center,
    or when, turned to face the Base, its Line of Fire would reach the Base
    clear or through brick. Which way it faces now doesn't matter: an Enemy
    can turn and fire at any moment.
    """
    radius = CPU_PARTNER_THREAT_RADIUS * world.tile_size
    if _distance_to_base(base, enemy) <= radius:
        return True
    return any(
        _lane_is_open(world, replace(enemy, direction=facing), base)
        for facing in Direction
    )


class GoalKind(Enum):
    """What the CPU Partner is trying to do, highest priority first."""

    DEFEND = auto()
    GRAB_POWER_UP = auto()
    HUNT = auto()
    AMBUSH = auto()


@dataclass(frozen=True)
class _Goal:
    kind: GoalKind
    # The target Enemy's id, or the target Power-Up's or Enemy Spawn Point's
    # cell (neither ever moves).
    target: int | Cell


class CpuPartnerInput:
    """Computer-controlled input for the CPU Partner in the P2 slot.

    Reads the World View once per frame in :meth:`observe` and turns it into
    a movement direction and shoot requests, exactly like a human input. Like
    a human it is imperfect: it decides on its Goal only every
    ``decision_interval`` seconds, takes ``reaction_delay`` seconds to act on
    a new Goal or target, and sometimes (``hesitation_chance``) hesitates
    before a shot.
    """

    def __init__(
        self,
        decision_interval: float = CPU_PARTNER_DECISION_INTERVAL,
        reaction_delay: float = CPU_PARTNER_REACTION_DELAY,
        hesitation_chance: float = CPU_PARTNER_HESITATION_CHANCE,
    ) -> None:
        self._decision_frames = max(1, round(decision_interval * FPS))
        self._reaction_frames = round(reaction_delay * FPS)
        self._hesitation_chance = hesitation_chance
        self._movement: tuple[int, int] = (0, 0)
        self._shoot_requested: bool = False
        # The Goal it has decided on, and the one it is acting on: the
        # previous Goal until the reaction delay has passed.
        self._goal: _Goal | None = None
        self._acting_goal: _Goal | None = None
        self._frames_to_react: int = 0
        self._frames_to_decision: int = 0
        # Frames it has preferred another Goal to its current one.
        self._frames_preferring_other: int = 0
        # Whether it wanted to shoot last frame, and the frames it has left
        # to hesitate before shooting.
        self._was_aiming: bool = False
        self._frames_to_hesitate: int = 0
        # Enemies it found it can't reach, with the cell each stood on then;
        # left out of its Goals until they move.
        self._cut_off: dict[int, Cell] = {}
        self._last_position: tuple[float, float] | None = None
        self._stuck_frames: int = 0
        # The direction it keeps trying to move in while stuck.
        self._pushing: tuple[int, int] = (0, 0)
        # Tanks to route around, with the cells they blocked it from, while
        # they still stand on any of those cells.
        self._detour_around: dict[_TankKey, set[Cell]] = {}

    def reset(self) -> None:
        """Forget the current Goal and route (on stage start and respawn)."""
        self._goal = None
        self._acting_goal = None
        self._frames_to_react = 0
        self._frames_to_decision = 0
        self._frames_preferring_other = 0
        self._was_aiming = False
        self._frames_to_hesitate = 0
        self._cut_off = {}
        self._movement = (0, 0)
        self._shoot_requested = False
        self._last_position = None
        self._stuck_frames = 0
        self._pushing = (0, 0)
        self._detour_around = {}

    def handle_event(self, event: pygame.event.Event) -> None:
        """The CPU Partner ignores pygame events."""

    def observe(self, world: WorldView) -> None:
        """Decide this frame's movement and shooting from the World View."""
        self._track_progress(world.own_player)
        self._movement = (0, 0)
        self._shoot_requested = False
        self._act(world)
        self._hesitate()

    def _hesitate(self) -> None:
        """Now and then hold back a shot it has just lined up, for a moment."""
        aiming = self._shoot_requested
        if aiming and not self._was_aiming:
            if random.random() < self._hesitation_chance:
                self._frames_to_hesitate = round(CPU_PARTNER_HESITATION_TIME * FPS)
        self._was_aiming = aiming
        if self._frames_to_hesitate > 0:
            self._frames_to_hesitate -= 1
            self._shoot_requested = False

    def _act(self, world: WorldView) -> None:
        """Set this frame's movement and shoot request for its Goal."""
        own = world.own_player
        if own is None or not own.alive:
            return
        target = self._update_goal(world, own)
        if target is None:
            return
        if isinstance(target, PowerUpView):
            self._follow_path(world, own, _touching_cells(world, own, target), None)
            return
        if isinstance(target, _Box):
            self._ambush(world, own, target)
            return
        ox, oy = _center(own)
        ex, ey = _center(target)
        dx, dy = ex - ox, ey - oy
        vertical = Direction.DOWN if dy > 0 else Direction.UP
        horizontal = Direction.RIGHT if dx > 0 else Direction.LEFT
        facing = None
        if abs(dx) <= CPU_PARTNER_ALIGN_TOLERANCE:
            facing = vertical
        elif abs(dy) <= CPU_PARTNER_ALIGN_TOLERANCE:
            facing = horizontal
        if facing is None or not _lane_is_open(
            world, replace(own, direction=facing), target
        ):
            self._follow_path(world, own, _firing_positions(world, own, target), target)
            return
        if own.direction == facing:
            self._shoot_requested = is_line_of_fire_safe(
                world, own, target
            ) and not can_evade_shot(world, own, target)
        else:
            self._movement = facing.delta

    def _ambush(self, world: WorldView, own: PlayerView, spawn: _Box) -> None:
        """Go to a Firing Position on ``spawn`` and wait there, facing it."""
        spawn_point = _cell_of(world, spawn)
        positions = ambush_positions(world, own, spawn_point)
        cx, cy = _cell_of(world, own)
        if (cx, cy) not in positions:
            self._follow_path(world, own, positions, None)
            return
        sx, sy = spawn_point
        if cx == sx:
            facing = Direction.DOWN if sy > cy else Direction.UP
        else:
            facing = Direction.RIGHT if sx > cx else Direction.LEFT
        if own.direction != facing:
            self._movement = facing.delta

    def _track_progress(self, own: PlayerView | None) -> None:
        """Count the frames it has tried to move without getting anywhere."""
        position = None if own is None else (own.x, own.y)
        if self._movement != (0, 0) and position == self._last_position:
            self._stuck_frames += 1
            self._pushing = self._movement
        else:
            self._stuck_frames = 0
        self._last_position = position

    def _update_detour(
        self, world: WorldView, own: PlayerView, target: EnemyView | None
    ) -> tuple[set[Cell], set[Cell]]:
        """Update which tanks to route around and return their cells.

        Once stuck for long enough, the tanks right ahead of it (Enemies other
        than the ``target``, and the Human Player, to give way rather than push)
        are routed around until they move off the cells where they stood.
        Returns the cells of every tank to route around, and of the Players
        among them.
        """
        tanks: dict[_TankKey, PlayerView | EnemyView] = {
            ("enemy", e.enemy_id): e for e in world.enemies
        } | {
            ("player", p.player_id): p
            for p in world.players
            if p.player_id != own.player_id and p.alive
        }
        if self._stuck_frames >= CPU_PARTNER_STUCK_TIME * FPS:
            self._stuck_frames = 0
            dx, dy = self._pushing
            ahead = _covered_cells(
                world,
                replace(
                    own,
                    x=own.x + dx * world.tile_size,
                    y=own.y + dy * world.tile_size,
                ),
            )
            self._detour_around = {
                key: cells
                for key, t in tanks.items()
                if (target is None or key != ("enemy", target.enemy_id))
                and (cells := _covered_cells(world, t)) & ahead
            }
        still_there = {
            key: cells
            for key, t in tanks.items()
            if key in self._detour_around
            and (cells := _covered_cells(world, t)) & self._detour_around[key]
        }
        self._detour_around = {key: self._detour_around[key] for key in still_there}
        players = [cells for key, cells in still_there.items() if key[0] == "player"]
        return set().union(*still_there.values()), set().union(*players)

    def _follow_path(
        self,
        world: WorldView,
        own: PlayerView,
        goals: set[Cell],
        target: EnemyView | None,
    ) -> None:
        """Take the next step on the cheapest path to one of ``goals``.

        ``target`` is the Enemy the goals are Firing Positions for, if any.
        Shoots a brick that stands in the way once facing it.
        """
        start = _cell_of(world, own)
        blockers, players = self._update_detour(world, own, target)
        grid = self._nav_grid(world, own, blockers)
        path = find_path(grid, start, goals)
        if path is None:
            # No way round the Enemies in its way: push on and hope they move.
            # It never pushes the Human Player, though.
            grid = self._nav_grid(world, own, players)
            path = find_path(grid, start, goals)
        if path is None:
            if players and find_path(self._nav_grid(world, own), start, goals):
                # Only the Human Player is in the way: wait for them to move.
                return
            # Cut off from the target: pick another one next frame.
            if target is not None:
                self._cut_off[target.enemy_id] = _cell_of(world, target)
            if self._goal == self._acting_goal:
                self._goal = None
            self._acting_goal = None
            return
        if len(path) < 2:
            return
        (cx, cy), (nx, ny) = path[0], path[1]
        self._movement = (nx - cx, ny - cy)
        # Too far off the path's grid line (e.g. after sliding on ice) for the
        # steering nudge to line it up: get back on the line before moving on.
        if self._movement[0] == 0:
            off_line = cx * world.tile_size - own.x
            realign = (1 if off_line > 0 else -1, 0)
        else:
            off_line = cy * world.tile_size - own.y
            realign = (0, 1 if off_line > 0 else -1)
        if abs(off_line) > TANK_ALIGN_THRESHOLD:
            self._movement = realign
            return
        if (
            grid.has_brick((nx, ny))
            and own.direction.delta == self._movement
            and is_line_of_fire_safe(world, own, target)
        ):
            self._shoot_requested = True

    def _update_goal(
        self, world: WorldView, own: PlayerView
    ) -> EnemyView | PowerUpView | _Box | None:
        """Settle this frame's Goal and return what it acts on, if anything.

        It decides every decision interval, or at once when it has no Goal
        or its Goal's target is gone. Once it decides on a new Goal, it keeps
        acting on the old one for the reaction delay.
        """
        enemies = {e.enemy_id: e for e in world.enemies}
        self._cut_off = {
            enemy_id: cell
            for enemy_id, cell in self._cut_off.items()
            if enemy_id in enemies and _cell_of(world, enemies[enemy_id]) == cell
        }
        self._frames_to_decision -= 1
        if (
            self._frames_to_decision <= 0
            or self._goal is None
            or self._find_target(world, self._goal) is None
        ):
            self._frames_to_decision = self._decision_frames
            decided = self._decide_goal(world, own)
            if decided != self._goal:
                self._goal = decided
                self._frames_to_react = self._reaction_frames
        if self._frames_to_react > 0:
            self._frames_to_react -= 1
        else:
            self._acting_goal = self._goal
        goal = self._acting_goal
        return None if goal is None else self._find_target(world, goal)

    def _decide_goal(self, world: WorldView, own: PlayerView) -> _Goal | None:
        """The Goal to pursue from now on.

        It keeps its current Goal until another has been preferred for the
        stickiness time, unless the current Goal's target is gone. Ambush,
        just waiting, gives way at once.
        """
        preferred = self._preferred_goal(world, own)
        if (
            self._goal is None
            or self._goal.kind is GoalKind.AMBUSH
            or self._find_target(world, self._goal) is None
            or preferred == self._goal
        ):
            self._frames_preferring_other = 0
            return preferred
        self._frames_preferring_other += self._decision_frames
        if self._frames_preferring_other >= CPU_PARTNER_GOAL_STICKINESS * FPS:
            self._frames_preferring_other = 0
            return preferred
        return self._goal

    @staticmethod
    def _find_target(
        world: WorldView, goal: _Goal
    ) -> EnemyView | PowerUpView | _Box | None:
        """What ``goal`` targets in ``world``, or ``None`` once it's gone."""
        if goal.kind is GoalKind.GRAB_POWER_UP:
            return next(
                (p for p in world.power_ups if _cell_of(world, p) == goal.target),
                None,
            )
        if goal.kind is GoalKind.AMBUSH:
            spawn_point = goal.target
            if (
                not isinstance(spawn_point, tuple)
                or spawn_point not in world.enemy_spawn_points
            ):
                return None
            return _spawn_box(world, spawn_point)
        return next((e for e in world.enemies if e.enemy_id == goal.target), None)

    def _preferred_goal(self, world: WorldView, own: PlayerView) -> _Goal | None:
        """The Goal it would pick right now, highest priority first.

        Defend targets the Base Threat nearest the Base. Grab Power-Up targets
        the Power-Up cheapest to reach, if within range. Hunt keeps its
        current target while it lives, else takes the nearest Enemy. Enemies
        it couldn't reach from where they stand are left out. Ambush keeps
        its current Enemy Spawn Point, else takes the one cheapest to reach.
        """
        enemies = [e for e in world.enemies if e.enemy_id not in self._cut_off]
        base = _base_box(world)
        threats = [e for e in enemies if base and _is_base_threat(world, base, e)]
        if base is not None and threats:
            nearest = min(threats, key=lambda e: _distance_to_base(base, e))
            return _Goal(GoalKind.DEFEND, nearest.enemy_id)
        power_up = self._nearest_power_up(world, own)
        if power_up is not None:
            return _Goal(GoalKind.GRAB_POWER_UP, _cell_of(world, power_up))
        current = self._goal
        if current is not None and current.kind is GoalKind.HUNT:
            if any(e.enemy_id == current.target for e in enemies):
                return current
        target = self._nearest_enemy(world, own, enemies)
        if target is not None:
            return _Goal(GoalKind.HUNT, target.enemy_id)
        if current is not None and current.kind is GoalKind.AMBUSH:
            return current
        spawn_point = self._nearest_spawn_point(world, own)
        return None if spawn_point is None else _Goal(GoalKind.AMBUSH, spawn_point)

    def _nearest_power_up(
        self, world: WorldView, own: PlayerView
    ) -> PowerUpView | None:
        """The Power-Up cheapest to reach by path, if within grabbing range."""
        if not world.power_ups:
            return None
        cells = {
            cell: p
            for p in reversed(world.power_ups)
            for cell in _touching_cells(world, own, p)
        }
        grid = self._nav_grid(world, own)
        path = find_path(grid, _cell_of(world, own), cells)
        if path is None:
            return None
        cost = sum(grid.step_cost(cell) for cell in path[1:])
        return cells[path[-1]] if cost <= CPU_PARTNER_POWER_UP_RANGE else None

    def _nearest_enemy(
        self, world: WorldView, own: PlayerView, enemies: list[EnemyView]
    ) -> EnemyView | None:
        """The one of ``enemies`` cheapest to reach by path.

        If none can be reached, the nearest as the crow flies.
        """
        if not enemies:
            return None
        cells = {_cell_of(world, e): e for e in reversed(enemies)}
        path = find_path(self._nav_grid(world, own), _cell_of(world, own), cells)
        if path is not None:
            return cells[path[-1]]
        return min(enemies, key=lambda e: _distance(own, e))

    def _nearest_spawn_point(self, world: WorldView, own: PlayerView) -> Cell | None:
        """The Enemy Spawn Point cheapest to reach by path, if any can be."""
        path = find_path(
            self._nav_grid(world, own), _cell_of(world, own), world.enemy_spawn_points
        )
        return None if path is None else path[-1]

    @staticmethod
    def _nav_grid(
        world: WorldView, own: PlayerView, avoid: Collection[Cell] = frozenset()
    ) -> NavGrid:
        return NavGrid(world, math.ceil(own.size / world.tile_size), avoid)

    def get_movement_direction(self) -> tuple[int, int]:
        return self._movement

    def consume_shoot(self) -> bool:
        requested = self._shoot_requested
        self._shoot_requested = False
        return requested

    def clear_pending_shoot(self) -> None:
        self._shoot_requested = False
