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
        power_bullet: bool = False,
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
        self.color: Tuple[int, int, int] = WHITE
        self.prev_x: float = x
        self.prev_y: float = y
        self.owner = owner
        self.owner_type: OwnerType = owner.owner_type
        self.map_width_px: int = owner.map_width_px
        self.map_height_px: int = owner.map_height_px
        self.power_bullet: bool = power_bullet
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

        self.prev_x = self.x
        self.prev_y = self.y

        dx, dy = self.direction.delta
        self.x += dx * self.speed * dt
        self.y += dy * self.speed * dt

        # Check if bullet is out of bounds
        if (
            self.x < 0
            or self.x > self.map_width_px
            or self.y < 0
            or self.y > self.map_height_px
        ):
            self.active = False
            return

        # Update the bullet's rect
        super().update(dt)

    @property
    def swept_rect(self) -> pygame.Rect:
        """Return a rect covering both the previous and current positions.

        Used for continuous collision detection so fast-moving bullets
        cannot tunnel through each other between frames.
        """
        x1 = min(self.prev_x, self.x)
        y1 = min(self.prev_y, self.y)
        x2 = max(self.prev_x + self.width, self.x + self.width)
        y2 = max(self.prev_y + self.height, self.y + self.height)
        return pygame.Rect(round(x1), round(y1), round(x2 - x1), round(y2 - y1))

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
