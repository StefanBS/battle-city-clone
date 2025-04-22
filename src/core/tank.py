import pygame
from typing import Optional, Tuple
from .game_object import GameObject
from .bullet import Bullet
from utils.constants import (
    TILE_SIZE,
    TANK_SPEED,
    TANK_WIDTH,
    TANK_HEIGHT,
    BULLET_WIDTH,
    BULLET_HEIGHT,
)


class Tank(GameObject):
    """Base tank class with common functionality."""

    def __init__(
        self,
        x: float,
        y: float,
        tile_size: int = TILE_SIZE,
        sprite: Optional[pygame.Surface] = None,
        health: int = 1,
        lives: int = 1,
        speed: float = TANK_SPEED,
    ):
        """
        Initialize the tank.

        Args:
            x: Initial x position
            y: Initial y position
            tile_size: Size of a tile in pixels
            sprite: Optional sprite surface
            health: Initial health points
            lives: Number of lives
            speed: Movement speed multiplier
        """
        super().__init__(x, y, TANK_WIDTH, TANK_HEIGHT, sprite)
        self.speed = speed
        self.direction = "up"  # Initial direction
        self.bullet: Optional[Bullet] = None
        self.tile_size = tile_size
        self.health: int = health
        self.max_health: int = health
        self.lives: int = lives
        self.owner_type: str = "base_tank"  # Default or abstract type
        self.move_timer: float = 0
        self.move_delay: float = 0.15  # Time between movements in seconds
        # Store previous position for collision rollback
        self.prev_x: float = x
        self.prev_y: float = y
        self.target_position: Tuple[float, float] = (x, y)
        self.is_invincible: bool = False
        self.invincibility_timer: float = 0
        self.invincibility_duration: float = 0
        self.blink_timer: float = 0
        self.blink_interval: float = 0.2  # Blink every 0.2 seconds during invincibility

    def take_damage(self, amount: int = 1) -> bool:
        """
        Take damage and return whether the tank was destroyed.

        Args:
            amount: Amount of damage to take (defaults to 1)

        Returns:
            True if the tank was destroyed, False otherwise
        """
        if self.is_invincible:
            return False

        # Ensure we don't go below 0 health
        self.health = max(0, self.health - amount)

        # If health reaches 0, lose a life and reset health
        if self.health <= 0:
            self.lives -= 1
            if self.lives > 0:
                self.health = self.max_health
                return False
            return True
        return False

    def shoot(self) -> None:
        """Create a new bullet if none exists."""
        if self.bullet is None or not self.bullet.active:
            bullet_x = self.x + self.width // 2 - BULLET_WIDTH // 2
            bullet_y = self.y + self.height // 2 - BULLET_HEIGHT // 2
            self.bullet = Bullet(bullet_x, bullet_y, self.direction, self.owner_type)

    def update(self, dt: float) -> None:
        """
        Update the tank's state.

        Args:
            dt: Time elapsed since last update in seconds
        """
        # Store position before any potential movement this frame
        self.prev_x = self.x
        self.prev_y = self.y

        # Update invincibility timer
        if self.is_invincible:
            self.invincibility_timer += dt
            self.blink_timer += dt
            if self.invincibility_timer >= self.invincibility_duration:
                self.is_invincible = False
                self.invincibility_timer = 0

        # Update movement timer
        self.move_timer += dt

        # Update the tank's rect *before* bullet update if bullet depends on final pos?
        # Let's keep it here for now, might need adjustment.
        super().update(dt)

        # Update bullet if it exists
        if self.bullet is not None:
            self.bullet.update(dt)

    def _move(self, dx: int, dy: int) -> bool:
        """
        Attempt to move the tank by updating its position.
        Collision checks are handled externally by GameManager.

        Args:
            dx: X movement amount (-1, 0, or 1)
            dy: Y movement amount (-1, 0, or 1)

        Returns:
            True if movement was attempted (timer ready), False otherwise.
        """
        if self.move_timer < self.move_delay:
            return False  # Not ready to move yet

        if dx != 0 and dy != 0:
            return False  # Ignore diagonal movement attempts

        # Calculate target position (move by one tile)
        target_x = self.x + dx * self.tile_size  # Move full tile increments
        target_y = self.y + dy * self.tile_size

        # Apply movement (position will be validated/reverted by GameManager)
        self.x = target_x
        self.y = target_y
        self.target_position = (self.x, self.y)
        self.move_timer = 0  # Reset timer after movement attempt

        # Update rect immediately after position change
        self.rect.topleft = (round(self.x), round(self.y))

        return True  # Movement was attempted

    def revert_move(self) -> None:
        """Reverts the tank to its previous position."""
        self.x = self.prev_x
        self.y = self.prev_y
        self.rect.topleft = (round(self.x), round(self.y))
        self.target_position = (self.x, self.y)

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw the tank and its bullet on the given surface.

        Args:
            surface: Surface to draw on
        """
        # Only draw if not invincible or during visible phase of blinking
        if (
            not self.is_invincible
            or self.blink_timer % (self.blink_interval * 2) < self.blink_interval
        ):
            if self.sprite:
                surface.blit(self.sprite, self.rect)

        if self.bullet is not None and self.bullet.active:
            self.bullet.draw(surface)
