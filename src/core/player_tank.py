import pygame
from loguru import logger
from .tank import Tank
from src.managers.input_handler import InputHandler
from typing import Optional


class PlayerTank(Tank):
    """Player-controlled tank entity."""

    def __init__(
        self,
        x: int,
        y: int,
        tile_size: int,
        sprite: Optional[pygame.Surface] = None,
    ) -> None:
        """
        Initialize the player tank.

        Args:
            x: Initial x position
            y: Initial y position
            tile_size: Size of a tile in pixels
            sprite: Optional sprite surface
        """
        # Ensure x and y are aligned to the grid
        grid_x = round(x / tile_size) * tile_size
        grid_y = round(y / tile_size) * tile_size
        logger.debug(f"Creating PlayerTank at initial grid ({grid_x}, {grid_y})")
        # Initialize with grid-aligned position
        super().__init__(
            grid_x, grid_y, tile_size, sprite, health=1, lives=3
        )  # Player starts with 3 lives
        self.owner_type = "player"
        self.input_handler = InputHandler()
        self.initial_position = (grid_x, grid_y)
        self.invincibility_duration = 3.0  # 3 seconds invincibility after respawn
        self.color = (0, 255, 0)  # Green color for player tank

    def handle_event(self, event: pygame.event.Event) -> None:
        """
        Handle a pygame event.

        Args:
            event: The pygame event to handle
        """
        if not self.is_invincible:  # Only handle input if not invincible
            self.input_handler.handle_event(event)

            # Handle shooting
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                logger.debug("Player attempting to shoot.")
                self.shoot()
        else:
            logger.trace("Player input ignored (invincible).")

    def update(self, dt: float) -> None:
        """
        Update the tank's position based on input and check for collisions.

        Args:
            dt: Time elapsed since last update in seconds
        """
        # Update base tank state
        super().update(dt)

        if self.is_invincible:
            return  # Don't move or shoot while invincible

        # Get movement direction from input
        dx, dy = self.input_handler.get_movement_direction()

        # Update direction based on movement
        if dx != 0 or dy != 0:
            if dx > 0:
                self.direction = "right"
            elif dx < 0:
                self.direction = "left"
            elif dy > 0:
                self.direction = "down"
            elif dy < 0:
                self.direction = "up"

            # Attempt to move
            self._move(dx, dy)

    def respawn(self) -> None:
        """Respawn the tank at its initial position."""
        if self.lives > 0:
            logger.info(
                f"Player respawning at {self.initial_position}. Lives: {self.lives}"
            )
            self.x, self.y = self.initial_position
            self.target_position = self.initial_position
            self.is_invincible = True
            self.invincibility_timer = 0
            self.blink_timer = 0
            self.direction = "up"  # Reset direction
            self.move_timer = 0

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
            else:
                # Draw a simple green tank if no sprite is provided
                pygame.draw.rect(surface, self.color, self.rect)

        if self.bullet is not None and self.bullet.active:
            self.bullet.draw(surface)
