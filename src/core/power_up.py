"""Power-up entity that spawns when a carrier enemy is destroyed."""

import pygame

from src.core.game_object import GameObject
from src.managers.texture_manager import TextureManager
from src.utils.animation import is_blink_visible
from src.utils.constants import (
    POWERUP_BLINK_INTERVAL,
    POWERUP_TIMEOUT,
    TILE_SIZE,
    PowerUpType,
)


class PowerUp(GameObject):
    """A collectible power-up item on the map."""

    def __init__(
        self,
        x: float,
        y: float,
        power_up_type: PowerUpType,
        texture_manager: TextureManager,
    ) -> None:
        sprite = texture_manager.get_sprite(f"powerup_{power_up_type}")
        super().__init__(x, y, TILE_SIZE, TILE_SIZE, sprite)
        self.power_up_type = power_up_type
        self.blink_timer: float = 0.0
        self.timeout_timer: float = 0.0
        self.active: bool = True

    def update(self, dt: float) -> None:
        """Update blink and timeout timers."""
        if not self.active:
            return
        self.blink_timer += dt
        self.timeout_timer += dt
        if self.timeout_timer >= POWERUP_TIMEOUT:
            self.active = False
        super().update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the power-up with blinking effect."""
        if not self.active:
            return
        if is_blink_visible(self.blink_timer, POWERUP_BLINK_INTERVAL):
            super().draw(surface)

    def collect(self) -> PowerUpType:
        """Collect the power-up. Returns the type for effect dispatch."""
        self.active = False
        return self.power_up_type
