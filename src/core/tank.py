import pygame
from typing import Optional, Tuple
from loguru import logger
from .game_object import GameObject
from .bullet import Bullet
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    TILE_SIZE,
    TANK_SPEED,
    TANK_WIDTH,
    TANK_HEIGHT,
    BULLET_WIDTH,
    BULLET_HEIGHT,
    BULLET_SPEED,
)


class Tank(GameObject):
    """Base tank class with common functionality."""

    def __init__(
        self,
        x: float,
        y: float,
        texture_manager: TextureManager,
        tile_size: int = TILE_SIZE,
        sprite: Optional[pygame.Surface] = None,
        health: int = 1,
        lives: int = 1,
        speed: float = TANK_SPEED,
        bullet_speed: float = BULLET_SPEED,
    ) -> None:
        """
        Initialize the tank.

        Args:
            x: Initial x position
            y: Initial y position
            texture_manager: TextureManager instance
            tile_size: Size of a tile in pixels
            sprite: Optional sprite surface
            health: Initial health points
            lives: Number of lives
            speed: Movement speed multiplier
            bullet_speed: Speed of bullets fired by this tank
        """
        logger.debug(f"Creating Tank at ({x}, {y})")
        super().__init__(x, y, TANK_WIDTH, TANK_HEIGHT, sprite)
        self.texture_manager = texture_manager
        self.speed = speed
        self.bullet_speed = bullet_speed
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
        self.animation_frame: int = 1  # Start with frame 1

    def _update_sprite(self) -> None:
        """Updates the tank's sprite based on direction and animation frame."""

        base_sprite_name = f"{self.owner_type}_tank"

        if self.owner_type.startswith("enemy"):
            base_sprite_name = "enemy_tank"

        sprite_name = f"{base_sprite_name}_{self.direction}_{self.animation_frame}"
        try:
            self.sprite = self.texture_manager.get_sprite(sprite_name)
            logger.trace(f"Set sprite to {sprite_name}")
        except KeyError:
            logger.error(
                f"Sprite '{sprite_name}' not found for {self.owner_type} tank."
            )
            # Optionally keep the old sprite or use a fallback
            # self.sprite = self.texture_manager.get_sprite("fallback_sprite") # Example

    def take_damage(self, amount: int = 1) -> bool:
        """
        Take damage and return whether the tank was destroyed.

        Args:
            amount: Amount of damage to take (defaults to 1)

        Returns:
            True if the tank was destroyed, False otherwise
        """
        logger.debug(
            f"Tank {self.owner_type} at ({self.x}, {self.y}) taking {amount} damage."
        )
        if self.is_invincible:
            logger.debug("Tank is invincible, ignoring damage.")
            return False

        # Ensure we don't go below 0 health
        self.health = max(0, self.health - amount)

        # If health reaches 0, lose a life and reset health
        if self.health <= 0:
            self.lives -= 1
            logger.info(
                f"Tank {self.owner_type} health reached 0. Lives left: {self.lives}"
            )
            if self.lives > 0:
                self.health = self.max_health
                logger.info(
                    f"Tank {self.owner_type} respawning with {self.health} health."
                )
                return False
            logger.info(f"Tank {self.owner_type} destroyed (no lives left).")
            return True
        logger.debug(f"Tank {self.owner_type} health now {self.health}.")
        return False

    def shoot(self) -> None:
        """Create a new bullet if none exists."""
        if self.bullet is None or not self.bullet.active:
            logger.debug(
                (
                    f"Tank {self.owner_type} at ({self.x}, {self.y}) shooting "
                    f"in direction {self.direction}."
                )
            )
            bullet_x = self.x + self.width // 2 - BULLET_WIDTH // 2
            bullet_y = self.y + self.height // 2 - BULLET_HEIGHT // 2
            self.bullet = Bullet(
                bullet_x,
                bullet_y,
                self.direction,
                self.owner_type,
                speed=self.bullet_speed,
            )
        else:
            logger.trace(
                (
                    f"Tank {self.owner_type} at ({self.x}, {self.y}) tried to shoot, "
                    f"but bullet is active."
                )
            )

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
            logger.trace(
                (
                    f"Tank {self.owner_type} move skipped (timer not ready: "
                    f"{self.move_timer:.2f}/{self.move_delay:.2f})"
                )
            )
            return False  # Not ready to move yet

        if dx != 0 and dy != 0:
            return False  # Ignore diagonal movement attempts

        # Calculate target position
        target_x = self.x + dx * self.speed
        target_y = self.y + dy * self.speed

        logger.debug(
            (
                f"Tank {self.owner_type} attempting move from ({self.x}, {self.y}) "
                f"to ({target_x}, {target_y})"
            )
        )

        # Apply movement (position will be validated/reverted by GameManager)
        self.x = target_x
        self.y = target_y
        self.target_position = (self.x, self.y)
        self.move_timer = 0  # Reset timer after movement attempt

        # Toggle animation frame and update sprite
        self.animation_frame = 3 - self.animation_frame  # Toggle between 1 and 2
        self._update_sprite()  # Update sprite after toggling frame

        # Update rect immediately after position change
        self.rect.topleft = (round(self.x), round(self.y))

        return True  # Movement was attempted

    def revert_move(self, obstacle_rect: Optional[pygame.Rect] = None) -> None:
        """
        Reverts the tank to its previous position or snaps it to an obstacle.
        If obstacle_rect is provided, snaps to it based on self.direction.
        Otherwise, reverts to self.prev_x, self.prev_y.
        """
        if obstacle_rect:
            logger.debug(
                f"Tank {self.owner_type} snapping to obstacle {obstacle_rect} due to "
                f"collision. Direction: {self.direction}"
            )
            # Start with current (collided) position as a basis for snapping
            snapped_x, snapped_y = self.x, self.y

            if self.direction == "right":

                snapped_x = float(obstacle_rect.left - self.width)
            elif self.direction == "left":
                snapped_x = float(obstacle_rect.right)
            elif self.direction == "down":
                snapped_y = float(obstacle_rect.top - self.height)
            elif self.direction == "up":
                snapped_y = float(obstacle_rect.bottom)

            self.x = snapped_x
            self.y = snapped_y
            logger.debug(
                f"Tank {self.owner_type} snapped to ({self.x:.2f}, {self.y:.2f})"
            )

        else:  # Fallback to previous position if no obstacle_rect is given
            logger.debug(
                (
                    f"Tank {self.owner_type} reverting move from ({self.x:.2f}, {self.y:.2f}) "
                    f"to ({self.prev_x:.2f}, {self.prev_y:.2f}) (no obstacle for snapping)"
                )
            )
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
