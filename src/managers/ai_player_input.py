"""AI implementation of the PlayerInput protocol for the AI co-op teammate."""

from __future__ import annotations

import json
from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame

from src.utils.constants import TILE_SIZE, Direction

if TYPE_CHECKING:
    from src.core.enemy_tank import EnemyTank
    from src.core.player_tank import PlayerTank


_AI_TEAMMATE_CONFIG_PATH = "assets/config/ai_teammate.json"
_ai_teammate_config: dict | None = None


def _get_ai_teammate_config() -> dict:
    global _ai_teammate_config
    if _ai_teammate_config is None:
        from src.utils.paths import resource_path

        with open(resource_path(_AI_TEAMMATE_CONFIG_PATH)) as f:
            _ai_teammate_config = json.load(f)
    return _ai_teammate_config


def _reset_ai_teammate_config() -> None:
    global _ai_teammate_config
    _ai_teammate_config = None


class AIRole(Enum):
    HUNTER = auto()
    DEFENDER = auto()


class AIPlayerInput:
    """PlayerInput implementation that steers a PlayerTank via a role-aware AI."""

    def __init__(self, tank: PlayerTank) -> None:
        cfg = _get_ai_teammate_config()
        self._tank = tank
        self._direction_change_interval: float = cfg["direction_change_interval"]
        self._shoot_interval: float = cfg["shoot_interval"]
        self._aligned_shoot_multiplier: float = cfg["aligned_shoot_multiplier"]
        self._defender_base_radius: float = (
            cfg["defender_base_radius_tiles"] * TILE_SIZE
        )
        self._hunter_target_bias: float = cfg["hunter_target_bias"]
        self._defender_base_bias: float = cfg["defender_base_bias"]
        self._defender_enemy_bias: float = cfg["defender_enemy_bias"]
        self._friendly_fire_check_px: float = (
            cfg["friendly_fire_check_tiles"] * TILE_SIZE
        )

        self._dx: int = 0
        self._dy: int = 0
        self._wants_shoot: bool = False
        self._direction_timer: float = 0.0
        self._shoot_timer: float = 0.0
        self._blocked_directions: set[Direction] = set()

    # PlayerInput protocol -----------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def get_movement_direction(self) -> tuple[int, int]:
        return (self._dx, self._dy)

    def consume_shoot(self) -> bool:
        flag, self._wants_shoot = self._wants_shoot, False
        return flag

    def clear_pending_shoot(self) -> None:
        self._wants_shoot = False

    # AI-specific, called by PlayerManager via isinstance branch ---------------
    def update(
        self,
        dt: float,
        enemies: list[EnemyTank],
        teammate: PlayerTank | None,
    ) -> None:
        """Advance AI state by one frame. Filled in over subsequent tasks."""
        return
