"""TankStepper: steps any tank through one frame and owns every bullet."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.core.bullet import Bullet
    from src.core.map import Map
    from src.core.tank import Tank


class TankIntent(Protocol):
    """Where a tank wants to go this frame, and whether it wants to fire."""

    def get_movement_direction(self) -> tuple[int, int]: ...
    def consume_shoot(self) -> bool: ...


@dataclass(frozen=True)
class StepResult:
    """What happened to a tank during its step, so callers can play sounds."""

    slide_started: bool = False
    fired: bool = False


class TankStepper:
    """Steps Players and Enemies alike: timers, ice, Slide or move, then fire.

    Knows nothing about sound, the Clock or lives: callers decide which tanks
    to step and what to play from the returned StepResult.
    """

    def __init__(self, game_map: Map) -> None:
        """Initialize the stepper for one stage.

        Args:
            game_map: The stage's map, used to tell whether a tank is on ice.
        """
        self._map = game_map
        self._bullets: list[Bullet] = []

    @property
    def bullets(self) -> list[Bullet]:
        """Every bullet in flight, Player and Enemy. Read-only view."""
        return self._bullets

    def step(self, tank: Tank, intent: TankIntent, dt: float) -> StepResult:
        """Advance ``tank`` one frame following ``intent``.

        Args:
            tank: The tank to step.
            intent: Where the tank wants to go and whether it wants to fire.
            dt: Time step in seconds.

        Returns:
            Whether a Slide started and whether a bullet was fired.
        """
        tank.update(dt)

        dx, dy = intent.get_movement_direction()
        has_direction = (dx != 0) != (dy != 0)

        # Read from where the tank stands now, before deciding to Slide.
        tank.on_ice = self._map.is_tile_slidable(
            tank.x, tank.y, tank.width, tank.height
        )
        slide_started = False
        if tank.on_ice and not tank.is_sliding:
            if not has_direction or (dx, dy) != tank.direction.delta:
                slide_started = tank.start_slide()

        if has_direction and not tank.is_sliding:
            tank.move(dx, dy, dt)

        fired = intent.consume_shoot() and self._fire(tank)
        return StepResult(slide_started=slide_started, fired=fired)

    def _fire(self, tank: Tank) -> bool:
        in_flight = sum(1 for b in self._bullets if b.owner is tank and b.active)
        if in_flight >= tank.max_bullets:
            return False
        bullet = tank.shoot()
        if bullet is None:
            return False
        self._bullets.append(bullet)
        return True

    def update_bullets(self, dt: float) -> None:
        """Advance every bullet and drop the inactive ones.

        Run once per frame, after every tank has stepped.
        """
        for bullet in self._bullets:
            bullet.update(dt)
        self._bullets = [b for b in self._bullets if b.active]
