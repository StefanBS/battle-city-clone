"""CPU Partner: a PlayerInput that drives P2 from the World View (ADR 0001)."""

import pygame

from src.managers.world_view import EnemyView, PlayerView, WorldView
from src.utils.constants import CPU_PARTNER_ALIGN_TOLERANCE, Direction


def _center(view: PlayerView | EnemyView) -> tuple[float, float]:
    return view.x + view.size / 2, view.y + view.size / 2


def _distance(a: PlayerView | EnemyView, b: PlayerView | EnemyView) -> float:
    """Manhattan distance between two tanks' centers, in pixels."""
    (ax, ay), (bx, by) = _center(a), _center(b)
    return abs(ax - bx) + abs(ay - by)


class CpuPartnerInput:
    """Computer-controlled input for the CPU Partner in the P2 slot.

    Reads the World View once per frame in :meth:`observe` and turns it into
    a movement direction and shoot requests, exactly like a human input.
    """

    def __init__(self) -> None:
        self._movement: tuple[int, int] = (0, 0)
        self._shoot_requested: bool = False
        self._target_id: int | None = None

    def reset(self) -> None:
        """Forget the current target (called on stage start and respawn)."""
        self._target_id = None
        self._movement = (0, 0)
        self._shoot_requested = False

    def handle_event(self, event: pygame.event.Event) -> None:
        """The CPU Partner ignores pygame events."""

    def observe(self, world: WorldView) -> None:
        """Decide this frame's movement and shooting from the World View."""
        self._movement = (0, 0)
        self._shoot_requested = False
        own = world.own_player
        if own is None or not own.alive:
            return
        target = self._pick_target(own, world.enemies)
        if target is None:
            return
        ox, oy = _center(own)
        ex, ey = _center(target)
        dx, dy = ex - ox, ey - oy
        vertical = Direction.DOWN if dy > 0 else Direction.UP
        horizontal = Direction.RIGHT if dx > 0 else Direction.LEFT
        if abs(dx) <= CPU_PARTNER_ALIGN_TOLERANCE:
            facing = vertical
        elif abs(dy) <= CPU_PARTNER_ALIGN_TOLERANCE:
            facing = horizontal
        else:
            # Not lined up: close the shorter gap first to get into the
            # target's row or column.
            self._movement = (horizontal if abs(dx) <= abs(dy) else vertical).delta
            return
        if own.direction == facing:
            self._shoot_requested = True
        else:
            self._movement = facing.delta

    def _pick_target(
        self, own: PlayerView, enemies: tuple[EnemyView, ...]
    ) -> EnemyView | None:
        """Hunt: keep the current target while it lives, else take the nearest."""
        for enemy in enemies:
            if enemy.enemy_id == self._target_id:
                return enemy
        if not enemies:
            self._target_id = None
            return None
        target = min(enemies, key=lambda e: _distance(own, e))
        self._target_id = target.enemy_id
        return target

    def get_movement_direction(self) -> tuple[int, int]:
        return self._movement

    def consume_shoot(self) -> bool:
        requested = self._shoot_requested
        self._shoot_requested = False
        return requested

    def clear_pending_shoot(self) -> None:
        self._shoot_requested = False
