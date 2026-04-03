from loguru import logger
from .tank import Tank
from src.managers.texture_manager import TextureManager
from src.utils.constants import Direction, OwnerType


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
        self.invincibility_duration = 3.0
        self._update_sprite()

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
            self.activate_invincibility(3.0)
            self.direction = Direction.UP
            self._update_sprite()
