"""AI implementation of the PlayerInput protocol for the AI co-op teammate."""

from __future__ import annotations

import json
import random
from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame

from src.core.ai_geometry import direction_moves_toward, is_aligned_with
from src.utils.constants import (
    DIRECTION_CHANGE_RANDOM_OFFSET,
    SHOOT_RANDOM_OFFSET,
    TILE_SIZE,
    Direction,
)

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

    def reset(self) -> None:
        """Clear all transient AI state. Called on the teammate's respawn so
        stale timers, pending shots, and block-memory from the previous life
        don't leak into the new one.
        """
        self._dx = 0
        self._dy = 0
        self._wants_shoot = False
        self._direction_timer = 0.0
        self._shoot_timer = 0.0
        self._blocked_directions.clear()

    # AI-specific, called by PlayerManager via isinstance branch ---------------
    def update(
        self,
        dt: float,
        enemies: list[EnemyTank],
        teammate: PlayerTank | None,
    ) -> None:
        """Advance AI state by one frame."""
        self._direction_timer += dt
        self._shoot_timer += dt

        moved = (self._tank.x != self._tank.prev_x) or (
            self._tank.y != self._tank.prev_y
        )
        requested_movement = self._dx != 0 or self._dy != 0
        if moved:
            self._blocked_directions.clear()
        elif requested_movement and not self._tank.is_frozen:
            self._blocked_directions.add(self._tank.direction)
            self._direction_timer = 0.0

        if self._direction_timer >= self._direction_change_interval:
            self._replan(enemies)
            self._direction_timer = random.uniform(0, DIRECTION_CHANGE_RANDOM_OFFSET)

        self._maybe_shoot(enemies, teammate)

    _ALL_DIRECTIONS = list(Direction)

    def _maybe_shoot(
        self,
        enemies: list[EnemyTank],
        teammate: PlayerTank | None,
    ) -> None:
        if self._shoot_timer < self._shoot_interval * self._aligned_shoot_multiplier:
            return

        if self._shoot_timer < self._shoot_interval:
            if not enemies:
                return
            nearest = min(
                enemies,
                key=lambda e: abs(e.x - self._tank.x) + abs(e.y - self._tank.y),
            )
            if not is_aligned_with(
                (self._tank.x, self._tank.y),
                self._tank.direction,
                self._tank.tile_size,
                (nearest.x, nearest.y),
            ):
                return

        if self._teammate_in_line_of_fire(teammate):
            return

        self._wants_shoot = True
        self._shoot_timer = random.uniform(0, SHOOT_RANDOM_OFFSET)

    def _teammate_in_line_of_fire(self, teammate: PlayerTank | None) -> bool:
        if teammate is None:
            return False
        dx, dy = self._tank.direction.delta
        ox = teammate.x - self._tank.x
        oy = teammate.y - self._tank.y
        if dx != 0:
            along = ox * dx
            perp = abs(oy)
        else:
            along = oy * dy
            perp = abs(ox)
        return 0 < along <= self._friendly_fire_check_px and perp <= TILE_SIZE

    def _replan(self, enemies: list[EnemyTank]) -> None:
        from src.core.enemy_tank import EnemyTank

        base_position = EnemyTank.base_position
        role = self._select_role(enemies, base_position)
        target_pos = self._select_target(enemies, base_position, role)

        candidates = self._candidate_directions()
        if not candidates:
            self._dx, self._dy = 0, 0
            return

        pos = (self._tank.x, self._tank.y)
        weights = self._compute_weights(
            candidates, pos, role, target_pos, base_position
        )
        new_direction = random.choices(candidates, weights)[0]
        self._dx, self._dy = new_direction.delta

    def _select_role(
        self,
        enemies: list[EnemyTank],
        base_position: tuple[float, float] | None,
    ) -> AIRole:
        if base_position is None:
            return AIRole.HUNTER
        bx, by = base_position
        for e in enemies:
            if abs(e.x - bx) + abs(e.y - by) <= self._defender_base_radius:
                return AIRole.DEFENDER
        return AIRole.HUNTER

    def _select_target(
        self,
        enemies: list[EnemyTank],
        base_position: tuple[float, float] | None,
        role: AIRole,
    ) -> tuple[float, float] | None:
        if not enemies:
            return None
        if role == AIRole.DEFENDER and base_position is not None:
            bx, by = base_position
            nearest = min(enemies, key=lambda e: abs(e.x - bx) + abs(e.y - by))
        else:
            nearest = min(
                enemies,
                key=lambda e: abs(e.x - self._tank.x) + abs(e.y - self._tank.y),
            )
        return (nearest.x, nearest.y)

    def _candidate_directions(self) -> list[Direction]:
        opposite = self._tank.direction.opposite
        filtered = [
            d
            for d in self._ALL_DIRECTIONS
            if d not in self._blocked_directions and d != opposite
        ]
        if filtered:
            return filtered
        return [d for d in self._ALL_DIRECTIONS if d not in self._blocked_directions]

    def _compute_weights(
        self,
        candidates: list[Direction],
        pos: tuple[float, float],
        role: AIRole,
        target_pos: tuple[float, float] | None,
        base_position: tuple[float, float] | None,
    ) -> list[float]:
        weights = [1.0] * len(candidates)
        if role == AIRole.DEFENDER and base_position is not None:
            for i, d in enumerate(candidates):
                if direction_moves_toward(pos, d, base_position):
                    weights[i] += self._defender_base_bias
                if target_pos is not None and direction_moves_toward(
                    pos, d, target_pos
                ):
                    weights[i] += self._defender_enemy_bias
        elif role == AIRole.HUNTER and target_pos is not None:
            for i, d in enumerate(candidates):
                if direction_moves_toward(pos, d, target_pos):
                    weights[i] += self._hunter_target_bias
        return weights
