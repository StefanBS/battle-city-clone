import pygame
from typing import Tuple
from .game_object import GameObject


class Bullet(GameObject):
    """Represents a bullet in the game."""

    def __init__(
        self,
        x: int,
        y: int,
        direction: str,
        tile_size: int,
        sprite: pygame.Surface = None,
    ):
        """
        Initialize a bullet.

        Args:
            x: Initial x position
            y: Initial y position
            direction: Direction of movement ("up", "down", "left", "right")
            tile_size: Size of a tile in pixels
            sprite: Optional sprite surface
        """
        # Bullet size is half of a tile
        bullet_size = tile_size // 2
        super().__init__(x, y, bullet_size, bullet_size, sprite)
        self.speed = 4  # Pixels per frame
        self.direction = direction
        self.active = True

    def update(self, dt: float) -> None:
        """
        Update the bullet's position.

        Args:
            dt: Time elapsed since last update in seconds
        """
        if not self.active:
            return

        # Calculate movement based on direction
        dx, dy = 0, 0
        if self.direction == "up":
            dy = -1
        elif self.direction == "down":
            dy = 1
        elif self.direction == "left":
            dx = -1
        elif self.direction == "right":
            dx = 1

        # Calculate new position
        new_x = self.x + dx * self.speed
        new_y = self.y + dy * self.speed

        # Update position
        self.x = new_x
        self.y = new_y
        super().update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw the bullet on the given surface.

        Args:
            surface: Surface to draw on
        """
        if self.active:
            if self.sprite:
                surface.blit(self.sprite, self.rect)
            else:
                # Draw a simple bullet if no sprite is provided
                pygame.draw.rect(surface, (255, 255, 0), self.rect)  # Yellow bullet 