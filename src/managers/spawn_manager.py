import random
from typing import List, Tuple

import pygame
from loguru import logger

from src.core.enemy_tank import EnemyTank
from src.core.map import Map
from src.core.player_tank import PlayerTank
from src.managers.texture_manager import TextureManager
from src.utils.constants import GRID_WIDTH


class SpawnManager:
    """Manages enemy tank spawning logic and state."""

    SPAWN_POINTS: List[Tuple[int, int]] = [
        (3, 1),  # Left spawn
        (GRID_WIDTH // 2, 1),  # Center spawn
        (GRID_WIDTH - 4, 1),  # Right spawn
    ]

    def __init__(
        self,
        tile_size: int,
        texture_manager: TextureManager,
        spawn_points: List[Tuple[int, int]],
        max_spawns: int,
        spawn_interval: float,
        player_tank: PlayerTank,
        game_map: Map,
    ) -> None:
        """Initialize the SpawnManager.

        Args:
            tile_size: Size of each tile in pixels.
            texture_manager: TextureManager for loading enemy sprites.
            spawn_points: List of (grid_x, grid_y) spawn locations.
            max_spawns: Maximum number of enemies to spawn in total.
            spawn_interval: Seconds between spawn attempts.
            player_tank: The player tank (for collision checking on initial spawn).
            game_map: The game map (for collision checking on initial spawn).
        """
        self.tile_size = tile_size
        self.texture_manager = texture_manager
        self.spawn_points = spawn_points
        self.max_enemy_spawns = max_spawns
        self.spawn_interval = spawn_interval
        self.enemy_tanks: List[EnemyTank] = []
        self.total_enemy_spawns: int = 0
        self.spawn_timer: float = 0.0
        # Initial spawn
        self.spawn_enemy(player_tank, game_map)

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
            # Always spawn 'basic' type for now
            enemy = EnemyTank(
                x, y, self.tile_size, self.texture_manager, tank_type="basic"
            )
            self.enemy_tanks.append(enemy)
            self.total_enemy_spawns += 1
            logger.debug(
                (
                    f"Spawned enemy {self.total_enemy_spawns}/{self.max_enemy_spawns} "
                    f"at ({x}, {y})"
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

    def reset(self, player_tank: PlayerTank, game_map: Map) -> None:
        """Reset spawn state and perform initial spawn.

        Args:
            player_tank: The player tank (for collision checking on initial spawn).
            game_map: The game map (for collision checking on initial spawn).
        """
        self.enemy_tanks = []
        self.total_enemy_spawns = 0
        self.spawn_timer = 0.0
        self.spawn_enemy(player_tank, game_map)
