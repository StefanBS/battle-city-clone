"""Read-only World View snapshot handed to every PlayerInput each frame."""

from __future__ import annotations

import itertools
import math
from collections.abc import Collection, Iterable
from dataclasses import dataclass, replace
from functools import cached_property
from typing import TYPE_CHECKING, Protocol

from src.core.tile import BrickVariant, TileType
from src.utils.constants import (
    BASE_THREAT_RADIUS,
    BULLET_SIZE,
    BULLET_SPEED,
    TANK_SPEED,
    TILE_SIZE,
    Direction,
    OwnerType,
    PowerUpType,
    TankType,
)

if TYPE_CHECKING:
    from src.core.bullet import Bullet
    from src.core.enemy_tank import EnemyTank
    from src.core.map import Map
    from src.core.player_tank import PlayerTank
    from src.core.power_up import PowerUp

Cell = tuple[int, int]


class Placed(Protocol):
    """Anything with a square footprint on the battlefield (pixels)."""

    @property
    def x(self) -> float: ...
    @property
    def y(self) -> float: ...
    @property
    def size(self) -> int: ...


@dataclass(frozen=True)
class Footprint:
    """A square footprint that isn't a tank, such as the Base (pixels)."""

    x: float
    y: float
    size: int


def center(placed: Placed) -> tuple[float, float]:
    """The pixel center of a footprint."""
    return placed.x + placed.size / 2, placed.y + placed.size / 2


@dataclass(frozen=True, kw_only=True)
class LineOfFire:
    """Where a bullet fired from a tank's center flies, and what it meets.

    ``lane`` is the span the bullet sweeps across its direction of travel,
    and ``step`` its direction along it (-1 or 1). ``stopped_at`` is the px
    from ``origin`` to the first solid tile, sure to stop the bullet, or
    ``math.inf`` when none does before the map's edge; a half-brick may leave
    the lane open, so it doesn't count as solid. ``endangers_base`` is whether
    the bullet could hit the Base or a Base Wall cell first, in which case
    ``stopped_at`` is where. ``bullet_proof_at`` is the px to the first tile
    a bullet can't destroy, which no bullet gets past.
    """

    horizontal: bool
    step: int
    origin: tuple[float, float]
    lane: tuple[float, float]
    stopped_at: float
    endangers_base: bool
    bullet_proof_at: float

    def distance_to(self, placed: Placed) -> float | None:
        """Px from the origin to where the bullet would first touch ``placed``.

        ``None`` when ``placed`` is outside the lane or behind the origin.
        """
        along, across = (
            (placed.x, placed.y) if self.horizontal else (placed.y, placed.x)
        )
        if across + placed.size <= self.lane[0] or across >= self.lane[1]:
            return None
        start = self.origin[0] if self.horizontal else self.origin[1]
        # Signed distances to its two edges along the direction of travel.
        edges = sorted(
            ((along - start) * self.step, (along + placed.size - start) * self.step)
        )
        if edges[1] <= 0:
            return None
        return max(edges[0], 0.0)

    def reaches(self, placed: Placed) -> bool:
        """Whether the bullet would reach ``placed``, clear or through brick."""
        distance = self.distance_to(placed)
        return distance is not None and distance <= self.bullet_proof_at

    def is_from_firing_position(self, placed: Placed) -> bool:
        """Whether it reaches ``placed`` and could never hit the Base or wall."""
        return self.reaches(placed) and not self.endangers_base


@dataclass(frozen=True, kw_only=True)
class PlayerView:
    """A Player's tank as seen in the World View (pixel coordinates)."""

    player_id: int
    x: float
    y: float
    direction: Direction
    frozen: bool = False
    shielded: bool = False
    can_fire: bool = True
    size: int = TILE_SIZE
    speed: float = TANK_SPEED
    bullet_speed: float = BULLET_SPEED


@dataclass(frozen=True, kw_only=True)
class EnemyView:
    """An Enemy tank as seen in the World View (pixel coordinates).

    ``enemy_id`` stays the same for as long as that Enemy is alive.
    """

    enemy_id: int
    x: float
    y: float
    direction: Direction
    tank_type: TankType = TankType.BASIC
    size: int = TILE_SIZE
    speed: float = TANK_SPEED


@dataclass(frozen=True, kw_only=True)
class BulletView:
    """An active bullet as seen in the World View (pixel coordinates).

    ``bullet_id`` stays the same for as long as that bullet is in flight.
    """

    bullet_id: int
    x: float
    y: float
    direction: Direction
    owner_type: OwnerType
    size: int = BULLET_SIZE
    speed: float = BULLET_SPEED


@dataclass(frozen=True, kw_only=True)
class PowerUpView:
    """An active Power-Up as seen in the World View (pixel coordinates)."""

    x: float
    y: float
    power_up_type: PowerUpType
    size: int = TILE_SIZE


