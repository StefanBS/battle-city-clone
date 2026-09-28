import random
from collections.abc import Sequence
from dataclasses import dataclass

import pygame
from loguru import logger

from src.core.effect import Effect
from src.core.enemy_tank import EnemyTank
from src.core.map import Map
from src.core.sprite_atlas import SpriteAtlas
from src.core.tank import Tank
from src.battle.effect_manager import EffectManager
from src.world_view.footprint import (
    Cell,
    Footprint,
    blocks_spawn_point,
    spawn_point_footprint,
)
from src.utils.constants import (
    EffectType,
    POWERUP_CARRIER_INDICES,
    TILE_SIZE,
    TILE_SIZE_HALF,
    TankType,
)


@dataclass
class _Spawning:
    """A Spawning Enemy: drawn from the Roster, its animation still playing.

    With no animation (``effect`` is None) it is ready at once.
    """

    x: int
    y: int
    tank_type: TankType
    effect: Effect | None
    rect: pygame.Rect
    is_carrier: bool = False

    @property
    def ready(self) -> bool:
        """Whether the Enemy can Appear: its animation is done."""
        return self.effect is None or not self.effect.active


class SpawnManager:
    """Sends the Stage's Roster onto the battlefield, one Enemy at a time.

    Owns the Roster still to come, the spawn timer, the Spawning Enemies and
    the Carrier indices. Building it starts no spawn: the caller starts the
    first with ``start_spawning``, and ``advance`` starts the rest. Enemies
    that Appear are handed over by ``take_appeared``; it does not keep them.
    """

    def __init__(
        self,
        atlas: SpriteAtlas,
        game_map: Map,
        enemy_composition: dict[TankType, int],
        spawn_interval: float,
        effect_manager: EffectManager | None = None,
        powerup_carrier_indices: tuple[int, ...] | None = None,
    ) -> None:
        """Initialize the SpawnManager.

        Args:
            atlas: Where the Enemies get their sprites.
            game_map: The game map (spawn points, dimensions, collision).
            enemy_composition: The Stage's Roster: how many Enemies of each type.
            spawn_interval: Seconds between one Enemy starting to Spawn and
                the next.
            effect_manager: EffectManager for spawn animations (optional).
            powerup_carrier_indices: Which Enemies, by draw order, are Carriers.
                Falls back to POWERUP_CARRIER_INDICES constant when not provided.
        """
        self._atlas = atlas
        self._map = game_map
        self._roster: list[TankType] = self._shuffled_roster(enemy_composition)
        self._roster_size: int = len(self._roster)
        self._spawn_interval = spawn_interval
        self._spawn_timer: float = 0.0
        self._effect_manager = effect_manager
        self._powerup_carrier_indices: tuple[int, ...] = (
            powerup_carrier_indices
            if powerup_carrier_indices is not None
            else POWERUP_CARRIER_INDICES
        )
        self._spawning: list[_Spawning] = []

    @staticmethod
    def _shuffled_roster(enemy_composition: dict[TankType, int]) -> list[TankType]:
        """The Roster as a list of Enemy types, in random order."""
        roster: list[TankType] = [
            tank_type
            for tank_type, count in enemy_composition.items()
            for _ in range(count)
        ]
        random.shuffle(roster)
        return roster

    @property
    def is_exhausted(self) -> bool:
        """Whether the whole Roster has Appeared: nothing left to spawn."""
        return not self._roster and not self._spawning

    def _spawn_rect(self, spawn_point: Cell) -> pygame.Rect:
        """The square an Enemy spawning at ``spawn_point`` takes up."""
        spawn = spawn_point_footprint(spawn_point, self._map.tile_size)
        return pygame.Rect(spawn.x, spawn.y, spawn.size, spawn.size)

    def _is_spawn_blocked(self, spawn_point: Cell, tanks: Sequence[Tank]) -> bool:
        """Check if a tile, a tank or a Spawning Enemy blocks the spawn point."""
        rect = self._spawn_rect(spawn_point)
        for map_rect in self._map.get_collidable_tiles():
            if rect.colliderect(map_rect):
                return True
        for tank in tanks:
            footprint = Footprint(tank.rect.x, tank.rect.y, tank.rect.width)
            if blocks_spawn_point(footprint, spawn_point, self._map.tile_size):
                return True
        for spawning in self._spawning:
            if rect.colliderect(spawning.rect):
                return True
        return False

    def start_spawning(self, tanks: Sequence[Tank]) -> bool:
        """Start the next Enemy of the Roster Spawning at a random spawn point.

        With an EffectManager it plays a spawn animation and Appears when the
        animation ends; without one it Appears at the next ``take_appeared``.

        Args:
            tanks: Every tank on the battlefield, which blocks spawn points.

        Returns:
            True if an Enemy started Spawning; False if the Roster is used up
            or the chosen spawn point is blocked.
        """
        if not self._roster:
            logger.trace("Roster used up, skipping spawn.")
            return False

        spawn_point = random.choice(self._map.spawn_points)
        if self._is_spawn_blocked(spawn_point, tanks):
            logger.warning(f"Spawn point {spawn_point} was blocked.")
            return False
        rect = self._spawn_rect(spawn_point)
        x, y = rect.topleft

        tank_type = self._roster.pop()
        draw_index = self._roster_size - len(self._roster) - 1
        is_carrier = draw_index in self._powerup_carrier_indices

        effect = None
        if self._effect_manager is not None:
            center_x = float(x + TILE_SIZE_HALF)
            center_y = float(y + TILE_SIZE_HALF)
            effect = self._effect_manager.spawn(EffectType.SPAWN, center_x, center_y)
        self._spawning.append(
            _Spawning(
                x=x,
                y=y,
                tank_type=tank_type,
                effect=effect,
                rect=rect,
                is_carrier=is_carrier,
            )
        )
        logger.debug(
            f"Enemy {draw_index + 1}/{self._roster_size} started Spawning "
            f"at ({x}, {y}) type={tank_type}"
        )
        return True

    def _appear(self, spawning: _Spawning) -> EnemyTank:
        """Create the EnemyTank for a Spawning Enemy whose animation is done."""
        enemy = EnemyTank(
            spawning.x,
            spawning.y,
            TILE_SIZE,
            self._atlas,
            tank_type=spawning.tank_type,
            map_width_px=self._map.width_px,
            map_height_px=self._map.height_px,
            is_carrier=spawning.is_carrier,
        )
        logger.debug(
            f"Enemy appeared at ({spawning.x}, {spawning.y}) "
            f"type={spawning.tank_type}{' [CARRIER]' if spawning.is_carrier else ''}"
        )
        return enemy

    def take_appeared(self) -> list[EnemyTank]:
        """Hand over the Spawning Enemies whose animation has ended.

        Returns:
            The Enemies that Appeared since the last call, for the caller to
            put on the battlefield. Each is handed over once.
        """
        appeared = [self._appear(s) for s in self._spawning if s.ready]
        self._spawning = [s for s in self._spawning if not s.ready]
        return appeared

    def advance(self, dt: float, tanks: Sequence[Tank]) -> None:
        """Run the spawn timer; start the next Enemy Spawning when it is due.

        A blocked spawn point keeps the timer due, so it tries again on the
        next advance.

        Args:
            dt: Delta time in seconds.
            tanks: Every tank on the battlefield, which blocks spawn points.
        """
        self._spawn_timer += dt
        if self._spawn_timer >= self._spawn_interval:
            logger.trace("Spawn timer triggered.")
            if self.start_spawning(tanks):
                self._spawn_timer = 0.0
