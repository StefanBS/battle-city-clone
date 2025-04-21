import pygame
from typing import Optional
from .game_object import GameObject
from utils.constants import (
    BULLET_SPEED,
    BULLET_WIDTH,
    BULLET_HEIGHT,
    WHITE,
)


class Bullet(GameObject):
    """Bullet entity that can be fired by tanks."""

    def __init__(
        self,
        x: int,
        y: int,
        direction: str,
        sprite: Optional[pygame.Surface] = None,
    ):
        """
        Initialize the bullet.

        Args:
            x: Initial x position
            y: Initial y position
            direction: Direction of movement ("up", "down", "left", "right")
            sprite: Optional sprite surface
        """
        super().__init__(x, y, BULLET_WIDTH, BULLET_HEIGHT, sprite)
        self.direction = direction
        self.speed = BULLET_SPEED
        self.active = True
        self.color = WHITE

    def update(self, dt: float) -> None:
        """
        Update the bullet's position.

        Args:
            dt: Time elapsed since last update in seconds
        """
        if not self.active:
            return

        # Calculate movement based on direction
        if self.direction == "left":
            self.x -= self.speed
        elif self.direction == "right":
            self.x += self.speed
        elif self.direction == "up":
            self.y -= self.speed
        elif self.direction == "down":
            self.y += self.speed

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
