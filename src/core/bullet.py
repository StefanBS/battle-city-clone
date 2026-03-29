import pygame
from typing import Optional, Tuple
from loguru import logger
from .game_object import GameObject
from src.utils.constants import (
    Direction,
    OwnerType,
    BULLET_SPEED,
    BULLET_WIDTH,
    BULLET_HEIGHT,
    WHITE,
)


ColorTuple = Tuple[int, int, int]


class Bullet(GameObject):
    """Bullet entity that can be fired by tanks."""

    def __init__(
        self,
        x: float,
        y: float,
        direction: Direction,
        owner,
        sprite: Optional[pygame.Surface] = None,
        speed: float = BULLET_SPEED,
    ) -> None:
        """
        Initialize the bullet.

        Args:
            x: Initial x position
            y: Initial y position
            direction: Direction of movement ("up", "down", "left", "right")
            owner: The tank that fired this bullet.
            sprite: Optional sprite surface
            speed: Speed of the bullet in pixels per second
        """
        super().__init__(x, y, BULLET_WIDTH, BULLET_HEIGHT, sprite)
        self.direction: Direction = direction
        self.speed: float = speed
        self.active: bool = True
        self.color: ColorTuple = WHITE
        self.owner = owner
        self.owner_type: OwnerType = owner.owner_type
        logger.trace(
            f"Created bullet for {self.owner_type} "
            f"at ({x:.1f}, {y:.1f}) moving {direction}"
        )

    def update(self, dt: float) -> None:
        """
        Update the bullet's position.

        Args:
            dt: Time elapsed since last update in seconds
        """
        if not self.active:
            return

        dx, dy = self.direction.delta
        self.x += dx * self.speed * dt
        self.y += dy * self.speed * dt

        # Check if bullet is out of bounds
        if (
            self.x < 0
            or self.x > self.owner.map_width_px
            or self.y < 0
            or self.y > self.owner.map_height_px
        ):
            self.active = False
            return

        # Update the bullet's rect
        super().update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw the bullet on the given surface.

        Args:
            surface: Surface to draw on
        """
        if not self.active:
            return

        if self.sprite:
            surface.blit(self.sprite, self.rect)
        else:
            pygame.draw.rect(surface, self.color, self.rect)
