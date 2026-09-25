import random
from collections.abc import Sequence
from dataclasses import dataclass

import pygame
from loguru import logger

from src.core.effect import Effect
from src.core.enemy_tank import EnemyTank
from src.core.map import Map
from src.core.tank import Tank
from src.managers.effect_manager import EffectManager
from src.managers.footprint import (
    Cell,
    Footprint,
    blocks_spawn_point,
    spawn_point_footprint,
)
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    EffectType,
    POWERUP_CARRIER_INDICES,
    TILE_SIZE,
    TILE_SIZE_HALF,
    TankType,
)


@dataclass
class _PendingSpawn:
    """A spawn waiting for its animation to finish.

    With no animation (``effect`` is None) it is ready at the next update.
    """

    x: int
    y: int
    tank_type: TankType
    effect: Effect | None
    rect: pygame.Rect
    is_carrier: bool = False

    @property
    def ready(self) -> bool:
        """Whether the Enemy can materialize: its animation is done."""
        return self.effect is None or not self.effect.active


class SpawnManager:
    """Sends the Stage's Roster onto the battlefield, one Enemy at a time.

    Owns the spawn queue, spawn timer, spawn animations and Carrier indices.
    The Enemies it materializes are handed back from ``update``; it does not
    keep them.
    """

    def __init__(
        self,
        texture_manager: TextureManager,
        game_map: Map,
        enemy_composition: dict[TankType, int],
        spawn_interval: float,
        tanks: Sequence[Tank],
        effect_manager: EffectManager | None = None,
        powerup_carrier_indices: tuple[int, ...] | None = None,
    ) -> None:
        """Initialize the SpawnManager.

        Args:
            texture_manager: TextureManager for loading enemy sprites.
            game_map: The game map (spawn points, dimensions, collision).
            enemy_composition: Dict mapping TankType to enemy counts for this stage.
            spawn_interval: Seconds between spawn attempts.
            tanks: Every tank on the battlefield, which blocks the initial spawn.
            effect_manager: EffectManager for spawn animations (optional).
            powerup_carrier_indices: Tuple of spawn indices that carry powerups.
                Falls back to POWERUP_CARRIER_INDICES constant when not provided.
        """
        self.tile_size = TILE_SIZE
        self.texture_manager = texture_manager
        self.spawn_points = game_map.spawn_points
        self._spawn_queue: list[TankType] = self._build_spawn_queue(enemy_composition)
        self.max_enemy_spawns: int = len(self._spawn_queue)
        self.spawn_interval = spawn_interval
        self.map_width_px = game_map.width_px
        self.map_height_px = game_map.height_px
        self.total_enemy_spawns: int = 0
        self.spawn_timer: float = 0.0
        self._effect_manager = effect_manager
        self._powerup_carrier_indices: tuple[int, ...] = (
            powerup_carrier_indices
            if powerup_carrier_indices is not None
            else POWERUP_CARRIER_INDICES
        )
        self._pending_spawns: list[_PendingSpawn] = []

        # Initial spawn
        self.spawn_enemy(tanks, game_map)

    def _build_spawn_queue(
        self, enemy_composition: dict[TankType, int]
    ) -> list[TankType]:
        """Build a shuffled list of enemy types from the composition dict.

        Args:
            enemy_composition: Dict mapping TankType to enemy counts.

        Returns:
            Shuffled list of TankType enum members.
        """
        queue: list[TankType] = [
            tank_type
            for tank_type, count in enemy_composition.items()
            for _ in range(count)
        ]
        random.shuffle(queue)
        return queue

    @staticmethod
    def _spawn_rect(spawn_point: Cell, game_map: Map) -> pygame.Rect:
        """The square an Enemy spawning at ``spawn_point`` takes up."""
        spawn = spawn_point_footprint(spawn_point, game_map.tile_size)
        return pygame.Rect(spawn.x, spawn.y, spawn.size, spawn.size)

    def _is_spawn_blocked(
        self,
        spawn_point: Cell,
        tanks: Sequence[Tank],
        game_map: Map,
    ) -> bool:
        """Check if a tile, a tank or a pending spawn blocks the spawn point."""
        rect = self._spawn_rect(spawn_point, game_map)
        for map_rect in game_map.get_collidable_tiles():
            if rect.colliderect(map_rect):
                return True
        for tank in tanks:
            footprint = Footprint(tank.rect.x, tank.rect.y, tank.rect.width)
            if blocks_spawn_point(footprint, spawn_point, game_map.tile_size):
                return True
        for pending in self._pending_spawns:
            if rect.colliderect(pending.rect):
                return True
        return False

    def spawn_enemy(self, tanks: Sequence[Tank], game_map: Map) -> bool:
        """Start spawning the next Enemy at a random spawn point, if any remain.

        If an EffectManager is available, plays a spawn animation first and
        the tank materializes when the animation finishes. Otherwise, it
        materializes at the next ``update``.

        Args:
            tanks: Every tank on the battlefield (for collision checking).
            game_map: The game map (for collision checking).

        Returns:
            True if a spawn was initiated, False otherwise.
        """
        if self.total_enemy_spawns >= self.max_enemy_spawns:
            logger.trace("Max enemy spawns reached, skipping spawn.")
            return False

        spawn_point = random.choice(self.spawn_points)
        rect = self._spawn_rect(spawn_point, game_map)
        x, y = rect.topleft
        if self._is_spawn_blocked(spawn_point, tanks, game_map):
            logger.warning(f"Spawn point ({x}, {y}) was blocked.")
            return False

        tank_type = self._spawn_queue.pop()
        self.total_enemy_spawns += 1
        is_carrier = (self.total_enemy_spawns - 1) in self._powerup_carrier_indices

        effect = None
        if self._effect_manager is not None:
            # Play spawn animation, materialize tank when it finishes
            center_x = float(x + TILE_SIZE_HALF)
            center_y = float(y + TILE_SIZE_HALF)
            effect = self._effect_manager.spawn(EffectType.SPAWN, center_x, center_y)
        self._pending_spawns.append(
            _PendingSpawn(
                x=x,
                y=y,
                tank_type=tank_type,
                effect=effect,
                rect=rect,
                is_carrier=is_carrier,
            )
        )
        logger.debug(
            f"Spawn started for enemy "
            f"{self.total_enemy_spawns}/{self.max_enemy_spawns} "
            f"at ({x}, {y}) type={tank_type}"
        )
        return True

    def _materialize_enemy(self, pending: _PendingSpawn) -> EnemyTank:
        """Create the EnemyTank for a spawn whose animation is done."""
        enemy = EnemyTank(
            pending.x,
            pending.y,
            self.tile_size,
            self.texture_manager,
            tank_type=pending.tank_type,
            map_width_px=self.map_width_px,
            map_height_px=self.map_height_px,
            is_carrier=pending.is_carrier,
        )
        logger.debug(
            f"Enemy materialized at ({pending.x}, {pending.y}) "
            f"type={pending.tank_type}{' [CARRIER]' if pending.is_carrier else ''}"
        )
        return enemy

    def update(
        self, dt: float, tanks: Sequence[Tank], game_map: Map
    ) -> list[EnemyTank]:
        """Materialize finished spawns, then advance the spawn timer.

        Args:
            dt: Delta time in seconds.
            tanks: Every tank on the battlefield (for collision checking).
            game_map: The game map (for collision checking).

        Returns:
            The Enemies that materialized this frame, for the caller to put
            on the battlefield.
        """
        materialized = [
            self._materialize_enemy(p) for p in self._pending_spawns if p.ready
        ]
        self._pending_spawns = [p for p in self._pending_spawns if not p.ready]

        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval:
            logger.trace("Spawn timer triggered.")
            # Reset timer only if spawn was successful. Enemies that just
            # materialized aren't among ``tanks`` yet but still block.
            if self.spawn_enemy([*tanks, *materialized], game_map):
                self.spawn_timer = 0
        return materialized

    @property
    def is_exhausted(self) -> bool:
        """Whether the whole Roster has materialized: nothing left to spawn."""
        return (
            not self._pending_spawns
            and self.total_enemy_spawns >= self.max_enemy_spawns
        )
