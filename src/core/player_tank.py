from loguru import logger
from .tank import Tank
from src.managers.texture_manager import TextureManager
from src.utils.constants import Direction


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
        grid_x = round(x / tile_size) * tile_size
        grid_y = round(y / tile_size) * tile_size
        logger.debug(f"Creating PlayerTank at initial grid ({grid_x}, {grid_y})")
        super().__init__(
            grid_x,
            grid_y,
            texture_manager,
            tile_size,
            None,
            health=1,
            lives=3,
            map_width_px=map_width_px,
            map_height_px=map_height_px,
        )
        self.owner_type = "player"
        self.initial_position = (grid_x, grid_y)
        self.invincibility_duration = 3.0
        self._update_sprite()

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

    def update(self, dt: float) -> None:
        """
        Update the tank's state.

        Args:
            dt: Time elapsed since last update in seconds
        """
        super().update(dt)

    def respawn(self) -> None:
        """Respawn the tank at its initial position."""
        if self.lives > 0:
            logger.info(
                f"Player respawning at {self.initial_position}. "
                f"Lives: {self.lives}"
            )
            self.x, self.y = self.initial_position
            self.target_position = self.initial_position
            self.is_invincible = True
            self.invincibility_timer = 0
            self.blink_timer = 0
            self.direction = Direction.UP
            self._update_sprite()
