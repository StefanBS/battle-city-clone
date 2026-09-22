"""Read-only World View snapshot handed to every PlayerInput each frame."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from src.core.tile import BrickVariant, TileType
from src.utils.constants import (
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


@dataclass(frozen=True, kw_only=True)
class PlayerView:
    """A Player's tank as seen in the World View (pixel coordinates)."""

    player_id: int
    x: float
    y: float
    direction: Direction
    alive: bool = True
    frozen: bool = False
    size: int = TILE_SIZE
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
    """An active bullet as seen in the World View (pixel coordinates)."""

    x: float
    y: float
    direction: Direction
    owner_type: OwnerType


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
    ``tiles`` is indexed ``tiles[y][x]``. ``half_brick_cells`` are BRICK
    cells already shot down to half, which a bullet may slip past.
    """

    tile_size: int
    tiles: tuple[tuple[TileType, ...], ...]
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
        """The Player whose input is reading this view, if any."""
        for player in self.players:
            if player.player_id == self.own_player_id:
                return player
        return None

    def for_player(self, player_id: int) -> WorldView:
        """Return the same snapshot with ``player_id`` marked as its own tank."""
        return replace(self, own_player_id=player_id)


def build_world_view(
    game_map: Map,
    players: Iterable[PlayerTank],
    enemies: Iterable[EnemyTank],
    enemies_frozen: bool,
    power_ups: Iterable[PowerUp],
    bullets: Iterable[Bullet],
) -> WorldView:
    """Snapshot the live game objects into a WorldView."""
    tiles = tuple(
        tuple(tile.type if tile is not None else TileType.EMPTY for tile in row)
        for row in game_map.tiles
    )
    return WorldView(
        tile_size=game_map.tile_size,
        tiles=tiles,
        base_cells=frozenset(
            (t.x, t.y) for t in game_map.get_tiles_by_type([TileType.BASE])
        ),
        base_wall_cells=frozenset(
            (t.x, t.y) for t in game_map.get_base_surrounding_tiles(include_empty=True)
        ),
        half_brick_cells=frozenset(
            (tile.x, tile.y)
            for row in game_map.tiles
            for tile in row
            if tile is not None
            and tile.type is TileType.BRICK
            and tile.brick_variant is not BrickVariant.FULL
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
            BulletView(x=b.x, y=b.y, direction=b.direction, owner_type=b.owner_type)
            for b in bullets
            if b.active
        ),
        players=tuple(
            PlayerView(
                player_id=p.player_id,
                x=p.x,
                y=p.y,
                direction=p.direction,
                alive=p.health > 0,
                frozen=p.is_frozen,
                size=p.width,
                bullet_speed=p.bullet_speed,
            )
            for p in players
        ),
    )
