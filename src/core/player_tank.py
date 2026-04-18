import pygame
from loguru import logger
from .tank import Tank
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    Direction,
    INITIAL_PLAYER_LIVES,
    MAX_STAR_LEVEL,
    OwnerType,
    BULLET_SPEED,
    SPAWN_INVINCIBILITY_DURATION,
    STAR_BULLET_SPEED_MULTIPLIER,
    STAR_MAX_BULLETS,
    SHIELD_WARNING_DURATION,
    SHIELD_FLICKER_INTERVAL,
    SHIELD_FAST_FLICKER_INTERVAL,
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
        player_id: int = 1,
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
        # Store spawn position before Tank.__init__ snaps to grid
        self.initial_position = (float(x), float(y))
        super().__init__(
            x,
            y,
            texture_manager,
            tile_size,
            health=1,
            lives=INITIAL_PLAYER_LIVES,
            owner_type=OwnerType.PLAYER,
            map_width_px=map_width_px,
            map_height_px=map_height_px,
        )
        self.player_id: int = player_id
        self.star_level: int = 0
        self._freeze_timer: float = 0.0
        self._update_sprite()
        self._shield_frames: list[pygame.Surface] = [
            texture_manager.get_sprite("shield_1"),
            texture_manager.get_sprite("shield_2"),
        ]

    def apply_star(self) -> None:
        """Apply a star upgrade (up to tier 3)."""
        self._set_star_level(min(self.star_level + 1, MAX_STAR_LEVEL))

    def restore_star_level(self, level: int) -> None:
        """Restore star level (e.g., after stage load). Clamps to 0-3."""
        self._set_star_level(max(0, min(MAX_STAR_LEVEL, level)))

    def _set_star_level(self, level: int) -> None:
        """Set star level and apply stats and sprite changes."""
        self.star_level = level
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
    def shield_flicker_interval(self) -> float:
        """Current shield flicker speed — faster during warning phase."""
        if self.invincibility_duration >= SHIELD_WARNING_DURATION:
            remaining = self.invincibility_duration - self.invincibility_timer
            if remaining <= SHIELD_WARNING_DURATION:
                return SHIELD_FAST_FLICKER_INTERVAL
        return SHIELD_FLICKER_INTERVAL

    def _update_sprite(self) -> None:
        """Update sprite using tier-specific sprites."""
        prefix = "player2_tank" if self.player_id == 2 else "player_tank"
        sprite_name = (
            f"{prefix}_tier{self.star_level}_{self.direction}_{self.animation_frame}"
        )
        try:
            self.sprite = self.texture_manager.get_sprite(sprite_name)
        except KeyError:
            logger.error(f"Sprite '{sprite_name}' not found for player tank.")

    @property
    def is_frozen(self) -> bool:
        """Whether the player is currently frozen (friendly fire)."""
        return self._freeze_timer > 0

    def freeze(self, duration: float) -> None:
        """Freeze the player for the given duration (friendly fire effect)."""
        self._freeze_timer = duration

    def update(self, dt: float) -> None:
        """Update timers including freeze countdown."""
        super().update(dt)
        if self._freeze_timer > 0:
            self._freeze_timer = max(0.0, self._freeze_timer - dt)

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
        if self.is_frozen:
            return
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

    def shoot(self):
        """Shoot a bullet. Returns None if frozen."""
        if self.is_frozen:
            return None
        return super().shoot()

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
            self.direction = Direction.UP
            self._set_star_level(0)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the player tank with shield overlay when invincible."""
        if self.is_invincible:
            if self.sprite:
                surface.blit(self.sprite, self.rect)
            interval = self.shield_flicker_interval
            frame_idx = int(self.invincibility_timer % (interval * 2) >= interval)
            surface.blit(self._shield_frames[frame_idx], self.rect)
        else:
            super().draw(surface)
