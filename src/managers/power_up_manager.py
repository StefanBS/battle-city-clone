"""Manages power-up spawning, lifecycle, and collection."""

import random
from typing import List, Optional, Tuple

import pygame
from loguru import logger

from src.core.enemy_tank import EnemyTank
from src.core.player_tank import PlayerTank
from src.core.power_up import PowerUp
from src.core.map import Map
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    PowerUpType,
    SHOVEL_DURATION,
    SHOVEL_FLASH_CYCLE,
    SHOVEL_FLASH_INTERVAL,
    SHOVEL_WARNING_DURATION,
    TILE_SIZE,
)
from src.core.tile import BrickVariant, Tile, TileType


class PowerUpManager:
    """Manages active power-ups on the map."""

    def __init__(
        self,
        texture_manager: TextureManager,
        game_map: Map,
    ) -> None:
        self._texture_manager = texture_manager
        self._game_map = game_map
        self.active_power_ups: List[PowerUp] = []
        self.shovel_timer: float = 0.0
        self._shovel_original_tiles: List[Tuple[Tile, TileType]] = []
        self._shovel_flash_timer: float = 0.0
        self._shovel_flash_showing_steel: bool = True

    def spawn_power_up(
        self,
        player_tank: Optional[PlayerTank] = None,
        enemy_tanks: Optional[List[EnemyTank]] = None,
        power_up_type: Optional[PowerUpType] = None,
        position: Optional[tuple[int, int]] = None,
    ) -> None:
        """Spawn a power-up, appending it to the active list.

        If ``position`` is given, spawn there directly without searching.
        Otherwise, find a random walkable position not occupied by any tank.
        """
        if power_up_type is None:
            power_up_type = random.choice(list(PowerUpType))

        if position is not None:
            x, y = position
        else:
            pos = self._find_spawn_position(
                player_tank, enemy_tanks if enemy_tanks is not None else []
            )
            if pos is None:
                logger.warning("No valid position for power-up spawn.")
                return
            x, y = pos

        power_up = PowerUp(x, y, power_up_type, self._texture_manager)
        self.active_power_ups.append(power_up)
        logger.info(f"Power-up spawned: {power_up_type.value} at ({x}, {y})")

    def update(self, dt: float) -> None:
        """Update all active power-ups; remove any that have timed out."""
        any_expired = False
        for pu in self.active_power_ups:
            pu.update(dt)
            if not pu.active:
                any_expired = True
        if any_expired:
            self.active_power_ups = [pu for pu in self.active_power_ups if pu.active]

        self._tick_shovel(dt)

    def apply_shovel(self) -> None:
        """Fortify base walls with steel, restoring destroyed bricks first."""
        if not self._shovel_original_tiles:
            tiles = self._game_map.get_base_surrounding_tiles(include_empty=True)
            for tile in tiles:
                damaged = (
                    tile.type == TileType.EMPTY
                    or tile.brick_variant != BrickVariant.FULL
                )
                if damaged:
                    self._game_map.set_tile_type(tile, TileType.BRICK)
                    tile.brick_variant = BrickVariant.FULL
                    tile.reset_rect()
            # Save originals AFTER restoration so reverted tiles are BRICK, not EMPTY.
            self._shovel_original_tiles = [(t, t.type) for t in tiles]
            for tile in tiles:
                self._game_map.set_tile_type(tile, TileType.STEEL)
            logger.info(
                f"Shovel power-up applied: base fortified for {SHOVEL_DURATION}s"
            )
        self.shovel_timer = SHOVEL_DURATION
        self._shovel_flash_timer = 0.0
        self._shovel_flash_showing_steel = True

    def _tick_shovel(self, dt: float) -> None:
        if self.shovel_timer <= 0:
            return
        self.shovel_timer -= dt
        if self.shovel_timer <= 0:
            for tile, orig_type in self._shovel_original_tiles:
                if tile.type != TileType.EMPTY:
                    self._game_map.set_tile_type(tile, orig_type)
            self._shovel_original_tiles = []
            logger.info("Shovel expired: base walls reverted")
            return
        if self.shovel_timer <= SHOVEL_WARNING_DURATION:
            self._shovel_flash_timer += dt
            should_show_steel = (
                self._shovel_flash_timer % SHOVEL_FLASH_CYCLE < SHOVEL_FLASH_INTERVAL
            )
            if should_show_steel != self._shovel_flash_showing_steel:
                self._shovel_flash_showing_steel = should_show_steel
                for tile, orig_type in self._shovel_original_tiles:
                    if tile.type != TileType.EMPTY:
                        target = TileType.STEEL if should_show_steel else orig_type
                        self._game_map.set_tile_type(tile, target)

    def get_power_ups(self) -> List[PowerUp]:
        """Return the list of active power-ups for collision checking and rendering."""
        return self.active_power_ups

    def collect_power_up(self, power_up: PowerUp) -> Optional[PowerUpType]:
        """Collect a specific power-up. Returns its type, or None if not found."""
        if power_up not in self.active_power_ups:
            return None
        power_up_type = power_up.collect()
        self.active_power_ups.remove(power_up)
        return power_up_type

    def _find_spawn_position(
        self,
        player_tank: Optional[PlayerTank],
        enemy_tanks: List[EnemyTank],
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
                        if tile is not None and tile.type != TileType.EMPTY:
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
