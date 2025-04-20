import pygame
import random
from typing import Optional
from .tank import Tank


class EnemyTank(Tank):
    """Enemy tank entity with basic AI."""

    def __init__(
        self,
        x: int,
        y: int,
        tile_size: int,
        sprite: pygame.Surface = None,
        health: int = 1,
    ):
        """
        Initialize the enemy tank.

        Args:
            x: Initial x position
            y: Initial y position
            tile_size: Size of a tile in pixels
            sprite: Optional sprite surface
            health: Initial health points
        """
        super().__init__(x, y, tile_size, sprite, health=health, lives=1)
        self.direction = random.choice(["up", "down", "left", "right"])
        self.direction_timer = 0
        self.direction_change_interval = 2.0  # Change direction every 2 seconds
        self.shoot_timer = 0
        self.shoot_interval = 1.5  # Shoot every 1.5 seconds
        self.color = (255, 0, 0)  # Red color for enemy tank

    def _change_direction(self) -> None:
        """Randomly change the tank's direction."""
        directions = ["up", "down", "left", "right"]
        directions.remove(self.direction)  # Remove current direction
        self.direction = random.choice(directions)

    def update(self, dt: float, map_rects: list[pygame.Rect]) -> None:
        """
        Update the tank's position and behavior.

        Args:
            dt: Time elapsed since last update in seconds
            map_rects: List of rectangles representing collidable map tiles
        """
        # Update base tank state
        super().update(dt, map_rects)

        # Update timers
        self.direction_timer += dt
        self.shoot_timer += dt

        # Change direction periodically
        if self.direction_timer >= self.direction_change_interval:
            self._change_direction()
            self.direction_timer = 0

        # Shoot periodically
        if self.shoot_timer >= self.shoot_interval:
            self.shoot()
            self.shoot_timer = 0

        # Calculate movement based on current direction
        dx, dy = 0, 0
        if self.direction == "left":
            dx = -1
        elif self.direction == "right":
            dx = 1
        elif self.direction == "up":
            dy = -1
        elif self.direction == "down":
            dy = 1

        # Attempt to move
        if not self._move(dx, dy, map_rects):
            # If movement failed, change direction
            self._change_direction()

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw the tank and its bullet on the given surface.

        Args:
            surface: Surface to draw on
        """
        if self.sprite:
            surface.blit(self.sprite, self.rect)
        else:
            # Draw a simple red tank if no sprite is provided
            pygame.draw.rect(surface, self.color, self.rect)

        if self.bullet is not None and self.bullet.active:
            self.bullet.draw(surface)
