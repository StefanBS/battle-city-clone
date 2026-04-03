"""Manages power-up spawning, lifecycle, and collection."""

import random
from typing import List, Optional

import pygame
from loguru import logger

from src.core.power_up import PowerUp
from src.managers.texture_manager import TextureManager
from src.utils.constants import PowerUpType, TILE_SIZE


class PowerUpManager:
    """Manages the active power-up on the map."""

    def __init__(
        self,
        texture_manager: TextureManager,
        game_map,
    ) -> None:
        self._texture_manager = texture_manager
        self._game_map = game_map
        self.active_power_up: Optional[PowerUp] = None

    def spawn_power_up(
        self,
        player_tank,
        enemy_tanks: List,
        power_up_type: Optional[PowerUpType] = None,
    ) -> None:
        """Spawn a power-up at a random walkable position."""
        if self.active_power_up is not None:
            return

        if power_up_type is None:
            power_up_type = random.choice(list(PowerUpType))

        position = self._find_spawn_position(player_tank, enemy_tanks)
        if position is None:
            logger.warning("No valid position for power-up spawn.")
            return

        x, y = position
        self.active_power_up = PowerUp(
            x, y, power_up_type, self._texture_manager
        )
        logger.info(f"Power-up spawned: {power_up_type.value} at ({x}, {y})")

    def update(self, dt: float) -> None:
        """Update the active power-up; clear if timed out."""
        if self.active_power_up is not None:
            self.active_power_up.update(dt)
            if not self.active_power_up.active:
                logger.debug("Power-up timed out.")
                self.active_power_up = None

    def get_power_up(self) -> Optional[PowerUp]:
        """Return the active power-up for collision checking and rendering."""
        return self.active_power_up

    def collect_power_up(self) -> Optional[PowerUpType]:
        """Collect the active power-up. Returns its type, or None."""
        if self.active_power_up is None:
            return None
        power_up_type = self.active_power_up.collect()
        self.active_power_up = None
        return power_up_type

    def _find_spawn_position(
        self, player_tank, enemy_tanks: List
    ) -> Optional[tuple[int, int]]:
        """Find a random walkable tile position not occupied by any tank."""
        walkable = []
        grid = self._game_map.tiles
        tile_size = self._game_map.tile_size  # sub-tile size (16px)

        # Iterate in steps of 2 sub-tiles (= 1 TILE_SIZE = 32px)
        for row in range(0, len(grid), 2):
            for col in range(0, len(grid[0]), 2):
                all_empty = True
                for dr in range(2):
                    for dc in range(2):
                        r, c = row + dr, col + dc
                        if r >= len(grid) or c >= len(grid[0]):
                            all_empty = False
                            break
                        tile = grid[r][c]
                        if tile is not None and tile.type.name != "EMPTY":
                            all_empty = False
                            break
                    if not all_empty:
                        break
                if all_empty:
                    px = col * tile_size
                    py = row * tile_size
                    walkable.append((px, py))

        if not walkable:
            return None

        # Filter out positions occupied by tanks
        occupied_rects = [player_tank.rect] if player_tank else []
        occupied_rects.extend(t.rect for t in enemy_tanks)

        available = []
        for px, py in walkable:
            spawn_rect = pygame.Rect(px, py, TILE_SIZE, TILE_SIZE)
            if not any(spawn_rect.colliderect(r) for r in occupied_rects):
                available.append((px, py))

        if not available:
            return None

        return random.choice(available)
