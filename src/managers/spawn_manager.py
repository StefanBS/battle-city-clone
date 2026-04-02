import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame
from loguru import logger

from src.core.effect import Effect
from src.core.enemy_tank import EnemyTank
from src.core.map import Map
from src.core.player_tank import PlayerTank
from src.managers.effect_manager import EffectManager
from src.managers.texture_manager import TextureManager
from src.utils.constants import EffectType, SUB_TILE_SIZE, TILE_SIZE, TankType
from src.utils.level_data import STAGE_ENEMIES


@dataclass
class _PendingSpawn:
    """A spawn waiting for its animation to finish."""

    x: int
    y: int
    tank_type: TankType
    effect: Effect


class SpawnManager:
    """Manages enemy tank spawning logic and state."""

    def __init__(
        self,
        tile_size: int,
        texture_manager: TextureManager,
        spawn_points: List[Tuple[int, int]],
        stage: int,
        spawn_interval: float,
        player_tank: PlayerTank,
        game_map: Map,
        map_width_px: int,
        map_height_px: int,
        effect_manager: Optional[EffectManager] = None,
    ) -> None:
        """Initialize the SpawnManager.

        Args:
            tile_size: Size of each tile in pixels.
            texture_manager: TextureManager for loading enemy sprites.
            spawn_points: List of (grid_x, grid_y) spawn locations.
            stage: Current stage number (1-35, clamped for higher values).
            spawn_interval: Seconds between spawn attempts.
            player_tank: The player tank (for collision checking on initial spawn).
            game_map: The game map (for collision checking on initial spawn).
            map_width_px: Map width in pixels (passed to spawned enemies).
            map_height_px: Map height in pixels (passed to spawned enemies).
            effect_manager: EffectManager for spawn animations (optional).
        """
        self.tile_size = tile_size
        self.texture_manager = texture_manager
        self.spawn_points = spawn_points
        self._spawn_queue: List[TankType] = self._build_spawn_queue(stage)
        self.max_enemy_spawns: int = len(self._spawn_queue)
        self.spawn_interval = spawn_interval
        self.map_width_px = map_width_px
        self.map_height_px = map_height_px
        self.enemy_tanks: List[EnemyTank] = []
        self.total_enemy_spawns: int = 0
        self.spawn_timer: float = 0.0
        self._effect_manager = effect_manager
        self._pending_spawns: List[_PendingSpawn] = []
        # Initial spawn
        self.spawn_enemy(player_tank, game_map)

    def _build_spawn_queue(self, stage: int) -> List[TankType]:
        """Build a shuffled list of enemy types for the given stage.

        Args:
            stage: Stage number (1-based). Clamped to valid range.

        Returns:
            Shuffled list of TankType enum members.
        """
        index = min(stage - 1, len(STAGE_ENEMIES) - 1)
        basic, fast, power, armor = STAGE_ENEMIES[index]
        queue: List[TankType] = (
            [TankType.BASIC] * basic
            + [TankType.FAST] * fast
            + [TankType.POWER] * power
            + [TankType.ARMOR] * armor
        )
        random.shuffle(queue)
        return queue

    def spawn_enemy(self, player_tank: PlayerTank, game_map: Map) -> bool:
        """Spawn a new enemy tank at a random spawn point if under the spawn limit.

        If an EffectManager is available, plays a spawn animation first and
        the tank materializes when the animation finishes. Otherwise, the
        tank appears immediately.

        Args:
            player_tank: The player tank (for collision checking).
            game_map: The game map (for collision checking).

        Returns:
            True if a spawn was initiated, False otherwise.
        """
        if self.total_enemy_spawns >= self.max_enemy_spawns:
            logger.trace("Max enemy spawns reached, skipping spawn.")
            return False

        # Get a random spawn point (spawn coords are in sub-tile units)
        spawn_grid_x, spawn_grid_y = random.choice(self.spawn_points)
        x: int = spawn_grid_x * SUB_TILE_SIZE
        y: int = spawn_grid_y * SUB_TILE_SIZE

        # Check if the spawn point is clear
        temp_rect = pygame.Rect(x, y, self.tile_size, self.tile_size)
        collision: bool = False
        map_collidables: List[pygame.Rect] = game_map.get_collidable_tiles()
        for map_rect in map_collidables:
            if temp_rect.colliderect(map_rect):
                collision = True
                break

        # Check against player tank
        if not collision and player_tank:
            if temp_rect.colliderect(player_tank.rect):
                logger.debug(f"Spawn point ({x}, {y}) blocked by player tank.")
                collision = True

        if not collision:
            for enemy in self.enemy_tanks:
                if temp_rect.colliderect(enemy.rect):
                    collision = True
                    break

        # Also check against pending spawn locations
        if not collision:
            for pending in self._pending_spawns:
                pending_rect = pygame.Rect(
                    pending.x, pending.y, self.tile_size, self.tile_size
                )
                if temp_rect.colliderect(pending_rect):
                    collision = True
                    break

        if collision:
            logger.warning(f"Spawn point ({x}, {y}) was blocked.")
            return False

        tank_type = self._spawn_queue.pop()
        self.total_enemy_spawns += 1

        if self._effect_manager is not None:
            # Play spawn animation, materialize tank when it finishes
            center_x = float(x + TILE_SIZE // 2)
            center_y = float(y + TILE_SIZE // 2)
            effect = self._effect_manager.spawn(
                EffectType.SPAWN, center_x, center_y
            )
            self._pending_spawns.append(
                _PendingSpawn(x=x, y=y, tank_type=tank_type, effect=effect)
            )
            logger.debug(
                f"Spawn animation started for enemy "
                f"{self.total_enemy_spawns}/{self.max_enemy_spawns} "
                f"at ({x}, {y}) type={tank_type}"
            )
        else:
            self._materialize_enemy(x, y, tank_type)

        return True

    def _materialize_enemy(self, x: int, y: int, tank_type: TankType) -> None:
        """Create the actual EnemyTank and add it to the active list."""
        enemy = EnemyTank(
            x,
            y,
            self.tile_size,
            self.texture_manager,
            tank_type=tank_type,
            map_width_px=self.map_width_px,
            map_height_px=self.map_height_px,
        )
        self.enemy_tanks.append(enemy)
        logger.debug(
            f"Enemy materialized at ({x}, {y}) type={tank_type}"
        )

    def update(self, dt: float, player_tank: PlayerTank, game_map: Map) -> None:
        """Update spawn timer and attempt to spawn enemies.

        Also checks pending spawns and materializes tanks whose
        spawn animation has finished.

        Args:
            dt: Delta time in seconds.
            player_tank: The player tank (for collision checking).
            game_map: The game map (for collision checking).
        """
        # Materialize tanks whose spawn animation is done
        still_pending = []
        for pending in self._pending_spawns:
            if not pending.effect.active:
                self._materialize_enemy(
                    pending.x, pending.y, pending.tank_type
                )
            else:
                still_pending.append(pending)
        self._pending_spawns = still_pending

        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval:
            logger.trace("Spawn timer triggered.")
            # Reset timer only if spawn was successful
            if self.spawn_enemy(player_tank, game_map):
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