@dataclass(frozen=True, kw_only=True)
class WorldView:
    """Snapshot of the battlefield: plain data, never live game objects.

    Grid coordinates are ``(x, y)`` sub-tile cells; everything else is pixels.
    ``tiles`` is indexed ``tiles[y][x]``. The ``*_cells`` tile rules are
    copied from each tile's own flags: the cells that stop tanks, those that
    stop bullets, and those a bullet can destroy. ``half_brick_cells`` are
    BRICK cells already shot down to half, which a bullet may slip past.
    ``players`` holds only live Players: one missing from it is dead.
    """

    tile_size: int
    tiles: tuple[tuple[TileType, ...], ...]
    tank_blocking_cells: frozenset[tuple[int, int]] = frozenset()
    bullet_blocking_cells: frozenset[tuple[int, int]] = frozenset()
    destructible_cells: frozenset[tuple[int, int]] = frozenset()
    base_cells: frozenset[tuple[int, int]] = frozenset()
    base_wall_cells: frozenset[tuple[int, int]] = frozenset()
    half_brick_cells: frozenset[tuple[int, int]] = frozenset()
    enemies: tuple[EnemyView, ...] = ()
    enemies_frozen: bool = False
    enemy_spawn_points: tuple[tuple[int, int], ...] = ()
    power_ups: tuple[PowerUpView, ...] = ()
    bullets: tuple[BulletView, ...] = ()
    players: tuple[PlayerView, ...] = ()
    own_player_id: int | None = None

    @property
    def own_player(self) -> PlayerView | None:
        """The Player whose input is reading this view, or None while it's dead."""
        for player in self.players:
            if player.player_id == self.own_player_id:
                return player
        return None

    def for_player(self, player_id: int) -> WorldView:
        """Return the same snapshot with ``player_id`` marked as its own tank."""
        return replace(self, own_player_id=player_id)

    @property
    def _width(self) -> int:
        return len(self.tiles[0]) if self.tiles else 0

    def _on_map(self, cell: Cell) -> bool:
        x, y = cell
        return 0 <= x < self._width and 0 <= y < len(self.tiles)

    def blocks_tanks(self, cell: Cell) -> bool:
        """Whether a tank can't enter ``cell``; off the map counts as a wall."""
        return not self._on_map(cell) or cell in self.tank_blocking_cells

    def cell_of(self, placed: Placed) -> Cell:
        """The sub-tile nearest a footprint's top-left corner."""
        return round(placed.x / self.tile_size), round(placed.y / self.tile_size)

    def covered_cells(self, placed: Placed) -> set[Cell]:
        """Every sub-tile a footprint overlaps."""
        size = self.tile_size
        return {
            (x, y)
            for x in range(
                math.floor(placed.x / size), math.ceil((placed.x + placed.size) / size)
            )
            for y in range(
                math.floor(placed.y / size), math.ceil((placed.y + placed.size) / size)
            )
        }

    def spawn_footprint(self, spawn_point: Cell) -> Footprint:
        """The footprint an Enemy spawning at ``spawn_point`` takes up."""
        x, y = spawn_point
        return Footprint(
            float(x * self.tile_size), float(y * self.tile_size), TILE_SIZE
        )

    @cached_property
    def base_footprint(self) -> Footprint | None:
        """The Base's footprint, or ``None`` when the map has no Base."""
        if not self.base_cells:
            return None
        xs = [x for x, _ in self.base_cells]
        ys = [y for _, y in self.base_cells]
        return Footprint(
            float(min(xs) * self.tile_size),
            float(min(ys) * self.tile_size),
            (max(xs) - min(xs) + 1) * self.tile_size,
        )

    @cached_property
    def base_threats(self) -> tuple[EnemyView, ...]:
        """The Enemies that are Base Threats, nearest the Base first.

        An Enemy is one when its center is within the threat radius of the
        Base's center, or when, turned to face the Base, its Line of Fire
        would reach the Base clear or through brick. Which way it faces now
        doesn't matter: an Enemy can turn and fire at any moment.
        """
        base = self.base_footprint
        if base is None:
            return ()
        bx, by = center(base)

        def distance(enemy: EnemyView) -> float:
            ex, ey = center(enemy)
            return math.hypot(ex - bx, ey - by)

        radius = BASE_THREAT_RADIUS * self.tile_size
        threats = [
            e
            for e in self.enemies
            if distance(e) <= radius
            or any(self.line_of_fire(e, facing).reaches(base) for facing in Direction)
        ]
        return tuple(sorted(threats, key=distance))

    def line_of_fire(self, shooter: Placed, facing: Direction) -> LineOfFire:
        """The Line of Fire of a tank at ``shooter`` facing ``facing``."""
        horizontal = facing in (Direction.LEFT, Direction.RIGHT)
        origin = center(shooter)
        start, cross = origin if horizontal else origin[::-1]
        lane = (cross - BULLET_SIZE / 2, cross + BULLET_SIZE / 2)
        step = facing.delta[0] if horizontal else facing.delta[1]

        tile_size = self.tile_size
        lane_cells = range(
            math.floor(lane[0] / tile_size), math.ceil(lane[1] / tile_size)
        )
        stopped_at: float | None = None
        endangers_base = False
        bullet_proof_at: float | None = None
        row_or_col = math.floor(start / tile_size)
        limit = self._width if horizontal else len(self.tiles)
        while 0 <= row_or_col < limit and (
            stopped_at is None or bullet_proof_at is None
        ):
            edge = row_or_col * tile_size if step > 0 else (row_or_col + 1) * tile_size
            distance = max((edge - start) * step, 0.0)
            cells = (
                (row_or_col, c) if horizontal else (c, row_or_col) for c in lane_cells
            )
            blocking = [c for c in cells if c in self.bullet_blocking_cells]
            if stopped_at is None:
                if any(
                    c in self.base_cells or c in self.base_wall_cells for c in blocking
                ):
                    stopped_at, endangers_base = distance, True
                elif any(c not in self.half_brick_cells for c in blocking):
                    stopped_at = distance
            if bullet_proof_at is None and any(
                c not in self.destructible_cells for c in blocking
            ):
                bullet_proof_at = distance
            row_or_col += step
        return LineOfFire(
            horizontal=horizontal,
            step=step,
            origin=origin,
            lane=lane,
            stopped_at=math.inf if stopped_at is None else stopped_at,
            endangers_base=endangers_base,
            bullet_proof_at=math.inf if bullet_proof_at is None else bullet_proof_at,
        )

    def firing_positions(
        self,
        target: Placed,
        shooter_size: int,
        sides: Collection[Direction] = tuple(Direction),
    ) -> set[Cell]:
        """Cells in ``target``'s row or column from which a tank could hit it.

        A tank ``shooter_size`` px wide standing there and facing ``target``
        has a Line of Fire that reaches it clear or through brick, and could
        never hit the Base or a Base Wall cell. Only cells on ``sides`` of
        ``target`` (the directions from it to them) are taken. Cells where the
        tank would overlap ``target`` are left out; cells a tank can't stand
        on are left to the pathfinder to reject.
        """
        tx, ty = self.cell_of(target)
        size_cells = math.ceil(shooter_size / self.tile_size)
        positions: set[Cell] = set()
        for away in sides:
            # Walk outward from the target; once a tile no bullet gets past
            # cuts the Line of Fire, every cell further out is cut off too.
            dx, dy = away.delta
            for distance in itertools.count(size_cells):
                x, y = tx + dx * distance, ty + dy * distance
                if not self._on_map((x, y)):
                    break
                shooter = Footprint(
                    float(x * self.tile_size), float(y * self.tile_size), shooter_size
                )
                line = self.line_of_fire(shooter, away.opposite)
                if not line.reaches(target):
                    break
                if not line.endangers_base:
                    positions.add((x, y))
        return positions


