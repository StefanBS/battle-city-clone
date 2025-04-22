import pygame
from typing import Optional, Tuple
from .game_object import GameObject
from src.utils.constants import (
    BULLET_SPEED,
    BULLET_WIDTH,
    BULLET_HEIGHT,
    WHITE,
    GRID_WIDTH,
    GRID_HEIGHT,
    TILE_SIZE,
    FPS,
)


ColorTuple = Tuple[int, int, int]


class Bullet(GameObject):
    """Bullet entity that can be fired by tanks."""

    def __init__(
        self,
        x: float,
        y: float,
        direction: str,
        owner_type: str,
        sprite: Optional[pygame.Surface] = None,
        speed: float = BULLET_SPEED,
    ) -> None:
        """
        Initialize the bullet.

        Args:
            x: Initial x position
            y: Initial y position
            direction: Direction of movement ("up", "down", "left", "right")
            owner_type: The type of object that fired the bullet ('player' or 'enemy').
            sprite: Optional sprite surface
            speed: Speed of the bullet in pixels per second (adjusted by FPS)
        """
        super().__init__(x, y, BULLET_WIDTH, BULLET_HEIGHT, sprite)
        self.direction: str = direction
        self.speed: float = speed * FPS
        self.active: bool = True
        self.color: ColorTuple = WHITE
        self.owner_type: str = owner_type

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
            self.x -= self.speed * dt
        elif self.direction == "right":
            self.x += self.speed * dt
        elif self.direction == "up":
            self.y -= self.speed * dt
        elif self.direction == "down":
            self.y += self.speed * dt

        # Check if bullet is out of bounds
        if (
            self.x < 0
            or self.x > GRID_WIDTH * TILE_SIZE
            or self.y < 0
            or self.y > GRID_HEIGHT * TILE_SIZE
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
