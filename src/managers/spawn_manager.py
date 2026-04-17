import random
from dataclasses import dataclass
from typing import List, Optional

import pygame
from loguru import logger

from src.core.effect import Effect
from src.core.enemy_tank import EnemyTank
from src.core.map import Map
from src.core.player_tank import PlayerTank
from src.managers.effect_manager import EffectManager
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    Difficulty,
    EffectType,
    POWERUP_CARRIER_INDICES,
    TILE_SIZE,
    TILE_SIZE_HALF,
    TankType,
)


@dataclass
class _PendingSpawn:
    """A spawn waiting for its animation to finish."""

    x: int
    y: int
    tank_type: TankType
    effect: Effect
    rect: pygame.Rect
    is_carrier: bool = False


class SpawnManager:
    """Manages enemy tank spawning logic and state."""

    def __init__(
        self,
        texture_manager: TextureManager,
        game_map: Map,
        enemy_composition: dict[TankType, int],
        spawn_interval: float,
        player_tanks: List[PlayerTank],
        effect_manager: Optional[EffectManager] = None,
        difficulty: Difficulty = Difficulty.NORMAL,
        powerup_carrier_indices: Optional[tuple[int, ...]] = None,
    ) -> None:
        """Initialize the SpawnManager.

        Args:
            texture_manager: TextureManager for loading enemy sprites.
            game_map: The game map (spawn points, dimensions, collision).
            enemy_composition: Dict mapping TankType to enemy counts for this stage.
            spawn_interval: Seconds between spawn attempts.
            player_tanks: Player tanks for collision checking on initial spawn.
            effect_manager: EffectManager for spawn animations (optional).
            difficulty: AI difficulty level for spawned enemies.
            powerup_carrier_indices: Tuple of spawn indices that carry powerups.
                Falls back to POWERUP_CARRIER_INDICES constant when not provided.
        """
        self.tile_size = TILE_SIZE
        self._difficulty = difficulty
        self.texture_manager = texture_manager
        self.spawn_points = game_map.spawn_points
        self._spawn_queue: List[TankType] = self._build_spawn_queue(enemy_composition)
        self.max_enemy_spawns: int = len(self._spawn_queue)
        self.spawn_interval = spawn_interval
        self.map_width_px = game_map.width_px
        self.map_height_px = game_map.height_px
        self.enemy_tanks: List[EnemyTank] = []
        self.total_enemy_spawns: int = 0
        self.spawn_timer: float = 0.0
        self._freeze_timer: float = 0.0
        self._effect_manager = effect_manager
        self._powerup_carrier_indices: tuple[int, ...] = (
            powerup_carrier_indices
            if powerup_carrier_indices is not None
            else POWERUP_CARRIER_INDICES
        )
        self._pending_spawns: List[_PendingSpawn] = []

        # Set class-level base position for AI targeting
        base_tile = game_map.get_base()
        if base_tile is not None:
            EnemyTank.base_position = (
                float(base_tile.rect.centerx),
                float(base_tile.rect.centery),
            )

        # Initial spawn
        self.spawn_enemy(player_tanks, game_map)

    def _build_spawn_queue(
        self, enemy_composition: dict[TankType, int]
    ) -> List[TankType]:
        """Build a shuffled list of enemy types from the composition dict.

        Args:
            enemy_composition: Dict mapping TankType to enemy counts.

        Returns:
            Shuffled list of TankType enum members.
        """
        queue: List[TankType] = [
            tank_type
            for tank_type, count in enemy_composition.items()
            for _ in range(count)
        ]
        random.shuffle(queue)
        return queue

    def _is_spawn_blocked(
        self,
        rect: pygame.Rect,
        player_tanks: List[PlayerTank],
        game_map: Map,
    ) -> bool:
        """Check if a spawn rect overlaps any obstacle."""
        for map_rect in game_map.get_collidable_tiles():
            if rect.colliderect(map_rect):
                return True
        for player_tank in player_tanks:
            if player_tank and rect.colliderect(player_tank.rect):
                return True
        for enemy in self.enemy_tanks:
            if rect.colliderect(enemy.rect):
                return True
        for pending in self._pending_spawns:
            if rect.colliderect(pending.rect):
                return True
        return False

    def spawn_enemy(self, player_tanks: List[PlayerTank], game_map: Map) -> bool:
        """Spawn a new enemy tank at a random spawn point if under the spawn limit.

        If an EffectManager is available, plays a spawn animation first and
        the tank materializes when the animation finishes. Otherwise, the
        tank appears immediately.

        Args:
            player_tanks: List of player tanks (for collision checking).
            game_map: The game map (for collision checking).

        Returns:
            True if a spawn was initiated, False otherwise.
        """
        if self.total_enemy_spawns >= self.max_enemy_spawns:
            logger.trace("Max enemy spawns reached, skipping spawn.")
            return False

        spawn_grid_x, spawn_grid_y = random.choice(self.spawn_points)
        x, y = game_map.grid_to_pixels(spawn_grid_x, spawn_grid_y)

        temp_rect = pygame.Rect(x, y, self.tile_size, self.tile_size)
        if self._is_spawn_blocked(temp_rect, player_tanks, game_map):
            logger.warning(f"Spawn point ({x}, {y}) was blocked.")
            return False

        tank_type = self._spawn_queue.pop()
        self.total_enemy_spawns += 1
        is_carrier = (self.total_enemy_spawns - 1) in self._powerup_carrier_indices

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
                    rect=pygame.Rect(x, y, self.tile_size, self.tile_size),
                    is_carrier=is_carrier,
                )
            )
            logger.debug(
                f"Spawn animation started for enemy "
                f"{self.total_enemy_spawns}/{self.max_enemy_spawns} "
                f"at ({x}, {y}) type={tank_type}"
            )
        else:
            self._materialize_enemy(x, y, tank_type, is_carrier)

        return True

    def _materialize_enemy(
        self, x: int, y: int, tank_type: TankType, is_carrier: bool = False
    ) -> None:
        """Create the actual EnemyTank and add it to the active list."""
        enemy = EnemyTank(
            x,
            y,
            self.tile_size,
            self.texture_manager,
            tank_type=tank_type,
            map_width_px=self.map_width_px,
            map_height_px=self.map_height_px,
            difficulty=self._difficulty,
            is_carrier=is_carrier,
        )
        self.enemy_tanks.append(enemy)
        logger.debug(
            f"Enemy materialized at ({x}, {y}) type={tank_type}"
            f"{' [CARRIER]' if is_carrier else ''}"
        )

    def freeze(self, duration: float) -> None:
        """Freeze enemy AI updates for the given duration (clock power-up)."""
        self._freeze_timer = duration

    @property
    def enemies_frozen(self) -> bool:
        """Whether enemy AI updates are currently suppressed."""
        return self._freeze_timer > 0

    def update(self, dt: float, player_tanks: List[PlayerTank], game_map: Map) -> None:
        """Update spawn timer and attempt to spawn enemies.

        Also checks pending spawns and materializes tanks whose
        spawn animation has finished.

        Args:
            dt: Delta time in seconds.
            player_tanks: List of player tanks (for collision checking).
            game_map: The game map (for collision checking).
        """
        if self._freeze_timer > 0:
            self._freeze_timer -= dt

        # Materialize tanks whose spawn animation is done
        still_pending = []
        for pending in self._pending_spawns:
            if pending.effect.active:
                still_pending.append(pending)
                continue
            self._materialize_enemy(
                pending.x, pending.y, pending.tank_type, pending.is_carrier
            )
        self._pending_spawns = still_pending

        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval:
            logger.trace("Spawn timer triggered.")
            # Reset timer only if spawn was successful
            if self.spawn_enemy(player_tanks, game_map):
                self.spawn_timer = 0

    def remove_enemy(self, enemy: EnemyTank) -> None:
        """Remove a destroyed enemy from the active list."""
        if enemy in self.enemy_tanks:
            self.enemy_tanks.remove(enemy)

    def all_enemies_defeated(self) -> bool:
        """Check if all enemies have been spawned and destroyed."""
        return (
            not self.enemy_tanks
            and not self._pending_spawns
            and self.total_enemy_spawns >= self.max_enemy_spawns
        )
