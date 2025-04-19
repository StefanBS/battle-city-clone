import pygame
import random
from typing import Tuple, Optional
from .game_object import GameObject
from .bullet import Bullet


class EnemyTank(GameObject):
    """Enemy tank entity with basic AI."""

    def __init__(
        self,
        x: int,
        y: int,
        tile_size: int,
        sprite: pygame.Surface = None,
    ):
        """
        Initialize the enemy tank.

        Args:
            x: Initial x position
            y: Initial y position
            tile_size: Size of a tile in pixels
            sprite: Optional sprite surface
        """
        super().__init__(x, y, tile_size, tile_size, sprite)
        self.speed = 1  # Slower than player tank
        self.direction = "up"  # Initial direction
        self.tile_size = tile_size
        self.bullet: Optional[Bullet] = None
        self.direction_change_timer = 0
        self.direction_change_interval = 2.0  # Change direction every 2 seconds
        self.shoot_timer = 0
        self.shoot_interval = 3.0  # Shoot every 3 seconds

    def update(self, dt: float, map_rects: list[pygame.Rect]) -> None:
        """
        Update the tank's position and behavior.

        Args:
            dt: Time elapsed since last update in seconds
            map_rects: List of rectangles representing collidable map tiles
        """
        # Update timers
        self.direction_change_timer += dt
        self.shoot_timer += dt

        # Randomly change direction
        if self.direction_change_timer >= self.direction_change_interval:
            self.direction_change_timer = 0
            self._change_direction()

        # Randomly shoot
        if self.shoot_timer >= self.shoot_interval:
            self.shoot_timer = 0
            self.shoot()

        # Calculate movement based on current direction
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

        # Create a temporary rect for collision checking
        temp_rect = pygame.Rect(new_x, new_y, self.width, self.height)

        # Check for collisions with map tiles
        collision = False
        for map_rect in map_rects:
            if temp_rect.colliderect(map_rect):
                collision = True
                break

        # Only update position if no collision
        if not collision:
            self.x = new_x
            self.y = new_y
        else:
            # Change direction on collision
            self._change_direction()

        # Update the tank's rect
        super().update(dt)

        # Update bullet if it exists
        if self.bullet is not None:
            self.bullet.update(dt)

    def _change_direction(self) -> None:
        """Randomly change the tank's direction."""
        directions = ["up", "down", "left", "right"]
        self.direction = random.choice(directions)

    def shoot(self) -> None:
        """Create a new bullet if none exists."""
        if self.bullet is None or not self.bullet.active:
            # Calculate bullet starting position (center of tank)
            bullet_x = self.x + self.width // 2 - self.tile_size // 4
            bullet_y = self.y + self.height // 2 - self.tile_size // 4
            self.bullet = Bullet(bullet_x, bullet_y, self.direction, self.tile_size)

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
            pygame.draw.rect(surface, (255, 0, 0), self.rect)

        if self.bullet is not None and self.bullet.active:
            self.bullet.draw(surface) 