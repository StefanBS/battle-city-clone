import pygame
from typing import Optional
from loguru import logger
from .game_object import GameObject
from .bullet import Bullet
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    Direction,
    OwnerType,
    TILE_SIZE,
    TANK_SPEED,
    TANK_WIDTH,
    TANK_HEIGHT,
    TANK_ANIMATION_DISTANCE,
    TANK_ALIGN_THRESHOLD,
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
        *,
        owner_type: OwnerType,
        map_width_px: int,
        map_height_px: int,
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
            speed: Movement speed in pixels per second
            bullet_speed: Speed of bullets fired by this tank
            owner_type: Whether this tank belongs to a player or enemy
            map_width_px: Map width in pixels (for boundary clamping)
            map_height_px: Map height in pixels (for boundary clamping)
        """
        # Snap to grid
        x = round(x / tile_size) * tile_size
        y = round(y / tile_size) * tile_size
        logger.debug(f"Creating Tank at ({x}, {y})")
        super().__init__(x, y, TANK_WIDTH, TANK_HEIGHT, sprite)
        self.texture_manager = texture_manager
        self.speed = speed
        self.bullet_speed = bullet_speed
        self.map_width_px = map_width_px
        self.map_height_px = map_height_px
        self.direction = Direction.UP  # Initial direction
        self.max_bullets: int = 1
        self.tile_size = tile_size
        self.health: int = health
        self.max_health: int = health
        self.lives: int = lives
        self.owner_type: OwnerType = owner_type
        self.distance_since_last_toggle: float = 0
        # Store previous position for collision rollback
        self.prev_x: float = x
        self.prev_y: float = y
        self.is_invincible: bool = False
        self.invincibility_timer: float = 0
        self.invincibility_duration: float = 0
        self.blink_timer: float = 0
        self.blink_interval: float = 0.2  # Blink every 0.2 seconds during invincibility
        self.animation_frame: int = 1  # Start with frame 1

    def _update_sprite(self) -> None:
        """Updates the tank's sprite based on direction and animation frame."""

        sprite_name = f"{self.owner_type}_tank_{self.direction}_{self.animation_frame}"
        try:
            self.sprite = self.texture_manager.get_sprite(sprite_name)

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

    def shoot(self) -> Optional[Bullet]:
        """Create and return a new bullet.

        Returns:
            A new Bullet instance, or None if creation fails.
        """
        logger.debug(
            (
                f"Tank {self.owner_type} at ({self.x}, {self.y}) shooting "
                f"in direction {self.direction}."
            )
        )
        bullet_x = self.x + self.width // 2 - BULLET_WIDTH // 2
        bullet_y = self.y + self.height // 2 - BULLET_HEIGHT // 2
        try:
            bullet_sprite = self.texture_manager.get_sprite(
                f"bullet_{self.direction}"
            )
        except KeyError:
            bullet_sprite = None
        return Bullet(
            bullet_x,
            bullet_y,
            self.direction,
            owner=self,
            sprite=bullet_sprite,
            speed=self.bullet_speed,
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

        super().update(dt)

    @property
    def prev_rect(self) -> pygame.Rect:
        """Return a Rect at the tank's position from the start of this frame."""
        return pygame.Rect(
            round(self.prev_x),
            round(self.prev_y),
            self.width,
            self.height,
        )

    def on_movement_blocked(self) -> None:
        """Called when movement is blocked (wall, boundary, tank). No-op by default."""
        pass

    def _align_to_grid(self, value: float, dt: float) -> float:
        """Nudge a coordinate toward the nearest TILE_SIZE grid line.

        If the offset is within TANK_ALIGN_THRESHOLD, move toward the grid
        line at the tank's speed so the correction feels natural.
        """
        nearest = round(value / TILE_SIZE) * TILE_SIZE
        offset = nearest - value
        if abs(offset) > TANK_ALIGN_THRESHOLD:
            return value
        # Move toward the grid line, but don't overshoot
        max_step = self.speed * dt
        if abs(offset) <= max_step:
            return float(nearest)
        return value + max_step * (1.0 if offset > 0 else -1.0)

    def _move(self, dx: int, dy: int, dt: float) -> bool:
        """
        Attempt to move the tank by updating its position.
        Collision checks are handled externally by GameManager.

        Args:
            dx: X movement amount (-1, 0, or 1)
            dy: Y movement amount (-1, 0, or 1)
            dt: Time elapsed since last update in seconds

        Returns:
            True if movement was attempted, False otherwise.
        """
        if dx != 0 and dy != 0:
            return False  # Ignore diagonal movement attempts

        if dx == 0 and dy == 0:
            return False  # No movement requested

        # Steering assist: nudge perpendicular axis toward grid alignment
        if dx != 0:
            self.y = self._align_to_grid(self.y, dt)
        else:
            self.x = self._align_to_grid(self.x, dt)

        # Calculate target position
        target_x = self.x + dx * self.speed * dt
        target_y = self.y + dy * self.speed * dt

        # Apply movement and clamp to map bounds
        max_x = float(self.map_width_px - self.width)
        max_y = float(self.map_height_px - self.height)
        self.x = max(0.0, min(target_x, max_x))
        self.y = max(0.0, min(target_y, max_y))

        # Detect boundary hit (position was clamped)
        if self.x != target_x or self.y != target_y:
            self.on_movement_blocked()

        # Distance-based animation toggle
        distance = abs(dx * self.speed * dt) + abs(dy * self.speed * dt)
        self.distance_since_last_toggle += distance
        if self.distance_since_last_toggle >= TANK_ANIMATION_DISTANCE:
            self.distance_since_last_toggle -= TANK_ANIMATION_DISTANCE
            self.animation_frame = 3 - self.animation_frame  # Toggle between 1 and 2
            self._update_sprite()

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
            # Start with current (collided) position as a basis for snapping
            snapped_x, snapped_y = self.x, self.y

            if self.direction == Direction.RIGHT:
                snapped_x = float(obstacle_rect.left - self.width)
            elif self.direction == Direction.LEFT:
                snapped_x = float(obstacle_rect.right)
            elif self.direction == Direction.DOWN:
                snapped_y = float(obstacle_rect.top - self.height)
            elif self.direction == Direction.UP:
                snapped_y = float(obstacle_rect.bottom)

            self.x = snapped_x
            self.y = snapped_y

            # Clamp to map bounds
            max_x = float(self.map_width_px - self.width)
            max_y = float(self.map_height_px - self.height)
            self.x = max(0.0, min(self.x, max_x))
            self.y = max(0.0, min(self.y, max_y))

        else:  # Fallback to previous position if no obstacle_rect is given
            self.x = self.prev_x
            self.y = self.prev_y

        self.rect.topleft = (round(self.x), round(self.y))

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw the tank on the given surface.

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
