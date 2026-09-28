"""Manages power-up spawning, lifecycle, and collection."""

from __future__ import annotations

import random
from collections.abc import Sequence

import pygame
from loguru import logger

from src.core.player_tank import PlayerTank
from src.core.power_up import PowerUp
from src.core.map import Map
from src.core.tank import Tank
from src.core.sprite_atlas import SpriteAtlas
from src.utils.constants import (
    HELMET_INVINCIBILITY_DURATION,
    PowerUpType,
    TILE_SIZE,
)
from src.core.tile import TileType

from src.battle.outcomes import (
    BaseWallFortified,
    ClockStarted,
    BattleOutcome,
    GrenadeDetonated,
)


class PowerUpManager:
    """Manages active power-ups on the map."""

    def __init__(
        self,
        atlas: SpriteAtlas,
        game_map: Map,
    ) -> None:
        self._atlas = atlas
        self._game_map = game_map
        self.active_power_ups: list[PowerUp] = []

    def spawn_power_up(
        self,
        tanks: Sequence[Tank] = (),
        power_up_type: PowerUpType | None = None,
        position: tuple[int, int] | None = None,
    ) -> None:
        """Spawn a power-up, replacing any power-up already on the battlefield.

        If ``position`` is given, spawn there directly without searching.
        Otherwise, find a random walkable position not occupied by any of
        ``tanks``.
        """
        if power_up_type is None:
            power_up_type = random.choice(list(PowerUpType))

        if position is not None:
            x, y = position
        else:
            pos = self._find_spawn_position(tanks)
            if pos is None:
                logger.warning("No valid position for power-up spawn.")
                return
            x, y = pos

        power_up = PowerUp(x, y, power_up_type, self._atlas)
        self.active_power_ups = [power_up]
        logger.info(f"Power-up spawned: {power_up_type} at ({x}, {y})")

    def clear(self) -> None:
        """Remove the power-up on the battlefield, if any."""
        self.active_power_ups = []

    def update(self, dt: float) -> None:
        """Update all active power-ups; remove any that have timed out."""
        for power_up in self.active_power_ups:
            power_up.update(dt)
        self.active_power_ups = [p for p in self.active_power_ups if p.active]

    def apply(
        self, power_up_type: PowerUpType, player: PlayerTank
    ) -> list[BattleOutcome]:
        """Give the collecting Player a Power-Up's effect.

        Changes nothing but the Player. An effect on the whole battlefield
        comes back as an outcome for the Battle to apply.

        Args:
            power_up_type: The collected power-up type.
            player: The collecting Player.

        Returns:
            ``GrenadeDetonated`` for a Grenade, ``ClockStarted`` for a Clock,
            ``BaseWallFortified`` for a Shovel, otherwise nothing.
        """
        outcomes: list[BattleOutcome] = []
        match power_up_type:
            case PowerUpType.HELMET:
                player.activate_invincibility(HELMET_INVINCIBILITY_DURATION)
            case PowerUpType.EXTRA_LIFE:
                player.gain_life()
            case PowerUpType.GRENADE:
                outcomes = [GrenadeDetonated()]
            case PowerUpType.CLOCK:
                outcomes = [ClockStarted()]
            case PowerUpType.SHOVEL:
                outcomes = [BaseWallFortified()]
            case PowerUpType.STAR:
                player.apply_star()
            case _:
                logger.warning(f"Unhandled power-up type: {power_up_type}")
                return outcomes
        logger.info(f"Power-up applied: {power_up_type}")
        return outcomes

    def collect_power_up(self, power_up: PowerUp) -> PowerUpType | None:
        """Collect a specific power-up. Returns its type, or None if not found."""
        if power_up not in self.active_power_ups:
            return None
        power_up_type = power_up.collect()
        self.active_power_ups.remove(power_up)
        return power_up_type

    def _find_spawn_position(self, tanks: Sequence[Tank]) -> tuple[int, int] | None:
        """Find a random walkable tile position not occupied by any tank."""
        walkable = []
        grid = self._game_map.tiles

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
                    walkable.append(self._game_map.grid_to_pixels(col, row))

        if not walkable:
            return None

        # Filter out positions occupied by tanks
        occupied_rects = [t.rect for t in tanks]

        available = []
        for px, py in walkable:
            spawn_rect = pygame.Rect(px, py, TILE_SIZE, TILE_SIZE)
            if not any(spawn_rect.colliderect(r) for r in occupied_rects):
                available.append((px, py))

        if not available:
            return None

        return random.choice(available)
