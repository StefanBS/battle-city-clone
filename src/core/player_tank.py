import pygame
from loguru import logger
from .tank import Tank
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    Direction,
    OwnerType,
    BULLET_SPEED,
    SPAWN_INVINCIBILITY_DURATION,
    STAR_BULLET_SPEED_MULTIPLIER,
    STAR_MAX_BULLETS,
    SHIELD_WARNING_DURATION,
    SHIELD_FLICKER_INTERVAL,
)


class PlayerTank(Tank):
    """Player-controlled tank entity."""

    def __init__(
        self,
        x: int,
        y: int,
        tile_size: int,
        texture_manager: TextureManager,
        *,
        map_width_px: int,
        map_height_px: int,
    ) -> None:
        """
        Initialize the player tank.

        Args:
            x: Initial x position
            y: Initial y position
            tile_size: Size of a tile in pixels
            texture_manager: Instance of TextureManager
            map_width_px: Map width in pixels (for boundary clamping)
            map_height_px: Map height in pixels (for boundary clamping)
        """
        super().__init__(
            x,
            y,
            texture_manager,
            tile_size,
            None,
            health=1,
            lives=3,
            owner_type=OwnerType.PLAYER,
            map_width_px=map_width_px,
            map_height_px=map_height_px,
        )
        self.initial_position = (self.x, self.y)
        self.invincibility_duration = SPAWN_INVINCIBILITY_DURATION
        self.star_level: int = 0
        self._update_sprite()
        self._shield_frames: list[pygame.Surface] = [
            texture_manager.get_sprite("shield_1"),
            texture_manager.get_sprite("shield_2"),
        ]

    def apply_star(self) -> None:
        """Apply a star upgrade (up to tier 3)."""
        if self.star_level < 3:
            self.star_level += 1
        self._apply_star_stats()
        self._update_sprite()

    def _apply_star_stats(self) -> None:
        """Apply stats based on current star level."""
        if self.star_level >= 1:
            self.bullet_speed = BULLET_SPEED * STAR_BULLET_SPEED_MULTIPLIER
        else:
            self.bullet_speed = BULLET_SPEED
        if self.star_level >= 2:
            self.max_bullets = STAR_MAX_BULLETS
        else:
            self.max_bullets = 1
        self.power_bullets = self.star_level >= 3

    @property
    def is_shield_active(self) -> bool:
        """Whether the shield overlay should render."""
        if not self.is_invincible:
            return False
        if self.invincibility_duration <= SHIELD_WARNING_DURATION:
            return True
        remaining = self.invincibility_duration - self.invincibility_timer
        return remaining > SHIELD_WARNING_DURATION

    def _update_sprite(self) -> None:
        """Update sprite using tier-specific sprites when upgraded."""
        if self.star_level > 0:
            sprite_name = (
                f"player_tank_tier{self.star_level}"
                f"_{self.direction}_{self.animation_frame}"
            )
            try:
                self.sprite = self.texture_manager.get_sprite(sprite_name)
            except KeyError:
                logger.warning(f"Tier sprite '{sprite_name}' not found, using base")
                super()._update_sprite()
        else:
            super()._update_sprite()

    def activate_invincibility(self, duration: float) -> None:
        """Activate invincibility for the given duration."""
        self.is_invincible = True
        self.invincibility_timer = 0
        self.blink_timer = 0
        self.invincibility_duration = duration

    def move(self, dx: int, dy: int, dt: float) -> None:
        """
        Move the tank in the given direction.

        Sets the direction, updates the sprite, and calls _move().
        This is the public interface for external controllers (GameManager).

        Args:
            dx: X movement amount (-1, 0, or 1)
            dy: Y movement amount (-1, 0, or 1)
            dt: Time elapsed since last update in seconds
        """
        if dx == 0 and dy == 0:
            return

        new_direction = self.direction
        if dx > 0:
            new_direction = Direction.RIGHT
        elif dx < 0:
            new_direction = Direction.LEFT
        elif dy > 0:
            new_direction = Direction.DOWN
        elif dy < 0:
            new_direction = Direction.UP

        if new_direction != self.direction:
            self.direction = new_direction
            self._update_sprite()

        self._move(dx, dy, dt)

    def respawn(self) -> None:
        """Respawn the tank at its initial position."""
        if self.lives > 0:
            logger.info(
                f"Player respawning at {self.initial_position}. Lives: {self.lives}"
            )
            self.set_position(*self.initial_position)
            self.prev_x = self.x
            self.prev_y = self.y
            self.activate_invincibility(SPAWN_INVINCIBILITY_DURATION)
            self.star_level = 0
            self._apply_star_stats()
            self.direction = Direction.UP
            self._update_sprite()

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the player tank with shield overlay when active."""
        if self.is_shield_active:
            if self.sprite:
                surface.blit(self.sprite, self.rect)
            frame_idx = int(
                self.invincibility_timer % (SHIELD_FLICKER_INTERVAL * 2)
                >= SHIELD_FLICKER_INTERVAL
            )
            surface.blit(self._shield_frames[frame_idx], self.rect)
        else:
            super().draw(surface)