def build_world_view(
    game_map: Map,
    players: Iterable[PlayerTank],
    enemies: Iterable[EnemyTank],
    enemies_frozen: bool,
    power_ups: Iterable[PowerUp],
    bullets: Iterable[Bullet],
) -> WorldView:
    """Snapshot the live game objects into a WorldView.

    ``players`` must be the live Players only.
    """
    bullets = [b for b in bullets if b.active]
    tiles = tuple(
        tuple(tile.type if tile is not None else TileType.EMPTY for tile in row)
        for row in game_map.tiles
    )
    placed = [tile for row in game_map.tiles for tile in row if tile is not None]
    return WorldView(
        tile_size=game_map.tile_size,
        tiles=tiles,
        tank_blocking_cells=frozenset((t.x, t.y) for t in placed if t.blocks_tanks),
        bullet_blocking_cells=frozenset((t.x, t.y) for t in placed if t.blocks_bullets),
        destructible_cells=frozenset((t.x, t.y) for t in placed if t.is_destructible),
        base_cells=frozenset(
            (t.x, t.y) for t in game_map.get_tiles_by_type([TileType.BASE])
        ),
        base_wall_cells=frozenset(
            (t.x, t.y) for t in game_map.get_base_surrounding_tiles(include_empty=True)
        ),
        half_brick_cells=frozenset(
            (t.x, t.y)
            for t in placed
            if t.type is TileType.BRICK and t.brick_variant is not BrickVariant.FULL
        ),
        enemies=tuple(
            EnemyView(
                enemy_id=e.enemy_id,
                x=e.x,
                y=e.y,
                direction=e.direction,
                tank_type=e.tank_type,
                size=e.width,
                speed=e.speed,
            )
            for e in enemies
        ),
        enemies_frozen=enemies_frozen,
        enemy_spawn_points=tuple(game_map.spawn_points),
        power_ups=tuple(
            PowerUpView(x=p.x, y=p.y, power_up_type=p.power_up_type, size=p.width)
            for p in power_ups
            if p.active
        ),
        bullets=tuple(
            BulletView(
                bullet_id=b.bullet_id,
                x=b.x,
                y=b.y,
                direction=b.direction,
                owner_type=b.owner_type,
                size=b.width,
                speed=b.speed,
            )
            for b in bullets
        ),
        players=tuple(
            PlayerView(
                player_id=p.player_id,
                x=p.x,
                y=p.y,
                direction=p.direction,
                frozen=p.is_frozen,
                shielded=p.is_invincible,
                can_fire=sum(b.owner is p for b in bullets) < p.max_bullets,
                size=p.width,
                speed=p.speed,
                bullet_speed=p.bullet_speed,
            )
            for p in players
        ),
    )
