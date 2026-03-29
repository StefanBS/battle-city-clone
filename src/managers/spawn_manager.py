import random
from typing import List, Tuple

import pygame
from loguru import logger

from src.core.enemy_tank import EnemyTank
from src.core.map import Map
from src.core.player_tank import PlayerTank
from src.managers.texture_manager import TextureManager
from src.utils.constants import TankType
from src.utils.level_data import STAGE_ENEMIES


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

        Args:
            player_tank: The player tank (for collision checking).
            game_map: The game map (for collision checking).

        Returns:
            True if an enemy was successfully spawned, False otherwise.
        """
        if self.total_enemy_spawns >= self.max_enemy_spawns:
            logger.trace("Max enemy spawns reached, skipping spawn.")
            return False

        # Get a random spawn point
        spawn_grid_x, spawn_grid_y = random.choice(self.spawn_points)
        x: int = spawn_grid_x * self.tile_size
        y: int = spawn_grid_y * self.tile_size

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

        if not collision:
            tank_type = self._spawn_queue.pop()
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
            self.total_enemy_spawns += 1
            logger.debug(
                (
                    f"Spawned enemy {self.total_enemy_spawns}/{self.max_enemy_spawns} "
                    f"at ({x}, {y}) type={tank_type}"
                )
            )
            return True
        else:
            logger.warning(f"Spawn point ({x}, {y}) was blocked.")
            return False

    def update(self, dt: float, player_tank: PlayerTank, game_map: Map) -> None:
        """Update spawn timer and attempt to spawn enemies.

        Args:
            dt: Delta time in seconds.
            player_tank: The player tank (for collision checking).
            game_map: The game map (for collision checking).
        """
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
            and self.total_enemy_spawns >= self.max_enemy_spawns
        )

