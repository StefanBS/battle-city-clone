"""Game-level consequences of a frame's collisions and Power-Ups.

``CollisionResponseHandler`` returns these instead of applying score, removals,
respawns or Game Over itself; ``GameManager`` applies them in one place. See
``docs/adr/0003-collision-response-returns-outcomes.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.enemy_tank import EnemyTank
from src.core.player_tank import PlayerTank
from src.utils.constants import PowerUpType


@dataclass(frozen=True)
class CarrierHit:
    """A Player's bullet hit a Carrier, which now drops its Power-Up."""

    enemy: EnemyTank


@dataclass(frozen=True)
class EnemyDestroyed:
    """An Enemy was destroyed, by a Player's bullet or (``by=None``) a Grenade."""

    enemy: EnemyTank
    by: PlayerTank | None


@dataclass(frozen=True)
class PlayerDestroyed:
    """A Player's tank was destroyed and it lost a life."""

    player: PlayerTank


@dataclass(frozen=True)
class BaseDestroyed:
    """The Base was destroyed."""


@dataclass(frozen=True)
class PowerUpCollected:
    """A Player collected a Power-Up; its effect is not yet applied."""

    power_up_type: PowerUpType
    player: PlayerTank


CollisionOutcome = (
    CarrierHit | EnemyDestroyed | PlayerDestroyed | BaseDestroyed | PowerUpCollected
)
